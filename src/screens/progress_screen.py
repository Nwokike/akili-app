"""Progress screen — the XP/level/streak/badges dashboard.

Ported from Akili v1's progress_view.py:
stats row, level card with progress bar, quiz performance, badge row
(earned tap → share), share buttons, and the history link. Data loads on
mount (attempts + badges) and subscribes to the attempts token.
"""

from __future__ import annotations

import asyncio

import flet as ft

from components.banner_ad import build_banner_ad
from components.section_header import SectionHeader
from components.stat_card import StatCard
from core import tokens
from core.constants import (
    LBL_ACHIEVEMENTS,
    LBL_AVG_SCORE_LABEL,
    LBL_QUIZ_PERFORMANCE,
    LBL_QUIZZES_LABEL,
    LBL_SHARE_LEVEL,
    LBL_SHARE_STREAK,
    LBL_VIEW_HISTORY,
    LEVELS,
)
from core.theme import AppColors
from services.share_service import ShareType, show_share_sheet
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx


def _quiz_avg(attempts: list[dict]) -> tuple[float, int]:
    total = 0.0
    count = 0
    for a in attempts:
        marks = float(a.get("total") or 0)
        if marks <= 0:
            continue
        total += float(a.get("score") or 0) / marks * 100
        count += 1
    return ((total / count) if count else 0.0, count)


@ft.component
def ProgressScreen():
    """Progress dashboard — XP, level, streaks, quiz stats, badges."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    attempts, set_attempts = ft.use_state([])
    badges, set_badges = ft.use_state([])

    _ = app_state.attempts_version
    page = ft.context.page

    def _load():
        async def _run():
            await controller.load_attempts()
            set_attempts(list(app_state.quiz_attempts or []))
            try:
                from services.gamification import get_gamification

                gam = get_gamification()
                if gam is not None:
                    set_badges(await gam.get_badges())
            except Exception:
                pass

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    avg, total_q = _quiz_avg(attempts)
    courses = list(app_state.courses or [])

    # Next level name (v1 parity).
    next_level = ""
    for i, lvl in enumerate(LEVELS):
        if lvl["name"] == app_state.level and i + 1 < len(LEVELS):
            next_level = LEVELS[i + 1]["name"]
            break

    # ── Badges ──
    def _share_badge(badge: dict):
        show_share_sheet(
            page,
            ShareType.BADGE,
            {
                "badge_name": badge.get("name", ""),
                "badge_icon": badge.get("icon", "🏅"),
                "badge_desc": badge.get("desc", ""),
                "name": app_state.user_name,
            },
        )

    badge_tiles: list[ft.Control] = []
    for badge in badges:
        earned = bool(badge.get("earned"))
        opacity = 1.0 if earned else 0.2

        badge_tiles.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(badge.get("icon", "🏅"), size=32),
                        ft.Text(
                            str(badge.get("name", "")),
                            size=10,
                            weight=ft.FontWeight.W_500,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_XS,
                    tight=True,
                ),
                width=80,
                padding=tokens.SPACE_SM,
                border_radius=tokens.RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(0.05 * opacity + 0.02, ft.Colors.ON_SURFACE),
                opacity=opacity,
                tooltip=(str(badge.get("desc") or "") + (" — Tap to share!" if earned else "")),
                ink=earned,
                on_click=(lambda e, b=badge: _share_badge(b)) if earned else None,
            )
        )

    # ── Sections ──
    sections: list[ft.Control] = [
        ft.Container(
            content=ft.Row(
                controls=[
                    StatCard("XP", app_state.xp_total, AppColors.ACCENT),
                    StatCard("Streak", f"{app_state.current_streak}d", AppColors.ERROR),
                    StatCard("Courses", len(courses), AppColors.PRIMARY),
                ],
                spacing=tokens.SPACE_SM,
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            ),
            padding=tokens.SPACE_MD,
            border_radius=tokens.RADIUS_LG,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
        ),
        ft.Container(height=tokens.SPACE_MD),
        SectionHeader("Level"),
        ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(f"Level: {app_state.level}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Next: {next_level}" if next_level else "Max level reached!", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=tokens.SPACE_XS),
                    ft.ProgressBar(
                        value=app_state.get_level_progress(),
                        color=AppColors.PRIMARY,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                        height=8,
                        border_radius=4,
                    ),
                ],
                spacing=tokens.SPACE_XS,
                tight=True,
            ),
            padding=tokens.SPACE_LG,
            border_radius=tokens.RADIUS_LG,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
        ),
        ft.Container(height=tokens.SPACE_MD),
        SectionHeader(LBL_QUIZ_PERFORMANCE),
        ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                f"{avg:.0f}%",
                                size=34,
                                weight=ft.FontWeight.BOLD,
                                color=AppColors.SUCCESS if avg >= 60 else AppColors.ERROR,
                            ),
                            ft.Text(LBL_AVG_SCORE_LABEL, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
                    ),
                    ft.VerticalDivider(),
                    ft.Column(
                        controls=[
                            ft.Text(f"{total_q}", size=34, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                            ft.Text(LBL_QUIZZES_LABEL, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=tokens.SPACE_LG,
            border_radius=tokens.RADIUS_LG,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
        ),
        ft.Container(height=tokens.SPACE_MD),
        SectionHeader(LBL_ACHIEVEMENTS),
        (ft.Row(controls=badge_tiles, spacing=tokens.SPACE_SM, scroll=ft.ScrollMode.AUTO) if badge_tiles else ft.Text("No badges yet — keep learning!", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT)),
        ft.Container(height=tokens.SPACE_MD),
        ft.Row(
            controls=[
                ft.TextButton(
                    LBL_SHARE_STREAK,
                    icon=ft.Icons.SHARE_ROUNDED,
                    on_click=lambda e: show_share_sheet(page, ShareType.STREAK, {"streak": app_state.current_streak, "name": app_state.user_name}),
                ),
                ft.TextButton(
                    LBL_SHARE_LEVEL,
                    icon=ft.Icons.SHARE_ROUNDED,
                    on_click=lambda e: show_share_sheet(
                        page,
                        ShareType.LEVEL_UP,
                        {
                            "level": app_state.level,
                            "icon": next((lvl.get("icon", "🎓") for lvl in LEVELS if lvl["name"] == app_state.level), "🎓"),
                            "xp": app_state.xp_total,
                            "name": app_state.user_name,
                        },
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
        ft.Container(height=tokens.SPACE_SM),
        ft.OutlinedButton(
            LBL_VIEW_HISTORY,
            icon=ft.Icons.HISTORY_ROUNDED,
            on_click=lambda e: controller.show_history(),
            width=float("inf"),
        ),
        ft.Container(height=tokens.SPACE_SM),
    ]

    return ft.Column(
        controls=[
            ft.ListView(controls=sections, spacing=0, expand=True, padding=tokens.SPACE_LG),
            build_banner_ad(page),
        ],
        spacing=0,
        expand=True,
    )
