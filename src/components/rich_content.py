"""RichContentRenderer — shared component for beautiful AI content rendering.

Extracts videos and images from AI markdown responses and renders them as
premium native Flet cards with thumbnails, metadata, and smooth interactions.
Used by tutor_chat.py, lesson_view.py, and any future AI content surface.
"""

import logging
import re

import flet as ft

from core.theme import AppColors, AppStyles

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────

# Markdown video links: [title](url)
_VIDEO_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_VIDEO_DOMAINS = ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")
_VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".3gp", ".webm")

# Markdown images: ![alt](url)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^\)]+)\)")

# Lesson video format: [VIDEO]: Title - https://youtube.com/...
_LESSON_VIDEO_RE = re.compile(r"\[VIDEO\]:\s*(.*?)\s*-\s*(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)")

# Duration patterns in text
_DURATION_RE = re.compile(r"(\d+:\d+(?::\d+)?|\d+\s*min)")


def _is_video_url(url: str) -> bool:
    lower = url.lower()
    return any(d in lower for d in _VIDEO_DOMAINS) or any(lower.endswith(ext) for ext in _VIDEO_EXTENSIONS)


def _get_youtube_thumbnail(url: str) -> str | None:
    """Extract YouTube video ID and return high-quality thumbnail URL."""
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    if match:
        return f"https://img.youtube.com/vi/{match.group(1)}/hqdefault.jpg"
    return None


def _get_platform_info(url: str) -> tuple[str, str]:
    """Return (platform_name, accent_color_hex) for a video URL."""
    lower = url.lower()
    if "youtube" in lower or "youtu.be" in lower:
        return "YouTube", "#FF0000"
    if "vimeo" in lower:
        return "Vimeo", "#1AB7EA"
    if "dailymotion" in lower:
        return "Dailymotion", "#0066DC"
    return "Video", AppColors.PRIMARY


# ── Extract helpers ───────────────────────────────────────────────────────


def extract_video_links(text: str) -> list[dict]:
    """Extract video links with metadata from markdown text."""
    matches = _VIDEO_LINK_RE.findall(text)
    videos = []
    for title, url in matches:
        if _is_video_url(url):
            # Try to find duration near this URL
            duration = ""
            for line in text.split("\n"):
                if url in line or title in line:
                    dm = _DURATION_RE.search(line)
                    if dm:
                        duration = dm.group(1)
                        break
            videos.append(
                {
                    "title": title.strip(),
                    "url": url.strip(),
                    "duration": duration,
                    "thumbnail": _get_youtube_thumbnail(url),
                }
            )
    return videos


def extract_lesson_videos(text: str) -> list[dict]:
    """Extract [VIDEO]: format from lesson content."""
    matches = _LESSON_VIDEO_RE.findall(text)
    return [
        {
            "title": title.strip(),
            "url": url.strip(),
            "duration": "",
            "thumbnail": _get_youtube_thumbnail(url),
        }
        for title, url in matches
    ]


def extract_images(text: str) -> list[dict]:
    """Extract markdown images ![alt](url) from text."""
    matches = _IMAGE_RE.findall(text)
    return [{"alt": alt.strip(), "url": url.strip()} for alt, url in matches]


def strip_media_markdown(text: str) -> str:
    """Remove image markdown and [VIDEO]: lines from content for clean rendering."""
    # Remove ![alt](url) image markdown
    text = _IMAGE_RE.sub("", text)
    # Remove [VIDEO]: lines
    text = _LESSON_VIDEO_RE.sub("", text)
    # Clean up excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Card builders ─────────────────────────────────────────────────────────


