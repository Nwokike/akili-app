import flet as ft

from components.camera_viewfinder import CameraViewfinder
from components.input_bar import InputBar
from components.media_preview import MediaPreviewBar
from core.constants import AITaskType
from core.state import state
from core.theme import AppColors, AppStyles
from services.ai_service import ai_service
from services.audio import AudioService
from services.credit_service import credit_service
from services.file_picker import FilePickerService
from services.gamification import gamification_service


def build_tutor_chat_view(page: ft.Page, navigate) -> ft.View:
    chat_messages: list[dict] = []
    pending_media: list[dict] = []

    messages_col = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, expand=True, auto_scroll=True)

    messages_container = ft.Container(content=messages_col, padding=ft.Padding(20, 10, 20, 10), expand=True)

    # ── Header ────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                        ft.Image(src="/icon.png", width=32, height=32),
                    ],
                    spacing=12,
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=14, color=AppColors.ACCENT),
                                    ft.Text(f"{state.credits_remaining}", size=12, weight=ft.FontWeight.W_600),
                                ],
                                spacing=4,
                            ),
                            padding=ft.Padding(12, 6, 12, 6),
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                            border_radius=AppStyles.RADIUS_SMALL,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(8, 8, 20, 8),
    )

    audio_service = AudioService(page)

    def _on_media_result(data: bytes, mime: str, filename: str):
        m_type = "image" if mime.startswith("image/") else "audio" if mime.startswith("audio/") else "file"
        pending_media.append({"type": m_type, "data": data, "mime": mime, "filename": filename})
        media_preview.set_media(pending_media)

    file_picker = FilePickerService(page, on_result=_on_media_result)

    async def _on_send(text: str):
        if not text.strip() and not pending_media:
            return

        ok = await credit_service.spend("tutor_question")
        if not ok:
            page.snack_bar = ft.SnackBar(ft.Text("Not enough credits"), bgcolor=ft.Colors.ERROR)
            page.snack_bar.open = True
            page.update()
            return

        # Pass media to AI service separately (not in messages dict to avoid bytes serialization)
        media_to_process = list(pending_media)
        pending_media.clear()
        media_preview.set_media([])

        user_msg = {"role": "user", "content": text}
        chat_messages.append(user_msg)
        _render_chat()

        msg_id = len(chat_messages)
        chat_messages.append({"role": "assistant", "content": "Thinking...", "id": msg_id})
        _render_chat()

        try:
            response = await ai_service.chat(
                messages=chat_messages[:-1],
                system_prompt=f"You are Akili, a helpful AI tutor for {state.education_level or 'Grade 10'} students. Be concise, encouraging, and clear.",
                task_type=AITaskType.TEXT,
                media=media_to_process[0] if media_to_process else None,
            )
            chat_messages[msg_id]["content"] = response.get("content", "Sorry, I encountered an error.")
            if not response.get("_error"):
                await gamification_service.award_xp("tutor_question")
        except Exception as e:
            chat_messages[msg_id]["content"] = f"Error: {str(e)}"

        _render_chat()

    async def _handle_mic(stop: bool = False):
        if not stop:
            await audio_service.start_recording()
            return

        result = await audio_service.stop_recording()
        if not result:
            return

        data, mime = result
        page.snack_bar = ft.SnackBar(ft.Text("Transcribing..."), bgcolor=AppColors.PRIMARY)
        page.snack_bar.open = True
        page.update()

        transcript = await ai_service.transcribe_audio(data, mime)
        if transcript:
            input_bar.text_field.value = transcript
            input_bar.text_field.update()

    def _render_chat():
        messages_col.controls.clear()
        for msg in chat_messages:
            is_user = msg["role"] == "user"

            # Simplified bubbles
            bubble = ft.Container(
                content=ft.Column(
                    [
                        ft.Markdown(
                            msg["content"],
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        )
                        if not is_user
                        else ft.Text(msg["content"], size=15),
                    ],
                    tight=True,
                ),
                padding=16,
                border_radius=ft.BorderRadius(
                    top_left=16,
                    top_right=16,
                    bottom_left=4 if is_user else 16,
                    bottom_right=16 if is_user else 4,
                ),
                bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_user else ft.Colors.SURFACE_CONTAINER_HIGHEST,
                alignment=ft.Alignment.CENTER_RIGHT if is_user else ft.Alignment.CENTER_LEFT,
                width=(page.width or 400) * 0.75,
            )

            row = ft.Row(
                [bubble],
                alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
            )
            messages_col.controls.append(row)
        page.update()

    async def _open_camera(e=None):
        camera = CameraViewfinder(page, _on_media_result, lambda: None)
        page.overlay.append(camera)
        page.update()
        ok = await camera.initialize()
        if not ok:
            page.overlay.remove(camera)
            page.update()

    media_preview = MediaPreviewBar(on_remove=lambda item: pending_media.remove(item))

    input_bar = InputBar(
        page=page,
        on_send=_on_send,
        on_camera=lambda: page.run_task(_open_camera),
        on_mic=lambda stop=False: page.run_task(_handle_mic, stop),
        on_attach=lambda: page.run_task(file_picker.pick_image),
    )

    return ft.View(
        route="/tutor",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            messages_container,
                            media_preview,
                            input_bar,
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
        spacing=0,
    )
