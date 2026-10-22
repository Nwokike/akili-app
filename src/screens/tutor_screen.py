"""Tutor screen — the agentic chat with the AI tutor.

Ported from DDGS chat_screen.py structure (the house standard).

One transcript owns what the user sees; the model history is projected
from it. Every transcript write goes through a use_state UPDATER function
so the emit handler — which runs across many renders — always sees the
latest value instead of a stale capture. Streaming text and reasoning are
throttled so a long answer does not repaint the list per token.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

import flet as ft

from core import tokens
from core.constants import LBL_TUTOR_PLACEHOLDER
from core.theme import AppColors
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger("TutorScreen")


def _history_from_turns(turns: list[dict]) -> list[dict]:
    """Project the display transcript to flat user/assistant pairs."""
    out: list[dict] = []
    for turn in turns:
        role = turn.get("role")
        text = (turn.get("text") or "").strip()
        if role in ("user", "assistant") and text:
            out.append({"role": role, "content": text})
    return out


def _find_streaming(turns: list[dict]) -> int:
    for i in range(len(turns) - 1, -1, -1):
        t = turns[i]
        if t.get("role") == "assistant" and t.get("streaming"):
            return i
    return -1


def _render_step_row(step: dict) -> ft.Control:
    status = step.get("status", "running")
    if status == "done":
        icon, color = ft.Icons.CHECK_CIRCLE_ROUNDED, AppColors.SUCCESS
    elif status == "error":
        icon, color = ft.Icons.ERROR_OUTLINE_ROUNDED, AppColors.ERROR
    else:
        icon, color = ft.Icons.AUTORENEW_ROUNDED, AppColors.PRIMARY
    label = str(step.get("label") or "")
    suffix = ""
    if status == "done" and step.get("count"):
        suffix = f" · {step['count']} results"
    elif status == "error":
        suffix = f" · {str(step.get('error') or '')[:80]}"
    return ft.Row(
        controls=[
            ft.Icon(icon, size=tokens.ICON_XS, color=color),
            ft.Text(f"{label}{suffix}", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
        ],
        spacing=tokens.SPACE_XS,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _render_cards(cards: list) -> ft.Control | None:
    if not cards:
        return None
    seen: set[str] = set()
    rows: list[ft.Control] = []
    for card in cards:
        url = getattr(card, "url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        host = url.split("/")[2] if "//" in url else url
        is_video = getattr(card, "kind", "") == "videos"
        rows.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.PLAY_CIRCLE_ROUNDED if is_video else ft.Icons.PUBLIC_ROUNDED,
                            size=tokens.ICON_SM,
                            color=AppColors.PRIMARY,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    str(getattr(card, "title", ""))[:80],
                                    size=tokens.FONT_SM,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(host[:50], size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=1,
                            expand=True,
                            tight=True,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_SM),
                border_radius=tokens.RADIUS_SM,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            )
        )
        if len(rows) >= 5:
            break
    if not rows:
        return None
    return ft.Column(controls=rows, spacing=tokens.SPACE_XS, tight=True)


def _render_turn(turn: dict) -> ft.Control:
    role = turn.get("role")
    if role == "user":
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(turn.get("text", ""), size=tokens.FONT_MD, selectable=True, color=ft.Colors.ON_PRIMARY),
                    padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=AppColors.PRIMARY,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
        )

    controls: list[ft.Control] = []

    thought = turn.get("thought") or ""
    if thought.strip():
        from components.thinking_block import ThinkingBlock

        controls.append(
            ThinkingBlock(
                thought,
                streaming=bool(turn.get("streaming")) and not (turn.get("text") or "").strip(),
                expanded=bool(turn.get("streaming")) or not (turn.get("text") or "").strip(),
            )
        )

    for step in turn.get("steps") or []:
        controls.append(_render_step_row(step))

    cards_control = _render_cards(turn.get("cards") or [])
    if cards_control is not None:
        controls.append(cards_control)

    text = turn.get("text") or ""
    if text.strip():
        controls.append(ft.Markdown(text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB))

    error = turn.get("error")
    if error:
        label = {
            "credits": "Out of AI credits. Add credits from the wallet.",
            "midstream": "The AI stopped mid-answer. You were charged for what you saw.",
            "empty": "The AI produced no answer. You were not charged.",
            "unavailable": turn.get("error_message") or "The AI is unavailable right now.",
        }.get(error, "Something went wrong.")
        controls.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=tokens.ICON_SM, color=AppColors.WARNING),
                        ft.Text(label, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT, expand=True),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
                padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_SM),
                border_radius=tokens.RADIUS_SM,
                bgcolor=ft.Colors.with_opacity(0.06, AppColors.WARNING),
            )
        )

    if turn.get("stopped") and not error:
        controls.append(ft.Text("Stopped early.", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT, italic=True))

    if turn.get("nudge"):
        controls.append(ft.Text(str(turn.get("nudge")), size=tokens.FONT_XS, italic=True, color=AppColors.WARNING))

    if not controls:
        controls.append(
            ft.Row(
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=AppColors.PRIMARY),
                    ft.Text("Working…", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=tokens.SPACE_XS,
            )
        )

    cost = turn.get("cost")
    if cost is not None and not turn.get("streaming"):
        meta = f"{turn.get('steps_count', 0)} steps · {cost} credits"
        model = turn.get("model")
        if model:
            meta += f" · {model}"
        usage = turn.get("tokens")
        if isinstance(usage, dict):
            total = int(usage.get("in") or 0) + int(usage.get("out") or 0)
            if total:
                meta += f" · {total:,} tok"
        controls.append(ft.Text(meta, size=tokens.FONT_XS, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)))

    return ft.Container(content=ft.Column(controls=controls, spacing=tokens.SPACE_SM, tight=True))


_SUGGESTIONS = (
    ("Explain photosynthesis for JSS 3", ft.Icons.SCIENCE_ROUNDED),
    ("Help me solve quadratic equations", ft.Icons.CALCULATE_ROUNDED),
    ("Summarise the causes of World War 1", ft.Icons.HISTORY_EDU_ROUNDED),
    ("Find a video explaining the water cycle", ft.Icons.PLAY_CIRCLE_ROUNDED),
)


@ft.component
def TutorScreen():
    """The AI tutor chat."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    turns, set_turns = ft.use_state([])
    busy, set_busy = ft.use_state(False)
    draft, set_draft = ft.use_state("")
    media_tick, set_media_tick = ft.use_state(0)  # bump to repaint the preview bar
    cancel_ref = ft.use_ref(None)
    task_ref = ft.use_ref(None)
    flush_ref = ft.use_ref(0.0)
    media_ref = ft.use_ref([])  # pending attachments: [{type, data, mime, filename}]
    audio_ref = ft.use_ref(None)
    picker_ref = ft.use_ref(None)

    page = ft.context.page

    def _refresh_media() -> None:
        set_media_tick(media_tick + 1)

    def _classify(mime: str) -> str:
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("audio/"):
            return "audio"
        return "file"

    def _on_media_result(data: bytes, mime: str, filename: str) -> None:
        media_ref.current = [*media_ref.current, {"type": _classify(mime), "data": data, "mime": mime, "filename": filename}]
        _refresh_media()

    def _remove_media(item: dict) -> None:
        media_ref.current = [m for m in media_ref.current if m is not item]
        _refresh_media()

    def _ensure_services():
        from services.audio import AudioService
        from services.file_picker import FilePickerService

        if audio_ref.current is None:
            audio_ref.current = AudioService(page)
        if picker_ref.current is None:
            picker = FilePickerService(page, on_result=_on_media_result)
            picker_ref.current = picker
            with contextlib.suppress(Exception):
                page.overlay.append(picker.picker)

    async def _on_mic() -> None:
        _ensure_services()
        audio = audio_ref.current
        if audio.is_recording:
            result = await audio.stop_recording()
            if result is None:
                return
            data, mime = result
            _transcribe_into_draft(data, mime)
        else:
            await audio.start_recording()

    def _transcribe_into_draft(data: bytes, mime: str) -> None:
        async def _run():
            from services.gateway_media import is_failure, transcribe_audio

            text = await transcribe_audio(data, mime)
            if text and not is_failure(text):
                set_draft(f"{draft} {text}".strip() if draft.strip() else text)

        asyncio.ensure_future(_run())

    def _on_attach() -> None:
        _ensure_services()
        picker = picker_ref.current

        async def _pick():
            await picker.pick_image()

        asyncio.ensure_future(_pick())

    # ── Transcript writers (updater fns — never stale) ──
    def _append(turn: dict) -> None:
        set_turns(lambda prev: [*prev, turn])

    def _update_streaming(mutate) -> None:
        def _updater(prev):
            idx = _find_streaming(prev)
            if idx < 0:
                return prev
            new = list(prev)
            turn = dict(new[idx])
            mutate(turn)
            new[idx] = turn
            return new

        set_turns(_updater)

    # ── Emit protocol consumer ──
    def _emit(kind: str, data: dict) -> None:
        if kind == "user":
            _append({"role": "user", "text": data.get("text", "")})
        elif kind == "assistant_start":
            _append(
                {
                    "role": "assistant",
                    "text": "",
                    "thought": "",
                    "steps": [],
                    "cards": [],
                    "streaming": True,
                }
            )
        elif kind == "text_partial":
            now = time.monotonic()
            if now - flush_ref.current < 0.2:
                return
            flush_ref.current = now
            _update_streaming(lambda t: t.update({"text": data.get("text", "")}))
        elif kind == "thought":
            now = time.monotonic()
            if now - flush_ref.current < 0.5:
                return
            flush_ref.current = now
            _update_streaming(lambda t: t.update({"thought": data.get("text", "")}))
        elif kind == "step_start":
            _update_streaming(lambda t: t.setdefault("steps", []).append({"id": data.get("id"), "label": data.get("label"), "status": "running"}))
        elif kind == "step_done":

            def _done(t):
                for s in t.get("steps", []):
                    if s.get("id") == data.get("id"):
                        s.update({"status": "done", "count": data.get("count", 0)})
                        return

            _update_streaming(_done)
        elif kind == "step_error":

            def _err(t):
                for s in t.get("steps", []):
                    if s.get("id") == data.get("id"):
                        s.update({"status": "error", "error": data.get("error")})
                        return

            _update_streaming(_err)
        elif kind == "results":
            _update_streaming(lambda t: t.update({"cards": [*(t.get("cards") or []), *data.get("results", [])]}))
        elif kind == "text_final":
            _update_streaming(
                lambda t: t.update(
                    {
                        "text": data.get("text", t.get("text", "")),
                        "model": data.get("model"),
                        "cost": data.get("cost", 0),
                        "steps_count": data.get("steps", 0),
                        "tokens": data.get("tokens"),
                        "streaming": False,
                    }
                )
            )
        elif kind == "stopped":
            _update_streaming(lambda t: t.update({"stopped": True, "streaming": False, "cost": data.get("cost", 0)}))
        elif kind == "nudge":
            _update_streaming(lambda t: t.update({"nudge": data.get("text", "")}))
        elif kind == "error":
            _update_streaming(lambda t: t.update({"error": data.get("kind"), "error_message": data.get("message"), "cost": data.get("cost", 0), "streaming": False}))

    async def _run(user_text: str, history: list[dict], media: list[dict]) -> None:
        from core.constants import COST_TUTOR_MEDIA

        cancel = asyncio.Event()
        cancel_ref.current = cancel
        set_busy(True)
        app_state.chat_busy = True
        try:
            from agent import chat_agent
            from services.gateway_media import analyze_image, is_failure

            # Pre-translate attachments to text (v1 parity): the router turn
            # itself stays text-only. Only the first attachment is sent.
            surcharge = 0
            enriched = user_text
            first = next((m for m in media if m.get("type") in ("image", "audio")), None)
            if first is not None:
                surcharge = COST_TUTOR_MEDIA
                if first["type"] == "image":
                    description = await analyze_image(first["data"], first["mime"])
                    if not is_failure(description):
                        enriched = f"{user_text}\n\n[Extracted Image Context]: {description}"
                elif first["type"] == "audio":
                    from services.gateway_media import transcribe_audio

                    transcript = await transcribe_audio(first["data"], first["mime"])
                    if not is_failure(transcript):
                        enriched = f"{user_text}\n\n[Voice Note Transcription]: {transcript}"
                for m in media:
                    m["data"] = None  # ephemeral — never persisted

            hub = getattr(page, "_akili_mcp_hub", None)
            extra = list(hub.tools or []) if hub is not None else []
            await chat_agent.run_turn(enriched, history, _emit, cancel, extra_tools=extra, media_surcharge=surcharge)
        except Exception:
            logger.exception("turn failed")
        finally:
            set_busy(False)
            app_state.chat_busy = False
            task_ref.current = None

    def _send(text: str) -> None:
        text = (text or "").strip()
        media = list(media_ref.current)
        if (not text and not media) or busy:
            return
        set_draft("")
        media_ref.current = []
        _refresh_media()
        history = _history_from_turns(turns)
        task_ref.current = asyncio.ensure_future(_run(text, history, media))

    def _stop() -> None:
        if cancel_ref.current is not None:
            cancel_ref.current.set()
        task = task_ref.current
        if task is not None and not task.done():
            task.cancel()

    # ── Chrome ──
    from components.credit_pill import build_credit_pill, build_wallet_dialog
    from components.model_picker import build_model_dialog, build_model_pill

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Text("AI Tutor", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
                build_model_pill(on_click=lambda e: page.show_dialog(build_model_dialog(page))),
                build_credit_pill(on_click=lambda e: page.show_dialog(build_wallet_dialog(page))),
            ],
            spacing=tokens.SPACE_XS,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    body_controls: list[ft.Control] = []
    if not turns:
        body_controls.append(ft.Container(height=tokens.SPACE_XL))
        body_controls.append(
            ft.Column(
                controls=[
                    ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=tokens.ICON_FEATURE, color=ft.Colors.with_opacity(0.3, AppColors.PRIMARY)),
                    ft.Text("Ask me anything", size=tokens.FONT_XL, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "I can search the web and find videos to explain any topic.",
                        size=tokens.FONT_SM,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_XS,
            )
        )
        for label, icon in _SUGGESTIONS:
            body_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(icon, size=tokens.ICON_SM, color=AppColors.PRIMARY),
                            ft.Text(label, size=tokens.FONT_SM, expand=True),
                        ],
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=lambda e, t=label: _send(t),
                )
            )
    else:
        for turn in turns:
            body_controls.append(_render_turn(turn))

    list_view = ft.ListView(
        controls=body_controls,
        expand=True,
        spacing=tokens.SPACE_MD,
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_MD),
        auto_scroll=True,
    )

    from components.media_preview import MediaPreviewBar

    preview_bar = MediaPreviewBar(on_remove=_remove_media)
    preview_bar.set_media(media_ref.current)

    composer = ft.Container(
        content=ft.Column(
            controls=[
                preview_bar,
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ATTACH_FILE_ROUNDED,
                            tooltip="Attach an image",
                            icon_size=tokens.ICON_MD,
                            on_click=lambda e: _on_attach(),
                        ),
                        ft.TextField(
                            value=draft,
                            hint_text=LBL_TUTOR_PLACEHOLDER,
                            multiline=True,
                            min_lines=1,
                            max_lines=4,
                            border=ft.OutlineInputBorder(
                                border_radius=tokens.RADIUS_LG,
                                side=ft.BorderSide(0, ft.Colors.TRANSPARENT),
                            ),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            expand=True,
                            on_change=lambda e: set_draft(e.control.value),
                            on_submit=lambda e: _send(e.control.value),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.MIC_ROUNDED,
                            tooltip="Dictate",
                            icon_size=tokens.ICON_MD,
                            on_click=lambda e: asyncio.ensure_future(_on_mic()),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.STOP_CIRCLE_ROUNDED if busy else ft.Icons.SEND_ROUNDED,
                            icon_color=ft.Colors.WHITE,
                            bgcolor=AppColors.ERROR if busy else AppColors.PRIMARY,
                            icon_size=tokens.ICON_MD,
                            on_click=(lambda e: _stop()) if busy else (lambda e: _send(draft)),
                            tooltip="Stop" if busy else "Send",
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
            ],
            spacing=tokens.SPACE_XS,
            tight=True,
        ),
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_MD),
    )

    return ft.Column(controls=[header, list_view, composer], spacing=0, expand=True)
