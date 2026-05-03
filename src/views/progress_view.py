import flet as ft

from core.constants import LEVELS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.gamification import gamification_service


async def build_progress_view(page: ft.Page, navigate) -> ft.View:
    courses = await db_manager.get_courses()
    quiz_stats = await db_manager.get_quiz_stats()
    badges = await gamification_service.get_badges()
    earned = [b for b in badges if b["earned"]]

    progress = state.get_level_progress()
    next_level = ""
    for i, lvl in enumerate(LEVELS):
        if lvl["name"] == state.level and i + 1 < len(LEVELS):
            next_level = LEVELS[i + 1]["name"]
            break

    avg = quiz_stats.get("avg_score", 0)
    total_q = quiz_stats.get("total_attempts", 0)

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/dashboard"),
            ),
            ft.Text("Progress", size=18, weight=ft.FontWeight.BOLD),
        ], spacing=4),
        padding=ft.Padding(4, 8, 16, 8),
    )

    stats = ft.Row([
        _stat("XP", str(state.xp_total), AppColors.ACCENT),
        _stat("Streak", f"{state.current_streak}d", AppColors.ERROR),
        _stat("Courses", str(len(courses)), AppColors.PRIMARY),
    ], spacing=8)

    level_section = ft.Column([
        ft.Row([
            ft.Text(state.level, size=15, weight=ft.FontWeight.W_600),
            ft.Text(
                f"→ {next_level}" if next_level else "Max level",
                size=13, color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.ProgressBar(
            value=progress, color=AppColors.ACCENT,
            bgcolor=ft.Colors.SURFACE_CONTAINER, height=6,
            border_radius=3,
        ),
    ], spacing=8)

    quiz_section = ft.Row([
        ft.Column([
            ft.Text(
                f"{int(avg)}%", size=28, weight=ft.FontWeight.BOLD,
                color=AppColors.SUCCESS if avg >= 60 else AppColors.ERROR,
            ),
            ft.Text("Avg Score", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
        ft.Column([
            ft.Text(
                str(total_q), size=28,
                weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY,
            ),
            ft.Text("Quizzes", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
    ])

    badge_row = ft.Row(
        [
            ft.Container(
                content=ft.Column([
                    ft.Text(b["icon"], size=24),
                    ft.Text(b["name"], size=9, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                padding=8, border_radius=10, width=72, height=72,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                opacity=1.0 if b["earned"] else 0.3,
            )
            for b in badges
        ],
        wrap=True, spacing=8, run_spacing=8,
    )

    course_rows = ft.Column(spacing=0)
    for c in courses[:8]:
        pct = c.get("progress_pct", 0)
        course_rows.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(c["subject"], size=13, expand=True),
                    ft.Text(
                        f"{int(pct)}%", size=12,
                        weight=ft.FontWeight.BOLD,
                        color=AppColors.SUCCESS if pct >= 80 else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ]),
                padding=ft.Padding(0, 8, 0, 8),
            )
        )

    return ft.View(
        route="/progress",
        controls=[ft.SafeArea(
            ft.Column([
                header,
                ft.Container(
                    content=ft.Column([
                        stats,
                        ft.Divider(height=1, thickness=0.5),
                        level_section,
                        ft.Divider(height=1, thickness=0.5),
                        ft.Text("Quiz Performance", size=15, weight=ft.FontWeight.W_600),
                        quiz_section,
                        ft.Divider(height=1, thickness=0.5),
                        ft.Text(f"Badges ({len(earned)}/{len(badges)})", size=15, weight=ft.FontWeight.W_600),
                        badge_row,
                        ft.Divider(height=1, thickness=0.5),
                        ft.Text("Courses", size=15, weight=ft.FontWeight.W_600),
                        course_rows if courses else ft.Text(
                            "No courses yet", size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], spacing=16),
                    padding=ft.Padding(20, 8, 20, 20),
                    expand=True,
                ),
            ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )


def _stat(label: str, value: str, color: str) -> ft.Control:
    return ft.Container(
        content=ft.Column([
            ft.Text(value, size=20, weight=ft.FontWeight.BOLD, color=color),
            ft.Text(label, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        padding=12, border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        expand=True,
    )
