"""Quiz screen — the 5-question module quiz.

Ported from Akili v1's quiz_view.py:
free, scoped to the lesson cache, sequential questions, instant feedback
on objectives (correct shown), open answers AI-graded, pass ≥50% →
complete module + unlock next + quiz_pass XP.
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
from services.scoring import feedback_cards, score_mixed
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger("QuizScreen")


@ft.component
def QuizScreen():
    """The module knowledge check."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    course = app_state.current_course or {}
    module = app_state.current_module or {}

    stage, set_stage = ft.use_state("loading")  # loading|ready|evaluating|done|error|offline
    questions, set_questions = ft.use_state([])
    index, set_index = ft.use_state(0)
    selected, set_selected = ft.use_state(None)
    answered, set_answered = ft.use_state(False)
    feedback, set_feedback = ft.use_state("")
    objective_correct, set_objective_correct = ft.use_state(0)
    answers, set_answers = ft.use_state({})  # qidx -> text
    images, set_images = ft.use_state({})  # qidx -> (bytes, mime); ephemeral, never persisted
    draft, set_draft = ft.use_state("")
    status, set_status = ft.use_state("")
    error, set_error = ft.use_state("")
    error_kind, set_error_kind = ft.use_state("")  # generate|grade — drives retry branching
    result, set_result = ft.use_state(None)

    page = ft.context.page
    level = course.get("level") or app_state.education_level or "Grade 10"

    def _load():
        async def _run():
            if not module.get("id"):
                set_error("No module selected.")
                set_error_kind("generate")
                set_stage("error")
                return
            if not app_state.is_online:
                set_stage("offline")
                return
            set_stage("loading")
            try:
                from services import generation

                qs = await generation.generate_quiz_questions(module, level, on_status=lambda s: set_status(s))
                if not qs:
                    set_error("Couldn't generate quiz questions. Please try again.")
                    set_error_kind("generate")
                    set_stage("error")
                    return
                set_questions(qs)
                set_stage("ready")
            except Exception as exc:
                logger.exception("quiz generation failed")
                set_error(f"Couldn't generate quiz questions: {str(exc)[:100]}")
                set_error_kind("generate")
                set_stage("error")

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    total = len(questions)
    q = questions[index] if 0 <= index < total else None

    def _reset_run():
        set_index(0)
        set_selected(None)
        set_answered(False)
        set_feedback("")
        set_objective_correct(0)
        set_answers({})
        set_images({})
        set_draft("")
        set_result(None)
        _load()

    def _select_option(idx: int):
        if answered or q is None:
            return
        set_selected(idx)
        set_answered(True)
        correct = q.get("correct")
        if idx == correct:
            set_objective_correct(objective_correct + 1)
            explanation = (q.get("explanation") or "").strip()
            set_feedback(f"✅ Correct! {explanation}".strip())
        else:
            options = list(q.get("options") or [])
            correct_text = str(options[correct]) if correct is not None and 0 <= correct < len(options) else ""
            explanation = (q.get("explanation") or "").strip()
            set_feedback(f"❌ The answer was: {correct_text}. {explanation}".strip())

    def _save_open():
        if q is None:
            return
        set_answers({**answers, index: draft})

    def _advance():
        if q is None:
            return
        if q.get("type") in QuestionType.OPEN:
            _save_open()
        set_draft("")
        set_selected(None)
        set_answered(False)
        set_feedback("")
        if index + 1 >= total:
            page.run_task(_finish, 0)
        else:
            set_index(index + 1)

    async def _finish(_e):
        set_stage("evaluating")
        set_status("Evaluating your answers…")
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
            cards = feedback_cards(evals, 0.5, questions=open_qs)
            total_score, total_possible, pct, passed, _ = score_mixed(questions, objective_correct, evals)

            store = getattr(page, "_akili_course_store", None)
            if store is not None:
                slim_answers = [{"text": answers.get(i, ""), "had_image": bool(images.get(i))} for i in range(total)]
                await store.save_quiz_attempt(
                    module["id"],
                    total_score,
                    total_possible,
                    questions,
                    passed,
                    slim_answers,
                    evals,
                )
                if passed:
                    await controller.complete_quiz_pass(module["id"], course["id"])
                    gam = get_gamification()
                    if gam is not None:
                        await gam.award_xp("quiz_pass")
                        for event in await controller.check_earn_conditions():
                            page.run_task(_offer_event, event)

            set_result(
                {
                    "passed": passed,
                    "score": total_score,
                    "total": total_possible,
                    "pct": pct,
                    "cards": cards,
                    "evals": evals,
                }
            )
            set_stage("done")
        except Exception as exc:
            logger.exception("quiz finalise failed")
            set_error(f"Couldn't grade your answers: {str(exc)[:100]}")
            set_error_kind("grade")
            set_stage("error")

    def _retry(_e=None):
        # Grading failures keep the questions and every answer — re-grade
        # only (v1 _finalize_quiz parity). Generation failures regenerate.
        if error_kind == "grade":
            page.run_task(_finish, 0)
        else:
            _load()

    async def _offer_event(event):
        from services.share_service import offer_share_event

        offer_share_event(page, event)

    # ── Header ──
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.show_lesson(course, module), tooltip="Back"),
                ft.Column(
                    controls=[
                        ft.Text("Knowledge Check", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                        ft.Text(str(module.get("title") or ""), size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=1,
                    expand=True,
                    tight=True,
                ),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Body ──
    if stage == "loading":
        body = ProgressState(status or "Preparing your quiz…")
    elif stage == "evaluating":
        body = ProgressState(status or "Evaluating…")
    elif stage == "offline":
        body = OfflineState(on_retry=lambda e: _load())
    elif stage == "error":
        body = ErrorState("Quiz unavailable", error, "Try again", _retry)
    elif stage == "done" and result:

        def _share(payload):
            from services.share_service import ShareType, show_share_sheet

            show_share_sheet(page, ShareType.QUIZ_RESULT, payload)

        # v1's pass/fail unlock banner above the results panel.
        unlock_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.LOCK_OPEN_ROUNDED if result["passed"] else ft.Icons.LOCK_ROUNDED,
                        size=tokens.ICON_SM,
                        color=AppColors.SUCCESS if result["passed"] else AppColors.WARNING,
                    ),
                    ft.Text(
                        "Next module unlocked!" if result["passed"] else "Score 50% or more to unlock the next module.",
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600,
                        color=AppColors.SUCCESS if result["passed"] else AppColors.WARNING,
                        expand=True,
                    ),
                ],
                spacing=tokens.SPACE_SM,
            ),
            padding=tokens.SPACE_MD,
            border_radius=tokens.RADIUS_MD,
            bgcolor=ft.Colors.with_opacity(0.08, AppColors.SUCCESS if result["passed"] else AppColors.WARNING),
        )

        body = ft.Column(
            controls=[
                unlock_banner,
                ResultsPanel(
                    passed=result["passed"],
                    score=result["score"],
                    total=result["total"],
                    pct=result["pct"],
                    feedback_cards=result["cards"],
                    retake_label="Retake Quiz",
                    on_retake=_reset_run,
                    continue_label="Back to Modules",
                    on_continue=lambda: controller.show_course(course),
                    on_share=_share,
                    share_payload={
                        "pct": result["pct"],
                        "subject": course.get("subject", ""),
                        "module": module.get("title", ""),
                        "name": app_state.user_name,
                    },
                ),
            ],
            spacing=tokens.SPACE_SM,
            expand=True,
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
            show_correct=True,
            feedback=feedback,
            on_select_option=_select_option,
            answer_value=draft,
            on_answer_change=set_draft,
            on_answer_image=_on_image,
            answer_has_image=bool(images.get(index)),
        )
        controls = [
            ft.Text("Score 50% or more to unlock the next module.", size=tokens.FONT_XS, color=AppColors.WARNING),
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
        body = ErrorState("Quiz unavailable", "No questions to show.", "Try again", lambda e: _load())

    return ft.Column(
        controls=[header, ft.Container(content=body, padding=tokens.SPACE_LG, expand=True)],
        spacing=0,
        expand=True,
    )
