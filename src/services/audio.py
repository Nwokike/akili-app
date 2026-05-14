import contextlib
import os
import tempfile

import flet as ft
import flet_audio_recorder as far


class AudioService:
    def __init__(self, page: ft.Page):
        self.page = page
        self.recorder = far.AudioRecorder()

        self.is_recording = False
        self._temp_file = ""

    async def start_recording(self) -> bool:
        try:
            self._temp_file = os.path.join(tempfile.gettempdir(), "akili_voice_note.wav")
            await self.recorder.start_recording(self._temp_file)
            self.is_recording = True
            self.page.update()
            return True
        except Exception as e:
            print(f"[AudioService] Error starting recording: {e}")
            return False

    async def stop_recording(self) -> tuple[bytes, str] | None:
        if not self.is_recording:
            return None

        try:
            await self.recorder.stop_recording()
            self.is_recording = False
            self.page.update()

            # Read the audio bytes into memory
            with open(self._temp_file, "rb") as f:
                data = f.read()

            with contextlib.suppress(Exception):
                os.remove(self._temp_file)

            return data, "audio/wav"
        except Exception as e:
            print(f"[AudioService] Error stopping recording: {e}")
            return None
