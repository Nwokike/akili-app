import json
import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager


async def build_course_detail_view(page: ft.Page, navigate) -> ft.View:
    course = state.current_course
    if not course:
        return ft.View(route="/modules", controls=[ft.Text("No course selected")])

    modules = await db_manager.get_modules(course["id"])
    color = AppColors.SUBJECT_COLORS[course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)]

    # ── Header (Minimalist) ───────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    on_click=lambda e: page.run_task(navigate, "/dashboard"),
                ),
                ft.Image(src="/icon.png", width=32, height=32),
                ft.Column([
                    ft.Text(course["subject"], size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{len(modules)} Modules", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=0, tight=True),
            ], spacing=12),
        ]),
        padding=ft.Padding(8, 8, 16, 8),
    )

    # ── Progress Summary (Minimalist) ─────────────────────────────
    progress_card = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("Your Progress", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(f"{course.get('progress_pct', 0):.0f}%", size=28, weight=ft.FontWeight.BOLD),
            ], spacing=2, expand=True),
            ft.Stack([
                ft.ProgressRing(width=48, height=48, value=course.get('progress_pct', 0)/100, stroke_width=6, color=color),
                ft.Container(
                    content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18, color=color),
                    alignment=ft.Alignment.CENTER,
                    width=48, height=48,
                )
            ])
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=24,
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    module_list = ft.Column(spacing=12, expand=True)

    for i, mod in enumerate(modules):
        is_locked = not mod["is_unlocked"]
        is_done = mod["is_completed"]

        async def on_module_tap(e, m=mod):
            if m["is_unlocked"]:
                state.current_module = m
                await navigate("/lesson")

        card = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.LOCK_ROUNDED if is_locked else ft.Icons.CHECK_CIRCLE_ROUNDED if is_done else ft.Icons.PLAY_CIRCLE_ROUNDED,
                        color=ft.Colors.ON_SURFACE_VARIANT if is_locked else AppColors.SUCCESS if is_done else AppColors.PRIMARY,
                        size=24,
                    ),
                    width=40, height=40,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column([
                    ft.Text(mod["title"], size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE if not is_locked else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(f"Module {i+1}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=2, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(16, 16, 16, 16),
            border_radius=AppStyles.RADIUS,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if not is_locked else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)) if is_locked else None,
            on_click=lambda e, m=mod: page.run_task(on_module_tap, e, m),
            disabled=is_locked,
        )
        module_list.controls.append(card)

    content = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                progress_card,
                ft.Container(height=10),
                ft.Text("Modules", size=18, weight=ft.FontWeight.BOLD),
                module_list,
            ], spacing=16),
            padding=20,
            expand=True,
        ),
    ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

    return ft.View(
        route="/modules",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=content,
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0, spacing=0,
    )
