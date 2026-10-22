"""Notification bell — badge + bottom sheet with the 5 v1 types.

Ported from Akili v1's notification_bell.py as a declarative component:
pending/overdue assignments (tappable), daily-credit refill, streak
reminder, XP-to-next-level, and a study tip. Data loads when the sheet
opens, straight from the store + observable state.
"""

from __future__ import annotations

from datetime import datetime

import flet as ft
from flet import Control

from core import tokens
from core.constants import LEVELS
from core.state import state
from core.theme import AppColors
from state.controller_ctx import ControllerMethodsCtx


def _tile(icon, color, title: str, subtitle: str, is_new: bool = False, on_tap=None) -> Control:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=20, color=ft.Colors.WHITE),
                    width=40,
                    height=40,
                    border_radius=12,
                    bgcolor=color,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    controls=[
                        ft.Text(title, size=14, weight=ft.FontWeight.W_600),
                        ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Container(
                    width=8,
                    height=8,
                    border_radius=4,
                    bgcolor=AppColors.PRIMARY if is_new else ft.Colors.TRANSPARENT,
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(20, 12, 20, 12),
        ink=on_tap is not None,
        on_click=on_tap,
    )


async def _collect() -> tuple[list[dict], bool]:
    """(assignment items, has_unread). has_unread = credits reset today."""
    items: list[dict] = []
    has_unread = False
    try:
        page = ft.context.page
        store = getattr(page, "_akili_course_store", None)
        if store is not None:
            pending = await store.get_pending_assignments()
            courses = {c["id"]: c.get("subject", "") for c in await store.get_courses()}
            for a in pending:
                items.append({**a, "subject": courses.get(a.get("course_id"), "Assignment")})
        storage = getattr(page, "_akili_storage", None)
        if storage is not None:
            from core.constants import STORAGE_LAST_RESET

            last = await storage.get(STORAGE_LAST_RESET, "")
            has_unread = last == datetime.now().date().isoformat()
    except Exception:
        pass
    return items, has_unread


def _build_tiles(assignments: list[dict], has_unread: bool, on_open_assignment) -> list[Control]:
    tiles: list[Control] = []
    for a in assignments:
        is_overdue = False
        due_text = ""
        if a.get("due_date"):
            try:
                due = datetime.fromisoformat(a["due_date"])
                is_overdue = datetime.now() > due
                due_text = f" (overdue since {due.strftime('%b %d')})" if is_overdue else f" (due {due.strftime('%b %d')})"
            except Exception:
                pass
        aid = a.get("id")
        subject = a.get("subject", "Assignment")
        title = a.get("title", "Assignment")

        def _open(e, assignment_id=aid):
            on_open_assignment(assignment_id)

        tiles.append(
            _tile(
                ft.Icons.ASSIGNMENT_LATE_ROUNDED if is_overdue else ft.Icons.ASSIGNMENT_ROUNDED,
                ft.Colors.RED_700 if is_overdue else AppColors.ACCENT,
                f"{'⚠️ Overdue' if is_overdue else '📋 Pending'}: {subject}",
                f"{title}{due_text}",
                is_new=True,
                on_tap=_open,
            )
        )

    if has_unread:
        tiles.append(
            _tile(
                ft.Icons.SAVINGS_ROUNDED,
                AppColors.ACCENT,
                "Daily Credits Refilled!",
                f"You have {state.credits_remaining} credits ready to use today.",
                is_new=True,
            )
        )

    streak = int(getattr(state, "current_streak", 0) or 0)
    if streak > 0:
        tiles.append(
            _tile(
                ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                ft.Colors.ORANGE_700,
                f"🔥 {streak}-day streak!",
                "Keep learning daily to maintain your streak.",
            )
        )

    xp = int(getattr(state, "xp_total", 0) or 0)
    current, nxt = LEVELS[0], None
    for i, lvl in enumerate(LEVELS):
        if xp >= lvl["xp"]:
            current = lvl
            if i + 1 < len(LEVELS):
                nxt = LEVELS[i + 1]
    if nxt:
        tiles.append(
            _tile(
                ft.Icons.EMOJI_EVENTS_ROUNDED,
                AppColors.PRIMARY,
                f"{current['icon']} {current['name']}",
                f"{nxt['xp'] - xp} XP to reach {nxt['icon']} {nxt['name']}",
            )
        )

    tiles.append(
        _tile(
            ft.Icons.LIGHTBULB_ROUNDED,
            ft.Colors.AMBER_700,
            "Study Tip",
            "Use the AI tutor to ask questions about topics you find difficult!",
        )
    )
    return tiles


@ft.component
def NotificationBell():
    """Bell icon with unread badge; opens the notification sheet."""
    controller = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    count, set_count = ft.use_state(0)

    def _refresh_count():
        async def _run():
            items, unread = await _collect()
            set_count((1 if unread else 0) + len(items))

        page.run_task(_run)

    ft.use_effect(_refresh_count, [])

    def _open(e):
        async def _run():
            items, unread = await _collect()

            def _open_assignment(aid: int):
                async def _go():
                    state.current_assignment_id = aid
                    controller.show_assignment(aid)

                page.run_task(_go)

            tiles = _build_tiles(items, unread, _open_assignment)
            body: ft.Control = (
                ft.Column(controls=tiles, scroll=ft.ScrollMode.AUTO, spacing=0)
                if tiles
                else ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=48, color=AppColors.SUCCESS),
                            ft.Text("You're all caught up!", size=16, weight=ft.FontWeight.W_500),
                            ft.Text("No new notifications right now.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            )
            set_count(0)
            page.show_dialog(
                ft.BottomSheet(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.NOTIFICATIONS_ROUNDED, size=22, color=AppColors.PRIMARY),
                                            ft.Text("Notifications", size=18, weight=ft.FontWeight.BOLD, expand=True),
                                            ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=20, on_click=lambda ev: page.pop_dialog()),
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    padding=ft.Padding(20, 16, 12, 8),
                                ),
                                ft.Divider(height=1),
                                body,
                            ],
                            spacing=0,
                            tight=True,
                        ),
                        padding=ft.Padding(0, 0, 0, 20),
                        border_radius=ft.BorderRadius(20, 20, 0, 0),
                    ),
                )
            )

        page.run_task(_run)

    return ft.Stack(
        controls=[
            ft.IconButton(icon=ft.Icons.NOTIFICATIONS_OUTLINED, on_click=_open, tooltip="Notifications"),
            ft.Container(
                width=18,
                height=18,
                bgcolor=ft.Colors.RED_700,
                border_radius=9,
                top=4,
                right=4,
                visible=count > 0,
                content=ft.Text(
                    str(count) if count > 0 else "",
                    size=10,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
            ),
        ]
    )
