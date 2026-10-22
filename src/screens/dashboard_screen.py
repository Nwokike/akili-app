"""Dashboard screen — the courses list.

Ported from Akili v1's dashboard (the house standard: AppHeader +
virtualized list + EmptyState + banner ads + stats strip).
"""

from __future__ import annotations

import flet as ft

from components.banner_ad import build_banner_ad
from components.course_card import CourseCard
from components.empty_state import EmptyState
from components.stat_card import StatCard
from core import tokens
from core.constants import (
    LBL_CREATE_COURSE,
    LBL_EMPTY_COURSES,
    LBL_EMPTY_COURSES_DESC,
)
from core.theme import AppColors
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx


@ft.component
def DashboardScreen():
    """Home dashboard — courses list, stats, quick create."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    # Subscribe to the render token and load once.
    _ = app_state.courses_version

    def _load():
        import asyncio

        async def _run():
            await controller.load_courses()

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    def _open(course):
        controller.show_course(course)

    courses = list(app_state.courses or [])

    # ── Stats strip ──
    stats = ft.Container(
        content=ft.Row(
            controls=[
                StatCard("Level", app_state.level, AppColors.PRIMARY),
                StatCard("XP", app_state.xp_total),
                StatCard("Streak", app_state.current_streak),
                StatCard("Credits", app_state.credits_remaining, AppColors.ACCENT),
            ],
            spacing=tokens.SPACE_SM,
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
        padding=tokens.SPACE_MD,
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
    )

    # ── Greeting (v1 welcome section) ──
    greeting = ft.Container(
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Hello,", size=tokens.FONT_MD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(app_state.user_name or "Student", size=tokens.FONT_HERO, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=2,
                    expand=True,
                    tight=True,
                ),
                ft.Container(
                    content=ft.Text("🎓", size=tokens.FONT_XL),
                    width=60,
                    height=60,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=tokens.RADIUS_FULL,
                    alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(2, AppColors.PRIMARY),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_MD),
    )

    # ── Body ──
    body: list[ft.Control] = [greeting, stats, ft.Container(height=tokens.SPACE_MD)]

    body.append(
        ft.Row(
            controls=[
                ft.TextButton(
                    "History",
                    icon=ft.Icons.HISTORY_ROUNDED,
                    on_click=lambda e: controller.show_history(),
                ),
                ft.TextButton(
                    "Timetable",
                    icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
                    on_click=lambda e: controller.show_timetable(),
                ),
                ft.TextButton(
                    "Parents",
                    icon=ft.Icons.FAMILY_RESTROOM_ROUNDED,
                    on_click=lambda e: controller.show_parent_portal(),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            wrap=True,
        )
    )
    body.append(ft.Container(height=tokens.SPACE_SM))

    if not courses:
        body.append(
            EmptyState(
                LBL_EMPTY_COURSES,
                LBL_EMPTY_COURSES_DESC,
                LBL_CREATE_COURSE,
                on_action=lambda e: controller.show_create_course(),
                icon=ft.Icons.SCHOOL_ROUNDED,
            )
        )
    else:
        body.append(
            ft.Row(
                controls=[
                    ft.Text("Your Courses", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
                    ft.TextButton(
                        "New",
                        icon=ft.Icons.ADD_ROUNDED,
                        on_click=lambda e: controller.show_create_course(),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        body.append(
            ft.ListView(
                controls=[CourseCard(c, on_tap=_open) for c in courses],
                spacing=tokens.SPACE_MD,
                build_controls_on_demand=True,
                expand=True,
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Column(
                    controls=body,
                    spacing=0,
                    expand=True,
                    scroll=ft.ScrollMode.AUTO if not courses else None,
                ),
                build_banner_ad(ft.context.page),
            ],
            spacing=0,
            expand=True,
        ),
        padding=tokens.SPACE_LG,
        expand=True,
    )
