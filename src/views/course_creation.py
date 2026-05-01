"""Course creation — AI curriculum wizard with subject picker + AI generation."""

import json
import random

import flet as ft

from core.constants import CREDIT_COSTS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.ai_service import ai_service
from services.credit_service import credit_service
from services.gamification import gamification_service


# Popular subjects for quick selection
SUBJECTS = [
    {"name": "Mathematics", "icon": ft.Icons.CALCULATE, "color": "#6366F1"},
    {"name": "English", "icon": ft.Icons.MENU_BOOK, "color": "#10B981"},
    {"name": "Physics", "icon": ft.Icons.BOLT, "color": "#F59E0B"},
    {"name": "Chemistry", "icon": ft.Icons.SCIENCE, "color": "#EF4444"},
    {"name": "Biology", "icon": ft.Icons.BIOTECH, "color": "#3B82F6"},
    {"name": "Economics", "icon": ft.Icons.TRENDING_UP, "color": "#8B5CF6"},
    {"name": "Government", "icon": ft.Icons.ACCOUNT_BALANCE, "color": "#EC4899"},
    {"name": "Literature", "icon": ft.Icons.AUTO_STORIES, "color": "#14B8A6"},
    {"name": "Computer Science", "icon": ft.Icons.COMPUTER, "color": "#6366F1"},
    {"name": "Geography", "icon": ft.Icons.PUBLIC, "color": "#10B981"},
    {"name": "History", "icon": ft.Icons.HISTORY_EDU, "color": "#F59E0B"},
    {"name": "Accounting", "icon": ft.Icons.RECEIPT_LONG, "color": "#EF4444"},
]


