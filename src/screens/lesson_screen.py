"""Lesson screen — fetch-or-generate and render.

Ported from Akili v1's lesson_view.py (the house standard):
a cached lesson renders free and instantly; an uncached one is generated
with web research (5 credits, RESERVED then committed — v1 charged even
on failure). Completion is unlocked by the quiz, not by a button.

A successful generation also awards lesson XP and auto-creates the
module's assignment (v1 parity).
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.banner_ad import build_banner_ad
from components.error_state import ErrorState, OfflineState
from components.loading_state import ProgressState
from components.rich_content import render_rich_content
from core import tokens
from core.constants import COST_LESSON_GEN
from core.theme import AppColors
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger("LessonScreen")


@ft.component
def LessonScreen():
    """Read or generate a module's lesson."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    course = app_state.current_course or {}
    module = app_state.current_module or {}

    stage, set_stage = ft.use_state("init")  # init|ready|generating|error|offline
    content, set_content = ft.use_state("")
    status, set_status = ft.use_state("")
    error, set_error = ft.use_state("")

    page = ft.context.page
    level = course.get("level") or app_state.education_level or "Grade 10"
    subject = course.get("subject") or "General"

    def _open_video(url: str, title: str):
        """Play in-app; external browser only when resolving fails."""
        from components.lesson_player import show_lesson_player

        show_lesson_player(page, url, title)

    async def _ensure_lesson():
        cached = module.get("lesson_cache")
        if cached:
            set_content(cached)
            set_stage("ready")
            return
        if not app_state.is_online:
            set_stage("offline")
            return

        credits = app_state.credit_service
        if credits is None:
            set_error("AI credits are unavailable right now.")
            set_stage("error")
            return
        tx = await credits.reserve(COST_LESSON_GEN)
        if tx is None:
            set_error(f"Not enough credits — you need {COST_LESSON_GEN}.")
            set_stage("error")
            return

        set_stage("generating")
        set_status("Searching the web for accurate content…")
        try:
            from services import generation

            lesson = await generation.generate_lesson(module, subject, level, on_status=lambda s: set_status(s))
            if not lesson:
                await credits.rollback(tx)
                set_error("Lesson generation failed. Please try again.")
                set_stage("error")
                return
            await controller.save_lesson_cache(module["id"], lesson)
            module["lesson_cache"] = lesson
            await credits.commit(tx)
            set_content(lesson)
            set_stage("ready")
            page.run_task(_post_generation(), lesson)
        except Exception as exc:
            await credits.rollback(tx)
            logger.exception("lesson generation failed")
            set_error(f"Lesson generation failed: {str(exc)[:120]}")
            set_stage("error")

    async def _post_generation(lesson: str):
        """Award lesson XP and auto-create the assignment (v1 parity)."""
        try:
            from services.gamification import get_gamification

            gam = get_gamification()
            if gam is not None:
                await gam.award_xp("lesson_complete")
        except Exception:
            logger.debug("lesson XP award failed", exc_info=True)
        await _create_assignment(lesson)

    async def _create_assignment(lesson: str):
        store = getattr(page, "_akili_course_store", None)
        if store is None or not module.get("id") or not course.get("id"):
            return
        try:
            existing = await store.get_module_assignment(module["id"])
            if existing:
                return
            from services import generation

            questions = await generation.generate_assignment_questions(module, course, lesson)
            if not questions:
                return
            await store.create_assignment(
                module["id"],
                course["id"],
                f"{module.get('title', 'Module')} — Assignment",
                "Complete both questions. You may type or upload a photo of your handwritten work.",
                questions,
                due_days=3,
            )
            await controller.show_snack("New assignment created!", "info")
            # Schedule the OS due-date nudge (Android; no-op elsewhere).
            try:
                from services import os_notifications

                created = await store.get_module_assignment(module["id"])
                if created:
                    await os_notifications.schedule_overdue(created["id"], created.get("title") or "Assignment", str(created.get("due_date") or ""))
            except Exception:
                logger.debug("assignment notification scheduling failed", exc_info=True)
        except Exception:
            logger.debug("assignment auto-create failed", exc_info=True)

    def _load():
        asyncio.ensure_future(_ensure_lesson())

    ft.use_effect(_load, [])

    def _retry(e):
        set_error("")
        set_stage("init")
        _load()

    # ── Header ──
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    on_click=lambda e: controller.show_course(course),
                    tooltip="Back",
                ),
                ft.Column(
                    controls=[
                        ft.Text(str(module.get("title") or "Lesson"), size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(subject, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=1,
                    expand=True,
                    tight=True,
                ),
            ],
            spacing=tokens.SPACE_XS,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Body ──
    if stage == "init" or stage == "generating":
        body = ProgressState(status or "Preparing your lesson…")
    elif stage == "offline":
        body = OfflineState(on_retry=_retry)
    elif stage == "error":
        body = ErrorState("Lesson unavailable", error, "Try again", _retry)
    else:
        # v1 layout: pinned notebook tip, scrolling lesson body (banner ad
        # appended at the end of the content), pinned Take-Quiz footer —
        # the CTA never scrolls out of reach.
        tip = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=tokens.ICON_SM, color=AppColors.WARNING),
                    ft.Text(
                        "Keep your notebook ready — take notes as you read. You'll need them for the quiz.",
                        size=tokens.FONT_XS,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        expand=True,
                    ),
                ],
                spacing=tokens.SPACE_XS,
            ),
            padding=tokens.SPACE_MD,
            border_radius=tokens.RADIUS_MD,
            bgcolor=ft.Colors.with_opacity(0.08, AppColors.WARNING),
        )
        scroll_children = list(render_rich_content(content, page, on_play_video=_open_video))
        scroll_children.append(build_banner_ad(page))
        body = ft.Column(
            controls=[
                tip,
                ft.Container(
                    content=ft.Column(
                        controls=scroll_children,
                        spacing=tokens.SPACE_SM,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    expand=True,
                ),
                ft.Column(
                    controls=[
                        ft.FilledButton(
                            "Take Quiz",
                            icon=ft.Icons.QUIZ_ROUNDED,
                            on_click=lambda e: controller.show_quiz(course, module),
                            width=float("inf"),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                                padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
                            ),
                        ),
                        ft.Text(
                            "Pass the quiz (50%+) to unlock the next module.",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                    tight=True,
                ),
            ],
            spacing=tokens.SPACE_MD,
            expand=True,
        )

    return ft.Column(
        controls=[
            header,
            ft.Container(content=body, padding=tokens.SPACE_LG, expand=True),
        ],
        spacing=0,
        expand=True,
    )
