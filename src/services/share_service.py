"""Share service — generates beautiful shareable content for achievements.

Two sharing modes:
1. Text share: Emoji-rich formatted text with Play Store link → WhatsApp, SMS, clipboard
2. Card display: On-screen achievement card that users can screenshot

The card always includes the Akili branding and Play Store link so every
share acts as organic marketing.
"""

import urllib.parse

import flet as ft

from core.constants import APP_FULL_NAME, APP_TAGLINE, PLAYSTORE_URL, SHARE_HASHTAG
from core.state import state
from core.theme import AppColors


class ShareType:
    QUIZ_RESULT = "quiz_result"
    EXAM_RESULT = "exam_result"
    ASSIGNMENT_RESULT = "assignment_result"
    XP_MILESTONE = "xp_milestone"
    STREAK = "streak"
    BADGE = "badge"
    LEVEL_UP = "level_up"
    COURSE_COMPLETE = "course_complete"


def _build_share_text(share_type: str, data: dict) -> str:
    """Generate emoji-rich shareable text with Play Store link."""
    name = data.get("name", state.user_name or "A student")
    lines = []

    if share_type == ShareType.QUIZ_RESULT:
        pct = data.get("pct", 0)
        subject = data.get("subject", "")
        module = data.get("module", "")
        emoji = "🏆" if pct >= 90 else "⭐" if pct >= 70 else "📊"
        lines = [
            f"{emoji} Quiz Result!",
            "",
            f"📚 {subject} — {module}",
            f"📊 Score: {pct:.0f}%",
            f"{'💯 Perfect Score!' if pct >= 100 else '🎯 Great job!' if pct >= 70 else '📖 Keep studying!'}",
        ]

    elif share_type == ShareType.EXAM_RESULT:
        grade = data.get("grade", "N/A")
        pct = data.get("pct", 0)
        subject = data.get("subject", "")
        duration = data.get("duration", "")
        emoji = "🏆" if grade in ("A", "A+") else "🌟" if grade in ("B", "B+") else "📝"
        lines = [
            f"{emoji} Mock Exam Completed!",
            "",
            f"📚 Subject: {subject}",
            f"📊 Grade: {grade} ({pct:.0f}%)",
        ]
        if duration:
            lines.append(f"⏱ Time: {duration}")

    elif share_type == ShareType.ASSIGNMENT_RESULT:
        pct = data.get("pct", 0)
        subject = data.get("subject", "")
        title = data.get("title", "")
        lines = [
            "✅ Assignment Graded!",
            "",
            f"📚 {subject}: {title}",
            f"📊 Score: {pct:.0f}%",
        ]

    elif share_type == ShareType.XP_MILESTONE:
        xp = data.get("xp", 0)
        level = data.get("level", "Freshman")
        lines = [
            "⚡ XP Milestone!",
            "",
            f"🎮 Total XP: {xp:,}",
            f"🏅 Level: {level}",
        ]

    elif share_type == ShareType.STREAK:
        streak = data.get("streak", 0)
        lines = [
            f"🔥 {streak}-Day Study Streak!",
            "",
            f"📅 {name} has been studying for {streak} days straight!",
        ]

    elif share_type == ShareType.BADGE:
        badge_name = data.get("badge_name", "")
        badge_icon = data.get("badge_icon", "🏅")
        badge_desc = data.get("badge_desc", "")
        lines = [
            f"{badge_icon} New Badge Earned!",
            "",
            f"🏅 {badge_name}",
            f"📝 {badge_desc}",
        ]

    elif share_type == ShareType.LEVEL_UP:
        new_level = data.get("level", "")
        level_icon = data.get("icon", "🎓")
        lines = [
            f"{level_icon} Level Up!",
            "",
            f"🎓 {name} is now a {new_level}!",
        ]

    elif share_type == ShareType.COURSE_COMPLETE:
        subject = data.get("subject", "")
        lines = [
            "🎓 Course Completed!",
            "",
            f"📚 {name} completed {subject}!",
        ]

    # Common footer on every share
    lines.extend(
        [
            "",
            f"— {APP_FULL_NAME}",
            f"📲 Download: {PLAYSTORE_URL}",
            SHARE_HASHTAG,
        ]
    )

    return "\n".join(lines)


