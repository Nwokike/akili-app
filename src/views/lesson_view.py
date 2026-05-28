import json
import re

import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.credit_service import credit_service
from services.gamification import gamification_service


async def build_lesson_view(page: ft.Page, navigate) -> ft.View:
    module = state.current_module
    if not module:
        return ft.View(route="/lesson", controls=[ft.Text("No module selected")])

    course = state.current_course or {}
    topics = json.loads(module["topics_json"]) if module.get("topics_json") else []
    cached = module.get("lesson_cache")

    lesson_content = ft.Column(spacing=16, expand=True)
    loading_indicator = ft.Column(
        [
            ft.ProgressRing(width=40, height=40, stroke_width=3, color=AppColors.PRIMARY),
            ft.Text("Generating lesson...", size=14, weight=ft.FontWeight.W_500),
            ft.Text("Searching web for accurate content", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
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

        ok = await credit_service.spend("lesson_gen")
        if not ok:
            error_text.value = "⚠️ Not enough credits."
            error_text.visible = True
            page.update()
            return

        loading_indicator.visible = True
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
                f"- Aim for 800-1200 words"
            )

            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=f"You are Akili, a helpful AI tutor for {level} students.",
            )

            content = response.get("content", "")
            if content and not response.get("_error"):
                await db_manager.save_lesson(module["id"], content)
                _render_lesson(content)
                await gamification_service.award_xp("lesson_complete")
            else:
                error_text.value = "Failed to generate lesson"
                error_text.visible = True
        except Exception as ex:
            error_text.value = f"Error: {str(ex)[:50]}"
            error_text.visible = True
        finally:
            loading_indicator.visible = False
            page.update()

    def _render_lesson(content: str):
        content = re.sub(r"\$\$(.*?)\$\$", r"\1", content, flags=re.DOTALL)
        content = re.sub(r"\$(.*?)\$", r"\1", content)
        lesson_content.controls.clear()
        lesson_content.controls.append(
            ft.Markdown(
                content,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                expand=True,
            )
        )
        page.update()

    async def _mark_complete(e):
        await db_manager.complete_module(module["id"])
        page.snack_bar = ft.SnackBar(ft.Text("✅ Module completed!"), bgcolor=AppColors.SUCCESS)
        page.snack_bar.open = True
        await navigate("/modules")

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

    # ── Action Buttons (Minimalist) ───────────────────────────────
    actions = ft.Container(
        content=ft.Row(
            [
                ft.FilledButton(
                    "Practice Quiz",
                    icon=ft.Icons.QUIZ_ROUNDED,
                    on_click=lambda e: page.run_task(navigate, "/quiz"),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                    ),
                    expand=True,
                ),
                ft.OutlinedButton(
                    "Mark as Done",
                    icon=ft.Icons.DONE_ALL_ROUNDED,
                    on_click=lambda e: page.run_task(_mark_complete),
                    style=ft.ButtonStyle(
                        color=AppColors.SUCCESS,
                        shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                    ),
                    expand=True,
                ),
            ],
            spacing=12,
        ),
        padding=ft.Padding(20, 12, 20, 20),
        bgcolor=ft.Colors.SURFACE,
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
                            ft.Container(
                                content=ft.Column(
                                    [
                                        loading_indicator,
                                        error_text,
                                        lesson_content,
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    scroll=ft.ScrollMode.AUTO,
                                ),
                                padding=20,
                                expand=True,
                            ),
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
