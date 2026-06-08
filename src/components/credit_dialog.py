import asyncio
import contextlib
import time

import flet as ft

from core.state import state
from core.theme import AppColors


def show_credits_dialog(page: ft.Page, credit_service, ad_service):
    """Show the premium credits panel, featuring Ad Rewards with a 30s cooldown on mobile."""

    if not hasattr(state, "ad_cooldown_end"):
        state.ad_cooldown_end = 0.0

    is_mobile = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)

    credits_text = ft.Text(
        f"{state.credits_remaining}",
        size=36,
        weight="bold",
        color=AppColors.PRIMARY,
    )

    cooldown_label = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER)

    watch_btn = None
    if is_mobile:
        watch_btn = ft.FilledButton(
            "Watch Ad (+5 Credits)",
            icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
            bgcolor=AppColors.ACCENT,
            color=ft.Colors.WHITE,
            disabled=False,
        )

    dialog_open = True

    def _close_dialog(e=None):
        nonlocal dialog_open
        dialog_open = False
        dlg.open = False
        page.update()

    def _on_dismiss(e):
        nonlocal dialog_open
        dialog_open = False

    async def _update_timer_loop():
        if not is_mobile or watch_btn is None:
            return
        # A loop that updates the countdown in real-time while the dialog is visible
        while dialog_open and dlg.open:
            now = time.time()
            remaining = int(state.ad_cooldown_end - now)
            if remaining > 0:
                watch_btn.disabled = True
                watch_btn.text = f"Cooldown ({remaining}s)"
                cooldown_label.value = f"Please wait {remaining}s before watching another ad."
                cooldown_label.color = AppColors.ERROR
                try:
                    watch_btn.update()
                    cooldown_label.update()
                except Exception:
                    break
            else:
                watch_btn.disabled = False
                watch_btn.text = "Watch Ad (+5 Credits)"
                cooldown_label.value = "Watch a short ad to receive +5 learning credits instantly!"
                cooldown_label.color = ft.Colors.ON_SURFACE_VARIANT
                try:
                    watch_btn.update()
                    cooldown_label.update()
                except Exception:
                    break
                break
            await asyncio.sleep(0.5)

    async def _on_watch_success():
        # Award credits securely
        new_balance = await credit_service.add_credits(5)
        credits_text.value = str(new_balance)
        with contextlib.suppress(Exception):
            credits_text.update()

    async def _on_watch_click(e):
        if not is_mobile or watch_btn is None:
            # Desktop/simulator fallback
            await _on_watch_success()
            return

        now = time.time()
        if state.ad_cooldown_end > now:
            return

        # Start cooldown immediately to prevent duplicate clicks
        state.ad_cooldown_end = now + 30.0

        watch_btn.disabled = True
        with contextlib.suppress(Exception):
            watch_btn.update()

        page.run_task(_update_timer_loop)

        # Trigger interstitial ad safely
        success = await ad_service.show_rewarded_interstitial(_on_watch_success)
        if not success:
            # If trigger failed, reset cooldown
            state.ad_cooldown_end = 0
            watch_btn.disabled = False
            with contextlib.suppress(Exception):
                watch_btn.update()

    if is_mobile and watch_btn is not None:
        watch_btn.on_click = lambda e: page.run_task(_on_watch_click, e)

    content_controls = [
        ft.Row(
            [
                ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=28, color=AppColors.ACCENT),
                ft.Text("Akili Credit Balance", size=18, weight="bold"),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        ft.Container(height=10),
        ft.Row(
            [
                credits_text,
                ft.Text("credits", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        ft.Container(height=6),
        ft.Text(
            "Akili grants 100 free learning credits every 24 hours. Credits are spent when generating new course content, tutor chats, and assignment evaluations.",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        ),
    ]

    # Mobile button or Desktop simulation button
    if is_mobile:
        content_controls.extend(
            [
                ft.Divider(height=20, thickness=0.5),
                ft.Text(
                    "Need more credits?",
                    size=12,
                    weight="bold",
                    color=AppColors.PRIMARY,
                ),
                cooldown_label,
                ft.Container(height=4),
                watch_btn,
            ]
        )
    else:
        # Simulation button for testing on Desktop
        sim_btn = ft.FilledButton(
            "Simulate Ad (+5 Credits)",
            icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
            bgcolor=AppColors.PRIMARY,
            color=ft.Colors.WHITE,
            on_click=lambda e: page.run_task(_on_watch_click, e),
        )
        content_controls.extend(
            [
                ft.Divider(height=20, thickness=0.5),
                ft.Text(
                    "Desktop Ad Simulator",
                    size=12,
                    weight="bold",
                    color=AppColors.PRIMARY,
                ),
                ft.Text(
                    "Watching ads is supported on mobile devices. Click below to simulate earning credits.",
                    size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=4),
                sim_btn,
            ]
        )

    dlg = ft.AlertDialog(
        content=ft.Container(
            content=ft.Column(
                content_controls,
                spacing=8,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=320,
            padding=10,
        ),
        actions=[ft.TextButton("Close", on_click=_close_dialog)],
        on_dismiss=_on_dismiss,
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()

    if is_mobile:
        # Start timer loop immediately on load
        page.run_task(_update_timer_loop)
