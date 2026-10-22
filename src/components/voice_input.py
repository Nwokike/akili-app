"""Voice input — dictate into a text field, transcribed via the gateway.

Ported from Akili v1's voice_input.py. Append-mode: the transcript is
added after existing text. Offline-disabled, 60s cap, transcribing
indicator while the gateway works.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import flet as ft

from core import tokens
from core.theme import AppColors
from services.audio import AudioService
from services.gateway_media import is_failure, transcribe_audio

logger = logging.getLogger(__name__)


class VoiceInputHandler:
    """Dictate button + timer + transcribing state bound to a TextField."""

    def __init__(self, page: ft.Page | None, text_field: ft.TextField, on_state_change=None):
        self._page = page
        self._field = text_field
        self._on_state_change = on_state_change
        self._audio = AudioService(page)
        self._transcribing = False
        self._elapsed = 0

        from core.state import state

        self.record_btn = ft.OutlinedButton(
            "🎙️ Dictate Answer",
            icon=ft.Icons.MIC_ROUNDED,
            on_click=lambda e: page.run_task(self._on_click) if page else None,
            disabled=not state.is_online,
        )
        self.timer_text = ft.Text("00:00 / 01:00", size=12, color=AppColors.ERROR, visible=False, weight=ft.FontWeight.BOLD)
        self.status_indicator = ft.Row(
            controls=[
                ft.ProgressRing(width=16, height=16, stroke_width=2),
                ft.Text("Transcribing your voice...", size=tokens.FONT_XS),
            ],
            spacing=tokens.SPACE_XS,
            visible=False,
        )

    @property
    def is_transcribing(self) -> bool:
        return self._transcribing

    async def _on_click(self) -> None:
        from core.state import state

        if self._transcribing:
            return
        if not state.is_online:
            self._snack("Dictation needs an internet connection.", error=True)
            return
        if not self._audio.available:
            self._snack("Audio recording is not supported on this device.", error=True)
            return
        if self._audio.is_recording:
            await self._stop_and_transcribe()
        else:
            await self._start()

    async def _start(self) -> None:
        ok = await self._audio.start_recording(on_auto_stop=self._handle_auto_stop)
        if not ok:
            return
        self._elapsed = 0
        self.record_btn.text = "Stop Dictating"
        self.record_btn.icon = ft.Icons.STOP_ROUNDED
        self.timer_text.visible = True
        self._field.disabled = True
        self._emit(False)
        self._refresh()
        asyncio.ensure_future(self._update_timer())

    async def _stop_and_transcribe(self) -> None:
        result = await self._audio.stop_recording()
        self.record_btn.text = "🎙️ Dictate Answer"
        self.record_btn.icon = ft.Icons.MIC_ROUNDED
        self.timer_text.visible = False
        self._field.disabled = False
        self._refresh()
        if result is None:
            self._emit(True)
            return
        data, mime = result
        self._transcribing = True
        self.status_indicator.visible = True
        self._refresh()
        try:
            transcript = await transcribe_audio(data, mime)
        finally:
            self._transcribing = False
            self.status_indicator.visible = False
            self._refresh()
        if transcript and not is_failure(transcript):
            current = (self._field.value or "").strip()
            self._field.value = f"{current} {transcript}".strip() if current else transcript
            self._snack("🗣️ Transcribed!")
        else:
            self._snack(f"❌ {transcript}", error=True)
        self._emit(True)
        self._refresh()

    async def _handle_auto_stop(self, _result) -> None:
        await self._stop_and_transcribe()

    async def _update_timer(self) -> None:
        while self._audio.is_recording and self._elapsed < 60:
            await asyncio.sleep(1)
            self._elapsed += 1
            self.timer_text.value = f"00:{self._elapsed:02d} / 01:00"
            self._refresh()

    def _emit(self, idle: bool) -> None:
        if self._on_state_change is not None:
            with contextlib.suppress(Exception):
                self._on_state_change(idle)

    def _refresh(self) -> None:
        for ctrl in (self.record_btn, self.timer_text, self.status_indicator, self._field):
            with contextlib.suppress(Exception):
                ctrl.update()

    def _snack(self, message: str, error: bool = False) -> None:
        if self._page is None:
            return
        try:
            from core.notify import show_snack

            show_snack(self._page, message, AppColors.ERROR if error else AppColors.PRIMARY)
        except Exception:
            pass