def build_video_card(
    title: str,
    url: str,
    on_play,
    page: ft.Page,
    duration: str = "",
    thumbnail: str | None = None,
) -> ft.Container:
    """Premium video card with thumbnail, gradient overlay, metadata badge."""
    platform_name, platform_color = _get_platform_info(url)
    thumb_url = thumbnail or _get_youtube_thumbnail(url)

    # Thumbnail with gradient overlay
    if thumb_url:
        thumb_content = ft.Stack(
            [
                ft.Image(
                    src=thumb_url,
                    fit=ft.BoxFit.COVER,
                    width=120,
                    height=80,
                    border_radius=ft.BorderRadius(10, 0, 0, 10),
                ),
                # Gradient overlay
                ft.Container(
                    width=120,
                    height=80,
                    gradient=ft.LinearGradient(
                        colors=[
                            ft.Colors.with_opacity(0.0, ft.Colors.BLACK),
                            ft.Colors.with_opacity(0.4, ft.Colors.BLACK),
                        ],
                        begin=ft.Alignment.CENTER_LEFT,
                        end=ft.Alignment.CENTER_RIGHT,
                    ),
                ),
                # Play icon centered
                ft.Container(
                    width=120,
                    height=80,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Container(
                        content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.WHITE, size=28),
                        width=40,
                        height=40,
                        border_radius=20,
                        bgcolor=ft.Colors.with_opacity(0.7, ft.Colors.BLACK),
                        alignment=ft.Alignment.CENTER,
                    ),
                ),
                # Duration badge
                *(
                    [
                        ft.Container(
                            content=ft.Text(duration, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                            padding=ft.Padding(6, 2, 6, 2),
                            border_radius=4,
                            bgcolor=ft.Colors.with_opacity(0.75, ft.Colors.BLACK),
                            right=4,
                            bottom=4,
                        )
                    ]
                    if duration
                    else []
                ),
            ],
        )
    else:
        # Fallback: gradient background with play icon
        thumb_content = ft.Container(
            content=ft.Icon(ft.Icons.PLAY_CIRCLE_FILL_ROUNDED, size=36, color=platform_color),
            width=80,
            height=80,
            bgcolor=ft.Colors.with_opacity(0.06, platform_color),
            border_radius=ft.BorderRadius(10, 0, 0, 10),
            alignment=ft.Alignment.CENTER,
        )

    # Metadata column
    meta_col = ft.Column(
        [
            ft.Container(
                content=ft.Text(
                    platform_name,
                    size=10,
                    color=platform_color,
                    weight=ft.FontWeight.BOLD,
                ),
                padding=ft.Padding(8, 2, 8, 2),
                border_radius=4,
                bgcolor=ft.Colors.with_opacity(0.08, platform_color),
            ),
            ft.Text(
                title,
                size=13,
                weight=ft.FontWeight.W_600,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Row(
                [
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("Tap to watch", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=4,
            ),
        ],
        spacing=4,
        expand=True,
        tight=True,
    )

    return ft.Container(
        content=ft.Row(
            [thumb_content, meta_col],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        border_radius=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        margin=ft.Margin(0, 4, 0, 4),
        on_click=lambda e, u=url, t=title: page.run_task(on_play, u, t),
        ink=True,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


def build_image_card(alt: str, url: str, page: ft.Page) -> ft.Container:
    """Beautiful image card with rounded corners, caption, and tap-to-open."""

    async def _open_image(e):
        try:
            await page.launch_url_async(url)
        except Exception as ex:
            logger.warning("Failed to open image URL: %s", ex)

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Image(
                        src=url,
                        fit=ft.BoxFit.COVER,
                        width=float("inf"),
                        height=180,
                        error_content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, size=32, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text("Image unavailable", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                            height=120,
                            alignment=ft.Alignment.CENTER,
                        ),
                    ),
                    border_radius=ft.BorderRadius(10, 10, 0, 0),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                ),
                *(
                    [
                        ft.Container(
                            content=ft.Text(
                                alt,
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                italic=True,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            padding=ft.Padding(12, 8, 12, 8),
                        )
                    ]
                    if alt
                    else []
                ),
            ],
            spacing=0,
            tight=True,
        ),
        border_radius=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        margin=ft.Margin(0, 4, 0, 4),
        on_click=_open_image,
    )


# ── Full content renderer ────────────────────────────────────────────────


def render_rich_content(
    content: str,
    page: ft.Page,
    on_play_video,
    on_tap_link=None,
    show_images: bool = True,
    show_videos: bool = True,
) -> list[ft.Control]:
    """Parse AI markdown and return a list of Flet controls: markdown + media cards.

    This is the single entry point for rendering AI content anywhere in the app.
    """
    controls = []

    # Extract media
    videos = extract_video_links(content) if show_videos else []
    images = extract_images(content) if show_images else []

    # Clean markdown (remove image markdown — we render them natively)
    clean = strip_media_markdown(content) if images else content

    # Main markdown
    md = ft.Markdown(
        clean or "...",
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        on_tap_link=((lambda e: page.run_task(on_tap_link, e.href)) if on_tap_link else None),
        md_style_sheet=AppStyles.markdown_stylesheet(),
    )
    controls.append(md)

    # Image cards
    if images:
        controls.append(ft.Container(height=8))
        for img in images:
            controls.append(build_image_card(img["alt"], img["url"], page))

    # Video cards
    if videos:
        controls.append(ft.Container(height=8))
        for v in videos:
            controls.append(
                build_video_card(
                    title=v["title"],
                    url=v["url"],
                    on_play=on_play_video,
                    page=page,
                    duration=v.get("duration", ""),
                    thumbnail=v.get("thumbnail"),
                )
            )

    return controls
