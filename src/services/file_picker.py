"""Image picking for answers — core FilePicker with guard rails.

Ported from Akili v1's file_picker.py. The picker is constructed here;
the caller adds it to page.overlay. 10MB cap, extension mime detection.
"""

from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = ("png", "jpg", "jpeg", "webp")


def detect_mime(filename: str) -> str:
    """Extension-based mime detection (no content sniffing, v1 parity)."""
    lowered = (filename or "").lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _snack(page: ft.Page | None, message: str) -> None:
    if page is None:
        return
    try:
        from core.notify import show_snack
        from core.theme import AppColors

        show_snack(page, message, AppColors.ERROR)
    except Exception:
        pass


class FilePickerService:
    """Ephemeral image picker: returns (bytes, mime, filename) or None."""

    def __init__(self, page: ft.Page | None = None, on_result=None):
        self._page = page
        self._on_result = on_result
        self.picker = ft.FilePicker(on_result=self._handle_result)

    async def pick_image(self) -> None:
        """Open the picker; the result arrives via on_result."""
        try:
            await self.picker.pick_files(
                allow_multiple=False,
                allowed_extensions=list(ALLOWED_EXTENSIONS),
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
        except Exception as exc:
            logger.warning("image pick failed: %s", exc)

    def _handle_result(self, e) -> None:
        files = getattr(e, "files", None) or []
        if not files:
            return
        file = files[0]
        data = getattr(file, "bytes", None)
        if data is None and getattr(file, "path", None):
            try:
                with open(file.path, "rb") as handle:
                    data = handle.read()
            except Exception as exc:
                logger.warning("could not read picked file: %s", exc)
                return
        if not data:
            return
        if len(data) > MAX_IMAGE_BYTES:
            _snack(self._page, "❌ File too large. Please keep images under 10MB.")
            return
        name = getattr(file, "name", "") or "image"
        mime = detect_mime(name)
        if self._on_result is not None:
            import asyncio

            result = self._on_result(data, mime, name)
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    pass
