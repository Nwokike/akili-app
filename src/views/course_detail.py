import json

import flet as ft

from core.state import state
from core.theme import AppColors
from database.manager import db_manager


async def build_course_detail_view(page: ft.Page, navigate) -> ft.View:
    course = state.current_course
    if not course:
        return ft.View(route="/modules", controls=[ft.Text("No course selected")])

    modules = await db_manager.get_modules(course["id"])
    color = AppColors.SUBJECT_COLORS[course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)]

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/dashboard"),
            ),
            ft.Column([
                ft.Text(
                    course["subject"], size=18, weight=ft.FontWeight.BOLD,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    f"{course['level']} · {len(modules)} modules · {course.get('progress_pct', 0):.0f}%",
                    size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ], spacing=2, expand=True),
        ], spacing=4),
        padding=ft.Padding(4, 8, 16, 8),
    )

    module_list = ft.Column(spacing=0, expand=True)

    for i, mod in enumerate(modules):
        is_locked = not mod["is_unlocked"]
        is_done = mod["is_completed"]
        topics = json.loads(mod["topics_json"]) if mod["topics_json"] else []

        if is_done:
            status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppColors.SUCCESS, size=20)
        elif is_locked:
            status_icon = ft.Icon(ft.Icons.LOCK_OUTLINED, color=ft.Colors.ON_SURFACE_VARIANT, size=20)
        else:
            status_icon = ft.Container(
                width=8, height=8, border_radius=4, bgcolor=color,
            )

        async def on_module_tap(e, m=mod):
            if m["is_unlocked"]:
                state.current_module = m
                await navigate("/lesson")

        topic_text = ", ".join(topics[:3]) if topics else ""

        card = ft.Container(
            content=ft.Row([
                ft.Text(
                    str(i + 1), size=13, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.ON_SURFACE_VARIANT, width=24,
                ),
                ft.Column([
                    ft.Text(
                        mod["title"], size=14, weight=ft.FontWeight.W_600,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                        color=ft.Colors.ON_SURFACE if not is_locked else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        topic_text, size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    ) if topic_text else ft.Container(),
                ], spacing=2, expand=True),
                status_icon,
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(16, 14, 16, 14),
            opacity=0.5 if is_locked else 1.0,
            on_click=lambda e, m=mod: page.run_task(on_module_tap, e, m) if m["is_unlocked"] else None,
            ink=not is_locked,
        )
        module_list.controls.append(card)
        module_list.controls.append(ft.Divider(height=1, thickness=0.3))

    actions = ft.Container(
        content=ft.Row([
            ft.TextButton(
                "AI Tutor", icon=ft.Icons.CHAT_OUTLINED,
                on_click=lambda e: page.run_task(navigate, "/tutor"),
            ),
            ft.TextButton(
                "Mock Exam", icon=ft.Icons.QUIZ_OUTLINED,
                on_click=lambda e: page.run_task(navigate, "/exam"),
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
        padding=ft.Padding(16, 8, 16, 12),
    )

    return ft.View(
        route="/modules",
        controls=[
            ft.SafeArea(
                ft.Column([
                    header,
                    ft.Container(
                        content=module_list,
                        padding=ft.Padding(0, 0, 0, 0),
                        expand=True,
                    ),
                    actions,
                ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
                expand=True,
            ),
        ],
        padding=0, spacing=0,
    )
