"""Share service — achievements as emoji text + a screenshotable card.

Ported from Akili v1's share_service.py (payloads + thresholds verbatim).
v2 additions: an XP_MILESTONE card branch (v1 had text only), native
`ft.Share.share_text` tried first with the v1 URL-intent buttons as
fallback, and offer_share_event() so screens share one event→sheet mapping.

Two modes (v1 parity): (1) emoji text via clipboard / URL intents, (2) an
on-screen gradient card for screenshots. Every share appends the Akili
marketing footer. Never raises — all entry points are best-effort.
"""

from __future__ import annotations

import logging
from datetime import datetime

import flet as ft

from core import tokens
from core.constants import (
    APP_FULL_NAME,
    APP_TAGLINE,
    PLAYSTORE_URL,
    SHARE_HASHTAG,
)
from core.theme import AppColors

logger = logging.getLogger(__name__)


class ShareType:
    QUIZ_RESULT = "quiz_result"
    EXAM_RESULT = "exam_result"
    ASSIGNMENT_RESULT = "assignment_result"
    XP_MILESTONE = "xp_milestone"
    STREAK = "streak"
    BADGE = "badge"
    LEVEL_UP = "level_up"
    COURSE_COMPLETE = "course_complete"


def build_share_text(share_type: str, data: dict) -> str:
    """The emoji share text for a type + payload (v1 verbatim)."""
    data = data or {}
    lines: list[str] = []

    if share_type == ShareType.QUIZ_RESULT:
        pct = float(data.get("pct", 0))
        emoji = "🏆" if pct >= 90 else "⭐" if pct >= 70 else "📊"
        lines.append(f"{emoji} Quiz Result!")
        lines.append(f"📚 {data.get('subject', '')} — {data.get('module', '')}")
        lines.append(f"📊 Score: {pct:.0f}%")
        if pct >= 100:
            lines.append("💯 Perfect Score!")
        elif pct >= 70:
            lines.append("🎯 Great job!")
        else:
            lines.append("📖 Keep studying!")

    elif share_type == ShareType.EXAM_RESULT:
        grade = str(data.get("grade", ""))
        pct = float(data.get("pct", 0))
        emoji = "🏆" if grade in ("A", "A+") else "🌟" if grade in ("B", "B+") else "📝"
        lines.append(f"{emoji} Mock Exam Completed!")
        lines.append(f"📚 {data.get('subject', '')}")
        lines.append(f"Grade: {grade} ({pct:.0f}%)")
        if data.get("duration"):
            seconds = int(data["duration"])
            lines.append(f"⏱ Time: {seconds // 60}m {seconds % 60:02d}s")

    elif share_type == ShareType.ASSIGNMENT_RESULT:
        pct = float(data.get("pct", 0))
        lines.append("✅ Assignment Graded!")
        lines.append(f"📚 {data.get('subject', '')}: {data.get('title', '')}")
        lines.append(f"📊 Score: {pct:.0f}%")

    elif share_type == ShareType.XP_MILESTONE:
        lines.append("⚡ XP Milestone!")
        lines.append(f"🎮 Total XP: {int(data.get('xp', 0)):,}")
        lines.append(f"🏅 Level: {data.get('level', '')}")

    elif share_type == ShareType.STREAK:
        streak = int(data.get("streak", 0))
        lines.append(f"🔥 {streak}-Day Study Streak!")
        lines.append(f"📅 {data.get('name', '')} has been studying every day!")

    elif share_type == ShareType.BADGE:
        lines.append(f"{data.get('badge_icon', '🏅')} New Badge Earned!")
        lines.append(f"🏅 {data.get('badge_name', '')}")
        if data.get("badge_desc"):
            lines.append(f"📝 {data['badge_desc']}")

    elif share_type == ShareType.LEVEL_UP:
        lines.append(f"{data.get('icon', '🎓')} Level Up!")
        lines.append(f"🎓 {data.get('name', '')} is now a {data.get('level', '')}!")

    elif share_type == ShareType.COURSE_COMPLETE:
        lines.append("🎓 Course Completed!")
        lines.append(f"📚 {data.get('name', '')} completed {data.get('subject', '')}!")

    else:
        lines.append("🎓 Learning with Akili!")

    lines.append(f"— {APP_FULL_NAME}")
    lines.append(f"📲 Download: {PLAYSTORE_URL}")
    lines.append(SHARE_HASHTAG)
    return "\n".join(lines)


def _big_line(share_type: str, data: dict) -> tuple[str, str]:
    """(big number, big caption) for the share card."""
    if share_type == ShareType.QUIZ_RESULT:
        return (f"{float(data.get('pct', 0)):.0f}%", "Quiz Score")
    if share_type == ShareType.EXAM_RESULT:
        return (str(data.get("grade", "")), f"{float(data.get('pct', 0)):.0f}% on the mock exam")
    if share_type == ShareType.ASSIGNMENT_RESULT:
        return (f"{float(data.get('pct', 0)):.0f}%", "Assignment Score")
    if share_type == ShareType.XP_MILESTONE:
        return (f"{int(data.get('xp', 0)):,}", "Total XP")
    if share_type == ShareType.STREAK:
        return (f"{int(data.get('streak', 0))} days", "Study Streak")
    if share_type == ShareType.BADGE:
        return (str(data.get("badge_icon", "🏅")), str(data.get("badge_name", "")))
    if share_type == ShareType.LEVEL_UP:
        return (str(data.get("icon", "🎓")), str(data.get("level", "")))
    if share_type == ShareType.COURSE_COMPLETE:
        return ("🎓", str(data.get("subject", "")))
    return ("🎓", "Learning with Akili")


