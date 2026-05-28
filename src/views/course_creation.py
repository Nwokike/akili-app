import json
import random
import re

import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.credit_service import credit_service


def build_course_creation_view(page: ft.Page, navigate) -> ft.View:
    selected_subject = {"value": ""}
    status_text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    loading_ring = ft.ProgressRing(width=24, height=24, visible=False, stroke_width=2, color=AppColors.PRIMARY)

    subject_field = ft.TextField(
        hint_text="Search or type a subject...",
        border_radius=AppStyles.RADIUS,
        filled=True,
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        on_change=lambda e: _filter_subjects(e.control.value),
    )

    subject_list = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)
    all_items = []

    def _select(name: str):
        selected_subject["value"] = name
        subject_field.value = name
        for item in all_items:
            is_sel = item["name"] == name
            item["container"].bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT
            item["container"].border = ft.Border.all(2, AppColors.PRIMARY) if is_sel else None
        page.update()

    async def _load_suggestions():
        subject_list.controls.clear()
        all_items.clear()
        loading_ring.visible = True
        page.update()
        try:
            prompt = f"Suggest 10 subjects suitable for a {state.education_level} student from {state.country}. Return ONLY a JSON array of strings."
            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Return ONLY valid JSON array of subject names. No markdown.",
                use_tools=False,
            )
            content = response.get("content", "[]")
            try:
                content = re.sub(r"```[a-zA-Z]*", "", content)
                content = content.replace("```", "").strip()
                start = content.find("[")
                end = content.rfind("]")
                if start != -1 and end != -1:
                    content = content[start:end+1]
                subjects = json.loads(content)
            except Exception:
                subjects = []

            if isinstance(subjects, list):
                for subj in subjects[:10]:
                    if isinstance(subj, dict):
                        subj = subj.get("name") or subj.get("subject") or subj.get("title") or str(subj)
                    subj_str = str(subj)
                    text_ctrl = ft.Text(subj_str, size=14)
                    container = ft.Container(
                        content=ft.Row([text_ctrl]),
                        padding=ft.Padding(16, 12, 16, 12),
                        border_radius=AppStyles.RADIUS_SMALL,
                        on_click=lambda e, s=subj_str: _select(s),
                        ink=True,
                    )
                    all_items.append({"name": subj_str, "container": container, "text": text_ctrl})
                    subject_list.controls.append(container)
        except Exception:
            pass
        finally:
            loading_ring.visible = False
            page.update()

    def _filter_subjects(query: str):
        query = (query or "").lower().strip()
        selected_subject["value"] = subject_field.value.strip()
        for item in all_items:
            match = not query or query in item["name"].lower()
            item["container"].visible = match
        page.update()

    async def _generate(e=None):
        subject = subject_field.value.strip() if subject_field.value else selected_subject["value"]
        if not subject:
            status_text.value = "Please enter a subject"
            status_text.color = AppColors.ERROR
            page.update()
            return

        generate_btn.disabled = True
        loading_ring.visible = True
        status_text.color = ft.Colors.ON_SURFACE_VARIANT
        page.update()

        def _update_status(msg):
            status_text.value = msg
            page.update()

        try:
            ok = await credit_service.spend("course_create")
            if not ok:
                status_text.value = "Not enough credits"
                status_text.color = AppColors.ERROR
                return

            prompt = f"Generate curriculum for {subject} at {state.education_level} level for {state.country}. Tailor it to regional standards."

            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Return ONLY valid JSON with 'modules' list. Each module has 'title' and 'topics' list. If you cannot find info, still try your best to return a JSON structure with general topics.",
                on_status=_update_status
            )

            content = response.get("content", "")
            curriculum = _extract_json(content)

            if curriculum and "modules" in curriculum:
                color_idx = random.randint(0, len(AppColors.SUBJECT_COLORS) - 1)
                course_id = await db_manager.add_course(
                    subject=subject,
                    level=state.education_level,
                    curriculum_json=json.dumps(curriculum),
                    color_index=color_idx,
                )
                for i, mod in enumerate(curriculum["modules"]):
                    await db_manager.add_module(
                        course_id=course_id,
                        title=mod["title"],
                        topics_json=json.dumps(mod.get("topics", [])),
                        order_num=i,
                        unlocked=1 if i == 0 else 0,
                    )
                await navigate("/dashboard")
            else:
                status_text.color = AppColors.ERROR
                if "I'm sorry" in content or "couldn't find" in content:
                    status_text.value = "AI couldn't find verified syllabus info for this subject."
                else:
                    status_text.value = "Failed to parse curriculum."
        except Exception as ex:
            status_text.value = f"Error: {str(ex)[:50]}"
        finally:
            generate_btn.disabled = False
            loading_ring.visible = False
            page.update()

    generate_btn = ft.FilledButton(
        "Generate My Path",
        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=AppColors.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
            padding=24,
        ),
        on_click=lambda e: page.run_task(_generate, e),
        width=float("inf"),
    )

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                ft.Text("New Course", size=18, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        padding=ft.Padding(4, 8, 16, 8),
    )

    page.run_task(_load_suggestions)

    return ft.View(
        route="/create-course",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(f"Subject for {state.education_level}?", size=24, weight=ft.FontWeight.BOLD),
                                        ft.Container(height=10),
                                        subject_field,
                                        ft.Container(
                                            content=subject_list,
                                            height=300,
                                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                            border_radius=AppStyles.RADIUS,
                                            padding=10,
                                        ),
                                        ft.Row([loading_ring, status_text], spacing=10),
                                        generate_btn,
                                    ],
                                    spacing=15,
                                    scroll=ft.ScrollMode.AUTO,
                                ),
                                padding=20,
                                expand=True,
                            ),
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
    )


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None
