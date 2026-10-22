"""SectionHeader — uppercase section label.

Ported from Sherlock's SectionHeader (the house standard).
Plain function — testable without a renderer.
"""

from __future__ import annotations

import flet as ft
from flet import Control

from core import tokens
from core.theme import AppColors


def SectionHeader(text: str) -> Control:
    """Uppercase primary label with letter spacing."""
    return ft.Text(
        text.upper(),
        size=tokens.FONT_XS,
        weight=ft.FontWeight.W_600,
        color=AppColors.PRIMARY,
        font_family="Outfit",
    )
