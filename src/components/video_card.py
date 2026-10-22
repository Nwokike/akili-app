"""VideoCard — a tappable video preview for lessons.

Ported from Akili v1's rich_content video card (the house standard):
YouTube thumbnail, platform badge, duration, tap to play.
Plain function — testable without a renderer.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import flet as ft
from flet import Control

from core import tokens
from core.theme import AppColors

_YT_THUMB_RE = re.compile(r"(?:v=|youtu\.be/|embed/|shorts/)([\w-]{11})")


def youtube_thumbnail(url: str) -> str:
    """The hqdefault thumbnail for a YouTube URL, or ""."""
    match = _YT_THUMB_RE.search(url or "")
    if not match:
        return ""
    return f"https://img.youtube.com/vi/{match.group(1)}/hqdefault.jpg"


def platform_info(url: str) -> tuple[str, str]:
    """(platform label, brand colour) for a video URL."""
    lowered = (url or "").lower()
    if "youtube" in lowered or "youtu.be" in lowered:
        return ("YouTube", "#FF0000")
    if "vimeo" in lowered:
        return ("Vimeo", "#1AB7EA")
    if "dailymotion" in lowered:
        return ("Dailymotion", "#0066DC")
    return ("Video", AppColors.PRIMARY)


def VideoCard(
    title: str,
    url: str,
    on_play: Callable[[str, str], None] | None = None,
    duration: str = "",
) -> Control:
    """A 280px video card: thumbnail + play overlay + title + platform badge."""
    thumb = youtube_thumbnail(url)
    platform, colour = platform_info(url)

    thumb_layer: ft.Control
    if thumb:
        thumb_layer = ft.Image(
            src=thumb,
            width=120,
            height=80,
            fit=ft.BoxFit.COVER,
            border_radius=tokens.RADIUS_SM,
            error_content=ft.Icon(ft.Icons.PLAY_CIRCLE_ROUNDED, size=36, color=ft.Colors.with_opacity(0.5, colour)),
        )
    else:
        thumb_layer = ft.Container(
            content=ft.Icon(ft.Icons.PLAY_CIRCLE_ROUNDED, size=36, color=colour),
            width=120,
            height=80,
            border_radius=tokens.RADIUS_SM,
            bgcolor=ft.Colors.with_opacity(0.08, colour),
            alignment=ft.Alignment.CENTER,
        )

    overlay: list[ft.Control] = [
        thumb_layer,
        ft.Container(
            content=ft.Container(
                content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=24, color=ft.Colors.WHITE),
                width=36,
                height=36,
                border_radius=18,
                bgcolor=ft.Colors.with_opacity(0.7, ft.Colors.BLACK),
                alignment=ft.Alignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            width=120,
            height=80,
        ),
    ]
    if duration:
        overlay.append(
            ft.Container(
                content=ft.Text(duration, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                padding=ft.Padding(4, 1, 4, 1),
                border_radius=4,
                bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLACK),
                right=4,
                bottom=4,
            )
        )

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Stack(controls=overlay, width=120, height=80),
                ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Text(platform.upper(), size=9, weight=ft.FontWeight.BOLD, color=colour),
                            padding=ft.Padding(6, 1, 6, 1),
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.12, colour),
                        ),
                        ft.Text(
                            title or "Video",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text("Tap to watch", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=2,
                    expand=True,
                    tight=True,
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=tokens.SPACE_SM,
        border_radius=tokens.RADIUS_MD,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        width=320,
        ink=on_play is not None,
        on_click=(lambda e: on_play(url, title)) if on_play else None,
        animate=ft.Animation(tokens.ANIM_NORMAL, ft.AnimationCurve.EASE_OUT),
    )