def build_course_creation_view(page: ft.Page, navigate) -> ft.View:
    """Subject picker → AI generates curriculum → save to DB."""

    selected_subject = {"value": ""}
    custom_input = ft.TextField(
        hint_text="Or type any subject...",
        border_radius=16,
        filled=True,
        prefix_icon=ft.Icons.SEARCH,
        text_size=14,
    )
    status_text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    generate_btn = ft.Button(
        "Generate Curriculum ✨",
        icon=ft.Icons.AUTO_AWESOME,
        style=ft.ButtonStyle(
            bgcolor=AppColors.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=16),
            padding=ft.Padding(24, 14, 24, 14),
        ),
        on_click=lambda e: page.run_task(_generate_curriculum),
        disabled=False,
    )
    loading_ring = ft.ProgressRing(width=24, height=24, visible=False, stroke_width=2)

    # Subject grid
    subject_grid = ft.ResponsiveRow(spacing=10, run_spacing=10)

    def _select_subject(name: str):
        selected_subject["value"] = name
        custom_input.value = name
        # Update visual selection
        for ctrl in subject_grid.controls:
            if hasattr(ctrl, "data"):
                is_selected = ctrl.data == name
                ctrl.border = ft.Border(
                    left=ft.BorderSide(2, AppColors.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
                    top=ft.BorderSide(2, AppColors.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
                    right=ft.BorderSide(2, AppColors.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
                    bottom=ft.BorderSide(2, AppColors.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
                )
        page.update()

    for subj in SUBJECTS:
        subject_grid.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Icon(subj["icon"], size=24, color=ft.Colors.WHITE),
                            width=44,
                            height=44,
                            border_radius=12,
                            bgcolor=subj["color"],
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text(subj["name"], size=11, text_align=ft.TextAlign.CENTER, max_lines=1),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                col={"xs": 3, "sm": 2},
                padding=10,
                border_radius=14,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border=ft.Border(
                    left=ft.BorderSide(2, ft.Colors.TRANSPARENT),
                    top=ft.BorderSide(2, ft.Colors.TRANSPARENT),
                    right=ft.BorderSide(2, ft.Colors.TRANSPARENT),
                    bottom=ft.BorderSide(2, ft.Colors.TRANSPARENT),
                ),
                on_click=lambda e, name=subj["name"]: _select_subject(name),
                data=subj["name"],
                ink=True,
            )
        )

    # ── Generate curriculum ──────────────────────────────────
    async def _generate_curriculum(e=None):
        subject = custom_input.value.strip() if custom_input.value else selected_subject["value"]
        if not subject:
            status_text.value = "⚠️ Pick or type a subject first"
            status_text.color = AppColors.ERROR
            page.update()
            return

        level = state.education_level or "SS 2"

        # Check credits
        cost = CREDIT_COSTS["course_create"]
        ok = await credit_service.spend("course_create")
        if not ok:
            status_text.value = "⚠️ Not enough credits. Resets at midnight."
            status_text.color = AppColors.ERROR
            page.update()
            return

        # Show loading
        generate_btn.disabled = True
        loading_ring.visible = True
        status_text.value = f"🔍 Researching {subject} curriculum for {level}..."
        status_text.color = ft.Colors.ON_SURFACE_VARIANT
        page.update()

        def _update_status(msg):
            status_text.value = msg
            page.update()

        try:
            prompt = (
                f"Create a structured curriculum for {subject} at {level} level. "
                f"Based on the search results provided, create a comprehensive course outline. "
                f"Return ONLY a valid JSON object with this exact structure:\n"
                f'{{"subject": "{subject}", "level": "{level}", '
                f'"modules": ['
                f'{{"title": "Module 1: Topic Name", "topics": ["subtopic 1", "subtopic 2", "subtopic 3"]}}, '
                f'{{"title": "Module 2: Topic Name", "topics": ["subtopic 1", "subtopic 2"]}} '
                f']}}\n'
                f"Include 6-10 modules covering the full syllabus. "
                f"Each module should have 2-5 specific topics. "
                f"Order modules from basic to advanced. "
                f"Return ONLY the JSON, no markdown, no explanation."
            )

            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    "You are a curriculum designer. Create structured course outlines. "
                    "Return ONLY valid JSON. No markdown code blocks, no explanation, just the JSON object."
                ),
                search_query=f"{subject} {level} curriculum syllabus topics Nigeria scheme of work",
                on_status=_update_status,
            )

            content = response.get("content", "")

            # Parse JSON from response (handle markdown code blocks)
            curriculum = _extract_json(content)

            if not curriculum or "modules" not in curriculum:
                print(f"[Course] JSON parse failed. Raw content:\n{content[:500]}")
                status_text.value = f"⚠️ AI format error. Raw: {content[:120]}..."
                status_text.color = AppColors.ERROR
                page.update()
                return

            # Save to DB
            status_text.value = "💾 Saving course..."
            page.update()

            color_idx = random.randint(0, len(AppColors.SUBJECT_COLORS) - 1)
            course_id = await db_manager.add_course(
                subject=subject,
                level=level,
                curriculum_json=json.dumps(curriculum),
                color_index=color_idx,
            )

            # Create modules
            for i, mod in enumerate(curriculum["modules"]):
                await db_manager.add_module(
                    course_id=course_id,
                    title=mod.get("title", f"Module {i + 1}"),
                    topics_json=json.dumps(mod.get("topics", [])),
                    order_num=i,
                    unlocked=1 if i == 0 else 0,  # First module unlocked
                )

            # XP reward
            await gamification_service.award_xp("course_create")

            status_text.value = f"✅ {subject} course created with {len(curriculum['modules'])} modules!"
            status_text.color = AppColors.SUCCESS
            page.update()

            # Navigate to course detail
            courses = await db_manager.get_courses()
            if courses:
                state.current_course = courses[0]
                await navigate("/modules")

        except Exception as ex:
            status_text.value = f"⚠️ Error: {str(ex)[:80]}"
            status_text.color = AppColors.ERROR

        finally:
            generate_btn.disabled = False
            loading_ring.visible = False
            page.update()

    # ── Header ───────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.run_task(navigate, "/dashboard"),
                ),
                ft.Text("Create Course", size=22, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.Text(
                    f"⚡ {state.credits_remaining}",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    color=AppColors.ACCENT,
                ),
            ],
        ),
        padding=ft.Padding(8, 8, 16, 8),
    )

    # ── Layout ───────────────────────────────────────────────
    content = ft.Column(
        [
            header,
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "What would you like to learn?",
                            size=18,
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            "Pick a subject or type your own. AI will build a full curriculum.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Container(height=4),
                        subject_grid,
                        ft.Container(height=8),
                        custom_input,
                        ft.Container(height=8),
                        ft.Row(
                            [generate_btn, loading_ring],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=12,
                        ),
                        status_text,
                    ],
                    spacing=8,
                ),
                padding=ft.Padding(16, 0, 16, 20),
                expand=True,
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        route="/create-course",
        controls=[ft.SafeArea(content, expand=True)],
        padding=0,
        spacing=0,
    )


def _extract_json(text: str) -> dict | None:
    """Extract JSON from AI response, handling markdown code blocks and think tags."""
    import re

    if not text:
        return None

    # Strip <think>...</think> blocks first
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None
