"""Parent portal — a PIN-gated student overview.

Derived live from the course store + gamification (no parent table, v1
precedent). The PIN is changeable and persisted (v1 hardcoded 1234).
"""

from __future__ import annotations

import asyncio

import flet as ft

from components.banner_ad import build_banner_ad
from components.empty_state import EmptyState
from components.section_header import SectionHeader
from components.stat_card import StatCard
from core import tokens
from core.constants import (
    DEFAULT_PARENT_PIN,
    LBL_PARENT_AVG_SCORE,
    LBL_PARENT_CHANGE_PIN,
    LBL_PARENT_CONFIRM_PIN,
    LBL_PARENT_LAST_ACTIVE,
    LBL_PARENT_LOCK_DESC,
    LBL_PARENT_LOCK_TITLE,
    LBL_PARENT_NEW_PIN,
    LBL_PARENT_PIN_CHANGED,
    LBL_PARENT_PIN_MISMATCH,
    LBL_PARENT_PIN_SHORT,
    LBL_PARENT_STUDENT_OVERVIEW,
    LBL_PARENT_TOTAL_QUIZZES,
    LBL_PARENT_UNLOCK,
    LBL_PARENT_WRONG_PIN,
    STORAGE_PARENT_PIN,
)
from core.theme import AppColors
from services.parent_stats import get_parent_stats
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

_PIN_LEN = 4


