"""Local credit economy — flat per-step, reserve/commit/rollback.

Ported from DDGS credit_service.py (the house standard).

100 free AI credits daily (500 when premium), UTC date-change reset back
to the cap (no rollover, by design). Transaction-keyed reservations
prevent overlapping commit/rollback corruption; auto-rollback after
ROLLBACK_SECONDS (240s) for orphans.

Only AI entry points spend: browsing, quizzes and mock exams never call
this service, which is how "practice stays free" is enforced.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from datetime import UTC, datetime

from core.constants import (
    DAILY_FREE_CREDITS,
    PREMIUM_DAILY_CREDITS,
    STORAGE_CREDITS,
    STORAGE_LAST_RESET,
)

logger = logging.getLogger(__name__)

# How long an UNSETTLED, INACTIVE hold is trusted before the service gives
# the credits back on its own. Deferred while the owning turn is active.
ROLLBACK_SECONDS = 240.0
ROLLBACK_MAX_DEFERRALS = 3


class CreditService:
    """Manages the local credit economy over the app's StorageService."""

    def __init__(self, storage=None):
        self._storage = storage
        self._reservations: dict[str, int] = {}
        self._active: set[str] = set()
        self._rollback_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._reset_day: str = ""

    async def initialize(self) -> int:
        """Load credits from storage, reset if new day. Returns current balance."""
        await self._check_daily_reset()
        return await self._get_credits()

    async def reserve(self, amount: int) -> str | None:
        """Optimistically reserve credits. Returns tx id, or None if insufficient."""
        tx_id = str(uuid.uuid4())
        async with self._lock:
            current = await self._get_credits()
            total_reserved = sum(self._reservations.values())
            if current - total_reserved < amount:
                return None
            self._reservations[tx_id] = amount
            self._active.add(tx_id)
        self._arm_rollback(tx_id, amount)
        return tx_id

    async def reserve_more(self, tx_id: str, extra: int) -> bool:
        """Grow an existing hold. False means the balance dipped — soft
        metering: the caller keeps going (never breaks work)."""
        async with self._lock:
            if tx_id not in self._reservations:
                return False
            total_reserved = sum(self._reservations.values())
            if await self._get_credits() - total_reserved < extra:
                return False
            self._reservations[tx_id] += extra
            held = self._reservations[tx_id]
        self._arm_rollback(tx_id, held)
        return True

    def _arm_rollback(self, tx_id: str, amount: int) -> None:
        task = self._rollback_tasks.pop(tx_id, None)
        if task:
            task.cancel()
        born = time.monotonic()

        async def _auto_rollback():
            while True:
                await asyncio.sleep(ROLLBACK_SECONDS)
                async with self._lock:
                    if tx_id not in self._reservations:
                        return
                    deferments = int((time.monotonic() - born) // ROLLBACK_SECONDS)
                    if tx_id in self._active and deferments < ROLLBACK_MAX_DEFERRALS:
                        continue
                    del self._reservations[tx_id]
                    self._active.discard(tx_id)
                    self._rollback_tasks.pop(tx_id, None)
                    logger.warning("Auto-rolled back %d credits (tx: %s)", amount, tx_id)
                    return

        # No running loop (unit tests) is fine — settlement handles it.
        with contextlib.suppress(RuntimeError):
            self._rollback_tasks[tx_id] = asyncio.create_task(_auto_rollback())

    async def commit_amount(self, tx_id: str, amount: int | None = None) -> int:
        """Settle a hold. Idempotent; overdraft clamps at zero."""
        from core.state import state

        task = self._rollback_tasks.pop(tx_id, None)
        if task:
            task.cancel()
        async with self._lock:
            self._active.discard(tx_id)
            if tx_id not in self._reservations:
                logger.info("settlement for %s already applied", tx_id)
                return await self._get_credits()
            held = self._reservations.pop(tx_id, 0)
            if amount is None:
                amount = held
            if amount <= 0:
                return await self._get_credits()
            current = await self._get_credits()
            new_balance = max(0, current - amount)
            await self._storage.set(STORAGE_CREDITS, str(new_balance))
            state.credits_remaining = new_balance
        logger.info("Settled %d credits (held %d, tx: %s). Remaining: %d", amount, held, tx_id, new_balance)
        return new_balance

    async def commit(self, tx_id: str) -> int:
        """Finalize a reservation — deduct the full held amount."""
        return await self.commit_amount(tx_id)

    async def charge(self, amount: int) -> int:
        """Direct debit with no hold; overdraft clamps at zero."""
        from core.state import state

        async with self._lock:
            current = await self._get_credits()
            new_balance = max(0, current - amount)
            await self._storage.set(STORAGE_CREDITS, str(new_balance))
            state.credits_remaining = new_balance
        logger.info("Charged %d credits. Remaining: %d", amount, new_balance)
        return new_balance

    async def rollback(self, tx_id: str) -> None:
        """Release a reservation without deducting credits."""
        task = self._rollback_tasks.pop(tx_id, None)
        if task:
            task.cancel()
        async with self._lock:
            self._reservations.pop(tx_id, None)
            self._active.discard(tx_id)

    async def spend(self, amount: int) -> tuple[bool, int]:
        """Deduct credits directly (no reservation). Returns (success, remaining)."""
        from core.state import state

        async with self._lock:
            current = await self._get_credits()
            total_reserved = sum(self._reservations.values())
            if current - total_reserved < amount:
                return False, current
            new_balance = current - amount
            await self._storage.set(STORAGE_CREDITS, str(new_balance))
            state.credits_remaining = new_balance
        logger.info("Spent %d credits. Remaining: %d", amount, new_balance)
        return True, new_balance

    async def add_credits(self, amount: int) -> int:
        """Add credits (ad rewards, premium grant). Returns the new balance."""
        from core.state import state

        async with self._lock:
            current = await self._get_credits()
            new_balance = current + amount
            await self._storage.set(STORAGE_CREDITS, str(new_balance))
            state.credits_remaining = new_balance
        logger.info("Added %d credits. New balance: %d", amount, new_balance)
        return new_balance

    async def get_balance(self) -> int:
        await self._check_daily_reset()
        return await self._get_credits()

    async def check_balance(self, amount: int) -> tuple[bool, int]:
        balance = await self._get_credits()
        return balance >= amount, balance

    async def get_daily_cap(self) -> int:
        """Premium users refill to the premium cap."""
        from core.state import state

        if getattr(state, "is_premium", False):
            return PREMIUM_DAILY_CREDITS
        return DAILY_FREE_CREDITS

    async def _check_daily_reset(self) -> None:
        """UTC date change resets the balance to the daily cap."""
        from core.state import state

        today = datetime.now(tz=UTC).date().isoformat()
        if self._reset_day == today:
            return
        last_reset = await self._storage.get(STORAGE_LAST_RESET)
        if last_reset == today:
            self._reset_day = today
            return
        async with self._lock:
            if self._reset_day == today:
                return
            daily_cap = await self.get_daily_cap()
            new_balance = daily_cap  # flat reset: no rollover
            await self._storage.set(STORAGE_CREDITS, str(new_balance))
            await self._storage.set(STORAGE_LAST_RESET, today)
            state.credits_remaining = new_balance
            self._reset_day = today
            # Deliberately NOT clearing self._reservations: a turn in flight
            # at midnight holds a reservation it is about to settle.
        logger.info("Daily credit reset: balance topped up at %d.", new_balance)

    async def _get_credits(self) -> int:
        val = await self._storage.get(STORAGE_CREDITS)
        try:
            return int(val) if val else DAILY_FREE_CREDITS
        except (TypeError, ValueError):
            return DAILY_FREE_CREDITS


def init_credit_service(storage) -> CreditService:
    """Create the credit service (called once by AppController)."""
    return CreditService(storage=storage)
