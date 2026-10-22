"""Exam screen — the 10-question timed mock exam.

Ported from Akili v1's mock_exam.py:
aggregated course material, objectives-first (Section A / Section B),
15:00 countdown with auto-submit, no correct-text reveal, grade bands,
pass ≥60% → mock_exam_complete XP. Free.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.banner_ad import build_banner_ad
from components.error_state import ErrorState, OfflineState
from components.loading_state import ProgressState
from components.question_card import QuestionCard
from components.results_panel import ResultsPanel
from core import tokens
from core.question_types import QuestionType
from core.theme import AppColors
from services.scoring import exam_grade, feedback_cards, score_mixed
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger("ExamScreen")

EXAM_SECONDS = 15 * 60
WARN_SECONDS = 120


@ft.component
def ExamScreen():
    """The course mock exam."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    course = app_state.current_course or {}

    stage, set_stage = ft.use_state("loading")  # loading|ready|evaluating|done|error|offline
    questions, set_questions = ft.use_state([])
    index, set_index = ft.use_state(0)
    selected, set_selected = ft.use_state(None)
    answered, set_answered = ft.use_state(False)
    objective_correct, set_objective_correct = ft.use_state(0)
    answers, set_answers = ft.use_state({})
    images, set_images = ft.use_state({})  # qidx -> (bytes, mime); ephemeral
    draft, set_draft = ft.use_state("")
    seconds, set_seconds = ft.use_state(EXAM_SECONDS)
    status, set_status = ft.use_state("")
    error, set_error = ft.use_state("")
    error_kind, set_error_kind = ft.use_state("")  # generate|grade — drives retry branching
    result, set_result = ft.use_state(None)

    page = ft.context.page
    level = course.get("level") or app_state.education_level or "Grade 10"
    timer_ref = ft.use_ref(None)

    def _load():
        # Fresh run: re-arm the countdown and submit guard (refs persist
        # across retry/retake within this component instance).
        started_ref.current = False
        finishing_ref.current = False
        seconds_ref.current = EXAM_SECONDS

        async def _run():
            if not course.get("id"):
                set_error("No course selected.")
                set_error_kind("generate")
                set_stage("error")
                return
            if not app_state.is_online:
                set_stage("offline")
                return
            set_stage("loading")
            try:
                from services import generation

                store = getattr(page, "_akili_course_store", None)
                modules = await store.get_modules(course["id"]) if store else []
                qs = await generation.generate_exam_questions(course, modules, level, on_status=lambda s: set_status(s))
                if not qs:
                    set_error("Couldn't generate exam questions. Please try again.")
                    set_error_kind("generate")
                    set_stage("error")
                    return
                set_questions(qs)
                set_seconds(EXAM_SECONDS)
                set_stage("ready")
            except Exception as exc:
                logger.exception("exam generation failed")
                set_error(f"Couldn't generate the exam: {str(exc)[:100]}")
                set_error_kind("generate")
                set_stage("error")

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    # ── Countdown: start when the questions arrive, cancel on unmount ──
    started_ref = ft.use_ref(False)
    finishing_ref = ft.use_ref(False)  # dedupes timer auto-submit vs manual submit
    seconds_ref = ft.use_ref(EXAM_SECONDS)  # live remaining, readable from stale closures

    def _maybe_start_timer():
        if stage != "ready" or started_ref.current:
            return
        started_ref.current = True

        async def _tick():
            remaining = EXAM_SECONDS
            try:
                while remaining > 0:
                    await asyncio.sleep(1)
                    remaining -= 1
                    seconds_ref.current = remaining
                    set_seconds(remaining)
                # Time up — auto-submit; _finish dedupes against a manual
                # submit racing in the same moment.
                page.run_task(_finish, 0)
            except asyncio.CancelledError:
                pass

        timer_ref.current = asyncio.ensure_future(_tick())

    def _stop_timer():
        task = timer_ref.current
        if task is not None and not task.done():
            task.cancel()

    # System-back / header-back unmount this component without touching
    # _stop_timer — run it as the unmount cleanup so a stray _tick can
    # never set state or auto-submit a dead screen.
    ft.use_effect(_maybe_start_timer, [stage], cleanup=_stop_timer)

    total = len(questions)
    q = questions[index] if 0 <= index < total else None

    def _reset_run():
        _stop_timer()
        set_index(0)
        set_selected(None)
        set_answered(False)
        set_objective_correct(0)
        set_answers({})
        set_images({})
        set_draft("")
        set_result(None)
        _load()

    def _section_label() -> str:
        if q is None:
            return ""
        return "Section A — Objectives" if q.get("type") == QuestionType.OBJECTIVE else "Section B — Theory"

    def _select_option(idx: int):
        if answered or q is None:
            return
        set_selected(idx)
        set_answered(True)
        # Exam highlights right/wrong but never reveals the correct text.
        if idx == q.get("correct"):
            set_objective_correct(objective_correct + 1)

    def _advance():
        if q is None:
            return
        if q.get("type") in QuestionType.OPEN:
            set_answers({**answers, index: draft})
        set_draft("")
        set_selected(None)
        set_answered(False)
        if index + 1 >= total:
            _stop_timer()
            page.run_task(_finish, 0)
        else:
            set_index(index + 1)

    async def _finish(_e):
        if finishing_ref.current:
            return
        finishing_ref.current = True
        _stop_timer()
        set_stage("evaluating")
        set_status("Grading your exam…")
        # Live remaining from the ref — the closure's `seconds` is frozen at
        # whichever render created this handler (auto-submit would record 0).
        duration = EXAM_SECONDS - max(0, seconds_ref.current)
        try:
            from services import evaluation
            from services.gamification import get_gamification

            open_qs = [qq for qq in questions if qq.get("type") in QuestionType.OPEN]
            open_ans = [
                {
                    "text": answers.get(i, ""),
                    "image_bytes": (images.get(i) or (None, None))[0],
                    "image_mime": (images.get(i) or (None, None))[1] or "image/jpeg",
                }
                for i, qq in enumerate(questions)
                if qq.get("type") in QuestionType.OPEN
            ]
            evals = await evaluation.evaluate_open_answers(open_qs, open_ans, level) if open_qs else []
            cards = feedback_cards(evals, 0.6, questions=open_qs)
            total_score, total_possible, pct, _, _ = score_mixed(questions, objective_correct, evals)
            grade, passed = exam_grade(pct)

            store = getattr(page, "_akili_course_store", None)
            if store is not None:
                slim_answers = [{"text": answers.get(i, ""), "had_image": bool(images.get(i))} for i in range(total)]
                await store.save_assessment(course["id"], total_score, total_possible, grade, duration, questions, slim_answers, evals)
                if passed:
                    gam = get_gamification()
                    if gam is not None:
                        await gam.award_xp("mock_exam_complete")
                        for event in await controller.check_earn_conditions():
                            page.run_task(_offer_event, event)

            set_result({"grade": grade, "passed": passed, "score": total_score, "total": total_possible, "pct": pct, "cards": cards, "duration": duration})
            set_stage("done")
        except Exception as exc:
            logger.exception("exam grading failed")
            set_error(f"Couldn't grade your exam: {str(exc)[:100]}")
            # Re-arm the submit guard so Retry can re-grade; the countdown
            # stays stopped and seconds_ref keeps the frozen remaining time
            # (v1 preserves elapsed time across a grading retry).
            finishing_ref.current = False
            set_error_kind("grade")
            set_stage("error")

    def _retry(_e=None):
        # Grading failures keep the questions, answers, and elapsed time —
        # re-grade only. Generation failures regenerate from scratch.
        if error_kind == "grade":
            page.run_task(_finish, 0)
        else:
            _load()

    async def _offer_event(event):
        from services.share_service import offer_share_event

        offer_share_event(page, event)

    def _back():
        _stop_timer()
        controller.go_home()

    # ── Timer display ──
    mins, secs = divmod(max(0, seconds), 60)
    timer_label = f"{mins:02d}:{secs:02d}"
    timer_color = AppColors.ERROR if seconds < WARN_SECONDS else AppColors.PRIMARY

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: _back(), tooltip="Leave exam"),
                ft.Text("Mock Exam", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TIMER_OUTLINED, size=tokens.ICON_SM, color=timer_color),
                        ft.Text(timer_label, size=tokens.FONT_MD, weight=ft.FontWeight.BOLD, color=timer_color),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Body ──
    if stage == "loading":
        body = ProgressState(status or "Preparing your exam…")
    elif stage == "evaluating":
        body = ProgressState(status or "Grading…")
    elif stage == "offline":
        body = OfflineState(on_retry=lambda e: _load())
    elif stage == "error":
        body = ErrorState("Exam unavailable", error, "Try again", _retry)
    elif stage == "done" and result:
        took = result["duration"]

        def _share(payload):
            from services.share_service import ShareType, show_share_sheet

            show_share_sheet(page, ShareType.EXAM_RESULT, payload)

        body = ResultsPanel(
            passed=result["passed"],
            score=result["score"],
            total=result["total"],
            pct=result["pct"],
            grade=result["grade"],
            feedback_cards=result["cards"],
            extra_line=f"Time: {took // 60}m {took % 60:02d}s",
            retake_label="Retake Exam",
            on_retake=_reset_run,
            continue_label="Back Home",
            on_continue=lambda: controller.go_home(),
            on_share=_share,
            share_payload={
                "grade": result["grade"],
                "pct": result["pct"],
                "subject": course.get("subject", ""),
                "duration": took,
                "name": app_state.user_name,
            },
        )
    elif q is not None:

        def _on_image(data: bytes, mime: str, filename: str) -> None:
            set_images({**images, index: (data, mime)})

        card = QuestionCard(
            q,
            index + 1,
            total,
            selected=selected,
            revealed=answered,
            show_correct=False,
            section_label=_section_label(),
            answer_value=draft,
            on_answer_change=set_draft,
            on_answer_image=_on_image,
            answer_has_image=bool(images.get(index)),
        )
        controls = [
            card,
            ft.FilledButton(
                "Submit Answer" if (index + 1 >= total and q.get("type") in QuestionType.OPEN) else "Submit & Continue" if q.get("type") in QuestionType.OPEN else "Next Question",
                on_click=lambda e: _advance(),
                disabled=(not answered and q.get("type") not in QuestionType.OPEN),
                width=float("inf"),
                style=ft.ButtonStyle(
                    bgcolor=AppColors.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                    padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
                ),
            ),
            build_banner_ad(page),
        ]
        body = ft.Column(controls=controls, spacing=tokens.SPACE_MD, scroll=ft.ScrollMode.AUTO, expand=True)
    else:
        body = ErrorState("Exam unavailable", "No questions to show.", "Try again", lambda e: _load())

    return ft.Column(
        controls=[header, ft.Container(content=body, padding=tokens.SPACE_LG, expand=True)],
        spacing=0,
        expand=True,
    )