@ft.component
def ParentPortalScreen():
    """PIN gate + student overview."""
    ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    unlocked, set_unlocked = ft.use_state(False)
    pin, set_pin = ft.use_state("")
    pin_error, set_pin_error = ft.use_state("")
    stats, set_stats = ft.use_state(None)
    loading, set_loading = ft.use_state(False)

    new_pin, set_new_pin = ft.use_state("")
    confirm_pin, set_confirm_pin = ft.use_state("")
    pin_msg, set_pin_msg = ft.use_state("")
    pin_msg_ok, set_pin_msg_ok = ft.use_state(True)

    page = ft.context.page

    async def _pin() -> str:
        store = getattr(page, "_akili_storage", None)
        if store is not None:
            saved = await store.get(STORAGE_PARENT_PIN)
            if saved:
                return saved
        return DEFAULT_PARENT_PIN

    def _try_unlock(_e):
        async def _run():
            if pin.strip() == await _pin():
                set_pin_error("")
                set_unlocked(True)
                set_pin_msg("")
                set_loading(True)
                try:
                    store = getattr(page, "_akili_course_store", None)
                    from services.gamification import get_gamification

                    set_stats(await get_parent_stats(store, get_gamification()))
                except Exception:
                    set_stats({"total_quizzes": 0, "avg_score": "0%", "last_active": "Never"})
                finally:
                    set_loading(False)
            else:
                set_pin_error(LBL_PARENT_WRONG_PIN)

        asyncio.ensure_future(_run())

    def _change_pin(_e):
        async def _run():
            set_pin_msg_ok(False)
            if pin.strip() != await _pin():
                set_pin_msg(LBL_PARENT_WRONG_PIN)
                return
            if len(new_pin.strip()) != _PIN_LEN or not new_pin.strip().isdigit():
                set_pin_msg(LBL_PARENT_PIN_SHORT)
                return
            if new_pin.strip() != confirm_pin.strip():
                set_pin_msg(LBL_PARENT_PIN_MISMATCH)
                return
            store = getattr(page, "_akili_storage", None)
            if store is not None:
                await store.set(STORAGE_PARENT_PIN, new_pin.strip())
            set_pin("")
            set_new_pin("")
            set_confirm_pin("")
            set_pin_msg_ok(True)
            set_pin_msg(LBL_PARENT_PIN_CHANGED)

        asyncio.ensure_future(_run())

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Text("Parent Portal", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Locked ──
    if not unlocked:
        return ft.Column(
            controls=[
                header,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED, size=tokens.ICON_FEATURE, color=AppColors.PRIMARY),
                            ft.Text(LBL_PARENT_LOCK_TITLE, size=tokens.FONT_XL, weight=ft.FontWeight.BOLD),
                            ft.Text(LBL_PARENT_LOCK_DESC, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                            ft.TextField(
                                label="PIN",
                                value=pin,
                                password=True,
                                can_reveal_password=True,
                                hint_text="Enter 4-digit PIN",
                                width=200,
                                keyboard_type=ft.KeyboardType.NUMBER,
                                max_length=_PIN_LEN,
                                text_align=ft.TextAlign.CENTER,
                                border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                                on_change=lambda e: set_pin(e.control.value),
                                on_submit=_try_unlock,
                            ),
                            *([ft.Text(pin_error, color=AppColors.ERROR, size=tokens.FONT_SM)] if pin_error else []),
                            ft.FilledButton(
                                LBL_PARENT_UNLOCK,
                                on_click=_try_unlock,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD)),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=tokens.SPACE_XL,
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
            spacing=0,
            expand=True,
        )

    # ── Unlocked ──
    if loading or stats is None:
        from components.loading_state import LoadingState

        return ft.Column(
            controls=[header, ft.Container(content=LoadingState("Loading overview…"), expand=True)],
            spacing=0,
            expand=True,
        )

    gam = stats.get("gamification", {})
    overview = ft.Container(
        content=ft.Row(
            controls=[
                StatCard(LBL_PARENT_TOTAL_QUIZZES, stats.get("total_quizzes", 0)),
                StatCard(LBL_PARENT_AVG_SCORE, stats.get("avg_score", "0%")),
                StatCard(LBL_PARENT_LAST_ACTIVE, str(stats.get("last_active", "Never"))[:10]),
            ],
            spacing=tokens.SPACE_SM,
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
        ),
        padding=tokens.SPACE_MD,
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
    )

    course_rows: list[ft.Control] = []
    for c in stats.get("courses", []):
        course_rows.append(
            ft.Row(
                controls=[
                    ft.Text(str(c.get("subject") or ""), size=tokens.FONT_MD, weight=ft.FontWeight.W_600, expand=True),
                    ft.Text(f"{float(c.get('progress_pct', 0)):.0f}%", size=tokens.FONT_SM, color=AppColors.PRIMARY),
                ],
            )
        )
        course_rows.append(
            ft.ProgressBar(
                value=float(c.get("progress_pct", 0)) / 100,
                color=AppColors.PRIMARY,
                height=tokens.PROGRESS_BAR_HEIGHT,
                border_radius=tokens.RADIUS_FULL,
            )
        )
        course_rows.append(
            ft.Text(
                f"{c.get('modules_done', 0)}/{c.get('modules_total', 0)} modules · {c.get('level', '')}",
                size=tokens.FONT_XS,
                color=ft.Colors.ON_SURFACE_VARIANT,
            )
        )
        course_rows.append(ft.Container(height=tokens.SPACE_SM))

    recent_rows: list[ft.Control] = []
    for r in stats.get("recent_quizzes", [])[:5]:
        recent_rows.append(
            ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.WARNING_AMBER_ROUNDED if r.get("weak") else ft.Icons.CHECK_CIRCLE_ROUNDED,
                        size=tokens.ICON_SM,
                        color=AppColors.WARNING if r.get("weak") else AppColors.SUCCESS,
                    ),
                    ft.Text(str(r.get("subject") or "Quiz"), size=tokens.FONT_SM, expand=True),
                    ft.Text(f"{float(r.get('pct', 0)):.0f}%", size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                ],
                spacing=tokens.SPACE_SM,
            )
        )

    counts = stats.get("assignment_counts", {})
    pending = stats.get("pending_assignments", [])

    body = ft.ListView(
        controls=[
            SectionHeader(LBL_PARENT_STUDENT_OVERVIEW),
            overview,
            ft.Container(height=tokens.SPACE_MD),
            SectionHeader("Courses"),
            *(course_rows or [ft.Text("No courses yet.", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT)]),
            ft.Container(height=tokens.SPACE_MD),
            SectionHeader("Recent Quizzes"),
            *(recent_rows or [ft.Text("No quizzes yet.", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT)]),
            ft.Container(height=tokens.SPACE_MD),
            SectionHeader("Assignments"),
            ft.Text(
                f"{counts.get('pending', 0)} pending · {counts.get('submitted', 0)} submitted · {counts.get('graded', 0)} graded",
                size=tokens.FONT_SM,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            *([ft.Text(f"• {a.get('title', '')}", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT) for a in pending[:5]]),
            ft.Container(height=tokens.SPACE_MD),
            SectionHeader("Motivation"),
            ft.Text(
                f"Level {gam.get('level', '')} · {int(gam.get('xp_total', 0)):,} XP · 🔥 {int(gam.get('current_streak', 0))}-day streak · 🏅 {int(gam.get('badges_earned', 0))} badges",
                size=tokens.FONT_SM,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Container(height=tokens.SPACE_MD),
            SectionHeader(LBL_PARENT_CHANGE_PIN),
            ft.TextField(
                label="Current PIN",
                value=pin,
                password=True,
                max_length=_PIN_LEN,
                keyboard_type=ft.KeyboardType.NUMBER,
                border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_change=lambda e: set_pin(e.control.value),
            ),
            ft.Row(
                controls=[
                    ft.TextField(
                        label=LBL_PARENT_NEW_PIN,
                        value=new_pin,
                        password=True,
                        max_length=_PIN_LEN,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        expand=True,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        on_change=lambda e: set_new_pin(e.control.value),
                    ),
                    ft.TextField(
                        label=LBL_PARENT_CONFIRM_PIN,
                        value=confirm_pin,
                        password=True,
                        max_length=_PIN_LEN,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        expand=True,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        on_change=lambda e: set_confirm_pin(e.control.value),
                    ),
                ],
                spacing=tokens.SPACE_SM,
            ),
            *([ft.Text(pin_msg, size=tokens.FONT_SM, color=(AppColors.SUCCESS if pin_msg_ok else AppColors.ERROR))] if pin_msg else []),
            ft.FilledButton(
                LBL_PARENT_CHANGE_PIN,
                on_click=_change_pin,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD)),
            ),
            ft.Container(height=tokens.SPACE_MD),
        ],
        spacing=0,
        expand=True,
        padding=tokens.SPACE_LG,
    )

    if not stats.get("courses"):
        body = EmptyState(
            "No student data yet",
            "Courses, quizzes, and assignments will appear here.",
            icon=ft.Icons.FAMILY_RESTROOM_ROUNDED,
        )

    return ft.Column(
        controls=[header, ft.Container(content=body, expand=True), build_banner_ad(page)],
        spacing=0,
        expand=True,
    )
