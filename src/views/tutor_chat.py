import flet as ft

from components.camera_viewfinder import CameraViewfinder
from components.input_bar import InputBar
from components.media_preview import MediaPreviewBar
from core.constants import AITaskType
from core.theme import AppColors
from services.ai_service import ai_service
from services.audio import AudioService
from services.credit_service import credit_service
from services.file_picker import FilePickerService
from services.gamification import gamification_service


def build_tutor_chat_view(page: ft.Page, navigate) -> ft.View:
    chat_messages: list[dict] = []
    pending_media: list[dict] = []

    messages_col = ft.Column(
        spacing=8, scroll=ft.ScrollMode.AUTO,
        expand=True, auto_scroll=True,
    )

    loading_indicator = ft.ProgressRing(
        width=20, height=20, visible=False, stroke_width=2,
    )

    status_bubble = ft.Container(
        content=ft.Row([
            ft.ProgressRing(width=14, height=14, stroke_width=2),
            ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=8),
        padding=ft.Padding(16, 8, 16, 8),
        visible=False,
    )
    status_text_ref = status_bubble.content.controls[1]

    def _show_status(msg):
        status_text_ref.value = msg
        status_bubble.visible = True
        page.update()

    def _hide_status():
        status_bubble.visible = False

    audio_service = AudioService(page)

    def _on_media_result(data: bytes, mime: str, filename: str):
        m_type = "image" if mime.startswith("image/") else "audio" if mime.startswith("audio/") else "file"
        pending_media.append({"type": m_type, "data": data, "mime": mime, "filename": filename})
        media_preview.set_media(pending_media)

    file_picker = FilePickerService(page, on_result=_on_media_result)

    def _open_camera():
        def close_camera():
            if viewfinder in page.overlay:
                page.overlay.remove(viewfinder)
            page.update()

        viewfinder = CameraViewfinder(page, on_capture=_on_media_result, on_close=close_camera)
        page.overlay.append(viewfinder)
        page.update()

        async def init_cam():
            success = await viewfinder.initialize()
            if not success:
                page.snack_bar = ft.SnackBar(ft.Text("Camera not available"))
                page.snack_bar.open = True
                close_camera()
        page.run_task(init_cam)

    async def _toggle_mic(stop=False):
        if stop or audio_service.is_recording:
            result = await audio_service.stop_recording()
            input_bar.set_recording_state(False)
            if result:
                data, mime = result
                pending_media.append({"type": "audio", "data": data, "mime": mime, "filename": "Voice Note.wav"})
                media_preview.set_media(pending_media)
        else:
            success = await audio_service.start_recording()
            if success:
                input_bar.set_recording_state(True)

    async def _send_message(text: str = ""):
        nonlocal pending_media
        media_to_send = None
        if pending_media:
            media_to_send = pending_media[0]
            pending_media.clear()
            media_preview.set_media([])

        if not text and not media_to_send:
            return

        ok = await credit_service.spend("tutor_question")
        if not ok:
            _add_system_msg("No credits remaining. Resets at midnight.")
            page.update()
            return

        if len(chat_messages) == 0 and messages_col.controls:
            messages_col.controls.clear()
            messages_col.controls.append(status_bubble)

        display_text = text
        if media_to_send:
            label = "📷 Image" if media_to_send["type"] == "image" else "🎤 Voice"
            display_text = f"{label}\n{text}".strip()

        chat_messages.append({"role": "user", "content": text})
        _add_user_bubble(display_text)

        loading_indicator.visible = True
        input_bar.set_disabled(True)
        _show_status("Thinking...")

        try:
            full_response = ""
            md_ref = None

            async for chunk in ai_service.chat_stream(
                messages=chat_messages,
                task_type=AITaskType.TEXT,
                media=media_to_send,
                on_status=_show_status,
            ):
                if md_ref is None:
                    _hide_status()
                    md_ref = _add_ai_bubble()

                full_response += chunk
                md_ref.value = full_response
                page.update()

            if not full_response:
                if md_ref is None:
                    _hide_status()
                    _add_system_msg("No response received from Akili.")
                page.update()

            chat_messages.append({"role": "assistant", "content": full_response})
            await gamification_service.award_xp("tutor_question")

        except Exception as ex:
            _hide_status()
            _add_system_msg(f"Error: {str(ex)[:100]}")
        finally:
            loading_indicator.visible = False
            input_bar.set_disabled(False)
            page.update()

    def _on_media_remove(item: dict):
        if item in pending_media:
            pending_media.remove(item)
        media_preview.set_media(pending_media)

    media_preview = MediaPreviewBar(on_remove=_on_media_remove)

    input_bar = InputBar(
        page=page,
        on_send=lambda text: page.run_task(_send_message, text),
        on_camera=_open_camera,
        on_mic=lambda stop=False: page.run_task(_toggle_mic, stop=stop),
        on_attach=lambda: page.run_task(file_picker.pick_image),
    )

    def _add_user_bubble(text: str):
        messages_col.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text(text, size=14, color=ft.Colors.WHITE, selectable=True),
                        padding=ft.Padding(14, 10, 14, 10),
                        border_radius=ft.BorderRadius(18, 18, 4, 18),
                        bgcolor=AppColors.PRIMARY,
                    ),
                ]),
                padding=ft.Padding(12, 2, 12, 2),
            )
        )

    def _add_ai_bubble() -> ft.Markdown:
        md = ft.Markdown(
            "", selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.MONOKAI,
        )
        messages_col.controls.append(
            ft.Container(
                content=md,
                padding=ft.Padding(14, 10, 14, 10),
                border_radius=ft.BorderRadius(18, 18, 18, 4),
            )
        )
        page.update()
        return md

    def _add_system_msg(text: str):
        messages_col.controls.append(
            ft.Container(
                content=ft.Text(
                    text, size=13, text_align=ft.TextAlign.CENTER,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.Padding(20, 8, 20, 8),
                alignment=ft.Alignment.CENTER,
            )
        )

    welcome = ft.Container(
        content=ft.Column([
            ft.Container(height=40),
            ft.Image(src="/icon.png", width=48, height=48),
            ft.Container(height=8),
            ft.Text(
                "Ask me anything, or snap a photo of your assignment.",
                size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=12),
            ft.Row([
                _chip("Explain photosynthesis", page, _send_message),
                _chip("Essay structure", page, _send_message),
            ], wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            ft.Row([
                _chip("Physics formulas", page, _send_message),
                _chip("Solve this equation", page, _send_message),
            ], wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=6),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        padding=ft.Padding(20, 20, 20, 20),
        alignment=ft.Alignment.CENTER,
    )
    messages_col.controls.append(welcome)
    messages_col.controls.append(status_bubble)

    header = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.run_task(navigate, "/dashboard"),
                ),
                ft.Image(src="/icon.png", width=28, height=28),
            ], spacing=8),
            ft.Row([loading_indicator], spacing=8),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding(4, 8, 16, 8),
    )

    return ft.View(
        route="/tutor",
        controls=[
            ft.SafeArea(
                ft.Column([
                    header,
                    messages_col,
                    media_preview,
                    input_bar,
                ], expand=True, spacing=0),
                expand=True,
            )
        ],
        padding=0, spacing=0,
    )


def _chip(text, page, send_fn):
    return ft.Container(
        content=ft.Text(text, size=12, color=AppColors.PRIMARY),
        padding=ft.Padding(12, 6, 12, 6),
        border_radius=16,
        border=ft.Border(
            left=ft.BorderSide(1, AppColors.PRIMARY),
            top=ft.BorderSide(1, AppColors.PRIMARY),
            right=ft.BorderSide(1, AppColors.PRIMARY),
            bottom=ft.BorderSide(1, AppColors.PRIMARY),
        ),
        on_click=lambda e: page.run_task(send_fn, text),
        ink=True,
    )