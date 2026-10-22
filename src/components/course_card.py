"""CourseCard — one course in the dashboard list.

Ported from Akili v1's course card (the house standard: icon-backdrop +
title/subtitle + trailing, whole card tappable).
Plain function — testable without a renderer.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft
from flet import Control

from core import tokens

# Subject colour palette (v1 parity — courses pick one at creation).
SUBJECT_COLORS = (
    "#6C5CE7",
    "#00B894",
    "#E17055",
    "#0984E3",
    "#FDCB6E",
    "#E84393",
    "#00CEC9",
    "#D63031",
    "#6AB04C",
    "#4834D4",
)


def subject_color(color_index: int) -> str:
    return SUBJECT_COLORS[color_index % len(SUBJECT_COLORS)]


def CourseCard(course: dict, on_tap: Callable[[dict], None] | None = None) -> Control:
    """A course row: colour dot, subject, level, progress bar."""
    colour = subject_color(course.get("color_index", 0))
    pct = float(course.get("progress_pct", 0.0))

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=tokens.ICON_SM, color=colour),
                            width=tokens.ICON_BACKDROP,
                            height=tokens.ICON_BACKDROP,
                            border_radius=tokens.ICON_BACKDROP_RADIUS,
                            bgcolor=ft.Colors.with_opacity(0.12, colour),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    str(course.get("subject") or "Course"),
                                    size=tokens.FONT_MD,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    str(course.get("level") or ""),
                                    size=tokens.FONT_XS,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=1,
                            expand=True,
                            tight=True,
                        ),
                        ft.Text(
                            f"{pct:.0f}%",
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.BOLD,
                            color=colour,
                        ),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=tokens.ICON_SM, color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)),
                    ],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.ProgressBar(
                    value=pct / 100,
                    color=colour,
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                    height=tokens.PROGRESS_BAR_HEIGHT,
                    border_radius=tokens.RADIUS_FULL,
                ),
            ],
            spacing=0,
            tight=True,
        ),
        padding=tokens.SPACE_LG,
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
        ink=on_tap is not None,
        on_click=(lambda e: on_tap(course)) if on_tap else None,
    )
