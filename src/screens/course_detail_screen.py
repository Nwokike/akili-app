"""Course detail — module list, progress, mock-exam gate.

Ported from Akili v1's course_detail.py (the house standard):
progress ring, lock/complete states, assignment indicators, and the
mock-exam button that unlocks only when the last module is unlocked.
"""

from __future__ import annotations

import asyncio

import flet as ft

from components.empty_state import EmptyState
from components.module_card import ModuleCard
from core import tokens
from core.state import state as core_state
from core.theme import AppColors
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx


@ft.component
def CourseDetailScreen():
    """A course's modules and progress."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    course = app_state.current_course or {}
    course_id = course.get("id")
    _ = app_state.courses_version

    assignments, set_assignments = ft.use_state({})
    can_complete, set_can_complete = ft.use_state((True, 0))

    page = ft.context.page

    def _load():
        async def _run():
            if course_id is None:
                return
            await controller.load_modules(course_id)
            store = getattr(page, "_akili_course_store", None)
            if store is None:
                return
            mods = await store.get_modules(course_id)
            mapping = {}
            for m in mods:
                a = await store.get_module_assignment(m["id"])
                if a:
                    mapping[m["id"]] = a
            set_assignments(mapping)
            set_can_complete(await store.can_complete_course(course_id))

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    if not course:
        return EmptyState("No course selected", "Go back and pick a course.", icon=ft.Icons.SCHOOL_ROUNDED)

    modules = list(app_state.modules or [])
    pct = float(course.get("progress_pct", 0.0))
    all_unlocked = bool(modules) and bool(modules[-1].get("is_unlocked"))
    pending_count = can_complete[1]

    def _open_module(module):
        core_state.current_module = module
        controller.show_lesson(course, module)

    def _open_exam(e):
        controller.show_exam(course)

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Column(
                    controls=[
                        ft.Text(str(course.get("subject") or "Course"), size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                        ft.Text(str(course.get("level") or ""), size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=1,
                    expand=True,
                    tight=True,
                ),
            ],
            spacing=tokens.SPACE_XS,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Progress card ──
    progress_card = ft.Container(
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Your Progress", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{pct:.0f}%", size=tokens.FONT_HERO, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                    ],
                    spacing=0,
                ),
                ft.Stack(
                    controls=[
                        ft.ProgressRing(value=pct / 100, width=56, height=56, stroke_width=5, color=AppColors.PRIMARY),
                    ],
                    width=56,
                    height=56,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=tokens.SPACE_LG,
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
    )

    controls: list[ft.Control] = [progress_card, ft.Container(height=tokens.SPACE_MD)]

    if not can_complete[0] and pending_count > 0:
        controls.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ASSIGNMENT_LATE_ROUNDED, size=tokens.ICON_SM, color=AppColors.WARNING),
                        ft.Text(
                            f"{pending_count} assignment(s) pending — complete all to finish this course",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            expand=True,
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
                padding=tokens.SPACE_MD,
                border_radius=tokens.RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(0.08, AppColors.WARNING),
                margin=ft.Margin(0, 0, 0, tokens.SPACE_MD),
            )
        )

    if not modules:
        controls.append(EmptyState("No modules yet", "This course has no modules.", icon=ft.Icons.MENU_BOOK_ROUNDED))
    else:
        for i, module in enumerate(modules):
            controls.append(ModuleCard(module, i, assignments.get(module["id"]), on_tap=_open_module))
            controls.append(ft.Container(height=tokens.SPACE_SM))

    controls.append(ft.Container(height=tokens.SPACE_SM))
    if all_unlocked:
        controls.append(
            ft.FilledButton(
                "Take Mock Exam",
                icon=ft.Icons.ASSIGNMENT_ROUNDED,
                on_click=_open_exam,
                width=float("inf"),
                style=ft.ButtonStyle(
                    bgcolor=AppColors.ACCENT,
                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                    padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
                ),
            )
        )
    else:
        unlocked = sum(1 for m in modules if m.get("is_unlocked"))
        controls.append(
            ft.Column(
                controls=[
                    ft.FilledButton(
                        f"Mock Exam — Locked ({unlocked}/{len(modules)} modules)",
                        icon=ft.Icons.LOCK_ROUNDED,
                        disabled=True,
                        width=float("inf"),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD)),
                    ),
                    ft.Text(
                        f"Finish all {len(modules)} modules to unlock the mock exam.",
                        size=tokens.FONT_XS,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=tokens.SPACE_XS,
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                header,
                ft.Column(controls=controls, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True),
            ],
            spacing=0,
            expand=True,
        ),
        padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_LG),
        expand=True,
    )
