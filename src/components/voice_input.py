import asyncio
import logging
import flet as ft
from services.audio import AudioService
from services.ai_service import ai_service
from core.state import state
from core.theme import AppColors

logger = logging.getLogger(__name__)


class VoiceInputHandler:
    """Reusable voice dictation handler for text inputs."""

    def __init__(self, page: ft.Page, text_field: ft.TextField, on_state_change: callable = None):
        self.page = page
        self.text_field = text_field
        self.on_state_change = on_state_change
        self.audio_service = AudioService(page)
        self.is_recording = False
        self.is_transcribing = False
        self.recording_time = 0
        self._timer_task = None

        # Build reusable UI controls
        self.record_btn = ft.OutlinedButton(
            "🎙️ Dictate Answer",
            icon=ft.Icons.MIC_ROUNDED,
            on_click=lambda e: page.run_task(self._on_click),
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
            disabled=not state.is_online,
        )

        self.timer_text = ft.Text(
            "00:00 / 01:00",
            size=12,
            color=AppColors.ERROR,
            visible=False,
            weight=ft.FontWeight.BOLD,
        )

        self.status_indicator = ft.Row(
            [
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=AppColors.PRIMARY),
                ft.Text(
                    "Transcribing your voice...",
                    size=12,
                    color=AppColors.PRIMARY,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
            visible=False,
        )

    def set_enabled(self, enabled: bool):
        """Enable or disable the record button dynamically based on connection/state."""
        self.record_btn.disabled = not enabled
        try:
            self.record_btn.update()
        except Exception:
            pass

    async def _update_timer(self):
        while self.is_recording:
            await asyncio.sleep(1)
            if self.is_recording:
                self.recording_time += 1
                self.timer_text.value = f"00:{self.recording_time:02d} / 01:00"
                try:
                    self.timer_text.update()
                except Exception:
                    pass

    async def _handle_auto_stop(self, result):
        self.is_recording = False
        self.is_transcribing = True

        self.record_btn.icon = ft.Icons.MIC_ROUNDED
        self.record_btn.text = "🎙️ Dictate Answer"
        self.record_btn.style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            color=None,
        )
        self.timer_text.visible = False
        self.status_indicator.visible = True
        self.page.update()

        if self.on_state_change:
            self.on_state_change()

        if result:
            data, mime = result
            transcript = await ai_service.transcribe_audio(data, mime)
            if transcript and not transcript.startswith("["):
                current_val = self.text_field.value or ""
                self.text_field.value = (current_val + " " + transcript).strip()
                self.page.snack_bar = ft.SnackBar(ft.Text("🗣️ Transcribed!"), bgcolor=AppColors.SUCCESS)
            else:
                err_msg = transcript.replace("[", "").replace("]", "") if transcript else "Could not transcribe."
                self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ {err_msg}"), bgcolor=AppColors.ERROR)
            self.page.snack_bar.open = True

        self.text_field.disabled = False
        self.status_indicator.visible = False
        self.is_transcribing = False
        self.page.update()

        if self.on_state_change:
            self.on_state_change()

    async def _on_click(self):
        if not state.is_online:
            self.page.snack_bar = ft.SnackBar(
                ft.Text("⚠️ Dictation requires an active internet connection."),
                bgcolor=AppColors.ERROR,
            )
            self.page.snack_bar.open = True
            self.page.update()
            return

        if not self.audio_service.available:
            self.page.snack_bar = ft.SnackBar(ft.Text("Voice note recording not supported on this platform."))
            self.page.snack_bar.open = True
            self.page.update()
            return

        if self.is_transcribing:
            return

        if not self.is_recording:
            started = await self.audio_service.start_recording(
                on_auto_stop=lambda res: self.page.run_task(self._handle_auto_stop, res)
            )
            if started:
                self.is_recording = True
                self.recording_time = 0
                self.record_btn.icon = ft.Icons.STOP_ROUNDED
                self.record_btn.text = "Stop Dictating"
                self.record_btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    color=AppColors.ERROR,
                )
                self.text_field.disabled = True
                self.timer_text.value = "00:00 / 01:00"
                self.timer_text.visible = True
                self.page.update()

                if self.on_state_change:
                    self.on_state_change()

                self.page.run_task(self._update_timer)
        else:
            self.is_recording = False
            self.is_transcribing = True
            self.record_btn.icon = ft.Icons.MIC_ROUNDED
            self.record_btn.text = "🎙️ Dictate Answer"
            self.record_btn.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                color=None,
            )
            self.timer_text.visible = False
            self.status_indicator.visible = True
            self.page.update()

            if self.on_state_change:
                self.on_state_change()

            result = await self.audio_service.stop_recording()
            if result:
                data, mime = result
                transcript = await ai_service.transcribe_audio(data, mime)
                if transcript and not transcript.startswith("["):
                    current_val = self.text_field.value or ""
                    self.text_field.value = (current_val + " " + transcript).strip()
                    self.page.snack_bar = ft.SnackBar(ft.Text("🗣️ Transcribed!"), bgcolor=AppColors.SUCCESS)
                else:
                    err_msg = transcript.replace("[", "").replace("]", "") if transcript else "Could not transcribe."
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"❌ {err_msg}"), bgcolor=AppColors.ERROR)
                self.page.snack_bar.open = True

            self.text_field.disabled = False
            self.status_indicator.visible = False
            self.is_transcribing = False
            self.page.update()

            if self.on_state_change:
                self.on_state_change()
