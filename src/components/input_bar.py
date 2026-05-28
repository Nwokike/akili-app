import flet as ft

from components.recording_indicator import RecordingIndicator
from core.theme import AppColors


class InputBar(ft.Container):
    def __init__(self, page: ft.Page, on_send: callable, on_camera: callable, on_mic: callable, on_attach: callable):
        super().__init__()
        self._page = page
        self.on_send = on_send
        self.on_camera = on_camera
        self.on_mic = on_mic
        self.on_attach = on_attach
        self.is_recording = False

        self.text_field = ft.TextField(
            hint_text="Ask Akili or snap an assignment...",
            expand=True,
            border_radius=24,
            filled=True,
            min_lines=1,
            max_lines=4,
            shift_enter=True,
            on_submit=self._handle_send,
            text_size=14,
        )

        self.mic_btn = ft.IconButton(icon=ft.Icons.MIC_ROUNDED, icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=self._handle_mic_start)
        self.camera_btn = ft.IconButton(icon=ft.Icons.CAMERA_ALT_ROUNDED, icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.on_camera())
        self.attach_btn = ft.IconButton(icon=ft.Icons.ATTACH_FILE_ROUNDED, icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.on_attach())
        self.send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=AppColors.PRIMARY, on_click=self._handle_send)

        self.recording_indicator = RecordingIndicator(page=self._page, on_stop=self._handle_mic_stop, max_duration=60)

        self.normal_input = ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[self.attach_btn, self.camera_btn, self.text_field, self.mic_btn, self.send_btn],
        )

        self.content = ft.Column(spacing=4, controls=[ft.Stack([self.normal_input, self.recording_indicator])])
        self.padding = ft.Padding(8, 8, 8, 12)
        self.bgcolor = ft.Colors.SURFACE_CONTAINER

    def set_recording_state(self, is_recording: bool):
        self.is_recording = is_recording
        if is_recording:
            self.normal_input.visible = False
            self.recording_indicator.start()
        else:
            self.recording_indicator.stop()
            self.normal_input.visible = True
        self.update()

    def set_disabled(self, disabled: bool):
        self.text_field.disabled = disabled
        self.send_btn.disabled = disabled
        self.update()

    def _handle_send(self, e=None):
        text = self.text_field.value.strip() if self.text_field.value else ""
        self._page.run_task(self.on_send, text)
        self.text_field.value = ""
        self.update()

    def _handle_mic_start(self, e=None):
        self.set_recording_state(True)
        self.on_mic()

    def _handle_mic_stop(self):
        self.set_recording_state(False)
        self.on_mic(True)
