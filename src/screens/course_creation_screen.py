"""Course creation — pick a subject, generate a curriculum.

Ported from Akili v1's course_creation.py (the house standard):
AI-suggested subjects + a custom field, a duplicate guard, and a
curriculum generated with web research (15 credits).

One deliberate v2 improvement: credits are RESERVED, then committed on
success or rolled back on failure — v1 charged even when generation
failed.
"""

from __future__ import annotations

import asyncio
import random

import flet as ft

from components.course_card import SUBJECT_COLORS
from components.error_state import ErrorState, OfflineState
from components.loading_state import ProgressState
from core import tokens
from core.constants import COST_COURSE_CREATE
from core.state import state as core_state
from core.theme import AppColors
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

_OTHER = "Other"


@ft.component
def CourseCreationScreen():
    """The create-course flow."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    stage, set_stage = ft.use_state("loading")  # loading|ready|generating|duplicate|error|offline
    suggestions, set_suggestions = ft.use_state([])
    selected, set_selected = ft.use_state("")
    custom, set_custom = ft.use_state("")
    status, set_status = ft.use_state("")
    error, set_error = ft.use_state("")
    duplicate, set_duplicate = ft.use_state(None)

    page = ft.context.page
    level = app_state.education_level or "Grade 10"
    country = app_state.country or "Global"

    def _load():
        async def _run():
            from services import generation

            if not app_state.is_online:
                set_stage("offline")
                return
            set_stage("loading")
            try:
                subs = await generation.suggest_subjects(level, country)
                if subs:
                    set_suggestions(subs)
                    set_stage("ready")
                else:
                    set_error("Could not load subject suggestions.")
                    set_stage("error")
            except Exception as exc:
                set_error(str(exc)[:120])
                set_stage("error")

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    async def _generate():
        subject = (custom.strip() if selected == _OTHER else selected).strip()
        if not subject:
            set_error("Please select or type a subject")
            return
        set_error("")

        store = getattr(page, "_akili_course_store", None)
        if store is not None:
            existing = await store.get_course_by_subject_level(subject, level)
            if existing:
                set_duplicate(existing)
                set_stage("duplicate")
                return

        credits = app_state.credit_service
        if credits is None:
            set_error("AI credits are unavailable right now.")
            return
        tx = await credits.reserve(COST_COURSE_CREATE)
        if tx is None:
            set_error(f"Not enough credits — you need {COST_COURSE_CREATE}.")
            return

        set_stage("generating")
        set_status("Designing your curriculum…")
        try:
            from services import generation

            curriculum = await generation.generate_curriculum(subject, level, country, on_status=lambda s: set_status(s))
            if not curriculum:
                await credits.rollback(tx)
                set_error("Failed to parse the curriculum. Please try again.")
                set_stage("ready")
                return
            color_index = random.randint(0, len(SUBJECT_COLORS) - 1)
            course = await controller.create_course(subject, level, curriculum, color_index)
            await credits.commit(tx)
            page.run_task(_first_course_badge)
            controller.show_course(course)
        except Exception as exc:
            await credits.rollback(tx)
            set_error(f"Error: {str(exc)[:100]}")
            set_stage("ready")

    async def _first_course_badge():
        from services.gamification import get_gamification
        from services.share_service import offer_share_event

        gam = get_gamification()
        store = getattr(page, "_akili_course_store", None)
        if gam is None or store is None:
            return
        for event in await gam.check_earn_conditions(store):
            offer_share_event(page, event)

    def _open_existing():
        if duplicate:
            core_state.current_course = duplicate
            controller.show_course(duplicate)

    def _choose_another():
        set_duplicate(None)
        set_stage("ready")

    # ── Header ──
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Text("New Course", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Stages ──
    if stage == "offline":
        body = OfflineState(on_retry=lambda e: _load())
    elif stage == "loading":
        body = ProgressState(f"Finding subjects for {level}…")
    elif stage == "generating":
        body = ProgressState(status or "Designing your curriculum…", value=None)
    elif stage == "error":
        body = ErrorState("Couldn't load subjects", error, "Try again", lambda e: _load())
    elif stage == "duplicate":
        body = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=tokens.ICON_FEATURE, color=AppColors.WARNING),
                            ft.Text("You already have this course", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"You've already created “{duplicate.get('subject') if duplicate else ''}” for {level}.",
                                size=tokens.FONT_SM,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=tokens.SPACE_SM),
                            ft.FilledButton("Open Existing", on_click=lambda e: _open_existing()),
                            ft.TextButton("Choose Another", on_click=lambda e: _choose_another()),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_XS,
                    ),
                    padding=tokens.SPACE_XL,
                    border_radius=tokens.RADIUS_LG,
                    bgcolor=ft.Colors.with_opacity(0.06, AppColors.WARNING),
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
        )
    else:
        # ── Subject selection (ready) ──
        tiles: list[ft.Control] = []
        for name in suggestions:
            is_sel = selected == name
            tiles.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.CIRCLE_OUTLINED,
                                size=tokens.ICON_SM,
                                color=AppColors.PRIMARY if is_sel else ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE),
                            ),
                            ft.Text(name, size=tokens.FONT_MD, expand=True),
                        ],
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_sel else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(2 if is_sel else 1, AppColors.PRIMARY if is_sel else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ink=True,
                    on_click=lambda e, n=name: (set_selected(n), set_error("")),
                )
            )

        is_other = selected == _OTHER
        tiles.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.EDIT_ROUNDED if is_other else ft.Icons.ADD_ROUNDED,
                            size=tokens.ICON_SM,
                            color=AppColors.PRIMARY if is_other else ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE),
                        ),
                        ft.Text("Other (Type subject…)", size=tokens.FONT_MD, expand=True),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
                padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
                border_radius=tokens.RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_other else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(2 if is_other else 1, AppColors.PRIMARY if is_other else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ink=True,
                on_click=lambda e: (set_selected(_OTHER), set_error("")),
            )
        )

        controls: list[ft.Control] = [
            ft.Text(f"Subject for {level}?", size=tokens.FONT_XL, weight=ft.FontWeight.BOLD),
            ft.Text("Pick a subject to build your course.", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(height=tokens.SPACE_SM),
            ft.Container(
                content=ft.Column(controls=tiles, spacing=tokens.SPACE_SM, scroll=ft.ScrollMode.AUTO),
                height=260,
            ),
        ]

        if is_other:
            controls.append(
                ft.TextField(
                    label="Type Custom Subject",
                    hint_text="e.g. Organic Chemistry, African History…",
                    value=custom,
                    on_change=lambda e: set_custom(e.control.value),
                    border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD, side=ft.BorderSide(0, ft.Colors.TRANSPARENT)),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                )
            )

        if error:
            controls.append(ft.Text(error, color=AppColors.ERROR, size=tokens.FONT_SM))

        controls.append(ft.Container(height=tokens.SPACE_SM))
        controls.append(
            ft.FilledButton(
                f"Generate Curriculum ({COST_COURSE_CREATE} credits)",
                icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                on_click=lambda e: page.run_task(_generate),
                width=float("inf"),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                    padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
                ),
            )
        )

        body = ft.Column(controls=controls, spacing=tokens.SPACE_SM, scroll=ft.ScrollMode.AUTO, expand=True)

    return ft.Column(
        controls=[
            header,
            ft.Container(content=body, padding=tokens.SPACE_LG, expand=True),
        ],
        spacing=0,
        expand=True,
    )
