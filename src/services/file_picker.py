"""Handles file selection for images and answer uploads.

Uses Flet's FilePicker with with_data=True so it works on mobile
without file paths. On mobile, file_type=IMAGE natively offers
both Gallery and Camera options — no flet_camera dependency needed.
"""

from pathlib import Path

import flet as ft


def _read_file_bytes(path: str) -> bytes:
    """Read file bytes using context manager (SIM115 compliant)."""
    with Path(path).open("rb") as f:
        return f.read()


def _detect_mime(filename: str) -> str:
    """Detect MIME type from filename extension."""
    lower = filename.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


class FilePickerService:
    def __init__(self, page: ft.Page, on_result: callable):
        self.page = page
        self.on_result = on_result
        self.picker = ft.FilePicker()

    async def pick_image(self):
        """Pick an image from gallery or camera. Returns bytes via on_result callback."""
        result = await self.picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,
        )

        if result and len(result) > 0:
            file = result[0]
            try:
                data = file.bytes if file.bytes else _read_file_bytes(file.path)
                mime_type = _detect_mime(file.name)
                self.on_result(data, mime_type, file.name)
            except Exception as ex:
                print(f"[FilePickerService] Error reading image: {ex}")

    async def pick_answer_image(self) -> tuple[bytes, str] | None:
        """Pick an image for answer submission. Returns (bytes, mime) or None.

        On mobile this shows Gallery + Camera options natively.
        Image bytes are ephemeral — processed by AI then discarded (no bloat).
        """
        result = await self.picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,
        )

        if not result or len(result) == 0:
            return None

        file = result[0]
        try:
            data = file.bytes if file.bytes else _read_file_bytes(file.path)
            mime_type = _detect_mime(file.name)
            return (data, mime_type)
        except Exception as ex:
            print(f"[FilePickerService] Error reading answer image: {ex}")
            return None
