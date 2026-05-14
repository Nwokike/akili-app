import asyncio
import base64

import flet as ft
from flet_camera import Camera
from flet_camera.types import ResolutionPreset

from core.theme import AppColors


class CameraViewfinder(ft.Stack):
    def __init__(
        self,
        page: ft.Page,
        on_capture: callable,  # (data, mime, filename)
        on_close: callable,
    ):
        super().__init__(expand=True)
        self._page = page
        self._on_capture = on_capture
        self._on_close = on_close

        self._camera = None
        self._cameras = []
        self._current_camera_index = 0

        self._preview_container = ft.Container(expand=True, bgcolor=ft.Colors.BLACK)

        self._close_btn = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_color=ft.Colors.WHITE,
            icon_size=32,
            bgcolor="#44000000",
            on_click=self._handle_close,
        )

        self._flip_btn = ft.IconButton(
            icon=ft.Icons.FLIP_CAMERA_IOS_ROUNDED,
            icon_color=ft.Colors.WHITE,
            icon_size=32,
            on_click=self._handle_flip,
            visible=False,
        )

        self._capture_btn = ft.Container(
            width=72,
            height=72,
            border_radius=36,
            border=ft.Border.all(4, AppColors.PRIMARY),
            bgcolor=ft.Colors.WHITE,
            on_click=self._handle_capture,
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )

        self.controls = [
            self._preview_container,
            ft.Container(
                content=self._close_btn,
                top=20,
                right=20,
            ),
            ft.Container(
                bottom=0,
                left=0,
                right=0,
                height=200,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_CENTER,
                    end=ft.Alignment.BOTTOM_CENTER,
                    colors=[ft.Colors.TRANSPARENT, "#CC000000"],
                ),
                content=ft.Column(
                    controls=[
                        ft.Stack(
                            height=100,
                            controls=[
                                ft.Container(
                                    content=self._capture_btn,
                                    alignment=ft.Alignment.CENTER,
                                ),
                                ft.Container(
                                    content=self._flip_btn,
                                    right=40,
                                    alignment=ft.Alignment.CENTER_RIGHT,
                                ),
                            ],
                        ),
                        ft.Container(height=40),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.END,
                    spacing=0,
                ),
            ),
        ]

    async def show(self):
        """Initialize camera and show as overlay."""
        self._page.overlay.append(self)
        self.update()
        ok = await self.initialize()
        if not ok:
            self._handle_close(None)

    async def initialize(self) -> bool:
        try:
            self._camera = Camera()
            self._preview_container.content = self._camera
            self.update()

            await asyncio.sleep(0.5)

            self._cameras = await self._camera.get_available_cameras()
            if not self._cameras:
                return False

            if len(self._cameras) > 1:
                self._flip_btn.visible = True

            await self._camera.initialize(
                description=self._cameras[self._current_camera_index],
                resolution_preset=ResolutionPreset.HIGH,
            )
            self.update()
            return True
        except Exception as e:
            print(f"[Camera] Init error: {e}")
            return False

    async def _handle_flip(self, e):
        if not self._cameras or not self._camera:
            return

        self._current_camera_index = (self._current_camera_index + 1) % len(self._cameras)
        try:
            await self._camera.initialize(
                description=self._cameras[self._current_camera_index],
                resolution_preset=ResolutionPreset.HIGH,
            )
        except Exception as err:
            print(f"[Camera] Flip error: {err}")

    async def _handle_capture(self, e):
        if not self._camera:
            return

        try:
            self._capture_btn.scale = 0.9
            self.update()
            await asyncio.sleep(0.1)

            image_base64 = await self._camera.take_picture()
            self._capture_btn.scale = 1.0
            self.update()

            if image_base64:
                image_bytes = base64.b64decode(image_base64) if isinstance(image_base64, str) else image_base64

                self._on_capture(image_bytes, "image/jpeg", "photo.jpg")
                self._handle_close(None)
        except Exception as err:
            print(f"[Camera] Capture failed: {err}")

    def _handle_close(self, e):
        if self._camera:
            try:
                self._preview_container.content = None
                self.update()
            except Exception:
                pass
        try:
            self._page.overlay.remove(self)
            self._page.update()
        except (ValueError, Exception):
            pass
        self._on_close()
