"""Media preview bar — attachment chips with remove buttons.

Ported from Akili v1's media_preview.py. Ephemeral by design: chips
reference in-memory bytes, never paths; the parent owns removal.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft
from flet import Control

from core import tokens
from core.theme import AppColors


def _chip_icon(item: dict) -> ft.IconData:
    mime = str(item.get("mime") or "")
    kind = str(item.get("type") or "")
    if kind == "image" or mime.startswith("image/"):
        return ft.Icons.IMAGE_ROUNDED
    if kind == "audio" or mime.startswith("audio/"):
        return ft.Icons.MIC_ROUNDED
    if kind == "video" or mime.startswith("video/"):
        return ft.Icons.VIDEO_FILE_ROUNDED
    return ft.Icons.INSERT_DRIVE_FILE_ROUNDED


def _chip_label(item: dict) -> str:
    if item.get("filename"):
        return str(item["filename"])
    if str(item.get("type") or "") == "audio":
        return "Voice Note"
    return "Attachment"


class MediaPreviewBar(ft.Container):
    """A row of attachment chips; hidden when empty."""

    def __init__(self, on_remove: Callable[[dict], None] | None = None):
        self._on_remove = on_remove
        self._items: ft.Row = ft.Row(controls=[], spacing=tokens.SPACE_SM, scroll=ft.ScrollMode.AUTO)
        super().__init__(
            content=self._items,
            padding=ft.Padding(tokens.SPACE_SM, 0, tokens.SPACE_SM, 0),
            visible=False,
            animate_opacity=300,
        )

    def set_media(self, media_list: list[dict]) -> None:
        """Rebuild chips from the current attachment list."""
        chips: list[Control] = []
        for item in media_list or []:
            chips.append(self._chip(item))
        self._items.controls = chips
        self.visible = len(chips) > 0
        with contextlib.suppress(Exception):
            self.update()

    def _chip(self, item: dict) -> Control:
        def _remove(_e):
            if self._on_remove is not None:
                self._on_remove(item)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(_chip_icon(item), size=tokens.ICON_XS, color=AppColors.PRIMARY),
                    ft.Text(
                        _chip_label(item),
                        size=tokens.FONT_XS,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=14,
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        width=24,
                        height=24,
                        padding=0,
                        on_click=_remove,
                        tooltip="Remove",
                    ),
                ],
                spacing=tokens.SPACE_XS,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
            border_radius=tokens.RADIUS_MD,
            bgcolor=ft.Colors.with_opacity(0.10, AppColors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.20, AppColors.PRIMARY)),
        )
