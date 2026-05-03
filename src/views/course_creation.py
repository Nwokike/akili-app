import json
import random
import re

import flet as ft

from core.constants import POPULAR_SUBJECTS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.ai_service import ai_service
from services.credit_service import credit_service
from services.gamification import gamification_service


def build_course_creation_view(page: ft.Page, navigate) -> ft.View:
    selected_subject = {"value": ""}
    status_text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    loading_ring = ft.ProgressRing(
        width=24, height=24, visible=False, stroke_width=2
    )

    subject_field = ft.TextField(
        hint_text="Type a subject or pick from below",
        border_radius=12, filled=True,
        prefix_icon=ft.Icons.SEARCH,
        text_size=15,
        on_change=lambda e: _filter_subjects(e.control.value),
    )

    subject_list = ft.Column(spacing=0)
    all_items = []

    def _select(name: str):
        selected_subject["value"] = name
        subject_field.value = name
        for item in all_items:
            item["container"].bgcolor = (
                AppColors.PRIMARY if item["name"] == name
                else ft.Colors.TRANSPARENT
            )
            item["text"].color = (
                ft.Colors.WHITE if item["name"] == name
                else ft.Colors.ON_SURFACE
            )
        page.update()

    for subj in POPULAR_SUBJECTS:
        text_ctrl = ft.Text(subj, size=14)
        container = ft.Container(
            content=ft.Row([text_ctrl], spacing=0),
            padding=ft.Padding(16, 12, 16, 12),
            border_radius=8,
            on_click=lambda e, s=subj: _select(s),
            ink=True,
        )
        all_items.append({"name": subj, "container": container, "text": text_ctrl})
        subject_list.controls.append(container)
        subject_list.controls.append(ft.Divider(height=1, thickness=0.3))

    def _filter_subjects(query: str):
        query = (query or "").lower().strip()
        selected_subject["value"] = subject_field.value.strip()
        for item in all_items:
            match = not query or query in item["name"].lower()
            item["container"].visible = match
        for _, item in enumerate(all_items):
            divider_idx = subject_list.controls.index(item["container"]) + 1
            if divider_idx < len(subject_list.controls):
                subject_list.controls[divider_idx].visible = item["container"].visible
        page.update()

    generate_btn = ft.FilledButton(
        "Generate Curriculum",
        icon=ft.Icons.AUTO_AWESOME,
        style=ft.ButtonStyle(
            bgcolor=AppColors.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(24, 14, 24, 14),
        ),
        on_click=lambda e: page.run_task(_generate),
        width=float("inf"),
    )

    async def _generate(e=None):
        subject = subject_field.value.strip() if subject_field.value else selected_subject["value"]
        if not subject:
            status_text.value = "Please type or select a subject"
            status_text.color = AppColors.ERROR
            page.update()
            return

        level = state.education_level or "Grade 10"

        ok = await credit_service.spend("course_create")
        if not ok:
            status_text.value = "Not enough credits. Resets at midnight."
            status_text.color = AppColors.ERROR
            page.update()
            return

        generate_btn.disabled = True
        loading_ring.visible = True
        status_text.value = f"Researching {subject}..."
        status_text.color = ft.Colors.ON_SURFACE_VARIANT
        page.update()

        def _on_status(msg):
            status_text.value = msg
            page.update()

        try:
            prompt = (
                f"Create a structured curriculum for {subject} at {level} level. "
                f"Based on the search results, create a comprehensive course outline. "
                f"Return ONLY a valid JSON object:\n"
                f'{{"subject": "{subject}", "level": "{level}", '
                f'"modules": ['
                f'{{"title": "Module 1: Topic Name", "topics": ["subtopic 1", "subtopic 2"]}}'
                f']}}\n'
                f"Include 6-10 modules covering the full syllabus. "
                f"Each module should have 2-5 specific topics. "
                f"Order from basic to advanced. Return ONLY the JSON."
            )

            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    "You are a curriculum designer. Create structured course outlines. "
                    "Return ONLY valid JSON. No markdown, no explanation."
                ),
                search_query=f"{subject} {level} curriculum syllabus topics",
                on_status=_on_status,
            )

            content = response.get("content", "")
            curriculum = _extract_json(content)

            if not curriculum or "modules" not in curriculum:
                status_text.value = "AI format error. Please try again."
                status_text.color = AppColors.ERROR
                page.update()
                return

            status_text.value = "Saving..."
            page.update()

            color_idx = random.randint(0, len(AppColors.SUBJECT_COLORS) - 1)
            course_id = await db_manager.add_course(
                subject=subject, level=level,
                curriculum_json=json.dumps(curriculum),
                color_index=color_idx,
            )

            for i, mod in enumerate(curriculum["modules"]):
                await db_manager.add_module(
                    course_id=course_id,
                    title=mod.get("title", f"Module {i + 1}"),
                    topics_json=json.dumps(mod.get("topics", [])),
                    order_num=i,
                    unlocked=1 if i == 0 else 0,
                )

            await gamification_service.award_xp("course_create")

            courses = await db_manager.get_courses()
            if courses:
                state.current_course = courses[0]
                await navigate("/modules")

        except Exception as ex:
            status_text.value = f"Error: {str(ex)[:80]}"
            status_text.color = AppColors.ERROR
        finally:
            generate_btn.disabled = False
            loading_ring.visible = False
            page.update()

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/dashboard"),
            ),
            ft.Text("New Course", size=18, weight=ft.FontWeight.BOLD),
        ], spacing=4),
        padding=ft.Padding(4, 8, 16, 0),
    )

    return ft.View(
        route="/create-course",
        controls=[ft.SafeArea(
            ft.Column([
                header,
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "What do you want to learn?",
                            size=20, weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            "Select a subject or type your own.",
                            size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Container(height=4),
                        subject_field,
                        ft.Container(
                            content=subject_list,
                            height=280,
                            border_radius=12,
                            bgcolor=ft.Colors.SURFACE_CONTAINER,
                        ),
                        ft.Container(height=8),
                        ft.Row(
                            [loading_ring, status_text],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Container(height=4),
                        generate_btn,
                    ], spacing=8, scroll=ft.ScrollMode.AUTO),
                    padding=ft.Padding(20, 8, 20, 20),
                    expand=True,
                ),
            ], expand=True, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )


def _extract_json(text: str) -> dict | None:
    if not text:
        return None

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None
