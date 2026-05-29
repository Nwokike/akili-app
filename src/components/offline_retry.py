import asyncio

import flet as ft

from core.state import check_internet_connection, state
from core.theme import AppColors, AppStyles


class OfflineRetryWidget(ft.Container):
    """A premium, reusable UI widget to display a beautiful offline connection recovery screen."""

    def __init__(self, page: ft.Page, on_retry, message: str = None):
        self.page = page
        self.on_retry = on_retry
        self.message = message or "Akili needs an active internet connection to load or generate this section."

        self.retry_btn = ft.FilledButton(
            "Try Again",
            icon=ft.Icons.REPLAY_ROUNDED,
            on_click=self._handle_retry,
            style=ft.ButtonStyle(
                bgcolor=AppColors.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                padding=16,
            ),
        )
        self.loading_indicator = ft.ProgressRing(width=24, height=24, stroke_width=2, color=AppColors.PRIMARY, visible=False)

        super().__init__(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=64, color=AppColors.ACCENT),
                    ft.Text("Connection Lost", size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        self.message,
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=16),
                    ft.Row(
                        [self.retry_btn, self.loading_indicator],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            padding=32,
            alignment=ft.alignment.center,
            expand=True,
        )

    async def _handle_retry(self, e):
        self.retry_btn.disabled = True
        self.loading_indicator.visible = True
        self.update()

        # Active check
        is_connected = await check_internet_connection()
        state.is_online = is_connected

        if is_connected:
            # Clear offline banner
            if self.page.banner and self.page.banner.open:
                self.page.close_banner()

            # Execute the retry callback
            if self.on_retry:
                if asyncio.iscoroutinefunction(self.on_retry):
                    await self.on_retry()
                else:
                    self.on_retry()
        else:
            self.page.snack_bar = ft.SnackBar(
                ft.Text("Still offline. Please check your Wi-Fi or mobile data.", color=ft.Colors.WHITE),
                bgcolor=AppColors.ERROR,
            )
            self.page.snack_bar.open = True
            self.page.update()

        self.retry_btn.disabled = False
        self.loading_indicator.visible = False
        self.update()
