import flet as ft

from core.constants import LEVELS
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.gamification import gamification_service


async def build_progress_view(page: ft.Page, navigate) -> ft.View:
    courses = await db_manager.get_courses()
    quiz_stats = await db_manager.get_quiz_stats()
    badges = await gamification_service.get_badges()
    progress = state.get_level_progress()
    next_level = ""
    for i, lvl in enumerate(LEVELS):
        if lvl["name"] == state.level and i + 1 < len(LEVELS):
            next_level = LEVELS[i + 1]["name"]
            break

    avg = quiz_stats.get("avg_score", 0)
    total_q = quiz_stats.get("total_attempts", 0)

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                ft.Text("Progress", size=20, weight=ft.FontWeight.BOLD),
            ],
            spacing=4,
        ),
        padding=ft.Padding(4, 8, 16, 8),
    )

    def _stat(label, value, color):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(value, size=24, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=16,
            expand=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=AppStyles.RADIUS,
        )

    stats_row = ft.Row(
        [
            _stat("XP", f"{state.xp_total}", AppColors.ACCENT),
            _stat("Streak", f"{state.current_streak}d", AppColors.ERROR),
            _stat("Courses", f"{len(courses)}", AppColors.PRIMARY),
        ],
        spacing=10,
    )

    level_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(f"Level: {state.level}", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Next: {next_level}" if next_level else "", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ProgressBar(
                    value=progress,
                    color=AppColors.PRIMARY,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    height=8,
                    border_radius=4,
                ),
            ],
            spacing=10,
        ),
        padding=24,
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    quiz_card = ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            f"{int(avg)}%",
                            size=32,
                            weight=ft.FontWeight.BOLD,
                            color=AppColors.SUCCESS if avg >= 60 else AppColors.ERROR,
                        ),
                        ft.Text("Avg Score", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                ft.Column(
                    [
                        ft.Text(f"{total_q}", size=32, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                        ft.Text("Quizzes", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
            ]
        ),
        padding=24,
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    badge_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=12)
    for b in badges:
        opacity = 1.0 if b["earned"] else 0.2
        badge_row.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(b["icon"], size=32),
                        ft.Text(b["name"], size=10, weight=ft.FontWeight.W_500),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                width=80,
                padding=12,
                border_radius=AppStyles.RADIUS_SMALL,
                bgcolor=ft.Colors.with_opacity(0.05 * opacity, ft.Colors.ON_SURFACE),
                opacity=opacity,
            )
        )

    return ft.View(
        route="/progress",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            ft.Container(
                                content=ft.Column(
                                    [
                                        stats_row,
                                        level_card,
                                        ft.Text("Quiz Performance", size=18, weight=ft.FontWeight.BOLD),
                                        quiz_card,
                                        ft.Text("Achievements", size=18, weight=ft.FontWeight.BOLD),
                                        badge_row,
                                        ft.Container(height=20),
                                        ft.OutlinedButton(
                                            "View Detailed History",
                                            icon=ft.Icons.HISTORY_ROUNDED,
                                            on_click=lambda e: page.run_task(navigate, "/history"),
                                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS)),
                                            width=float("inf"),
                                        ),
                                    ],
                                    spacing=20,
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
        spacing=0,
    )
