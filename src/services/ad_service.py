import asyncio
import logging

import flet as ft

logger = logging.getLogger(__name__)


try:
    import flet_ads as fta

    HAS_ADS = True
except ImportError:
    HAS_ADS = False


class AdService:
    BANNER_ID = "ca-app-pub-5679949845754640/1712130979"
    INTERSTITIAL_ID = "ca-app-pub-5679949845754640/5238266847"

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial = None
        self._on_interstitial_close = None

    def _is_mobile(self) -> bool:
        if self.page.web:
            return False
        if not HAS_ADS:
            return False
        try:
            return self.page.platform.is_mobile()
        except Exception:
            return False

    def _get_mock_ad_control(self, height: int = 50) -> ft.Control:
        from core.theme import AppColors

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=AppColors.PRIMARY, size=18),
                    ft.Text("Learn Smart with Akili Premium", size=13, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            height=height,
            alignment=ft.Alignment.CENTER,
        )

    def _create_ad_container(self, ad_control: ft.Control, width: int = None) -> ft.Control:
        from core.theme import AppStyles

        inner_content = ft.Column(
            [
                ft.Text(
                    "SPONSORED",
                    size=9,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    style=ft.TextStyle(letter_spacing=1.5),
                ),
                ad_control,
                ft.Text(
                    "Ads support the developer and keep the app free",
                    size=9,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            tight=True,
        )

        return ft.Container(
            content=inner_content,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            border_radius=AppStyles.RADIUS,
            padding=ft.Padding(16, 12, 16, 12),
            alignment=ft.Alignment.CENTER,
            margin=ft.Margin(12, 8, 12, 8),
            width=width,
        )

    def get_banner_ad(self, width: int = None, height: int = 50) -> ft.Control:
        if self._is_mobile():
            try:
                ad = fta.BannerAd(
                    unit_id=self.BANNER_ID,
                    width=320 if width is None else width,
                    height=height,
                    on_error=lambda e: None,
                )
                return self._create_ad_container(ad, width=width)
            except Exception:
                pass

        if self.page.web:
            from core.theme import AppColors, AppStyles

            def on_hover(e):
                e.control.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE) if e.data == "true" else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)
                e.control.update()

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.ANDROID_ROUNDED, color=AppColors.PRIMARY, size=20),
                        ft.Text(
                            "Akili Web Preview — Click to get the Android App",
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.ON_SURFACE,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                height=height,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                border_radius=AppStyles.RADIUS,
                padding=ft.Padding(12, 4, 12, 4),
                alignment=ft.Alignment.CENTER,
                margin=ft.Margin(12, 8, 12, 8),
                width=width,
                on_hover=on_hover,
                on_click=lambda e: self.page.launch_url("https://github.com/Nwokike/akili-app/releases/latest/download/akili-arm64-v8a.apk")
            )

        mock_ad = self._get_mock_ad_control(height=height)
        return self._create_ad_container(mock_ad, width=width)

    def get_anchor_banner(self) -> ft.Control:
        if self._is_mobile():
            try:
                ad = fta.BannerAd(
                    unit_id=self.BANNER_ID,
                    width=320,
                    height=50,
                    on_error=lambda e: None,
                )
                return ft.Container(
                    content=ad,
                    width=320,
                    height=50,
                    alignment=ft.Alignment.CENTER,
                )
            except Exception:
                pass
        return ft.Container(width=0, height=0)

    async def preload_interstitial(self, on_close=None):
        self._on_interstitial_close = on_close
        if not self._is_mobile():
            return
        try:
            self.interstitial = fta.InterstitialAd(
                unit_id=self.INTERSTITIAL_ID,
                on_load=lambda e: None,
                on_error=lambda e: None,
                on_close=self._handle_close,
            )
        except Exception:
            self.interstitial = None

    async def _handle_close(self, e):
        if self._on_interstitial_close:
            if asyncio.iscoroutinefunction(self._on_interstitial_close):
                await self._on_interstitial_close()
            else:
                self._on_interstitial_close()
        await self.preload_interstitial(on_close=self._on_interstitial_close)

    async def show_interstitial(self) -> bool:
        if self.interstitial:
            try:
                await self.interstitial.show()
                return True
            except Exception:
                return False
        return False

    async def show_rewarded_interstitial(self, on_close) -> bool:
        """Show a rewarded interstitial ad, triggering on_close when closed."""
        if not HAS_ADS or not self._is_mobile():
            # If offline/desktop, simulate successful completion of ad
            if asyncio.iscoroutinefunction(on_close):
                await on_close()
            else:
                on_close()
            return True

        try:
            # Create a brand new instance of InterstitialAd to avoid Flet reuse errors
            async def _show(e):
                await e.control.show()

            async def _close(e):
                self._active_rewarded_ad = None  # Clean reference to prevent leaks
                if asyncio.iscoroutinefunction(on_close):
                    await on_close()
                else:
                    on_close()

            # Store a strong reference to prevent immediate python garbage collection
            self._active_rewarded_ad = fta.InterstitialAd(
                unit_id=self.INTERSTITIAL_ID,
                on_load=lambda e: self.page.run_task(_show, e),
                on_close=lambda e: self.page.run_task(_close, e),
                on_error=lambda e: logger.error("Rewarded Interstitial error: %s", e.data),
            )
            return True
        except Exception as err:
            logger.error("Failed to trigger rewarded interstitial: %s", err)
            # Sim fallback in case of errors on unsupported platforms
            if asyncio.iscoroutinefunction(on_close):
                await on_close()
            else:
                on_close()
            return False
