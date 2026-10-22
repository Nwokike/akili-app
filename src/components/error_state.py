"""ErrorState — icon + title + description + retry, with an offline variant.

Ported from DDGS's error box pattern (the house standard).
Plain function — testable without a renderer.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft
from flet import Control

from core import tokens
from core.theme import AppColors


def ErrorState(
    title: str,
    message: str = "",
    action_label: str | None = None,
    on_action: Callable | None = None,
    icon: ft.IconData | None = None,
    offline: bool = False,
) -> Control:
    """A centred error panel with an optional retry action."""
    if icon is None:
        icon = ft.Icons.WIFI_OFF_ROUNDED if offline else ft.Icons.ERROR_OUTLINE_ROUNDED
    color = AppColors.WARNING if offline else AppColors.ERROR

    items: list[ft.Control] = [
        ft.Container(
            content=ft.Icon(icon, size=tokens.ICON_EMPTY, color=ft.Colors.with_opacity(0.8, color)),
            width=tokens.ICON_EMPTY * 2,
            height=tokens.ICON_EMPTY * 2,
            border_radius=tokens.ICON_EMPTY,
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_LIGHT, color),
            alignment=ft.Alignment.CENTER,
            margin=ft.Margin(0, 0, 0, tokens.SPACE_LG),
        ),
        ft.Text(title, size=tokens.FONT_LG, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
    ]
    if message:
        items.append(
            ft.Text(
                message,
                size=tokens.FONT_SM,
                color=ft.Colors.with_opacity(tokens.OPACITY_DIM, ft.Colors.ON_SURFACE),
                text_align=ft.TextAlign.CENTER,
                width=tokens.MESSAGE_MAX_WIDTH,
            )
        )
    if action_label and on_action:
        items.append(ft.Container(height=tokens.SPACE_MD))
        items.append(
            ft.FilledButton(
                content=ft.Text(action_label, weight=ft.FontWeight.W_600),
                on_click=on_action,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                    padding=ft.Padding(tokens.SPACE_XL, tokens.SPACE_SM, tokens.SPACE_XL, tokens.SPACE_SM),
                ),
            )
        )
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=tokens.SPACE_XL,
        content=ft.Column(
            controls=items,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
    )


def OfflineState(on_retry: Callable | None = None) -> Control:
    """The canonical offline panel."""
    return ErrorState(
        "You're offline",
        "Connect to the internet and try again — your progress is saved locally.",
        "Try again",
        on_retry,
        offline=True,
    )
