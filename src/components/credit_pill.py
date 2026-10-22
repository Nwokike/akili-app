"""Credit pill + wallet dialog — the tutor's balance display.

Ported from DDGS wallet.py (the house standard).
Colour thresholds: >20 green, >=5 amber, else red.
"""

from __future__ import annotations

import contextlib

import flet as ft

from core import tokens
from core.constants import (
    AD_TOPUP_COOLDOWN_SEC,
    AD_TOPUP_CREDITS,
    COST_STEP,
    COST_TUTOR_QUESTION,
    DAILY_FREE_CREDITS,
    PREMIUM_DAILY_CREDITS,
)
from core.state import state
from core.theme import AppColors


def credit_word(count: int) -> str:
    """Price copy that cannot go plural-blind: 1 credit, 3 credits."""
    return f"{count} credit" if count == 1 else f"{count} credits"


def _balance_color(balance: int) -> str:
    if balance > 20:
        return AppColors.SUCCESS
    if balance >= 5:
        return AppColors.WARNING
    return AppColors.ERROR


def build_credit_pill(on_click=None) -> ft.Control:
    """A compact balance chip. Re-renders when state.credits_remaining changes."""
    balance = state.credits_remaining
    color = _balance_color(balance)
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.BOLT_ROUNDED, size=tokens.ICON_XS, color=color),
                ft.Text(
                    str(balance),
                    size=tokens.FONT_XS,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                    no_wrap=True,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        padding=ft.Padding(10, 4, 10, 4),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border=ft.Border.all(1, color),
        ink=on_click is not None,
        on_click=on_click,
        tooltip="AI credits — tap for the wallet",
    )


def build_wallet_dialog(page: ft.Page) -> ft.Control:
    """The full wallet: balance, cap, reset note, cost table, top-ups."""
    balance = state.credits_remaining
    cap = PREMIUM_DAILY_CREDITS if state.is_premium else DAILY_FREE_CREDITS

    cost_rows = [
        ("Each AI model step", credit_word(COST_STEP)),
        ("A tutor question (about 2 steps)", f"~{credit_word(COST_TUTOR_QUESTION)}"),
        ("Practice quizzes", "Free"),
        ("Mock exams", "Free"),
        ("Browsing lessons", "Free"),
    ]

    def _cost_table() -> ft.Control:
        rows = []
        for label, price in cost_rows:
            rows.append(
                ft.Row(
                    controls=[
                        ft.Text(label, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                        ft.Text(price, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                    ],
                )
            )
        return ft.Column(controls=rows, spacing=tokens.SPACE_XS)

    async def _watch_ad(e):
        credits = getattr(state, "credit_service", None)
        if credits is None:
            return
        new_balance = await credits.add_credits(AD_TOPUP_CREDITS)
        state.ad_cooldown_end = __import__("time").time() + AD_TOPUP_COOLDOWN_SEC
        with contextlib.suppress(Exception):
            page.pop_dialog()
        from core.notify import show_snack

        show_snack(page, f"+{AD_TOPUP_CREDITS} credits — balance {new_balance}", AppColors.SUCCESS)

    ad_row = None
    if page.platform.is_mobile() and not state.is_premium:
        ad_row = ft.TextButton(
            f"Watch ad for +{AD_TOPUP_CREDITS} credits",
            icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
            on_click=lambda e: page.run_task(_watch_ad, e),
        )

    return ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=AppColors.PRIMARY),
                ft.Text("AI Credits", weight=ft.FontWeight.BOLD),
            ],
            spacing=tokens.SPACE_SM,
        ),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(str(balance), size=tokens.FONT_HERO, weight=ft.FontWeight.BOLD, color=_balance_color(balance)),
                        ft.Text(f"of {cap} daily", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    spacing=tokens.SPACE_SM,
                ),
                ft.Text("Resets at 00:00 UTC", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                _cost_table(),
                *([ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)), ad_row] if ad_row else []),
            ],
            spacing=tokens.SPACE_SM,
            tight=True,
            width=tokens.DIALOG_WIDTH_LG,
        ),
        actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
    )
