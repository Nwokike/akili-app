"""LoadingState — shimmer skeletons + a status label.

Ported from KTV Player's loading_state pattern (the house standard).
Plain function — testable without a renderer.
"""

from __future__ import annotations

import flet as ft
from flet import Control

from core import tokens
from core.theme import AppColors


def LoadingState(label: str | None = None, rows: int = 3) -> Control:
    """Skeleton cards on a shimmer, with an optional status label."""
    base = ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
    highlight = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
    skeleton = [
        ft.Container(
            height=84,
            border_radius=tokens.RADIUS_MD,
            bgcolor=base,
            margin=ft.Margin(0, 0, 0, tokens.SPACE_SM),
        )
        for _ in range(rows)
    ]
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            controls=[
                ft.Shimmer(
                    base_color=base,
                    highlight_color=highlight,
                    period=1400,
                    content=ft.Column(controls=skeleton, spacing=0),
                ),
                ft.Container(height=tokens.SPACE_MD),
                ft.Text(
                    label or "Loading...",
                    size=tokens.FONT_SM,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            width=360,
        ),
    )


def ProgressState(label: str, value: float | None = None) -> Control:
    """A determinate/indeterminate progress bar with a live status label."""
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            controls=[
                ft.ProgressBar(
                    value=value,
                    width=280,
                    color=AppColors.PRIMARY,
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                ),
                ft.Container(height=tokens.SPACE_MD),
                ft.Text(
                    label,
                    size=tokens.FONT_SM,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                    width=tokens.MESSAGE_MAX_WIDTH,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
    )
