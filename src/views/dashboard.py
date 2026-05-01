"""Dashboard — main hub with NavigationBar tabs."""

import flet as ft

from core.state import state
from core.theme import AppColors
from database.manager import db_manager


async def build_dashboard_view(page: ft.Page, navigate) -> ft.View:
    """Main dashboard with courses grid, XP bar, and quick actions."""

    ad_service = page.data.get("ad_service")
    courses = await db_manager.get_courses()

    # ── Header ───────────────────────────────────────────────
    def toggle_theme(e):
        page.theme_mode = (
            ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK
            else ft.ThemeMode.DARK
        )
        state.theme_mode = page.theme_mode
        page.update()

    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.AUTO_AWESOME, size=24, color=ft.Colors.WHITE),
                            width=40,
                            height=40,
                            border_radius=12,
                            gradient=ft.LinearGradient(
                                colors=[AppColors.PRIMARY, AppColors.TERTIARY],
                            ),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    f"Hey, {state.user_name or 'Student'} 👋",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    f"{state.level} • {state.xp_total} XP",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Row(
                    [
                        # Credits badge
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.BOLT, size=16, color=AppColors.ACCENT),
                                    ft.Text(
                                        str(state.credits_remaining),
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=AppColors.ACCENT,
                                    ),
                                ],
                                spacing=4,
                            ),
                            padding=ft.Padding(10, 6, 10, 6),
                            border_radius=20,
                            bgcolor=ft.Colors.SURFACE_CONTAINER,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.BRIGHTNESS_6,
                            icon_size=20,
                            on_click=toggle_theme,
                        ),
                    ],
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(20, 10, 20, 10),
    )

    # ── Streak + XP Progress ─────────────────────────────────
    progress_bar = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Text("🔥", size=18),
                                ft.Text(
                                    f"{state.current_streak} day streak",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                ),
                            ],
                            spacing=6,
                        ),
                        ft.Text(
                            f"Level: {state.level}",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ProgressBar(
                    value=state.get_level_progress(),
                    color=AppColors.PRIMARY,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    height=8,
                    border_radius=4,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding(20, 12, 20, 12),
        margin=ft.Margin(16, 0, 16, 0),
        border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    # ── Courses Grid ─────────────────────────────────────────
    courses_grid = ft.ResponsiveRow(spacing=12, run_spacing=12)

    if not courses:
        courses_grid.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.SCHOOL_OUTLINED, size=56, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "No courses yet",
                            size=18,
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(
                            "Create your first AI-powered course to start learning",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                col={"xs": 12},
                padding=40,
                alignment=ft.Alignment.CENTER,
            )
        )
    else:
        for i, course in enumerate(courses):
            color = AppColors.SUBJECT_COLORS[course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)]
            progress = course.get("progress_pct", 0.0)

            async def on_course_click(e, c=course):
                state.current_course = c
                await navigate("/modules")

            courses_grid.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.BOOK, size=28, color=ft.Colors.WHITE),
                                width=48,
                                height=48,
                                border_radius=14,
                                bgcolor=color,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Text(
                                course["subject"],
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                course["level"],
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.ProgressBar(
                                value=progress / 100 if progress else 0,
                                color=color,
                                bgcolor=ft.Colors.SURFACE_CONTAINER,
                                height=6,
                                border_radius=3,
                            ),
                            ft.Text(
                                f"{progress:.0f}% complete",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=6,
                    ),
                    padding=16,
                    border_radius=16,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    col={"xs": 6, "sm": 4, "md": 3},
                    on_click=lambda e, c=course: page.run_task(on_course_click, e, c),
                    ink=True,
                )
            )

    # ── Quick Actions ────────────────────────────────────────
    quick_actions = ft.Row(
        [
            _action_button(
                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                label="New Course",
                color=AppColors.PRIMARY,
                on_click=lambda e: page.run_task(navigate, "/create-course"),
            ),
            _action_button(
                icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                label="AI Tutor",
                color=AppColors.SECONDARY,
                on_click=lambda e: page.run_task(navigate, "/tutor"),
            ),
            _action_button(
                icon=ft.Icons.INSIGHTS,
                label="Progress",
                color=AppColors.ACCENT,
                on_click=lambda e: page.run_task(navigate, "/progress"),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
    )

    # ── Main content ─────────────────────────────────────────
    content_col = ft.Column(
        [
            header,
            progress_bar,
            ft.Container(height=8),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text("My Courses", size=18, weight=ft.FontWeight.BOLD),
                        ft.TextButton(
                            "See all",
                            on_click=lambda e: None,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.Padding(20, 8, 20, 0),
            ),
            ft.Container(
                content=courses_grid,
                padding=ft.Padding(16, 0, 16, 0),
                expand=True,
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    # ── Bottom Navigation ────────────────────────────────────
    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"),
            ft.NavigationBarDestination(icon=ft.Icons.SCHOOL_OUTLINED, selected_icon=ft.Icons.SCHOOL, label="Courses"),
            ft.NavigationBarDestination(icon=ft.Icons.ADD_CIRCLE_OUTLINE, selected_icon=ft.Icons.ADD_CIRCLE, label="Create"),
            ft.NavigationBarDestination(icon=ft.Icons.INSIGHTS_OUTLINED, selected_icon=ft.Icons.INSIGHTS, label="Progress"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Settings"),
        ],
        selected_index=0,
        on_change=lambda e: page.run_task(_nav_change, e),
    )

    async def _nav_change(e):
        idx = e.control.selected_index
        routes = ["/dashboard", "/dashboard", "/create-course", "/progress", "/settings"]
        if idx < len(routes) and routes[idx] != "/dashboard":
            await navigate(routes[idx])

    # ── Banner Ad (mobile only) ──────────────────────────────
    banner = ad_service.get_banner_ad() if ad_service else ft.Container()

    # ── Quick actions row ────────────────────────────────────
    actions_container = ft.Container(
        content=quick_actions,
        padding=ft.Padding(16, 12, 16, 12),
    )

    return ft.View(
        route="/dashboard",
        controls=[
            ft.SafeArea(
                ft.Column(
                    [
                        content_col,
                        actions_container,
                        banner,
                    ],
                    expand=True,
                    spacing=0,
                ),
                expand=True,
            ),
        ],
        navigation_bar=nav_bar,
        padding=0,
        spacing=0,
    )


def _action_button(icon, label, color, on_click) -> ft.Control:
    """Quick action button widget."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(icon, size=24, color=ft.Colors.WHITE),
                    width=48,
                    height=48,
                    border_radius=14,
                    bgcolor=color,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(label, size=12, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        on_click=on_click,
        ink=True,
    )
