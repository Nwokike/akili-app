"""Lesson player — in-app video playback for lesson videos.

A bottom sheet hosting flet-video: resolves YouTube URLs through the
InnerTube resolver, plays direct streams natively, retries transient
errors, and disposes on close. External browser only when resolving fails.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import flet as ft

from core import tokens
from core.theme import AppColors

logger = logging.getLogger(__name__)

try:
    import flet_video as fv

    _HAS_VIDEO = True
except ImportError:
    fv = None  # type: ignore[assignment]
    _HAS_VIDEO = False

STREAM_RETRY_MAX = 3
STREAM_RETRY_DELAY = 2


def _is_youtube(url: str) -> bool:
    lowered = (url or "").lower()
    return "youtube.com" in lowered or "youtu.be" in lowered


async def resolve_for_playback(url: str) -> str:
    """Turn a lesson video URL into a directly playable stream URL.

    YouTube watch/shorts/embed links go through the InnerTube resolver;
    anything else is returned unchanged (direct mp4 etc.).
    """
    url = (url or "").strip()
    if not url:
        return ""
    if not _is_youtube(url):
        return url
    try:
        from services.youtube_resolver import resolve_youtube_url

        return await resolve_youtube_url(url)
    except Exception as exc:
        logger.warning("YouTube resolve failed, falling back to external: %s", exc)
        return ""


def show_lesson_player(page: ft.Page, url: str, title: str = "") -> None:
    """Open the in-app player sheet. Falls back to external on failure."""
    if not _HAS_VIDEO:
        _launch_external(page, url)
        return
    sheet = _PlayerSheet(page, url, title or "Lesson Video")
    try:
        page.show_dialog(sheet.sheet)
    except Exception as exc:
        logger.warning("player sheet failed: %s", exc)
        _launch_external(page, url)
    page.run_task(sheet.start)


def _launch_external(page: ft.Page, url: str) -> None:
    try:
        launcher = getattr(page, "url_launcher", None) or ft.UrlLauncher()
        page.run_task(launcher.launch_url, url)
    except Exception as exc:
        logger.warning("external launch failed: %s", exc)


class _PlayerSheet:
    """Stateful player: resolve → play → retry → dispose."""

    def __init__(self, page: ft.Page, url: str, title: str):
        self.page = page
        self.url = url
        self.title = title
        self.video: fv.Video | None = None
        self.status = ft.Text("Loading stream…", size=tokens.FONT_SM, color=ft.Colors.WHITE)
        self._retries = 0
        self._closed = False

        self.sheet = ft.BottomSheet(
            show_drag_handle=True,
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(title, size=tokens.FONT_MD, weight=ft.FontWeight.BOLD, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, on_click=lambda e: self.close()),
                            ],
                        ),
                        ft.Stack(
                            controls=[
                                ft.Container(
                                    content=ft.ProgressRing(width=48, height=48, color=AppColors.PRIMARY),
                                    alignment=ft.Alignment.CENTER,
                                    height=220,
                                    bgcolor=ft.Colors.BLACK,
                                    border_radius=tokens.RADIUS_MD,
                                ),
                                ft.Container(content=self.status, alignment=ft.Alignment.CENTER, height=220),
                            ],
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    tight=True,
                ),
                padding=tokens.SPACE_LG,
                width=480,
            ),
            on_dismiss=lambda e: self.close(),
        )

    async def start(self) -> None:
        """Resolve then mount the Video control."""
        if self._closed:
            return
        stream = await resolve_for_playback(self.url)
        if self._closed:
            return
        if not stream:
            self._fail("Couldn't load this video.", external=True)
            return
        await self._mount(stream)

    async def _mount(self, stream: str) -> None:
        try:
            self.video = fv.Video(
                playlist=[fv.VideoMedia(stream)],
                title=self.title,
                autoplay=True,
                wakelock=True,
                pause_upon_entering_background_mode=True,
                resume_upon_entering_foreground_mode=False,
                fill_color=ft.Colors.BLACK,
                fit=ft.BoxFit.CONTAIN,
                controls=fv.AdaptiveVideoControls(),
                on_load=lambda e: self._ready(),
                on_error=lambda e: self._on_error(),
                on_complete=lambda e: self._on_complete(),
            )
            stack = self.sheet.content.content.controls[1]
            stack.controls = [self.video]
            with contextlib.suppress(Exception):
                self.page.update()
        except Exception as exc:
            logger.warning("player mount failed: %s", exc)
            self._fail("Couldn't start playback.", external=True)

    def _ready(self) -> None:
        self.status.value = ""
        with contextlib.suppress(Exception):
            self.page.update()

    def _on_error(self) -> None:
        if self._closed:
            return
        if self._retries < STREAM_RETRY_MAX:
            self._retries += 1
            self.status.value = f"Stream error, retrying ({self._retries}/{STREAM_RETRY_MAX})…"
            with contextlib.suppress(Exception):
                self.page.update()

            async def _retry():
                await asyncio.sleep(STREAM_RETRY_DELAY)
                if not self._closed and self.video is not None:
                    try:
                        await self.video.play()
                    except Exception:
                        self._on_error()

            with contextlib.suppress(Exception):
                self.page.run_task(_retry)
        else:
            self._fail("Failed to load. Tap to go back.", external=False)

    def _on_complete(self) -> None:
        self.status.value = "Stream ended."
        with contextlib.suppress(Exception):
            self.page.update()

    def _fail(self, message: str, external: bool) -> None:
        self.status.value = message
        with contextlib.suppress(Exception):
            self.page.update()
        if external:
            _launch_external(self.page, self.url)
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.video is not None:
            with contextlib.suppress(Exception):
                self.page.run_task(self.video.stop)
            self.video = None
        with contextlib.suppress(Exception):
            self.page.pop_dialog()
