"""Rich content — markdown interleaved with video and image cards.

Ported from Akili v1's rich_content.py (the house standard):
- strips LaTeX (the prompts emit Unicode maths instead)
- lifts `[VIDEO]: Title - URL` lines, markdown video links, and <iframe>s
  into tappable VideoCards
- lifts markdown images into tappable ImageCards (tap → lightbox)
- renders the remaining prose with ft.Markdown(GITHUB_WEB)

Plain function — testable without a renderer.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable

import flet as ft
from flet import Control

from core import tokens

_VIDEO_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_VIDEO_DOMAINS = ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")
_VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".3gp", ".webm")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")
_LESSON_VIDEO_RE = re.compile(r"\[VIDEO\]:\s*(.*?)\s*-\s*(https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)[\w-]+)")
_IFRAME_RE = re.compile(r"<iframe\b[^>]*src=[\"'](https?://[^\"']+)[\"'][^>]*>(?:.*?</iframe>)?", re.DOTALL | re.IGNORECASE)
_LATEX_BLOCK_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_LATEX_INLINE_RE = re.compile(r"\$(.*?)\$")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


def _is_video_url(url: str) -> bool:
    lowered = (url or "").lower()
    return any(d in lowered for d in _VIDEO_DOMAINS) or any(lowered.endswith(e) for e in _VIDEO_EXTENSIONS)


def _strip_latex(text: str) -> str:
    """The prompts forbid LaTeX; strip any that slips through."""
    text = _LATEX_BLOCK_RE.sub(r"\1", text)
    text = _LATEX_INLINE_RE.sub(r"\1", text)
    return text


def _preprocess(text: str) -> str:
    """Normalise iframes and lesson-video lines into markdown video links."""

    # <iframe src="..."> → a markdown video link
    def _iframe(match: re.Match) -> str:
        url = match.group(1)
        return f"\n\n[🎬 Watch Video]({url})\n\n"

    text = _IFRAME_RE.sub(_iframe, text)

    # [VIDEO]: Title - URL → a markdown video link (keeps the title)
    def _lesson_video(match: re.Match) -> str:
        title = (match.group(1) or "Watch Video").strip()
        return f"\n\n[🎬 {title}]({match.group(2)})\n\n"

    text = _LESSON_VIDEO_RE.sub(_lesson_video, text)
    return _BLANK_RUN_RE.sub("\n\n", text)


def _find_next_media(text: str, pos: int):
    """Earliest of: image, video link. Returns (kind, start, end, match) or None."""
    candidates = []
    img = _IMAGE_RE.search(text, pos)
    if img:
        candidates.append(("image", img.start(), img.end(), img))
    for link in _VIDEO_LINK_RE.finditer(text, pos):
        if _is_video_url(link.group(2)):
            candidates.append(("video", link.start(), link.end(), link))
            break
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[1])


def _lightbox(page: ft.Page, src: str, caption: str) -> ft.AlertDialog:
    return ft.AlertDialog(
        content=ft.Stack(
            controls=[
                ft.Image(src=src, fit=ft.BoxFit.CONTAIN),
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda e: page.pop_dialog(),
                    ),
                    right=0,
                    top=0,
                ),
            ],
        ),
        content_padding=0,
        bgcolor=ft.Colors.TRANSPARENT,
    )


def _image_card(page: ft.Page, alt: str, src: str) -> Control:
    def _open(e):
        with contextlib.suppress(Exception):
            page.show_dialog(_lightbox(page, src, alt))

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Image(
                    src=src,
                    width=320,
                    height=160,
                    fit=ft.BoxFit.COVER,
                    border_radius=tokens.RADIUS_MD,
                    error_content=ft.Container(
                        content=ft.Text("Image unavailable", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                        width=320,
                        height=160,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    ),
                ),
                *([ft.Text(alt, size=tokens.FONT_XS, italic=True, color=ft.Colors.ON_SURFACE_VARIANT)] if alt else []),
            ],
            spacing=tokens.SPACE_XS,
            tight=True,
        ),
        ink=True,
        on_click=_open,
    )


def render_rich_content(
    content: str,
    page: ft.Page,
    on_play_video: Callable[[str, str], None] | None = None,
    show_images: bool = True,
    show_videos: bool = True,
) -> list[Control]:
    """Turn a lesson/tutor markdown body into a list of interleaved controls."""
    from components.video_card import VideoCard

    if not content:
        return []

    text = _strip_latex(content)
    text = _preprocess(text)

    controls: list[Control] = []
    pos = 0
    while pos < len(text):
        found = _find_next_media(text, pos)
        if found is None:
            segment = text[pos:]
            if segment.strip():
                controls.append(_markdown(segment))
            break

        kind, start, end, match = found
        segment = text[pos:start]
        if segment.strip():
            controls.append(_markdown(segment))

        if kind == "video":
            if show_videos:
                controls.append(VideoCard(match.group(1), match.group(2), on_play=on_play_video))
        elif kind == "image" and show_images:
            controls.append(_image_card(page, match.group(1), match.group(2)))

        pos = end

    return controls


def _markdown(text: str) -> Control:
    return ft.Markdown(
        text,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
    )
