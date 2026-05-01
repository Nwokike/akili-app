"""Progress view — analytics dashboard with XP, streaks, quiz stats."""

import flet as ft

from core.constants import LEVELS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.gamification import gamification_service


async def build_progress_view(page: ft.Page, navigate) -> ft.View:
    # Load data
    courses = await db_manager.get_courses()
    quiz_stats = await db_manager.get_quiz_stats()
    badges = await gamification_service.get_badges()
    earned_badges = [b for b in badges if b["earned"]]

    # ── Stat cards ───────────────────────────────────────────
    def _stat(icon, label, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=28, color=color),
                ft.Text(str(value), size=22, weight=ft.FontWeight.BOLD),
                ft.Text(label, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            padding=16, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
            expand=True,
        )

    stats_row = ft.Row([
        _stat(ft.Icons.BOLT, "Total XP", state.xp_total, AppColors.ACCENT),
        _stat(ft.Icons.LOCAL_FIRE_DEPARTMENT, "Streak", f"{state.current_streak}🔥", AppColors.ERROR),
        _stat(ft.Icons.SCHOOL, "Courses", len(courses), AppColors.PRIMARY),
    ], spacing=8)

    # ── Level progress ───────────────────────────────────────
    progress = state.get_level_progress()
    current_level = state.level
    next_level = ""
    for i, lvl in enumerate(LEVELS):
        if lvl["name"] == current_level and i + 1 < len(LEVELS):
            next_level = LEVELS[i + 1]["name"]
            break

    level_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(f"Level: {current_level}", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"→ {next_level}" if next_level else "MAX", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ProgressBar(value=progress, color=AppColors.ACCENT, bgcolor=ft.Colors.SURFACE_CONTAINER),
            ft.Text(f"{int(progress*100)}% to next level", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=8),
        padding=20, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    # ── Quiz performance ─────────────────────────────────────
    avg_score = quiz_stats.get("avg_score", 0)
    total_quizzes = quiz_stats.get("total_attempts", 0)

    quiz_card = ft.Container(
        content=ft.Column([
            ft.Text("Quiz Performance", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Column([
                    ft.Text(f"{int(avg_score)}%", size=32, weight=ft.FontWeight.BOLD,
                            color=AppColors.SUCCESS if avg_score >= 60 else AppColors.ERROR),
                    ft.Text("Average Score", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
                ft.Column([
                    ft.Text(str(total_quizzes), size=32, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                    ft.Text("Quizzes Taken", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            ]),
        ], spacing=12),
        padding=20, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    # ── Badges ───────────────────────────────────────────────
    badge_chips = []
    for b in badges:
        badge_chips.append(
            ft.Container(
                content=ft.Column([
                    ft.Text(b["icon"], size=28),
                    ft.Text(b["name"], size=10, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                padding=10, border_radius=12, width=80, height=80,
                bgcolor=ft.Colors.SURFACE_CONTAINER if b["earned"] else ft.Colors.SURFACE_CONTAINER_HIGHEST,
                opacity=1.0 if b["earned"] else 0.4,
            )
        )

    badges_section = ft.Column([
        ft.Text(f"Badges ({len(earned_badges)}/{len(badges)})", size=16, weight=ft.FontWeight.BOLD),
        ft.Row(badge_chips, wrap=True, spacing=8, run_spacing=8),
    ], spacing=8)

    # ── Course progress ──────────────────────────────────────
    course_items = []
    for c in courses[:5]:
        pct = c.get("progress_pct", 0)
        course_items.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(c["subject"], size=14, expand=True),
                    ft.Text(f"{int(pct)}%", size=13, weight=ft.FontWeight.BOLD,
                            color=AppColors.SUCCESS if pct >= 80 else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(
                        content=ft.ProgressBar(value=pct/100, color=AppColors.PRIMARY, bgcolor=ft.Colors.SURFACE_CONTAINER),
                        width=80,
                    ),
                ]),
                padding=ft.Padding(12, 8, 12, 8),
            )
        )

    courses_section = ft.Column([
        ft.Text("Course Progress", size=16, weight=ft.FontWeight.BOLD),
        *(course_items if course_items else [ft.Text("No courses yet", size=13, color=ft.Colors.ON_SURFACE_VARIANT)]),
    ], spacing=8)

    # ── Layout ───────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: page.run_task(navigate, "/dashboard")),
            ft.Text("My Progress", size=18, weight=ft.FontWeight.BOLD),
        ], spacing=8),
        padding=ft.Padding(8, 8, 16, 8),
    )

    return ft.View(
        route="/progress",
        controls=[ft.SafeArea(
            ft.Column([
                header,
                ft.Container(
                    content=ft.Column([
                        stats_row, level_card, quiz_card, badges_section, courses_section,
                    ], spacing=16),
                    padding=ft.Padding(16, 8, 16, 16),
                    expand=True,
                ),
            ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )
