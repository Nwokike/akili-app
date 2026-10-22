"""Settings sections — AI Tutor (DDGS pattern).

Model row (shared picker subtitle + Change), thinking depth, credit
balance, and the COST_STEP-generated cost row (never hand-typed).
"""

from __future__ import annotations

import flet as ft

from components.credit_pill import build_wallet_dialog
from components.model_picker import build_model_dialog, model_picker_state, model_status_subtitle
from components.settings_kit import setting_row, settings_card
from core import tokens
from core.constants import (
    COST_STEP,
    DAILY_FREE_CREDITS,
    PREMIUM_DAILY_CREDITS,
    credit_word,
)
from core.state import state
from core.theme import AppColors
from state.controller_ctx import ControllerMethodsCtx


@ft.component
def build_ai_section(page: ft.Page) -> ft.Control:
    """The AI Tutor card."""
    controller = ft.use_context(ControllerMethodsCtx)
    narrow = bool(page and getattr(page, "width", None) and page.width < 600)

    def _save(key: str, value) -> None:
        controller.save(key, value)

    cap = PREMIUM_DAILY_CREDITS if state.is_premium else DAILY_FREE_CREDITS
    picker = model_picker_state()

    rows: list[ft.Control] = [
        setting_row(
            ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED,
            "AI tutor mode",
            "Show the tutor tab and suggestions",
            ft.Switch(
                value=state.ai_mode_enabled,
                active_color=AppColors.PRIMARY,
                on_change=lambda e: _save("ai_mode", e.control.value),
            ),
            stacked=narrow,
        ),
        setting_row(
            ft.Icons.PSYCHOLOGY_ROUNDED,
            "Thinking depth",
            "Auto leaves it to the model; Fast and Deep trade speed for care",
            ft.SegmentedButton(
                segments=[
                    ft.Segment(value="auto", label=ft.Text("Auto", size=10)),
                    ft.Segment(value="low", label=ft.Text("Fast", size=10)),
                    ft.Segment(value="high", label=ft.Text("Deep", size=10)),
                ],
                selected=[str(state.reasoning_effort or "auto")],
                allow_multiple_selection=False,
                show_selected_icon=False,
                on_change=lambda e: _save("reasoning_effort", (e.control.selected or ["auto"])[0]),
            ),
            stacked=True,
        ),
        setting_row(
            ft.Icons.MEMORY_ROUNDED,
            "AI model",
            f"{picker['label']} · {model_status_subtitle()}" if picker["active"] else model_status_subtitle(),
            ft.TextButton("Change", on_click=lambda e: page.show_dialog(build_model_dialog(page))),
            stacked=narrow,
        ),
        setting_row(
            ft.Icons.BOLT_ROUNDED,
            f"{state.credits_remaining} of {cap} credits left today",
            "Resets at 00:00 UTC — tap for the wallet",
            # v1's Remaining-Credits row opens the credits dialog (top-up).
            ft.TextButton(
                "Wallet",
                on_click=lambda e: page.show_dialog(build_wallet_dialog(page)),
            ),
            stacked=narrow,
        ),
        # Generated from COST_STEP, never typed by hand. A literal
        # "1 credit" here while the agent charges COST_STEP is how a user
        # ends up silently overcharged.
        setting_row(
            ft.Icons.PRICE_CHECK_ROUNDED,
            "What credits are for",
            f"Each AI model step costs {credit_word(COST_STEP)}. Practice quizzes, mock exams and browsing are free",
            ft.Text(f"{COST_STEP} / step", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT),
            stacked=narrow,
        ),
    ]

    return settings_card(rows)
