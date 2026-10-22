"""Premium orchestrator — Kiri License entitlement + credit grant.

Ported from KTV Player's premium_service.py (cadences, watcher, listener
fan-out, channel kill-switch) + DDGS's premium credit grant (top up to
the premium cap once on transition).

Single writer rule: `_recompute_premium()` is the ONLY place
`state.is_premium` is written. The license service reports its verdict
via on_change; this service mirrors it into the app-wide flag.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from collections.abc import Callable

from core.channel import CHANNEL
from core.constants import PREMIUM_DAILY_CREDITS
from core.state import state
from services.kiri_license import KiriLicenseService, LicenseUnavailable

logger = logging.getLogger(__name__)

CHECKOUT_WATCH_INTERVAL = 5.0
CHECKOUT_WATCH_TIMEOUT = 15 * 60.0
RECONCILE_INTERVAL = 60 * 60.0
RESUME_DEBOUNCE = 60.0


class PremiumService:
    """Owns the premium lifecycle: verify, reconcile, checkout, restore."""

    def __init__(self, page=None, storage=None):
        self.page = page
        self.storage = storage
        # asyncio holds only weak refs to tasks; keep strong refs so the
        # watcher and reconcile loop can't be collected mid-flight.
        self._checkout_watch_task: asyncio.Task | None = None
        self._reconcile_task: asyncio.Task | None = None
        self._last_reconcile_at = time.monotonic() - RESUME_DEBOUNCE
        self._listeners: list[Callable[[], None]] = []
        self.license = KiriLicenseService(storage=storage, on_change=self._recompute_premium)
        self.backend: str = "none"  # "kiri" | "none"
        if CHANNEL == "play":
            logger.info("Play channel build — premium disabled, free tier with ads")
            return
        self.backend = "kiri"

    # ── Listeners ───────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self.backend == "kiri"

    def _premium_disabled(self) -> bool:
        return CHANNEL == "play"

    def add_listener(self, callback: Callable[[], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        with __import__("contextlib").suppress(ValueError):
            self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                logger.debug("Premium listener failed", exc_info=True)

    def _recompute_premium(self) -> None:
        unlocked = self.license.unlocked
        if state.is_premium != unlocked:
            logger.info("Premium state -> %s (kiri)", unlocked)
        state.is_premium = unlocked
        self._notify_listeners()

    # ── Boot / reconcile ────────────────────────────────────────────────

    async def load_local(self) -> None:
        """Offline verdict before the first frame (cached token verify)."""
        if self._premium_disabled():
            state.is_premium = False
            return
        try:
            await self.license.apply_cached_token()
        except Exception:
            logger.warning("Could not verify the cached license", exc_info=True)
        self._recompute_premium()

    async def reconcile(self) -> None:
        """Authoritative refresh via token-ISSUING restore (not /status).

        /status never re-issues the signed token, so after a renewal the
        cached token's exp would lapse while the server still said active.
        """
        if self._premium_disabled():
            return
        self._last_reconcile_at = time.monotonic()
        recovery_id = await self.license.recovery_id()
        if not recovery_id:
            self._recompute_premium()
            return
        try:
            await self.license.restore(recovery_id)
        except LicenseUnavailable as ex:
            logger.info("Kiri license refresh: %s", ex)
        finally:
            self._recompute_premium()

    async def reconcile_if_due(self) -> None:
        """Debounced reconcile for lifecycle resume bursts."""
        if self._premium_disabled():
            return
        if time.monotonic() - self._last_reconcile_at < RESUME_DEBOUNCE:
            return
        await self.reconcile()

    def start_reconcile_loop(self) -> None:
        if self._premium_disabled():
            return
        self.stop_reconcile_loop()
        try:
            loop = asyncio.get_running_loop()
            self._reconcile_task = loop.create_task(self._reconcile_loop())
        except RuntimeError:
            pass

    def stop_reconcile_loop(self) -> None:
        task, self._reconcile_task = self._reconcile_task, None
        if task is not None and not task.done():
            task.cancel()

    async def _reconcile_loop(self) -> None:
        while True:
            await asyncio.sleep(RECONCILE_INTERVAL)
            try:
                await self.reconcile_if_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("reconcile loop tick failed", exc_info=True)

    # ── Checkout watcher ────────────────────────────────────────────────

    def start_checkout_watch(self, recovery_id: str) -> None:
        """Poll restore() until the payment lands. Lives on the service so
        navigation cannot orphan it."""
        if self._premium_disabled() or not recovery_id:
            return
        self.stop_checkout_watch()
        try:
            loop = asyncio.get_running_loop()
            self._checkout_watch_task = loop.create_task(self._checkout_watch_loop(recovery_id))
        except RuntimeError:
            pass

    def stop_checkout_watch(self) -> None:
        task, self._checkout_watch_task = self._checkout_watch_task, None
        if task is not None and not task.done():
            task.cancel()

    async def _checkout_watch_loop(self, recovery_id: str) -> None:
        deadline = time.monotonic() + CHECKOUT_WATCH_TIMEOUT
        failures = 0
        while time.monotonic() < deadline:
            # One sleep per iteration: base interval + proportional jitter
            # + backoff after consecutive transient failures. (A second
            # sleep inside the failure branch once blew past the deadline
            # and starved the remaining window.)
            backoff = min(30.0, CHECKOUT_WATCH_INTERVAL * failures)
            await asyncio.sleep(CHECKOUT_WATCH_INTERVAL + random.uniform(0, CHECKOUT_WATCH_INTERVAL) + backoff)
            try:
                status = await self.license.restore(recovery_id)
                failures = 0
            except LicenseUnavailable as ex:
                from services.kiri_license import WATCHER_ABORT_CODES

                if ex.is_refusal and ex.status_code in WATCHER_ABORT_CODES:
                    # Hard refusal (payment invalid / app not entitled):
                    # the license will never turn active — stop polling now
                    # instead of burning the budget for the full window.
                    # 404 is NOT abortive: right after payment the license
                    # may not exist yet (webhook lag) — keep waiting.
                    logger.info("Checkout watcher aborted: %s", ex)
                    return
                failures += 1
                logger.info("Checkout watcher waiting: %s", ex)
                continue
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                failures += 1
                logger.info("Checkout watcher waiting: %s", ex)
                continue
            # Guard on the VERIFIED token, not just the status text, so a
            # signing misconfiguration can never toast a lie.
            if status.status in ("active", "grace") and self.license.unlocked:
                with contextlib.suppress(Exception):
                    await self._grant_premium_benefits(first_time=True)
                try:
                    from core.notify import show_snack
                    from core.theme import AppColors

                    show_snack(self.page, premium_unlocked_message(self.page), AppColors.SUCCESS)
                except Exception:
                    pass
                return
        logger.info("Checkout watcher timed out — Restore purchases remains available")

    # ── Thin Kiri surface ───────────────────────────────────────────────

    async def kiri_catalog(self, force: bool = False):
        if self._premium_disabled():
            return []
        try:
            return await self.license.fetch_catalog(force=force)
        except LicenseUnavailable as ex:
            logger.info("License catalog unavailable: %s", ex)
            return []

    async def kiri_checkout(self, product_id: str, email: str):
        checkout = await self.license.checkout(product_id, email)
        self.start_checkout_watch(checkout.recovery_id)
        return checkout

    async def kiri_restore(self, recovery_id: str):
        status = await self.license.restore(recovery_id)
        self._recompute_premium()
        return status

    async def _grant_premium_benefits(self, *, first_time: bool) -> bool:
        """Top up to the premium credit cap once on transition into Premium.

        `first_time` is supplied by the caller on purpose: reading
        `state.is_premium` here cannot work because every call site flips
        the flag before calling.
        """
        if not first_time or not state.is_premium:
            return False
        credits = getattr(state, "credit_service", None)
        if credits is not None and state.credits_remaining < PREMIUM_DAILY_CREDITS:
            await credits.add_credits(PREMIUM_DAILY_CREDITS - state.credits_remaining)
        return True

    def shutdown(self) -> None:
        self.stop_checkout_watch()
        self.stop_reconcile_loop()


def premium_unlocked_message(page=None) -> str:
    """Honest unlock toast — 'ads off' only where ads exist."""
    try:
        mobile = page is not None and not page.web and page.platform.is_mobile()
    except Exception:
        mobile = False
    if mobile:
        return "Premium unlocked. Ads off, 500 credits a day."
    return "Premium unlocked. 500 credits a day."


def page_has_ads(page=None) -> bool:
    """Whether ads can run here (mobile only). Never claim 'no ads' on desktop."""
    try:
        return page is not None and not page.web and page.platform.is_mobile()
    except Exception:
        return True
