"""AI Tutor chat — text conversations with live status and real-time streaming."""

import flet as ft

from core.constants import AITaskType
from core.state import state
from core.theme import AppColors
from services.ai_service import ai_service
from services.credit_service import credit_service
from services.gamification import gamification_service


def build_tutor_chat_view(page: ft.Page, navigate) -> ft.View:

    chat_messages: list[dict] = []

    messages_col = ft.Column(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        auto_scroll=True,
    )
    input_field = ft.TextField(
        hint_text="Ask Akili anything...",
        border_radius=24,
        filled=True,
        expand=True,
        min_lines=1,
        max_lines=4,
        shift_enter=True,
        on_submit=lambda e: page.run_task(_send_message),
        text_size=14,
    )
    send_btn = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED,
        icon_color=AppColors.PRIMARY,
        on_click=lambda e: page.run_task(_send_message),
    )
    loading_indicator = ft.ProgressRing(width=20, height=20, visible=False, stroke_width=2)
    credit_badge = ft.Text(
        f"⚡ {state.credits_remaining}",
        size=13, weight=ft.FontWeight.BOLD, color=AppColors.ACCENT,
    )
    # Status text shown in chat during AI processing (searching, thinking)
    status_bubble = ft.Container(
        content=ft.Row(
            [
                ft.ProgressRing(width=14, height=14, stroke_width=2),
                ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, ref=None),
            ],
            spacing=8,
        ),
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

    # ── Send message ─────────────────────────────────────────
    async def _send_message(e=None):
        text = input_field.value.strip() if input_field.value else ""
        if not text:
            return

        ok = await credit_service.spend("tutor_question")
        if not ok:
            _add_system_msg("⚠️ No credits remaining. Resets at midnight.")
            page.update()
            return

        credit_badge.value = f"⚡ {state.credits_remaining}"
        input_field.value = ""

        # Remove welcome on first message
        if len(chat_messages) == 0 and messages_col.controls:
            messages_col.controls.clear()
            messages_col.controls.append(status_bubble)

        chat_messages.append({"role": "user", "content": text})
        _add_user_bubble(text)
        loading_indicator.visible = True
        send_btn.disabled = True
        _show_status("🧠 Thinking...")

        try:
            context = f"Student: {state.user_name or 'Student'}, Level: {state.education_level or 'unknown'}"
            
            full_response = ""
            md_ref = None

            # ── THE MAGIC: Real-time UI Streaming ──
            async for chunk in ai_service.chat_stream(
                messages=chat_messages,
                system_prompt=(
                    f"You are Akili, a friendly AI tutor. {context}. "
                    "Be encouraging, clear, and use examples. "
                    "Format with markdown for readability."
                ),
                search_query=text if len(text.split()) >= 3 else None,
                task_type=AITaskType.GENERAL,  # Use the new Routing Constant
                on_status=_show_status,
            ):
                # When the first chunk arrives, hide the "Thinking..." spinner and build the empty bubble
                if md_ref is None:
                    _hide_status()
                    md_ref = _add_streaming_ai_bubble()
                
                # Append the chunk and update the screen
                full_response += chunk
                md_ref.value = full_response
                page.update()

            if not full_response:
                if md_ref is None:
                    _hide_status()
                    md_ref = _add_streaming_ai_bubble()
                full_response = "Sorry, I couldn't generate a response."
                md_ref.value = full_response
                page.update()

            chat_messages.append({"role": "assistant", "content": full_response})
            await gamification_service.award_xp("tutor_question")

        except Exception as ex:
            _hide_status()
            _add_system_msg(f"⚠️ Error: {str(ex)[:100]}")

        finally:
            loading_indicator.visible = False
            send_btn.disabled = False
            page.update()

    # ── Bubble builders ──────────────────────────────────────
    def _add_user_bubble(text: str):
        messages_col.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Text(text, size=14, color=ft.Colors.WHITE, selectable=True),
                            padding=ft.Padding(14, 10, 14, 10),
                            border_radius=ft.BorderRadius(18, 18, 4, 18),
                            gradient=ft.LinearGradient(
                                colors=[AppColors.PRIMARY, AppColors.TERTIARY],
                            ),
                        ),
                    ],
                ),
                padding=ft.Padding(12, 2, 12, 2),
            )
        )

    def _add_streaming_ai_bubble() -> ft.Markdown:
        """Creates an empty AI bubble and returns the Markdown reference so we can stream text into it."""
        md_text = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.MONOKAI,
        )
        messages_col.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        md_text,
                        ft.Text("Akili", size=10, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                    ],
                    spacing=4,
                ),
                padding=ft.Padding(14, 10, 14, 10),
                border_radius=ft.BorderRadius(18, 18, 18, 4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
            )
        )
        page.update()
        return md_text

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

    # ── Welcome ──────────────────────────────────────────────
    welcome = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.AUTO_AWESOME, size=32, color=ft.Colors.WHITE),
                    width=56, height=56, border_radius=16,
                    gradient=ft.LinearGradient(colors=[AppColors.PRIMARY, AppColors.TERTIARY]),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text("Hi! I'm Akili 🧠", size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Your AI tutor. Ask me anything about your studies.",
                    size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER,
                ),
                ft.Row(
                    [
                        _chip("Explain photosynthesis", input_field, page, _send_message),
                        _chip("WAEC math tips", input_field, page, _send_message),
                    ],
                    wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=6,
                ),
                ft.Row(
                    [
                        _chip("Essay structure", input_field, page, _send_message),
                        _chip("Physics formulas", input_field, page, _send_message),
                    ],
                    wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=6,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12,
        ),
        padding=ft.Padding(20, 40, 20, 20),
        alignment=ft.Alignment.CENTER,
    )
    messages_col.controls.append(welcome)
    messages_col.controls.append(status_bubble)

    # ── Header ───────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                        ft.Container(
                            content=ft.Icon(ft.Icons.AUTO_AWESOME, size=18, color=ft.Colors.WHITE),
                            width=32, height=32, border_radius=10,
                            gradient=ft.LinearGradient(colors=[AppColors.PRIMARY, AppColors.TERTIARY]),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column([
                            ft.Text("Akili Tutor", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("AI-powered", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=0),
                    ],
                    spacing=8,
                ),
                ft.Row([credit_badge, loading_indicator], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(8, 8, 16, 8),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    input_bar = ft.Container(
        content=ft.Row([input_field, send_btn], spacing=4, vertical_alignment=ft.CrossAxisAlignment.END),
        padding=ft.Padding(12, 8, 8, 12),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    return ft.View(
        route="/tutor",
        controls=[ft.SafeArea(ft.Column([header, messages_col, input_bar], expand=True, spacing=0), expand=True)],
        padding=0, spacing=0,
    )


def _chip(text, input_field, page, send_fn):
    def on_tap(e):
        input_field.value = text
        page.run_task(send_fn)

    return ft.Container(
        content=ft.Text(text, size=12, color=AppColors.PRIMARY),
        padding=ft.Padding(12, 6, 12, 6),
        border_radius=16,
        border=ft.Border(
            left=ft.BorderSide(1, AppColors.PRIMARY), top=ft.BorderSide(1, AppColors.PRIMARY),
            right=ft.BorderSide(1, AppColors.PRIMARY), bottom=ft.BorderSide(1, AppColors.PRIMARY),
        ),
        on_click=on_tap, ink=True,
    )