def build_share_card(page: ft.Page, share_type: str, data: dict) -> ft.Container:
    """Build a beautiful on-screen achievement card (screenshot target)."""
    name = data.get("name", state.user_name or "Student")
    card_controls = []

    # Card header — branding
    card_controls.append(
        ft.Row(
            [
                ft.Image(src="/icon.png", width=28, height=28),
                ft.Column(
                    [
                        ft.Text("Akili", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text(APP_TAGLINE, size=10, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                    ],
                    spacing=0,
                    tight=True,
                ),
            ],
            spacing=8,
        )
    )
    card_controls.append(ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)))

    # Achievement-specific content
    if share_type == ShareType.QUIZ_RESULT:
        pct = data.get("pct", 0)
        emoji = "🏆" if pct >= 90 else "⭐" if pct >= 70 else "📊"
        card_controls.extend(
            [
                ft.Text(f"{emoji} Quiz Result", size=14, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Text(f"{pct:.0f}%", size=48, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(data.get("subject", ""), size=14, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
                ft.Text(data.get("module", ""), size=12, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
            ]
        )

    elif share_type == ShareType.EXAM_RESULT:
        grade = data.get("grade", "N/A")
        pct = data.get("pct", 0)
        card_controls.extend(
            [
                ft.Text("📝 Mock Exam", size=14, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Row(
                    [
                        ft.Text(grade, size=56, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Column(
                            [
                                ft.Text(f"{pct:.0f}%", size=20, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                                ft.Text(data.get("subject", ""), size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=16,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ]
        )

    elif share_type == ShareType.ASSIGNMENT_RESULT:
        pct = data.get("pct", 0)
        card_controls.extend(
            [
                ft.Text("✅ Assignment", size=14, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Text(f"{pct:.0f}%", size=48, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(data.get("subject", ""), size=14, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
            ]
        )

    elif share_type == ShareType.STREAK:
        streak = data.get("streak", 0)
        card_controls.extend(
            [
                ft.Text("🔥 Study Streak", size=14, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Text(f"{streak}", size=56, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text("days in a row!", size=16, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
            ]
        )

    elif share_type == ShareType.LEVEL_UP:
        level_icon = data.get("icon", "🎓")
        card_controls.extend(
            [
                ft.Text(f"{level_icon} Level Up!", size=14, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Text(data.get("level", ""), size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(f"{data.get('xp', 0):,} XP", size=16, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
            ]
        )

    elif share_type == ShareType.BADGE:
        card_controls.extend(
            [
                ft.Text(data.get("badge_icon", "🏅"), size=48),
                ft.Text(data.get("badge_name", ""), size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(data.get("badge_desc", ""), size=13, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
            ]
        )

    elif share_type == ShareType.COURSE_COMPLETE:
        card_controls.extend(
            [
                ft.Text("🎓", size=48),
                ft.Text("Course Completed!", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(data.get("subject", ""), size=16, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
            ]
        )

    # Student name + date
    from datetime import datetime

    card_controls.append(ft.Container(height=8))
    card_controls.append(
        ft.Row(
            [
                ft.Text(name, size=12, weight=ft.FontWeight.W_600, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Text(datetime.now().strftime("%b %d, %Y"), size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    )

    return ft.Container(
        content=ft.Column(card_controls, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding(24, 20, 24, 20),
        border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[AppColors.PRIMARY, AppColors.ACCENT],
        ),
        width=320,
    )


def show_share_sheet(page: ft.Page, share_type: str, data: dict):
    """Show a beautiful share bottom sheet with card + sharing options."""
    share_text = _build_share_text(share_type, data)
    card = build_share_card(page, share_type, data)

    def _copy(e):
        page.set_clipboard(share_text)
        page.snack_bar = ft.SnackBar(ft.Text("📋 Copied to clipboard!"), bgcolor=AppColors.SUCCESS)
        page.snack_bar.open = True
        page.update()

    def _share_whatsapp(e):
        encoded = urllib.parse.quote(share_text)
        page.run_task(page.launch_url_async, f"https://wa.me/?text={encoded}")

    def _share_generic(e):
        encoded = urllib.parse.quote(share_text)
        page.run_task(
            page.launch_url_async,
            f"https://www.facebook.com/sharer/sharer.php?quote={encoded}",
        )

    def _close_sheet():
        sheet.open = False
        page.update()

    sheet_content = ft.Container(
        content=ft.Column(
            [
                # Handle bar
                ft.Container(
                    content=ft.Container(width=40, height=4, border_radius=2, bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding(0, 8, 0, 8),
                ),
                ft.Text("Share Achievement 🎉", size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Screenshot the card or tap a share button below",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                # Achievement card (screenshot target)
                ft.Container(
                    content=card,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=16),
                # Share buttons
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.CONTENT_COPY_ROUNDED, size=24, color=AppColors.PRIMARY),
                                        width=52,
                                        height=52,
                                        border_radius=16,
                                        bgcolor=ft.Colors.with_opacity(0.08, AppColors.PRIMARY),
                                        alignment=ft.Alignment.CENTER,
                                        on_click=_copy,
                                    ),
                                    ft.Text("Copy", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.CHAT_ROUNDED, size=24, color=ft.Colors.GREEN_700),
                                        width=52,
                                        height=52,
                                        border_radius=16,
                                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN),
                                        alignment=ft.Alignment.CENTER,
                                        on_click=_share_whatsapp,
                                    ),
                                    ft.Text("WhatsApp", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.FACEBOOK_ROUNDED, size=24, color=ft.Colors.BLUE_700),
                                        width=52,
                                        height=52,
                                        border_radius=16,
                                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE),
                                        alignment=ft.Alignment.CENTER,
                                        on_click=_share_generic,
                                    ),
                                    ft.Text("Facebook", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.SHARE_ROUNDED, size=24, color=ft.Colors.ORANGE_700),
                                        width=52,
                                        height=52,
                                        border_radius=16,
                                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
                                        alignment=ft.Alignment.CENTER,
                                        on_click=_copy,  # Fallback: copy for other platforms
                                    ),
                                    ft.Text("Other", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=4,
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                ),
                ft.Container(height=8),
                ft.TextButton("Close", on_click=lambda e: _close_sheet()),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            tight=True,
        ),
        padding=ft.Padding(20, 8, 20, 24),
        border_radius=ft.BorderRadius(20, 20, 0, 0),
    )

    sheet = ft.BottomSheet(content=sheet_content)
    page.overlay.append(sheet)
    sheet.open = True
    page.update()
