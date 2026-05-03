"""Handles native gallery image and file selection."""

import flet as ft


class FilePickerService:
    def __init__(self, page: ft.Page, on_result: callable):
        self.page = page
        self.on_result = on_result

        # Flet 0.84.0: FilePicker is a Service, not a Control. Do not add to overlay.
        self.picker = ft.FilePicker()

    async def pick_image(self):
        result = await self.picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["png", "jpg", "jpeg", "webp"],
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True # Get bytes directly for multimodal AI
        )
        
        if result and len(result) > 0:
            file = result[0]
            try:
                # Use bytes directly if available (best for Android/iOS)
                if file.bytes:
                    data = file.bytes
                else:
                    with open(file.path, "rb") as f:
                        data = f.read()
                
                # Determine standard MIME type
                mime_type = "image/jpeg"
                if file.name.lower().endswith(".png"):
                    mime_type = "image/png"
                elif file.name.lower().endswith(".webp"):
                    mime_type = "image/webp"

                # Send the data back to the UI
                self.on_result(data, mime_type, file.name)
            except Exception as ex:
                print(f"[FilePickerService] Error reading image: {ex}")