def build_share_card(share_type: str, data: dict) -> ft.Control:
    """The 320px gradient share card."""
    big, caption = _big_line(share_type, data or {})
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Image(src="/icon.svg", width=28, height=28),
                        ft.Column(
                            controls=[
                                ft.Text("Akili", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(APP_TAGLINE, size=10, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                            ],
                            spacing=0,
                            tight=True,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=tokens.SPACE_MD),
                ft.Text(big, size=52, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                ft.Text(caption, size=tokens.FONT_MD, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE), text_align=ft.TextAlign.CENTER),
                ft.Container(height=tokens.SPACE_MD),
                ft.Text(
                    f"{(data or {}).get('name', '')} · {datetime.now().strftime('%b %d, %Y')}",
                    size=tokens.FONT_XS,
                    color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
        width=320,
        padding=tokens.SPACE_XL,
        border_radius=tokens.RADIUS_XL,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[AppColors.PRIMARY, AppColors.ACCENT],
        ),
    )


def _is_mobile(page: ft.Page | None) -> bool:
    """Ads and native share exist on mobile only — desktop gets copy/intents."""
    try:
        return page is not None and not page.web and page.platform.is_mobile()
    except Exception:
        return False


def _launch(page: ft.Page, url: str) -> None:
    """Open a URL, best-effort."""
    try:
        launcher = getattr(page, "url_launcher", None) or ft.UrlLauncher()
        page.run_task(launcher.launch_url, url)
    except Exception as exc:
        logger.warning("share launch failed: %s", exc)


async def _copy(page: ft.Page, text: str) -> bool:
    """Copy to clipboard; confirm only on success. Returns copied."""
    try:
        clipboard = ft.Clipboard()
        await clipboard.set(text)
    except Exception as exc:
        logger.warning("share copy failed: %s", exc)
        return False
    try:
        from core.notify import show_snack

        show_snack(page, "📋 Copied to clipboard!", AppColors.SUCCESS)
    except Exception:
        pass
    return True


async def _share_native(page: ft.Page, text: str) -> bool:
    """Platform share sheet (mobile only). Returns False when unavailable."""
    if not _is_mobile(page):
        return False
    try:
        await ft.Share().share_text(text)
        return True
    except Exception as exc:
        logger.debug("native share unavailable: %s", exc)
        return False


def show_share_sheet(page: ft.Page, share_type: str, data: dict) -> None:
    """Open the share bottom sheet. Best-effort, never raises."""
    from urllib.parse import quote

    try:
        text = build_share_text(share_type, data)
        encoded = quote(text)

        async def _do_copy() -> None:
            await _copy(page, text)

        async def _do_more() -> None:
            # Native sheet on mobile; copy fallback everywhere else.
            if not await _share_native(page, text):
                await _copy(page, text)

        sheet = ft.BottomSheet(
            show_drag_handle=True,
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            width=40,
                            height=4,
                            border_radius=2,
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text("Share Achievement 🎉", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Screenshot the card or tap a share button below",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Container(
                            content=build_share_card(share_type, data),
                            alignment=ft.Alignment.CENTER,
                            padding=tokens.SPACE_MD,
                        ),
                        ft.Row(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                    tooltip="Copy",
                                    on_click=lambda e: page.run_task(_do_copy),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CHAT_ROUNDED,
                                    tooltip="WhatsApp",
                                    icon_color=ft.Colors.GREEN,
                                    on_click=lambda e: _launch(page, f"https://wa.me/?text={encoded}"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FACEBOOK_ROUNDED,
                                    tooltip="Facebook",
                                    icon_color=ft.Colors.BLUE,
                                    on_click=lambda e: _launch(page, f"https://www.facebook.com/sharer/sharer.php?quote={encoded}"),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SHARE_ROUNDED,
                                    tooltip="More",
                                    icon_color=ft.Colors.ORANGE,
                                    on_click=lambda e: page.run_task(_do_more),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                        ),
                        ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_SM,
                    tight=True,
                ),
                padding=tokens.SPACE_LG,
                width=360,
            ),
        )
        page.show_dialog(sheet)
    except Exception as exc:
        logger.warning("share sheet failed: %s", exc)


def offer_share_event(page: ft.Page, event: dict | None) -> bool:
    """Open a share sheet for a gamification event. Returns True if shown."""
    if not event or not isinstance(event, dict):
        return False
    kind = event.get("type")
    data = event.get("data") or {}
    mapping = {
        "level_up": ShareType.LEVEL_UP,
        "xp_milestone": ShareType.XP_MILESTONE,
        "streak": ShareType.STREAK,
        "badge": ShareType.BADGE,
    }
    share_type = mapping.get(kind)
    if share_type is None:
        return False
    show_share_sheet(page, share_type, data)
    return True
