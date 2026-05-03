"""Lesson view — AI-generated lesson content with progress tracking."""

import json

import flet as ft

from core.state import state
from core.theme import AppColors
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
            ft.ProgressRing(width=40, height=40, stroke_width=3),
            ft.Text("Generating lesson...", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
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
            error_text.value = "⚠️ Not enough credits. Resets at midnight."
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
                f"- Use markdown formatting (headings, bullets, bold)\n"
                f"- Search the web for accurate, current information\n"
                f"- Aim for 800-1200 words\n"
                f"- End with a brief summary"
            )

            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    f"You are Akili, creating a lesson for a {level} student. "
                    f"Search the web for accurate curriculum content. "
                    f"Be thorough but clear. Use relatable examples."
                ),
            )

            content = response.get("content", "")
            if content and not response.get("_error"):
                # Cache in DB
                await db_manager.save_lesson(module["id"], content)
                _render_lesson(content)

                # XP
                await gamification_service.award_xp("lesson_complete")
            else:
                error_text.value = content or "Failed to generate lesson"
                error_text.visible = True

        except Exception as ex:
            error_text.value = f"⚠️ {str(ex)[:100]}"
            error_text.visible = True
        finally:
            loading_indicator.visible = False
            page.update()

    def _render_lesson(content: str):
        lesson_content.controls.clear()
        lesson_content.controls.append(
            ft.Markdown(
                content,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                code_theme=ft.MarkdownCodeTheme.MONOKAI,
            )
        )
        page.update()


    async def _mark_complete(e):
        await db_manager.complete_module(module["id"])


        if course.get("id"):
            all_modules = await db_manager.get_modules(course["id"])
            for i, m in enumerate(all_modules):
                if m["id"] == module["id"] and i + 1 < len(all_modules):
                    await db_manager.unlock_module(all_modules[i + 1]["id"])
                    break


            completed = sum(1 for m in all_modules if m["is_completed"])
            pct = (completed / len(all_modules) * 100) if all_modules else 0
            await db_manager.update_course_progress(course["id"], pct)

        page.snack_bar = ft.SnackBar(
            ft.Text("✅ Module completed! +10 XP", color=ft.Colors.WHITE),
            bgcolor=AppColors.SUCCESS,
        )
        page.snack_bar.open = True
        

        ad_service = page.data.get("ad_service")
        if ad_service:
            await ad_service.show_interstitial()
            
        await navigate("/modules")



    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.run_task(navigate, "/modules"),
                ),
                ft.Column(
                    [
                        ft.Text(
                            module["title"],
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            course.get("subject", ""),
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding(8, 8, 16, 8),
    )


    bottom = ft.Container(
        content=ft.Row(
            [
                ft.Button(
                    "Take Quiz",
                    icon=ft.Icons.QUIZ,
                    on_click=lambda e: page.run_task(navigate, "/quiz"),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.ACCENT,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
                ft.Button(
                    "Complete ✓",
                    icon=ft.Icons.CHECK,
                    on_click=lambda e: page.run_task(_mark_complete),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.SUCCESS,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
        padding=ft.Padding(16, 12, 16, 12),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )


    page.run_task(_generate_lesson)

    return ft.View(
        route="/lesson",
        controls=[
            ft.SafeArea(
                ft.Column(
                    [
                        header,
                        ft.Container(
                            content=ft.Column(
                                [loading_indicator, error_text, lesson_content],
                                spacing=8,
                            ),
                            padding=ft.Padding(16, 8, 16, 16),
                            expand=True,
                        ),
                        bottom,
                    ],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=0,
                ),
                expand=True,
            ),
        ],
        padding=0,
        spacing=0,
    )
