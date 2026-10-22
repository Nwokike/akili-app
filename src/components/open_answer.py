"""OpenAnswer — the written-answer input shared by quiz/exam/assignment.

Typing plus voice dictation (into the field) plus one photo answer
(via the picker's on_result). Image bytes flow back through `on_image`
so the screen can stash them alongside the text for grading.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

import flet as ft
from flet import Control

from components.voice_input import VoiceInputHandler
from core import tokens
from core.question_types import QuestionType
from services.file_picker import FilePickerService


def OpenAnswer(
    qtype: str,
    value: str = "",
    on_change: Callable[[str], None] | None = None,
    on_image: Callable[[bytes, str, str], None] | None = None,
    has_image: bool = False,
    disabled: bool = False,
) -> Control:
    """A multiline answer field with voice + photo actions."""
    label = "Share your analysis..." if qtype == QuestionType.SUBJECTIVE else "Type your answer..."

    field = ft.TextField(
        label=label,
        value=value,
        multiline=True,
        min_lines=3,
        max_lines=8,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        disabled=disabled,
        on_change=(lambda e: on_change(e.control.value)) if on_change else None,
    )
    voice = VoiceInputHandler(None, field)

    async def _pick(page: ft.Page | None):
        picker = FilePickerService(page, on_result=_on_picked)
        with contextlib.suppress(Exception):
            page.overlay.append(picker.picker)
        await picker.pick_image()

    def _on_picked(data: bytes, mime: str, filename: str) -> None:
        if on_image is not None:
            on_image(data, mime, filename)

    controls: list[ft.Control] = [
        field,
        ft.Row(
            controls=[
                voice.record_btn,
                voice.timer_text,
                ft.Text("or", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.OutlinedButton(
                    "📷 Upload answer photo" if not has_image else "📷 Photo attached ✓",
                    icon=ft.Icons.CAMERA_ALT_ROUNDED,
                    disabled=disabled,
                    on_click=lambda e: _open_picker(e),
                ),
            ],
            spacing=tokens.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        ),
        voice.status_indicator,
    ]

    def _open_picker(e) -> None:
        try:
            page = ft.context.page
        except Exception:
            return
        import asyncio

        try:
            page.run_task(_pick, page)
        except Exception:
            asyncio.ensure_future(_pick(page))

    return ft.Column(controls=controls, spacing=tokens.SPACE_XS, tight=True)
