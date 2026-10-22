"""ThinkingBlock — streaming reasoning display.

Ported from DDGS/chat_screen.py thinking rendering.
Open while thinking with live text; auto-collapses on the first answer
word, but never fights an explicit user toggle.
"""

from __future__ import annotations

import flet as ft

from core import tokens
from core.theme import AppColors

_MAX_CHARS = 8000


def ThinkingBlock(text: str, *, streaming: bool, expanded: bool) -> ft.Control:
    """One thinking row: header + (optionally) the reasoning text."""
    shown = (text or "")[:_MAX_CHARS]
    label = "Thinking…" if streaming else "Thought"
    header = ft.Row(
        controls=[
            ft.Icon(
                ft.Icons.PSYCHOLOGY_ALT_ROUNDED,
                size=tokens.ICON_SM,
                color=AppColors.PRIMARY,
            ),
            ft.Text(label, size=tokens.FONT_XS, weight=ft.FontWeight.W_600, color=AppColors.PRIMARY),
            ft.Icon(
                ft.Icons.EXPAND_LESS_ROUNDED if expanded else ft.Icons.EXPAND_MORE_ROUNDED,
                size=tokens.ICON_SM,
                color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
            ),
        ],
        spacing=tokens.SPACE_XS,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    controls: list[ft.Control] = [header]
    if expanded and shown.strip():
        controls.append(
            ft.Container(
                content=ft.Text(
                    shown,
                    size=tokens.FONT_XS,
                    color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    selectable=True,
                ),
                padding=ft.Padding(tokens.SPACE_SM, 0, 0, 0),
                border=ft.Border(left=ft.BorderSide(2, AppColors.PRIMARY)),
            )
        )
    return ft.Container(
        content=ft.Column(controls=controls, spacing=tokens.SPACE_XS, tight=True),
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
        border_radius=tokens.RADIUS_SM,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
    )
