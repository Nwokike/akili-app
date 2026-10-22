"""Ad service — UMP-gated banner + interstitial lifecycle.

Ported from Sherlock's ad_service.py (the house standard).

InterstitialAd and ConsentManager are ft.Service: Flet runs
unregister_services() after every event, so both are kept alive via
page.services.append. Every entry is gated on mobile + consent +
non-premium.
"""

from __future__ import annotations

import contextlib
import logging

import flet as ft

from core.constants import AD_BANNER_UNIT_ID, AD_INTERSTITIAL_UNIT_ID

logger = logging.getLogger(__name__)

USE_TEST_IDS = False

_BANNER_TEST_ID = "ca-app-pub-3940256099942544/9214589741"
_INTERSTITIAL_TEST_ID = "ca-app-pub-3940256099942544/1033173712"

try:
    import flet_ads as _ads

    _HAS_ADS = True
except ImportError:
    _ads = None  # type: ignore[assignment]
    _HAS_ADS = False


class AdService:
    """Owns consent, banner construction, and the interstitial preload chain."""

    def __init__(self, page: ft.Page):
        self.page = page
        self._can_request_ads = True
        self._consent_manager = None
        self._interstitial = None
        self._shown_interstitial = None

    # ── Platform / gating ─────────────────────────────────────────────

    def _is_mobile(self) -> bool:
        try:
            return self.page.platform.is_mobile()
        except Exception:
            return False

    def _gated(self) -> bool:
        """True when ads may be requested at all."""
        from core.state import state

        if not _HAS_ADS:
            return False
        if state.is_premium:
            return False
        if not self._is_mobile():
            return False
        return self._can_request_ads

    # ── Consent ───────────────────────────────────────────────────────

    async def gather_consent(self) -> None:
        """UMP flow. Failure defaults to allow (open unless denied)."""
        if not _HAS_ADS:
            self._can_request_ads = False
            return
        if not self._is_mobile():
            self._can_request_ads = True
            return
        try:
            manager = _ads.ConsentManager()
            self._consent_manager = manager
            self.page.services.append(manager)
            await manager.request_consent_info_update()
            await manager.load_and_show_consent_form_if_required()
            self._can_request_ads = await manager.can_request_ads()
        except Exception as exc:
            logger.warning("consent flow failed, allowing ads: %s", exc)
            self._can_request_ads = True

    async def show_privacy_options(self) -> str:
        """Open the UMP privacy form. Returns an honest outcome string."""
        if self._consent_manager is None:
            return "no_manager"
        try:
            from flet_ads import PrivacyOptionsRequirementStatus

            status = await self._consent_manager.get_privacy_options_requirement_status()
            if status != PrivacyOptionsRequirementStatus.REQUIRED:
                return "not_required"
            await self._consent_manager.show_privacy_options_form()
            return "form_shown"
        except Exception as exc:
            logger.warning("privacy options failed: %s", exc)
            return f"error:{exc}"

    # ── Banner ─────────────────────────────���──────────────────────────

    def banner_unit_id(self) -> str:
        return _BANNER_TEST_ID if USE_TEST_IDS else AD_BANNER_UNIT_ID

    def interstitial_unit_id(self) -> str:
        return _INTERSTITIAL_TEST_ID if USE_TEST_IDS else AD_INTERSTITIAL_UNIT_ID

    def build_banner(self):
        """A 320×50 banner, or None when gated."""
        if not self._gated():
            return None
        try:
            return _ads.BannerAd(
                unit_id=self.banner_unit_id(),
                width=320,
                height=50,
                on_load=lambda e: None,
                on_error=lambda e: logger.debug("banner error: %s", e.data),
            )
        except Exception as exc:
            logger.warning("banner build failed: %s", exc)
            return None

    # ── Interstitial ──────────────────────────────────────────────────

    async def preload_interstitial(self) -> None:
        """Mount the next interstitial ahead of time."""
        if not self._gated():
            return
        try:
            ad = _ads.InterstitialAd(
                unit_id=self.interstitial_unit_id(),
                on_load=lambda e: logger.debug("interstitial ready"),
                on_error=lambda e: logger.debug("interstitial error: %s", e.data),
                on_close=lambda e: self._handle_close(),
            )
            self._interstitial = ad
            self.page.services.append(ad)
        except Exception as exc:
            logger.warning("interstitial preload failed: %s", exc)

    def _handle_close(self) -> None:
        self._shown_interstitial = None
        self._interstitial = None
        with contextlib.suppress(Exception):
            self.page.run_task(self.preload_interstitial)

    async def show_interstitial(self) -> bool:
        """Show the preloaded ad, or a fresh self-loading one. Never blocks UX."""
        if not self._gated():
            return False
        ad = self._interstitial
        self._interstitial = None
        if ad is not None:
            try:
                self._shown_interstitial = ad
                await ad.show()
                return True
            except Exception as exc:
                logger.debug("interstitial show failed: %s", exc)
                self._shown_interstitial = None
        # Fallback: fresh instance that shows itself on load.
        try:
            fresh = _ads.InterstitialAd(
                unit_id=self.interstitial_unit_id(),
                on_load=lambda e: self.page.run_task(fresh.show),
                on_close=lambda e: self._handle_close(),
            )
            self.page.services.append(fresh)
            return True
        except Exception as exc:
            logger.warning("interstitial fallback failed: %s", exc)
            return False

    def close(self) -> None:
        """Release ad services from the page."""
        for item in (self._consent_manager, self._interstitial, self._shown_interstitial):
            if item is None:
                continue
            with contextlib.suppress(ValueError):
                self.page.services.remove(item)
        self._consent_manager = None
        self._interstitial = None
        self._shown_interstitial = None
