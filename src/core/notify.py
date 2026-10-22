"""Snackbar helper — best-effort message surfacing.

Ported from Sherlock's notify pattern (the house standard).
Logs failures, never raises. Replaces lingering snack, never closes real dialogs.
"""

from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)


def show_snack(
    page: ft.Page,
    message: str,
    bgcolor: str | None = None,
    duration: int = 4000,
) -> None:
    """Best-effort snackbar: logs failures, never raises."""
    try:
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=bgcolor or ft.Colors.BLACK,
            duration=duration,
        )
        try:
            page.show_dialog(snack)
        except RuntimeError:
            popped = page.pop_dialog()
            if popped is None or isinstance(popped, ft.SnackBar):
                page.show_dialog(snack)
    except Exception as ex:
        logger.warning("show_snack failed: %s", ex)
