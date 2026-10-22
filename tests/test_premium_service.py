"""Premium service tests — single-writer, cadence, watcher, Play kill-switch."""

import asyncio
import time

import pytest

from core.state import state
from services.premium_service import (
    PremiumService,
    page_has_ads,
    premium_unlocked_message,
)
from tests.conftest import FakePage, FakeStorage


@pytest.fixture(autouse=True)
def _reset_premium_state():
    state.is_premium = False
    yield
    state.is_premium = False


def _premium(monkeypatch=None, **kw):
    page = FakePage()
    storage = FakeStorage()
    svc = PremiumService(page=page, storage=storage, **kw)
    return svc, page, storage


def test_single_writer_recompute():
    svc, _, _ = _premium()
    assert state.is_premium is False
    svc.license._unlocked = True
    svc._recompute_premium()
    assert state.is_premium is True
    svc.license._unlocked = False
    svc._recompute_premium()
    assert state.is_premium is False


def test_listener_fan_out():
    svc, _, _ = _premium()
    seen = []
    svc.add_listener(lambda: seen.append(state.is_premium))
    svc.license._unlocked = True
    svc._recompute_premium()
    assert seen == [True]
    svc.remove_listener(seen.append if False else list(seen) and (lambda: None) or seen.append)
    # Removing a non-member is a no-op (no ValueError).
    svc.remove_listener(lambda: None)


def test_play_channel_inert(monkeypatch):
    import services.premium_service as mod

    monkeypatch.setattr(mod, "CHANNEL", "play")
    svc, _, _ = _premium()
    assert svc.available is False


def test_direct_channel_available(monkeypatch):
    import services.premium_service as mod

    monkeypatch.setattr(mod, "CHANNEL", "direct")
    svc, _, _ = _premium()
    assert svc.available is True


@pytest.mark.asyncio
async def test_load_local_offline_verdict(monkeypatch):
    # Force the backend to kiri (constructor reads the channel marker).
    svc, _, _ = _premium()
    svc.backend = "kiri"
    monkeypatch.setattr(svc.license, "apply_cached_token", lambda: _deny(svc))
    await svc.load_local()
    assert state.is_premium is False


async def _deny(svc):
    svc._unlocked = False
    svc.claims = None


@pytest.mark.asyncio
async def test_reconcile_without_recovery_id_recomputes():
    # No recovery ID means nothing to verify against: reconcile mirrors
    # the license service verdict (False) — KTV parity.
    svc, _, _ = _premium()
    svc.backend = "kiri"
    svc.license._unlocked = False
    state.is_premium = True
    await svc.reconcile()
    assert state.is_premium is False


@pytest.mark.asyncio
async def test_grant_premium_benefits_tops_up_once():
    from core.constants import PREMIUM_DAILY_CREDITS
    from services.credit_service import CreditService
    from tests.conftest import FakeStorage as FS

    storage = FS({"akili_credits": "40"})
    credits = CreditService(storage=storage)
    state.is_premium = True  # before init so the reset uses the premium cap
    await credits.initialize()
    state.credit_service = credits
    # Reset topped up to the premium cap already; spend down to test the grant.
    await credits.charge(460)
    assert state.credits_remaining == PREMIUM_DAILY_CREDITS - 460

    svc, _, _ = _premium()
    assert await svc._grant_premium_benefits(first_time=True) is True
    assert state.credits_remaining == PREMIUM_DAILY_CREDITS

    # Second call: already at cap, no-op but still True (idempotent top-up).
    assert await svc._grant_premium_benefits(first_time=True) is True
    assert state.credits_remaining == PREMIUM_DAILY_CREDITS

    state.credit_service = None


@pytest.mark.asyncio
async def test_grant_requires_first_time_and_premium():
    svc, _, _ = _premium()
    state.is_premium = False
    assert await svc._grant_premium_benefits(first_time=True) is False
    state.is_premium = True
    assert await svc._grant_premium_benefits(first_time=False) is False


@pytest.mark.asyncio
async def test_checkout_watch_unlocks_on_restore(monkeypatch):
    svc, _, _ = _premium()
    svc.backend = "kiri"

    async def _restore(recovery_id):
        from services.kiri_license import LicenseStatus

        svc.license._unlocked = True
        return LicenseStatus(status="active", product="monthly", recovery_id=recovery_id)

    monkeypatch.setattr(svc.license, "restore", _restore)
    monkeypatch.setattr("services.premium_service.CHECKOUT_WATCH_INTERVAL", 0.01)
    granted = []

    async def _grant(*, first_time):
        granted.append(first_time)
        state.is_premium = True
        return True

    monkeypatch.setattr(svc, "_grant_premium_benefits", _grant)
    svc.start_checkout_watch("R1")
    for _ in range(200):
        await asyncio.sleep(0.01)
        if granted:
            break
    assert granted == [True]
    svc.stop_checkout_watch()


@pytest.mark.asyncio
async def test_reconcile_if_due_debounce(monkeypatch):
    svc, _, _ = _premium()
    svc.backend = "kiri"
    calls = []

    async def _reconcile():
        calls.append(1)

    monkeypatch.setattr(svc, "reconcile", _reconcile)
    svc._last_reconcile_at = time.monotonic()  # just reconciled
    await svc.reconcile_if_due()
    assert calls == []
    svc._last_reconcile_at = 0.0  # long ago
    await svc.reconcile_if_due()
    assert calls == [1]


def test_page_has_ads_mobile_only():
    page = FakePage()
    page.web = False

    class _Platform:
        def is_mobile(self):
            return True

    page.platform = _Platform()
    assert page_has_ads(page) is True

    class _Desktop:
        def is_mobile(self):
            return False

    page.platform = _Desktop()
    assert page_has_ads(page) is False


def test_premium_unlocked_message_honest():
    page = FakePage()
    page.web = False

    class _Mobile:
        def is_mobile(self):
            return True

    class _Desktop:
        def is_mobile(self):
            return False

    page.platform = _Mobile()
    assert "Ads off" in premium_unlocked_message(page)
    page.platform = _Desktop()
    assert "Ads off" not in premium_unlocked_message(page)
