"""StatCard — label + large value + color.

Ported from Sherlock's StatCard (the house standard).
Auto-shrinks font for 3-5 digit counts.
Plain function — testable without a renderer.
"""

from __future__ import annotations

import flet as ft
from flet import Control

from core import tokens


def StatCard(label: str, value: str | int, color: str | None = None) -> Control:
    """A compact stat display with auto-shrinking value font."""
    value_str = str(value)
    font_size = tokens.FONT_XL
    if len(value_str) >= 5:
        font_size = tokens.FONT_MD
    elif len(value_str) >= 3:
        font_size = tokens.FONT_LG

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    value_str,
                    size=font_size,
                    weight=ft.FontWeight.BOLD,
                    color=color or ft.Colors.ON_SURFACE,
                    font_family="Outfit",
                ),
                ft.Text(
                    label,
                    size=tokens.FONT_XS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    font_family="Outfit",
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XXS,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_MD,
            right=tokens.SPACE_MD,
            top=tokens.SPACE_SM,
            bottom=tokens.SPACE_SM,
        ),
        border_radius=tokens.RADIUS_MD,
        bgcolor=ft.Colors.with_opacity(0.04, color or ft.Colors.ON_SURFACE),
    )
