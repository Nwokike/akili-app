"""Course detail — module listing with unlock flow."""

import json

import flet as ft

from core.state import state
from core.theme import AppColors
from database.manager import db_manager


async def build_course_detail_view(page: ft.Page, navigate) -> ft.View:
    """Shows all modules for a course with lock/unlock state."""

    course = state.current_course
    if not course:
        return ft.View(
            route="/modules",
            controls=[ft.Text("No course selected")],
        )

    modules = await db_manager.get_modules(course["id"])
    color = AppColors.SUBJECT_COLORS[course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)]

    # ── Header ───────────────────────────────────────────────
    header = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK,
                            icon_color=ft.Colors.WHITE,
                            on_click=lambda e: page.run_task(navigate, "/dashboard"),
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    course["subject"],
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                ),
                                ft.Text(
                                    f"{course['level']} • {len(modules)} modules",
                                    size=13,
                                    color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=8,
                ),
                ft.ProgressBar(
                    value=(course.get("progress_pct", 0) or 0) / 100,
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
                    height=6,
                    border_radius=3,
                ),
                ft.Text(
                    f"{course.get('progress_pct', 0):.0f}% complete",
                    size=12,
                    color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                ),
            ],
            spacing=12,
        ),
        padding=ft.Padding(16, 16, 20, 20),
        gradient=ft.LinearGradient(
            colors=[color, AppColors.TERTIARY],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        border_radius=ft.BorderRadius(0, 0, 24, 24),
    )

    # ── Module list ──────────────────────────────────────────
    module_list = ft.Column(spacing=8, expand=True)

    for i, mod in enumerate(modules):
        is_locked = not mod["is_unlocked"]
        is_done = mod["is_completed"]
        topics = json.loads(mod["topics_json"]) if mod["topics_json"] else []

        # Status icon
        if is_done:
            status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppColors.SUCCESS, size=24)
        elif is_locked:
            status_icon = ft.Icon(ft.Icons.LOCK_OUTLINED, color=ft.Colors.ON_SURFACE_VARIANT, size=24)
        else:
            status_icon = ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED, color=color, size=24)

        async def on_module_tap(e, m=mod):
            if m["is_unlocked"]:
                state.current_module = m
                await navigate("/lesson")

        # Topic chips
        topic_row = ft.Row(
            [
                ft.Container(
                    content=ft.Text(t, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=ft.Padding(8, 3, 8, 3),
                    border_radius=8,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                )
                for t in topics[:3]
            ],
            spacing=4,
            wrap=True,
        )

        card = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Text(
                            str(i + 1),
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE if not is_locked else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        width=36,
                        height=36,
                        border_radius=10,
                        bgcolor=color if not is_locked else ft.Colors.SURFACE_CONTAINER,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                mod["title"],
                                size=14,
                                weight=ft.FontWeight.W_600,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                color=ft.Colors.ON_SURFACE if not is_locked else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            topic_row,
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    status_icon,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=14,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            opacity=0.5 if is_locked else 1.0,
            on_click=lambda e, m=mod: page.run_task(on_module_tap, e, m) if m["is_unlocked"] else None,
            ink=not is_locked,
        )

        module_list.controls.append(card)

    # ── Actions ──────────────────────────────────────────────
    actions = ft.Container(
        content=ft.Row(
            [
                ft.Button(
                    "AI Tutor",
                    icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                    on_click=lambda e: page.run_task(navigate, "/tutor"),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.SECONDARY,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
                ft.Button(
                    "Mock Exam",
                    icon=ft.Icons.QUIZ_OUTLINED,
                    on_click=lambda e: page.run_task(navigate, "/exam"),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.ACCENT,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
        padding=ft.Padding(16, 12, 16, 12),
    )

    return ft.View(
        route="/modules",
        controls=[
            ft.Column(
                [
                    header,
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Modules", size=18, weight=ft.FontWeight.BOLD),
                                module_list,
                            ],
                            spacing=12,
                        ),
                        padding=ft.Padding(16, 16, 16, 0),
                        expand=True,
                    ),
                    actions,
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=0,
            ),
        ],
        padding=0,
        spacing=0,
    )
