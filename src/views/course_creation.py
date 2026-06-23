import json
import random
import re

import flet as ft

from core.ai_utils import extract_json_array, extract_json_object, validate_curriculum, validate_subject_list
from core.state import check_internet_connection, state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.credit_service import credit_service


def build_course_creation_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    selected_subject = {"value": ""}
    status_text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    loading_ring = ft.ProgressRing(width=24, height=24, visible=False, stroke_width=2, color=AppColors.PRIMARY)

    custom_subject_field = ft.TextField(
        label="Type Custom Subject",
        hint_text="e.g. Organic Chemistry, African History...",
        border_radius=AppStyles.RADIUS,
        filled=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        visible=False,
    )

    subject_list = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)
    all_items = []

    def _select(name: str):
        selected_subject["value"] = name
        if name == "Other":
            custom_subject_field.visible = True
        else:
            custom_subject_field.visible = False
            custom_subject_field.value = ""

        for item in all_items:
            is_sel = item["name"] == name
            item["container"].bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT
            item["container"].border = ft.Border.all(2, AppColors.PRIMARY) if is_sel else None
        page.update()

    async def _load_suggestions():
        from components.offline_retry import OfflineRetryWidget

        is_connected = await check_internet_connection()
        state.is_online = is_connected
        if not is_connected:
            body_container.content = OfflineRetryWidget(
                page,
                on_retry=_load_suggestions,
                message="Akili needs an active internet connection to suggest subjects.",
            )
            page.update()
            return

        body_container.content = form_layout
        page.update()

        subject_list.controls.clear()
        all_items.clear()
        loading_ring.visible = True
        page.update()
        try:
            try:
                prompt = f"Suggest 10 subjects suitable for a {state.education_level} student from {state.country}. Return ONLY a JSON array of strings."

                def val_subjects(text):
                    arr = extract_json_array(text)
                    if not arr:
                        return None
                    subjects = validate_subject_list(arr)
                    return subjects if subjects else None

                response = await ai_service.chat_with_healing(
                    messages=[{"role": "user", "content": prompt}],
                    validation_func=val_subjects,
                    system_prompt="Return ONLY valid JSON array of subject names. No markdown.",
                    use_tools=False,
                )
                parsed = response.get("parsed")
            except Exception as ex:
                parsed = None
                response = {"content": str(ex)}

            if isinstance(parsed, list) and parsed:
                for subj in parsed[:10]:
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

                # Append Other option
                other_text = ft.Text("Other (Type subject...)", size=14, color=AppColors.PRIMARY, weight=ft.FontWeight.BOLD)
                other_container = ft.Container(
                    content=ft.Row([other_text]),
                    padding=ft.Padding(16, 12, 16, 12),
                    border_radius=AppStyles.RADIUS_SMALL,
                    on_click=lambda e: _select("Other"),
                    ink=True,
                )
                all_items.append({"name": "Other", "container": other_container, "text": other_text})
                subject_list.controls.append(other_container)
            else:
                from components.offline_retry import OfflineRetryWidget

                err_msg = response.get("content", "Failed to load suggestions.") if response else "Failed to load suggestions."
                body_container.content = OfflineRetryWidget(page, on_retry=_load_suggestions, message=f"Failed to load suggestions: {err_msg}")
                page.update()
        finally:
            loading_ring.visible = False
            page.update()

    async def _generate(e=None):
        from components.offline_retry import OfflineRetryWidget

        is_connected = await check_internet_connection()
        state.is_online = is_connected
        if not is_connected:
            body_container.content = OfflineRetryWidget(
                page,
                on_retry=lambda: _generate(e),
                message="Akili needs an active internet connection to generate your learning path.",
            )
            page.update()
            return

        body_container.content = form_layout
        page.update()

        subject = custom_subject_field.value.strip() if selected_subject["value"] == "Other" else selected_subject["value"]

        if not subject:
            status_text.value = "Please select or type a subject"
            status_text.color = AppColors.ERROR
            page.update()
            return

        # ── Duplicate course check ──────────────────────────────────
        # Prevent the same subject + same class/level from being created twice.
        # A different level for the same subject is allowed (e.g. Biology SS1 vs SS2).
        existing = await db_manager.get_course_by_subject_level(subject, state.education_level)
        if existing:
            # Build a "you already have this course" panel with an Open button.
            async def _open_existing(_e=None):
                state.current_course = existing
                await navigate("/modules")

            existing_panel = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.LIBRARY_BOOKS_ROUNDED, size=56, color=AppColors.PRIMARY),
                        ft.Text("You already have this course", size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            f"You've already created “{existing['subject']}” for {existing['level']}. Open it to continue where you left off, or pick a different subject/level.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Row(
                            [
                                ft.FilledButton(
                                    "Open Existing",
                                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                    style=ft.ButtonStyle(
                                        bgcolor=AppColors.PRIMARY,
                                        color=ft.Colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                                    ),
                                    on_click=lambda e: page.run_task(_open_existing),
                                ),
                                ft.OutlinedButton(
                                    "Choose Another",
                                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                                    on_click=lambda e: page.run_task(navigate, "/dashboard"),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=12,
                        ),
                    ],
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=32,
                border_radius=AppStyles.RADIUS,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, AppColors.PRIMARY)),
                alignment=ft.Alignment.CENTER,
            )
            body_container.content = existing_panel
            page.update()
            return

        # Hide inputs and show the premium progress card
        suggestions_col.visible = False
        custom_subject_field.visible = False
        generate_btn.visible = False
        progress_card.visible = True
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
                # Restore inputs
                suggestions_col.visible = True
                if selected_subject["value"] == "Other":
                    custom_subject_field.visible = True
                generate_btn.visible = True
                progress_card.visible = False
                page.update()
                return

            prompt = (
                f"You are designing an official, high-quality curriculum for {subject} at {state.education_level} level "
                f"specifically tailored to standard curricula in {state.country}.\n\n"
                f"CRITICAL REQUIREMENTS:\n"
                f"1. Search the web specifically for the official curriculum documents and syllabus outlines "
                f"from reputable national or regional educational boards in {state.country} "
                f" for '{subject}'.\n"
                f"2. Ensure the modules are structured sequentially, covering all areas from foundational to advanced topics.\n"
                f"3. Return the result strictly as a JSON object containing a list of 'modules'. Each module "
                f"must have a 'title' (string) and a 'topics' list of strings (each topic must be highly detailed and specific, "
                f"e.g. 'Acid-Base Titration Techniques' rather than just 'Titration').\n\n"
                f"Format the final response strictly as a valid JSON object.\n\n"
                f"RESEARCH EFFICIENCY (quality-preserving):\n"
                f"- Do NOT keep searching after you have solid coverage — "
                f"re-reading the same site or guessing additional URLs does not improve the curriculum.\n"
                f"- Use the exact URLs returned by search_web. Do NOT guess or construct URLs (they 404).\n"
                f"- Once you have enough verified material, STOP researching and emit the final JSON immediately. "
                f"Do not preface it with any commentary, reasoning, or summary."
            )

            def val_curriculum(text):
                obj = extract_json_object(text)
                if not obj:
                    return None
                curr = validate_curriculum(obj)
                return curr if curr else None

            response = await ai_service.chat_with_healing(
                messages=[{"role": "user", "content": prompt}],
                validation_func=val_curriculum,
                system_prompt="Return ONLY valid JSON with 'modules' list. Each module has 'title' and 'topics' list. If you cannot find info, still try your best to return a JSON structure with general topics.",
                use_tools=True,
                on_status=_update_status,
            )

            curriculum = response.get("parsed")

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
                content = response.get("content", "")
                if "I'm sorry" in content or "couldn't find" in content:
                    status_text.value = "AI couldn't find verified syllabus info for this subject."
                else:
                    status_text.value = "Failed to parse curriculum."

                # Restore inputs since generation failed
                suggestions_col.visible = True
                if selected_subject["value"] == "Other":
                    custom_subject_field.visible = True
                generate_btn.visible = True
                progress_card.visible = False
        except Exception as ex:
            status_text.value = f"Error: {str(ex)[:50]}"
            # Restore inputs on exception
            suggestions_col.visible = True
            if selected_subject["value"] == "Other":
                custom_subject_field.visible = True
            generate_btn.visible = True
            progress_card.visible = False
        finally:
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

    suggestions_col = ft.Column(
        [
            ft.Text("Select a suggested subject below:", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(
                content=subject_list,
                height=260,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=AppStyles.RADIUS,
                padding=10,
            ),
        ],
        spacing=10,
    )

    progress_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.ProgressRing(width=28, height=28, stroke_width=3, color=AppColors.PRIMARY),
                        ft.Text("Designing Your Curriculum...", size=16, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Container(height=4),
                ft.Text(
                    "Akili is actively researching official exam boards and national curricula online to build a perfect study path for you.",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(
                    content=status_text,
                    padding=ft.Padding(12, 10, 12, 10),
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    border_radius=AppStyles.RADIUS_SMALL,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=24,
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, AppColors.PRIMARY)),
        visible=False,
    )

    form_layout = ft.Column(
        [
            ft.Text(f"Subject for {state.education_level}?", size=22, weight=ft.FontWeight.BOLD),
            suggestions_col,
            custom_subject_field,
            progress_card,
            generate_btn,
            ad_service.get_banner_ad() if ad_service else ft.Container(),
        ],
        spacing=15,
        scroll=ft.ScrollMode.AUTO,
    )

    body_container = ft.Container(
        content=form_layout,
        padding=20,
        expand=True,
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
                            body_container,
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
