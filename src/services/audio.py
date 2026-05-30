"""Audio recording service — voice input via flet-audio-recorder.

Uses PCM16BITS streaming (Spaninsight pattern) for reliable audio capture
across platforms, with WAV conversion, size limits, and auto-stop.
"""

import asyncio
import io
import logging
import wave

import flet as ft

from core.constants import MAX_AUDIO_SIZE_BYTES, MAX_VOICE_DURATION_SEC

logger = logging.getLogger(__name__)

try:
    from flet_audio_recorder import (
        AudioEncoder,
        AudioRecorder,
        AudioRecorderConfiguration,
        AudioRecorderStreamEvent,
    )

    _HAS_RECORDER = True
except ImportError as e:
    logger.warning("AudioRecorder not available: %s", e)
    _HAS_RECORDER = False

PCM_SAMPLE_RATE = 44100
PCM_CHANNELS = 1
PCM_BYTES_PER_SAMPLE = 2  # 16-bit


class AudioService:
    """Voice recording helper with auto-stop and buffer limits."""

    def __init__(self, page: ft.Page):
        self._page = page
        self._recorder: AudioRecorder | None = None
        self._recording = False
        self._pcm_buffer: bytearray = bytearray()
        self._auto_stop_task: asyncio.Task | None = None

        if _HAS_RECORDER:
            self._recorder = AudioRecorder(
                on_state_change=self._on_state_change,
                on_stream=self._on_stream,
            )
            if self._recorder not in page.overlay:
                page.overlay.append(self._recorder)

    @property
    def available(self) -> bool:
        return _HAS_RECORDER and self._recorder is not None

    @property
    def is_recording(self) -> bool:
        return self._recording

    async def start_recording(self, on_auto_stop=None) -> bool:
        """Start PCM16BITS streaming recording. Returns True if started."""
        if not self._recorder:
            self._page.snack_bar = ft.SnackBar(content=ft.Text("Audio recording not available on this platform"))
            self._page.snack_bar.open = True
            self._page.update()
            return False

        self._pcm_buffer.clear()

        try:
            ok = await self._recorder.start_recording(
                configuration=AudioRecorderConfiguration(
                    encoder=AudioEncoder.PCM16BITS,
                    sample_rate=PCM_SAMPLE_RATE,
                    channels=PCM_CHANNELS,
                ),
            )
            self._recording = bool(ok)
            logger.info("Audio recording started (PCM16BITS streaming, ok=%s)", ok)

            if self._recording:
                self._auto_stop_task = asyncio.create_task(self._auto_stop_timer(on_auto_stop))

            return self._recording
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            self._page.snack_bar = ft.SnackBar(content=ft.Text(f"Recording error: {e}"))
            self._page.snack_bar.open = True
            self._page.update()
            return False

    async def _auto_stop_timer(self, on_auto_stop=None):
        """Auto-stop recording after MAX_VOICE_DURATION_SEC."""
        try:
            await asyncio.sleep(MAX_VOICE_DURATION_SEC)
            if self._recording:
                logger.info(
                    "Auto-stopping recording after %ds limit",
                    MAX_VOICE_DURATION_SEC,
                )
                result = await self.stop_recording()

                # Notify the UI that recording was auto-stopped
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Voice note auto-stopped ({MAX_VOICE_DURATION_SEC}s limit)"),
                    duration=3000,
                )
                self._page.snack_bar.open = True
                self._page.update()

                if on_auto_stop and result:
                    if asyncio.iscoroutinefunction(on_auto_stop):
                        await on_auto_stop(result)
                    else:
                        callback_result = on_auto_stop(result)
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
        except asyncio.CancelledError:
            pass  # Manually stopped before timeout — expected

    async def stop_recording(self) -> tuple[bytes, str] | None:
        """Stop recording and return ``(wav_bytes, 'audio/wav')`` or None."""
        if not self._recorder or not self._recording:
            return None

        if self._auto_stop_task and not self._auto_stop_task.done():
            self._auto_stop_task.cancel()
            self._auto_stop_task = None

        try:
            await self._recorder.stop_recording()
            self._recording = False

            if not self._pcm_buffer:
                logger.warning("No PCM data collected during recording")
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text("No audio captured. Please try again."),
                    bgcolor=ft.Colors.ERROR,
                )
                self._page.snack_bar.open = True
                self._page.update()
                return None

            wav_bytes = _pcm_to_wav(
                bytes(self._pcm_buffer),
                sample_rate=PCM_SAMPLE_RATE,
                channels=PCM_CHANNELS,
                bytes_per_sample=PCM_BYTES_PER_SAMPLE,
            )
            logger.info(
                "Assembled WAV: %d PCM bytes → %d WAV bytes",
                len(self._pcm_buffer),
                len(wav_bytes),
            )
            self._pcm_buffer.clear()

            if len(wav_bytes) > MAX_AUDIO_SIZE_BYTES:
                logger.warning(
                    "Audio too large (%d bytes > %d limit)",
                    len(wav_bytes),
                    MAX_AUDIO_SIZE_BYTES,
                )
                self._page.snack_bar = ft.SnackBar(
                    content=ft.Text("Voice note too large. Please keep it under 25MB."),
                    bgcolor=ft.Colors.ERROR,
                )
                self._page.snack_bar.open = True
                self._page.update()
                return None

            return (wav_bytes, "audio/wav")
        except Exception as e:
            logger.error("Failed to stop recording: %s", e)
            self._recording = False
        return None

    def _on_stream(self, e: AudioRecorderStreamEvent):
        """Collect PCM16BITS chunks with 50MB safety cap."""
        MAX_BUFFER = 50 * 1024 * 1024
        if len(self._pcm_buffer) + len(e.chunk) > MAX_BUFFER:
            logger.warning("PCM buffer exceeded 50MB limit, discarding new data")
            return
        self._pcm_buffer.extend(e.chunk)

    def _on_state_change(self, e):
        logger.info("AudioRecorder state changed: %s", e)


def _pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = PCM_SAMPLE_RATE,
    channels: int = PCM_CHANNELS,
    bytes_per_sample: int = PCM_BYTES_PER_SAMPLE,
) -> bytes:
    """Wrap raw PCM16 bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(bytes_per_sample)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data)
    return buf.getvalue()
