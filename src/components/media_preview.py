

from collections.abc import Callable

import flet as ft

from core.theme import AppColors


class MediaPreviewBar(ft.Container):

    def __init__(self, on_remove: Callable[[dict], None]):
        self._on_remove = on_remove
        self._items = ft.Row(spacing=8, scroll=ft.ScrollMode.ADAPTIVE)
        
        super().__init__(
            content=self._items,
            padding=ft.Padding(16, 8, 16, 8),
            visible=False,
            animate_opacity=300,
        )

    def set_media(self, media_list: list[dict]):
        self._items.controls.clear()
        
        for item in media_list:

            icon = ft.Icons.INSERT_DRIVE_FILE_ROUNDED
            media_type = item.get("type", "file")
            mime = item.get("mime", "")
            
            if media_type == "image" or mime.startswith("image/"):
                icon = ft.Icons.IMAGE_ROUNDED
            elif media_type == "audio" or mime.startswith("audio/"):
                icon = ft.Icons.MIC_ROUNDED
            elif media_type == "video" or mime.startswith("video/"):
                icon = ft.Icons.VIDEO_FILE_ROUNDED
                
            label = item.get("filename") or ("Voice Note" if media_type == "audio" else "Attachment")

            chip = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=16, color=AppColors.PRIMARY),
                        ft.Text(label, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=14,
                            width=24,
                            height=24,
                            style=ft.ButtonStyle(padding=0),
                            on_click=self._make_remove_handler(item),
                        )
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(12, 4, 8, 4),
                bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, AppColors.PRIMARY)),
            )
            self._items.controls.append(chip)

        self.visible = len(media_list) > 0
        self.update()

    def _make_remove_handler(self, item: dict):
        def handler(e):
            self._on_remove(item)
        return handler
