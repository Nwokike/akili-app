"""ModuleCard — one module in the course detail list.

Ported from Akili v1's module card (the house standard):
lock / play / check icon by state, `Module N` + subtitle, assignment badge,
whole card tappable only when unlocked.
Plain function — testable without a renderer.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft
from flet import Control

from core import tokens
from core.theme import AppColors


def _assignment_badge(assignment: dict | None) -> Control | None:
    if not assignment:
        return None
    status = assignment.get("status", "pending")
    icon, colour, tip = {
        "pending": (ft.Icons.ASSIGNMENT_LATE_ROUNDED, AppColors.WARNING, "Assignment pending"),
        "submitted": (ft.Icons.UPLOAD_FILE_ROUNDED, AppColors.PRIMARY, "Assignment submitted"),
        "graded": (ft.Icons.TASK_ALT_ROUNDED, AppColors.SUCCESS, "Assignment graded"),
    }.get(status, (ft.Icons.ASSIGNMENT_ROUNDED, ft.Colors.ON_SURFACE_VARIANT, "Assignment"))
    return ft.Icon(icon, size=tokens.ICON_SM, color=colour, tooltip=tip)


def ModuleCard(
    module: dict,
    index: int,
    assignment: dict | None = None,
    on_tap: Callable[[dict], None] | None = None,
) -> Control:
    """A module row with lock/complete state and an assignment badge."""
    unlocked = bool(module.get("is_unlocked"))
    completed = bool(module.get("is_completed"))

    if completed:
        icon, colour = ft.Icons.CHECK_CIRCLE_ROUNDED, AppColors.SUCCESS
    elif unlocked:
        icon, colour = ft.Icons.PLAY_CIRCLE_ROUNDED, AppColors.PRIMARY
    else:
        icon, colour = ft.Icons.LOCK_ROUNDED, ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)

    subtitle = f"Module {index + 1}"
    if not unlocked:
        subtitle += " · Pass the quiz (50%+) to unlock"

    row_children: list[Control] = [
        ft.Container(
            content=ft.Icon(icon, size=tokens.ICON_SM, color=colour),
            width=tokens.ICON_BACKDROP,
            height=tokens.ICON_BACKDROP,
            border_radius=tokens.ICON_BACKDROP_RADIUS,
            bgcolor=ft.Colors.with_opacity(0.10, colour),
            alignment=ft.Alignment.CENTER,
        ),
        ft.Column(
            controls=[
                ft.Text(
                    str(module.get("title") or f"Module {index + 1}"),
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(subtitle, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            spacing=1,
            expand=True,
            tight=True,
        ),
    ]
    badge = _assignment_badge(assignment)
    if badge is not None:
        row_children.append(badge)

    card = ft.Container(
        content=ft.Row(
            controls=row_children,
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=tokens.SPACE_LG,
        border_radius=tokens.RADIUS_MD,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if unlocked else ft.Colors.TRANSPARENT,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        ink=unlocked and on_tap is not None,
        on_click=(lambda e: on_tap(module)) if (unlocked and on_tap) else None,
    )
    return card
