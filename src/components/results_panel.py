"""ResultsPanel — the score summary shared by quiz/exam/assignment.

Passed / keep practicing + score + (grade) + per-open-answer feedback cards
+ Retake / Continue + a share hook (Phase 5 wires the real share service;
the panel emits a result dict shaped like v1's ShareType payloads).
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft
from flet import Control

from components.banner_ad import build_banner_ad
from core import tokens
from core.theme import AppColors


def ResultsPanel(
    *,
    passed: bool,
    score: float,
    total: float,
    pct: float,
    grade: str | None = None,
    feedback_cards: list[dict] | None = None,
    extra_line: str = "",
    retake_label: str = "Retake",
    on_retake: Callable | None = None,
    continue_label: str = "Continue",
    on_continue: Callable | None = None,
    on_share: Callable[[dict], None] | None = None,
    share_payload: dict | None = None,
) -> Control:
    """One results panel for all three assessments."""
    title = "Passed! 🎉" if passed else "Keep Practicing"
    title_color = AppColors.SUCCESS if passed else AppColors.WARNING

    controls: list[ft.Control] = [
        ft.Container(
            content=ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if passed else ft.Icons.AUTORENEW_ROUNDED,
                size=tokens.ICON_FEATURE,
                color=title_color,
            ),
            alignment=ft.Alignment.CENTER,
        ),
        ft.Text(title, size=tokens.FONT_XL, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
    ]

    score_line = f"Score: {score:g} / {total:g} ({pct:.0f}%)"
    if grade:
        controls.append(ft.Text(f"Grade: {grade} ({pct:.0f}%)", size=tokens.FONT_HERO, weight=ft.FontWeight.BOLD, color=title_color, text_align=ft.TextAlign.CENTER))
    else:
        controls.append(ft.Text(score_line, size=tokens.FONT_XL, weight=ft.FontWeight.BOLD, color=title_color, text_align=ft.TextAlign.CENTER))
    if grade:
        controls.append(ft.Text(score_line, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER))

    if extra_line:
        controls.append(ft.Text(extra_line, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER))

    for card in feedback_cards or []:
        ok = bool(card.get("met"))
        controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"Q{card.get('index', 0) + 1} — Score: {card.get('score', 0):g}/{card.get('max_score', 0):g}",
                                    size=tokens.FONT_SM,
                                    weight=ft.FontWeight.W_600,
                                    color=AppColors.SUCCESS if ok else AppColors.ERROR,
                                    expand=True,
                                ),
                            ],
                        ),
                        *([ft.Text(str(card.get("question") or ""), size=tokens.FONT_XS, weight=ft.FontWeight.W_500, selectable=True)] if card.get("question") else []),
                        *([ft.Text(str(card.get("feedback") or ""), size=tokens.FONT_XS, selectable=True)] if card.get("feedback") else []),
                        *([ft.Text(f"💡 {card.get('suggestions')}", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT)] if card.get("suggestions") else []),
                    ],
                    spacing=tokens.SPACE_XS,
                    tight=True,
                ),
                padding=tokens.SPACE_MD,
                border_radius=tokens.RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(0.06, AppColors.SUCCESS if ok else AppColors.ERROR),
            )
        )

    controls.append(ft.Container(height=tokens.SPACE_SM))

    row: list[ft.Control] = []
    if on_share and share_payload is not None:
        row.append(
            ft.OutlinedButton(
                "Share",
                icon=ft.Icons.SHARE_ROUNDED,
                on_click=lambda e: on_share(share_payload),
            )
        )
    if on_retake:
        row.append(ft.OutlinedButton(retake_label, icon=ft.Icons.REFRESH_ROUNDED, on_click=lambda e: on_retake()))
    if on_continue:
        row.append(
            ft.FilledButton(
                continue_label,
                icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                on_click=lambda e: on_continue(),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD)),
            )
        )
    if row:
        controls.append(ft.Row(controls=row, spacing=tokens.SPACE_SM, alignment=ft.MainAxisAlignment.CENTER, wrap=True))

    controls.append(ft.Container(height=tokens.SPACE_SM))
    controls.append(build_banner_ad(None))

    return ft.Column(controls=controls, spacing=tokens.SPACE_SM, scroll=ft.ScrollMode.AUTO, expand=True)
