"""Tutor chat — beautiful streaming AI with full student context.

The tutor knows everything about the student and shows granular status
(searching, reading, synthesizing). Video links are rendered as rich
cards with metadata. All media bytes are ephemeral (no bloat).
"""

import contextlib
import re

import flet as ft

from components.credit_dialog import show_credits_dialog
from components.media_preview import MediaPreviewBar
from core.constants import AITaskType
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.audio import AudioService
from services.credit_service import credit_service
from services.file_picker import FilePickerService
from services.gamification import gamification_service


def build_tutor_chat_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    credits_text = ft.Text(f"{state.credits_remaining}", size=12, weight=ft.FontWeight.W_600)
    if not hasattr(state, "credit_text_controls"):
        state.credit_text_controls = []
    state.credit_text_controls.append(credits_text)

    chat_messages: list[dict] = []
    pending_media: list[dict] = []
    session_id = {"value": None}

    messages_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True, auto_scroll=True)

    # Status indicator — shows live AI actions with animation
    status_text = ft.Text("", size=12, color=AppColors.PRIMARY, weight=ft.FontWeight.W_500)
    status_indicator = ft.Container(
        content=ft.Row(
            [
                ft.ProgressRing(width=14, height=14, stroke_width=2, color=AppColors.PRIMARY),
                status_text,
            ],
            spacing=8,
        ),
        padding=ft.Padding(20, 6, 20, 6),
        visible=False,
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
    )

    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Image(src="/icon.png", width=28, height=28),
                                    ft.Column(
                                        [
                                            ft.Text("Akili Tutor", size=16, weight=ft.FontWeight.BOLD),
                                            ft.Text("AI-powered study companion", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ],
                                        spacing=0,
                                        tight=True,
                                    ),
                                ],
                                spacing=8,
                            ),
                        ),
                    ],
                    spacing=4,
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=14, color=AppColors.ACCENT),
                                    credits_text,
                                ],
                                spacing=4,
                            ),
                            padding=ft.Padding(10, 5, 10, 5),
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                            border_radius=16,
                            on_click=lambda e: show_credits_dialog(page, credit_service, ad_service),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD_COMMENT_ROUNDED,
                            icon_size=20,
                            tooltip="New conversation",
                            on_click=lambda e: page.run_task(_new_conversation),
                        ),
                    ],
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(4, 6, 8, 6),
        bgcolor=ft.Colors.SURFACE,
    )

    audio_service = AudioService(page)

    def _on_media_result(data: bytes, mime: str, filename: str):
        m_type = "image" if mime.startswith("image/") else "audio" if mime.startswith("audio/") else "file"
        pending_media.append({"type": m_type, "data": data, "mime": mime, "filename": filename})
        media_preview.set_media(pending_media)

    file_picker = FilePickerService(page, on_result=_on_media_result)

    async def _build_student_context_prompt() -> str:
        snapshot = await db_manager.get_student_snapshot()

        profile = snapshot.get("profile", {})
        lines = [
            "\n[STUDENT PROFILE]",
            f"Name: {profile.get('name', 'Student')} | Level: {profile.get('education_level', 'Unknown')}",
            f"Country: {profile.get('country', 'Unknown')}",
        ]

        courses = snapshot.get("courses", [])
        if courses:
            lines.append("\n[ENROLLED COURSES]")
            for i, c in enumerate(courses, 1):
                lines.append(f"{i}. {c['subject']} — {c['progress_pct']:.0f}% ({c['modules_done']}/{c['modules_total']} modules)")

        quizzes = snapshot.get("recent_quizzes", [])
        if quizzes:
            lines.append("\n[RECENT QUIZ SCORES]")
            for q in quizzes[:5]:
                status = "✓" if q["passed"] else "✗"
                lines.append(f"- {q['subject']} ({q['module']}): {q['pct']}% {status}")

        weak = snapshot.get("weak_areas", [])
        if weak:
            lines.append(f"\n[WEAK AREAS] {', '.join(weak[:5])}")

        pending = snapshot.get("pending_assignments", [])
        if pending:
            lines.append(f"\n[PENDING ASSIGNMENTS] ⚠️ {len(pending)} pending:")
            for a in pending[:3]:
                lines.append(f"  - {a['subject']}: {a['title']} (due {a.get('due_date', 'N/A')[:10]})")

        gam = snapshot.get("gamification", {})
        lines.append(f"\n[GAMIFICATION] {gam.get('level', 'Freshman')} ({gam.get('xp', 0)} XP) | Streak: {gam.get('streak', 0)} days")
        lines.append(f"[CREDITS] {snapshot.get('credits_remaining', 0)} remaining today")

        return "\n".join(lines)

    def _extract_video_links(text: str) -> list[dict]:
        """Extract video links with metadata from markdown text."""
        pattern = r"\[([^\]]+)\]\((https?://[^\)]+)\)"
        matches = re.findall(pattern, text)
        video_links = []
        video_domains = ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")
        video_extensions = (".mp4", ".mkv", ".avi", ".mov", ".3gp", ".webm")
        for title, url in matches:
            is_video = any(d in url.lower() for d in video_domains) or any(url.lower().endswith(ext) for ext in video_extensions)
            if is_video:
                video_links.append({"title": title, "url": url})
        return video_links

    def _extract_video_metadata(text: str, url: str) -> dict:
        """Try to extract video metadata from surrounding text context."""
        metadata = {"duration": "", "publisher": "", "description": ""}
        # Look for common metadata patterns near the URL
        lines = text.split("\n")
        for line in lines:
            lower = line.lower()
            if "duration" in lower or "min" in lower:
                duration_match = re.search(r"(\d+:\d+(?::\d+)?|\d+\s*min)", line)
                if duration_match:
                    metadata["duration"] = duration_match.group(1)
            if "by " in lower or "from " in lower:
                pub_match = re.search(r"(?:by|from)\s+([A-Za-z0-9\s]+)", line, re.IGNORECASE)
                if pub_match:
                    metadata["publisher"] = pub_match.group(1).strip()[:30]
        return metadata

    async def _play_video(url: str, title: str):
        page.session.set("playing_video_url", url)
        page.session.set("playing_video_title", title)
        if ad_service:
            await ad_service.show_interstitial()
        await navigate("/video_player")

    async def _handle_link_tap(href: str):
        video_domains = ("youtube.com", "youtu.be", "vimeo.com")
        video_extensions = (".mp4", ".mkv", ".avi", ".mov", ".3gp", ".webm")
        if any(d in href.lower() for d in video_domains) or any(href.lower().endswith(ext) for ext in video_extensions):
            await _play_video(href, "Video")
        else:
            await page.launch_url_async(href)

    def _build_video_card(title: str, url: str, metadata: dict | None = None):
        """Rich video card with metadata, thumbnail placeholder, and play button."""
        meta = metadata or {}
        subtitle_parts = []
        if meta.get("duration"):
            subtitle_parts.append(f"⏱ {meta['duration']}")
        if meta.get("publisher"):
            subtitle_parts.append(f"by {meta['publisher']}")
        subtitle = " · ".join(subtitle_parts) if subtitle_parts else "Tap to play video"

        # Determine platform icon
        platform_icon = ft.Icons.PLAY_CIRCLE_FILL_ROUNDED
        platform_color = AppColors.PRIMARY
        if "youtube" in url.lower() or "youtu.be" in url.lower():
            platform_color = ft.Colors.RED_700

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(platform_icon, size=32, color=platform_color),
                        width=56,
                        height=56,
                        bgcolor=ft.Colors.with_opacity(0.08, platform_color),
                        border_radius=12,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(title, size=14, weight=ft.FontWeight.W_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=3,
                        expand=True,
                        tight=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        icon_color=platform_color,
                        icon_size=28,
                        on_click=lambda e: page.run_task(_play_video, url, title),
                        bgcolor=ft.Colors.with_opacity(0.06, platform_color),
                        style=ft.ButtonStyle(shape=ft.CircleBorder()),
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 10, 8, 10),
            border_radius=AppStyles.RADIUS,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            margin=ft.Margin(0, 4, 0, 4),
        )

    def _build_user_bubble(text: str):
        """Beautiful user message bubble."""
        return ft.Row(
            [
                ft.Container(
                    content=ft.Text(text, size=15, color=ft.Colors.WHITE),
                    padding=ft.Padding(16, 12, 16, 12),
                    border_radius=ft.BorderRadius(20, 20, 4, 20),
                    bgcolor=AppColors.PRIMARY,
                    width=(page.width or 400) * 0.75,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
        )

    def _build_assistant_bubble(content: str):
        """Beautiful assistant message bubble with video cards."""
        video_links = _extract_video_links(content)

        controls = []
        # Avatar + markdown
        md = ft.Markdown(
            content or "...",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            on_tap_link=lambda e: page.run_task(_handle_link_tap, e.href),
        )
        controls.append(md)

        # Video cards with metadata
        if video_links:
            controls.append(ft.Container(height=6))
            for v in video_links:
                meta = _extract_video_metadata(content, v["url"])
                controls.append(_build_video_card(v["title"], v["url"], meta))

        bubble = ft.Container(
            content=ft.Column(controls, tight=True, spacing=4),
            padding=ft.Padding(16, 12, 16, 12),
            border_radius=ft.BorderRadius(20, 20, 20, 4),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            width=(page.width or 400) * 0.78,
        )

        return ft.Row(
            [
                ft.Container(
                    content=ft.Image(src="/icon.png", width=24, height=24),
                    width=32,
                    height=32,
                    border_radius=16,
                    bgcolor=ft.Colors.with_opacity(0.06, AppColors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                ),
                bubble,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _render_chat():
        messages_col.controls.clear()
        for idx, msg in enumerate(chat_messages):
            if msg["role"] == "user":
                messages_col.controls.append(_build_user_bubble(msg["content"]))
            elif msg["role"] == "assistant":
                messages_col.controls.append(_build_assistant_bubble(msg["content"]))

            # Strategic ad placement in between tutor messages (after the 2nd message, and every 4 messages after)
            if ad_service and idx > 0 and (idx == 1 or (idx - 1) % 4 == 0):
                messages_col.controls.append(ad_service.get_banner_ad())

        # Synchronize dynamic offline state
        offline_bar.visible = not state.is_online
        input_bar_field.disabled = not state.is_online
        attach_btn.disabled = not state.is_online
        send_btn.disabled = not state.is_online

        page.update()

    def _update_streaming_bubble(msg_idx: int, content: str):
        """Update the last assistant bubble during streaming."""
        if msg_idx < len(messages_col.controls):
            row = messages_col.controls[msg_idx]
            # Row > [avatar, bubble_container]
            if len(row.controls) >= 2:
                bubble = row.controls[1]
                if bubble.content and bubble.content.controls:
                    md = bubble.content.controls[0]
                    if isinstance(md, ft.Markdown):
                        md.value = content
                        with contextlib.suppress(Exception):
                            page.update()

    async def _on_send(text: str):
        if not text.strip() and not pending_media:
            return

        ok = await credit_service.spend("tutor_question")
        if not ok:
            page.snack_bar = ft.SnackBar(ft.Text("Not enough credits"), bgcolor=ft.Colors.ERROR)
            page.snack_bar.open = True
            page.update()
            return

        media_to_process = list(pending_media)
        pending_media.clear()
        media_preview.set_media([])

        # Add user message
        chat_messages.append({"role": "user", "content": text})
        _render_chat()

        # Add assistant placeholder
        msg_idx = len(chat_messages)
        chat_messages.append({"role": "assistant", "content": ""})
        messages_col.controls.append(_build_assistant_bubble(""))
        page.update()

        # Build student context
        context_prompt = await _build_student_context_prompt()

        system_prompt = (
            f"You are Akili, a warm and knowledgeable AI tutor.\n"
            f"{context_prompt}\n\n"
            f"[BEHAVIOR]\n"
            f"- If the student has pending assignments, gently remind them.\n"
            f"- Reference their actual courses and progress when relevant.\n"
            f"- Focus on their weak areas when they ask for help.\n"
            f"- Use beautiful markdown formatting.\n"
            f"- For math, use LaTeX: $inline$ or $$block$$.\n"
            f"- When sharing videos, include title, duration if known, and source.\n"
            f"- Cite your sources at the end of factual responses.\n"
            f"- Be encouraging, concise, and academically rigorous.\n"
            f"- IMPORTANT: When explaining concepts, remind the student to write key points "
            f"in their notebook. Say things like '📓 Jot this down in your notebook!' or "
            f"'This is a key formula — add it to your notes!' This helps them prepare for "
            f"quizzes and assignments where they can reference their notebooks."
        )

        def _update_status(msg):
            status_text.value = msg
            status_indicator.visible = True
            page.update()

        try:
            full_response = ""
            async for chunk in ai_service.chat_stream(
                messages=chat_messages[:-1],
                system_prompt=system_prompt,
                task_type=AITaskType.TEXT,
                media=media_to_process[0] if media_to_process else None,
                on_status=_update_status,
            ):
                if isinstance(chunk, str):
                    full_response += chunk
                    chat_messages[msg_idx]["content"] = full_response
                    _update_streaming_bubble(msg_idx, full_response)

            # Discard media bytes — no bloat
            for m in media_to_process:
                m["data"] = None

            if full_response:
                chat_messages[msg_idx]["content"] = full_response
                await gamification_service.award_xp("tutor_question")
            else:
                chat_messages[msg_idx]["content"] = "Sorry, I couldn't process that. Please try again."

        except Exception as e:
            chat_messages[msg_idx]["content"] = "⚠️ Something went wrong. Please try again."
            print(f"[Tutor] Error: {e}", flush=True)

        # Save and refresh
        if session_id["value"]:
            await db_manager.save_chat(session_id["value"], chat_messages)

        status_indicator.visible = False
        _render_chat()

    async def _handle_mic(stop: bool = False):
        if not stop:
            await audio_service.start_recording()
            return
        result = await audio_service.stop_recording()
        if not result:
            return
        data, mime = result
        page.snack_bar = ft.SnackBar(ft.Text("🎙️ Transcribing..."), bgcolor=AppColors.PRIMARY)
        page.snack_bar.open = True
        page.update()

        transcript = await ai_service.transcribe_audio(data, mime)
        if transcript and not transcript.startswith("["):
            input_bar_field.value = transcript
            input_bar_field.update()
            page.snack_bar = ft.SnackBar(ft.Text("🗣️ Transcribed!"), bgcolor=AppColors.SUCCESS)
        else:
            err_msg = transcript.replace("[", "").replace("]", "") if transcript else "Could not transcribe."
            page.snack_bar = ft.SnackBar(ft.Text(f"❌ {err_msg}"), bgcolor=AppColors.ERROR)
        page.snack_bar.open = True
        page.update()

    async def _new_conversation():
        chat_messages.clear()
        session_id["value"] = await db_manager.new_chat_session()
        _render_chat()

    async def _load_session():
        session_id["value"] = await db_manager.get_latest_chat_session()
        history = await db_manager.get_chat(session_id["value"])
        if history:
            chat_messages.extend(history)
            _render_chat()

    async def _retry_connection(e=None):
        from core.state import check_internet_connection

        is_connected = await check_internet_connection()
        state.is_online = is_connected

        offline_bar.visible = not is_connected
        input_bar_field.disabled = not is_connected
        attach_btn.disabled = not is_connected
        send_btn.disabled = not is_connected

        if is_connected:
            page.snack_bar = ft.SnackBar(ft.Text("Back online!"), bgcolor=AppColors.SUCCESS)
            page.snack_bar.open = True
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Still offline. Please check your network."), bgcolor=AppColors.ERROR)
            page.snack_bar.open = True

        page.update()

    media_preview = MediaPreviewBar(on_remove=lambda item: pending_media.remove(item))

    # ── Input bar ─────────────────────────────────────────────
    input_bar_field = ft.TextField(
        hint_text="Ask Akili anything...",
        border_radius=24,
        filled=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        content_padding=ft.Padding(16, 10, 8, 10),
        expand=True,
        max_lines=4,
        on_submit=lambda e: page.run_task(_on_send, e.control.value) if e.control.value else None,
        disabled=not state.is_online,
    )

    def _handle_send_click(e):
        text = input_bar_field.value or ""
        input_bar_field.value = ""
        page.update()
        page.run_task(_on_send, text)

    attach_btn = ft.IconButton(
        icon=ft.Icons.ATTACH_FILE_ROUNDED,
        icon_size=22,
        tooltip="Attach image",
        on_click=lambda e: page.run_task(file_picker.pick_image),
        disabled=not state.is_online,
    )

    send_btn = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED,
        icon_size=22,
        icon_color=AppColors.PRIMARY,
        on_click=_handle_send_click,
        tooltip="Send message",
        disabled=not state.is_online,
    )

    offline_bar = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=16, color=ft.Colors.AMBER_800),
                ft.Text("You are offline. Old messages are readable.", size=12, color=ft.Colors.AMBER_800, expand=True),
                ft.TextButton("Retry", style=ft.ButtonStyle(color=AppColors.PRIMARY), on_click=lambda e: page.run_task(_retry_connection)),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.AMBER),
        padding=ft.Padding(12, 6, 12, 6),
        border_radius=AppStyles.RADIUS_SMALL,
        margin=ft.Margin(12, 0, 12, 6),
        visible=not state.is_online,
    )

    input_bar = ft.Container(
        content=ft.Row(
            [
                attach_btn,
                input_bar_field,
                send_btn,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.END,
        ),
        padding=ft.Padding(8, 6, 8, 10),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border(top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE))),
    )

    # Welcome message if no history
    welcome = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Image(src="/icon.png", width=64, height=64),
                ft.Container(height=12),
                ft.Text("Hi! I'm Akili 👋", size=22, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Your AI study companion. Ask me anything\nabout your courses, homework, or exams!",
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=24),
                ft.Row(
                    [
                        ft.OutlinedButton("📚 Help me study", on_click=lambda e: _quick_prompt("Help me study for my upcoming quiz")),
                        ft.OutlinedButton("📝 My assignments", on_click=lambda e: _quick_prompt("What assignments do I have pending?")),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                    wrap=True,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
        visible=True,
    )

    def _quick_prompt(text: str):
        if not state.is_online:
            return
        input_bar_field.value = text
        page.update()
        _handle_send_click(None)

    page.run_task(_load_session)

    return ft.View(
        route="/tutor",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            status_indicator,
                            ft.Container(
                                content=ft.Stack(
                                    [
                                        welcome,
                                        messages_col,
                                    ]
                                ),
                                expand=True,
                                padding=ft.Padding(12, 6, 12, 6),
                            ),
                            media_preview,
                            offline_bar,
                            input_bar,
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
        spacing=0,
    )
