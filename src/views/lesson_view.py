import json
import logging
import re

import flet as ft

from components.rich_content import render_rich_content
from core.ai_utils import sanitize_lesson_content
from core.state import check_internet_connection, state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.assignment_service import generate_assignment
from services.credit_service import credit_service
from services.gamification import gamification_service

logger = logging.getLogger(__name__)


async def build_lesson_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    module = state.current_module
    if not module:
        return ft.View(route="/lesson", controls=[ft.Text("No module selected")])

    course = state.current_course or {}
    topics = json.loads(module["topics_json"]) if module.get("topics_json") else []
    cached = module.get("lesson_cache")

    lesson_content = ft.Column(spacing=16, expand=True)
    loading_status_text = ft.Text("Searching web for accurate content...", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    loading_indicator = ft.Column(
        [
            ft.ProgressRing(width=40, height=40, stroke_width=3, color=AppColors.PRIMARY),
            ft.Text("Generating lesson...", size=14, weight=ft.FontWeight.W_500),
            loading_status_text,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=False,
    )
    error_text = ft.Text("", visible=False, color=AppColors.ERROR, size=13)

    async def _generate_lesson():
        if cached:
            _render_lesson(cached)
            return

        from components.offline_retry import OfflineRetryWidget

        is_connected = await check_internet_connection()
        state.is_online = is_connected
        if not is_connected:
            body_container.content = OfflineRetryWidget(
                page,
                on_retry=_generate_lesson,
                message="Akili needs an active internet connection to generate this lesson.",
            )
            page.update()
            return

        body_container.content = normal_layout
        page.update()

        ok = await credit_service.spend("lesson_gen")
        if not ok:
            error_text.value = "⚠️ Not enough credits."
            error_text.visible = True
            page.update()
            return

        loading_status_text.value = "Searching web for accurate content..."
        loading_indicator.visible = True
        page.update()

        def _update_status(msg):
            loading_status_text.value = msg
            page.update()

        try:
            level = course.get("level", state.education_level or "Grade 10")
            subject = course.get("subject", "General")
            topic_list = ", ".join(topics) if topics else module["title"]

            prompt = (
                f"Create a comprehensive lesson for: {module['title']}\n"
                f"Subject: {subject}, Level: {level}\n"
                f"Topics to cover: {topic_list}\n\n"
                f"Requirements:\n"
                f"- Start with clear learning objectives\n"
                f"- Explain each concept step by step\n"
                f"- Use examples and analogies\n"
                f"- Include practice problems where relevant\n"
                f"- Use markdown formatting\n"
                f"- Aim for 800-1200 words\n"
                f"- FORMULA RENDERING CONSTRAINT: Do NOT use LaTeX syntax (like $, $$, \\frac, \\sqrt, etc.) for scientific/mathematical equations. "
                f"Instead, format all equations and formulas using standard Unicode characters, bold/italic text, and sub/superscripts "
                f"(e.g., use 'H₂O', 'x²', '±', '√', 'π', and italics for variables) so they render beautifully and natively in standard markdown.\n"
                f"- VIDEO RECOMMENDATION (OPTIONAL): If there are highly relevant educational YouTube videos, you MUST use the search_videos tool to find them. "
                f"Only recommend videos returned by the tool. Do NOT guess or construct YouTube URLs from memory — they will be broken. "
                f"If no good videos are found, omit this section entirely. "
                f"Format them at the very end of the lesson (just before the Notebook Checkpoint) "
                f"in a single-line markdown format: `[VIDEO]: Title - https://www.youtube.com/watch?v=VIDEO_ID` (Do not add extra characters around this line).\n"
                f"- END the lesson with a '📓 Notebook Checkpoint' section that lists 5-8 key points "
                f"the student should write down in their notebook. Frame it as: 'Write these in your "
                f"notebook — you will need them for your quiz and assignment.'"
            )

            try:
                response = await ai_service.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt=(
                        f"You are Akili, a helpful AI tutor for {level} students. "
                        "Output ONLY the lesson content in clean markdown. "
                        "Do NOT include any internal reasoning, planning notes, thought process, "
                        "word-count targets, structural outlines, or meta-instructions. "
                        "Begin directly with the lesson heading or learning objectives."
                    ),
                    on_status=_update_status,
                )
                content = sanitize_lesson_content(response.get("content", ""))
                is_error = response.get("_error", False)
            except Exception as ex:
                content = str(ex)
                is_error = True

            if content and not is_error:
                await db_manager.save_lesson(module["id"], content)
                _render_lesson(content)
                await gamification_service.award_xp("lesson_complete")

                # Auto-generate assignment for this module
                try:
                    a_id = await generate_assignment(
                        module=module,
                        course=course,
                        lesson_content=content,
                        on_status=_update_status,
                    )
                    if a_id:
                        page.snack_bar = ft.SnackBar(
                            ft.Text("📋 New assignment created!"),
                            bgcolor=AppColors.ACCENT,
                        )
                        page.snack_bar.open = True
                        page.update()
                except Exception as ex:
                    print(f"[Lesson] Assignment generation failed: {ex}")
            else:
                from components.offline_retry import OfflineRetryWidget

                loading_indicator.visible = False
                body_container.content = OfflineRetryWidget(page, on_retry=_generate_lesson, message=f"Lesson generation failed: {content[:150]}")
                page.update()
                return
        except Exception as ex:
            from components.offline_retry import OfflineRetryWidget

            loading_indicator.visible = False
            body_container.content = OfflineRetryWidget(page, on_retry=_generate_lesson, message=f"Lesson generation failed: {str(ex)[:150]}")
            page.update()
            return
        finally:
            loading_indicator.visible = False
            page.update()

    async def _play_video(url: str, title: str):
        """Navigate to the ImmersivePlayer natively."""
        logger.info("Playing lesson video: %s", title)
        page.data["playing_video_url"] = url
        page.data["playing_video_title"] = title
        if ad_service:
            await ad_service.show_interstitial()
        await navigate("/video_player")

    def _render_lesson(content: str):
        # Strip LaTeX
        content = re.sub(r"\$\$(.*?)\$\$", r"\1", content, flags=re.DOTALL)
        content = re.sub(r"\$(.*?)\$", r"\1", content)
        lesson_content.controls.clear()
        # Render rich content (markdown + images + inline video links, including [VIDEO]: cards inline)
        controls = render_rich_content(
            content=content,
            page=page,
            on_play_video=_play_video,
            show_images=True,
            show_videos=True,
        )
        lesson_content.controls.extend(controls)

        if ad_service:
            lesson_content.controls.append(ad_service.get_banner_ad())
        page.update()

    # Module completion is unlocked by passing the quiz (≥60%), not manually.

    # ── Notebook tip banner ───────────────────────────────────────
    notebook_tip = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=20, color=ft.Colors.AMBER_800),
                ft.Text(
                    "📓 Keep your notebook ready — take notes as you read. You'll need them for quizzes & assignments!",
                    size=12,
                    color=ft.Colors.AMBER_800,
                    expand=True,
                    max_lines=2,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding(16, 10, 16, 10),
        border_radius=AppStyles.RADIUS_SMALL,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER),
        margin=ft.Margin(20, 0, 20, 0),
    )

    # ── Header (Minimalist) ───────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    on_click=lambda e: page.run_task(navigate, "/modules"),
                ),
                ft.Column(
                    [
                        ft.Text(module["title"], size=18, weight=ft.FontWeight.BOLD, max_lines=1),
                        ft.Text(course.get("subject", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=0,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding(8, 8, 16, 8),
    )

    # ── Action Button ─────────────────────────────────────────────
    actions = ft.Container(
        content=ft.FilledButton(
            "Take Quiz",
            icon=ft.Icons.QUIZ_ROUNDED,
            on_click=lambda e: page.run_task(navigate, "/quiz"),
            style=ft.ButtonStyle(
                bgcolor=AppColors.PRIMARY,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
            ),
            width=float("inf"),
        ),
        padding=ft.Padding(20, 12, 20, 20),
        bgcolor=ft.Colors.SURFACE,
    )

    normal_layout = ft.Column(
        [
            loading_indicator,
            error_text,
            lesson_content,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
    )

    body_container = ft.Container(
        content=normal_layout,
        padding=20,
        expand=True,
    )

    page.run_task(_generate_lesson)

    return ft.View(
        route="/lesson",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            notebook_tip,
                            body_container,
                            actions,
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
