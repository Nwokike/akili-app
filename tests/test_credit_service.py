"""Credit service tests — the DDGS invariants that matter."""

import asyncio
from datetime import UTC, datetime

import pytest

from core.constants import (
    DAILY_FREE_CREDITS,
    PREMIUM_DAILY_CREDITS,
    STORAGE_CREDITS,
    STORAGE_LAST_RESET,
)
from services.credit_service import CreditService
from tests.conftest import FakeStorage

TODAY = datetime.now(tz=UTC).date().isoformat()


def _storage_with(balance: int) -> FakeStorage:
    """A store whose daily reset already ran today (so balance is preserved)."""
    return FakeStorage({STORAGE_CREDITS: str(balance), STORAGE_LAST_RESET: TODAY})


def _svc(storage=None):
    return CreditService(storage=storage or FakeStorage())


@pytest.mark.asyncio
async def test_initialize_reads_balance():
    svc = _svc(_storage_with(42))
    assert await svc.initialize() == 42


@pytest.mark.asyncio
async def test_initialize_defaults_to_cap():
    svc = _svc()
    assert await svc.initialize() == DAILY_FREE_CREDITS


@pytest.mark.asyncio
async def test_reserve_and_commit():
    svc = _svc(_storage_with(10))
    await svc.initialize()
    tx = await svc.reserve(3)
    assert tx is not None
    assert await svc.commit_amount(tx, 3) == 7


@pytest.mark.asyncio
async def test_reserve_fails_when_insufficient():
    svc = _svc(_storage_with(1))
    await svc.initialize()
    assert await svc.reserve(5) is None


@pytest.mark.asyncio
async def test_concurrent_reserves_cannot_oversell():
    svc = _svc(_storage_with(10))
    await svc.initialize()
    results = await asyncio.gather(*(svc.reserve(4) for _ in range(5)))
    granted = [r for r in results if r is not None]
    # 10 credits / 4 each => at most 2 grants (8 held), the rest refuse.
    assert len(granted) == 2


@pytest.mark.asyncio
async def test_settlement_is_idempotent():
    svc = _svc(_storage_with(10))
    await svc.initialize()
    tx = await svc.reserve(3)
    first = await svc.commit_amount(tx, 3)
    second = await svc.commit_amount(tx, 3)
    assert first == 7
    assert second == 7  # no double charge


@pytest.mark.asyncio
async def test_rollback_releases_without_charge():
    svc = _svc(_storage_with(10))
    await svc.initialize()
    tx = await svc.reserve(4)
    await svc.rollback(tx)
    assert await svc.get_balance() == 10


@pytest.mark.asyncio
async def test_overdraft_clamps_at_zero():
    svc = _svc(_storage_with(2))
    await svc.initialize()
    assert await svc.charge(5) == 0


@pytest.mark.asyncio
async def test_add_credits():
    svc = _svc(_storage_with(10))
    await svc.initialize()
    assert await svc.add_credits(5) == 15


@pytest.mark.asyncio
async def test_daily_cap_premium(monkeypatch):
    from core.state import state

    svc = _svc()
    monkeypatch.setattr(state, "is_premium", True)
    assert await svc.get_daily_cap() == PREMIUM_DAILY_CREDITS
    monkeypatch.setattr(state, "is_premium", False)
    assert await svc.get_daily_cap() == DAILY_FREE_CREDITS


@pytest.mark.asyncio
async def test_daily_reset_on_new_day():
    storage = FakeStorage({STORAGE_CREDITS: "5", STORAGE_LAST_RESET: "2020-01-01"})
    svc = _svc(storage)
    balance = await svc.initialize()
    assert balance == DAILY_FREE_CREDITS  # reset to cap
