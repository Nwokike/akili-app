"""Assignment screen — submit written answers, AI grading.

Ported from Akili v1's assignment_view.py:
typed answers (typing-only in Phase 4 — photo/voice land in Phase 7),
5-credit evaluation (reserved, committed on success, rolled back on
grading failure), due labels, on-time/late/perfect XP, per-question
score cards. A grading failure leaves status `submitted`, never half-graded.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import flet as ft

from components.error_state import ErrorState, OfflineState
from components.loading_state import ProgressState
from components.open_answer import OpenAnswer
from components.question_card import _badge
from components.results_panel import ResultsPanel
from core import tokens
from core.constants import COST_ASSIGNMENT_EVAL
from core.question_types import QuestionType
from core.theme import AppColors
from services.scoring import assignment_pct, feedback_cards
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger("AssignmentScreen")


def _due_label(due_date: str) -> tuple[str, bool]:
    """(label, overdue)."""
    if not due_date:
        return ("", False)
    today = date.today().isoformat()
    if due_date < today:
        return (f"⚠️ Overdue (was due {due_date})", True)
    try:
        from datetime import date as _d

        due = _d.fromisoformat(due_date)
        days = (due - _d.today()).days
        if days == 0:
            return ("Due today", False)
        if days == 1:
            return ("Due tomorrow", False)
        return (f"Due in {days} days", False)
    except Exception:
        return (f"Due {due_date}", False)


@ft.component
def AssignmentScreen():
    """The assignment detail + grading flow."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    stage, set_stage = ft.use_state("loading")  # loading|ready|grading|done|error|offline
    assignment, set_assignment = ft.use_state(None)
    drafts, set_drafts = ft.use_state({})  # qidx -> text
    images, set_images = ft.use_state({})  # qidx -> (bytes, mime); ephemeral
    status_text, set_status_text = ft.use_state("")
    error, set_error = ft.use_state("")
    course_subject, set_course_subject = ft.use_state("")
    result, set_result = ft.use_state(None)

    page = ft.context.page
    aid = app_state.current_assignment_id
    level = app_state.education_level or "Grade 10"

    def _load():
        async def _run():
            if aid is None:
                set_error("No assignment selected.")
                set_stage("error")
                return
            store = getattr(page, "_akili_course_store", None)
            if store is None:
                set_error("Storage unavailable.")
                set_stage("error")
                return
            a = await store.get_assignment(aid)
            if a is None:
                set_error("Assignment not found.")
                set_stage("error")
                return
            set_assignment(a)
            course = await store.get_course(a.get("course_id")) if a.get("course_id") is not None else None
            set_course_subject(str(course.get("subject") or "") if course else "")
            existing = {}
            for i, ans in enumerate(a.get("submission") or []):
                if isinstance(ans, dict):
                    existing[i] = str(ans.get("text") or "")
            set_drafts(existing)
            if a.get("status") == "graded":
                # Already graded — jump straight to the result (v1 shows the
                # graded feedback on revisit, never a fresh attempt form).
                _refresh_result(a)
                set_stage("done")
                return
            set_stage("ready")

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    def _refresh_result(a: dict):
        evals = list(a.get("evaluation") or [])
        questions = list(a.get("questions") or [])
        set_result({"pct": float(a.get("score") or 0.0), "cards": feedback_cards(evals, 0.6, questions=questions)})

    locked = assignment is not None and assignment.get("status") in ("submitted", "graded")

    async def _submit():
        if assignment is None:
            return
        if not app_state.is_online:
            set_stage("offline")
            return

        questions = list(assignment.get("questions") or [])
        answers = [
            {
                "text": drafts.get(i, ""),
                "image_bytes": (images.get(i) or (None, None))[0],
                "image_mime": (images.get(i) or (None, None))[1] or "image/jpeg",
            }
            for i in range(len(questions))
        ]

        credits = app_state.credit_service
        if credits is None:
            set_error("AI credits are unavailable right now.")
            return
        tx = await credits.reserve(COST_ASSIGNMENT_EVAL)
        if tx is None:
            set_error(f"Not enough credits — you need {COST_ASSIGNMENT_EVAL}.")
            return

        set_stage("grading")
        set_status_text("Grading your answers…")
        store = getattr(page, "_akili_course_store", None)
        try:
            from services import evaluation
            from services.gamification import get_gamification

            await store.submit_assignment(aid, [{"text": a["text"]} for a in answers])
            evals = await evaluation.evaluate_open_answers(questions, answers, level, on_status=lambda s: set_status_text(s))
            pct = assignment_pct(evals)
            feedback = "\n".join(f"Q{i + 1}: {str(ev.get('feedback') or '')}" for i, ev in enumerate(evals))
            await store.grade_assignment(aid, evals, pct, feedback)

            gam = get_gamification()
            if gam is not None:
                due = assignment.get("due_date") or ""
                on_time = not due or due >= date.today().isoformat()
                await gam.award_xp("assignment_on_time" if on_time else "assignment_late")
                if pct >= 90:
                    await gam.award_xp("assignment_perfect")
                for event in await controller.check_earn_conditions():
                    page.run_task(_offer_event, event)

            await credits.commit(tx)
            fresh = await store.get_assignment(aid)
            if fresh:
                set_assignment(fresh)
                _refresh_result(fresh)
            set_stage("done")
            # The due-date nudge has served its purpose — cancel it.
            try:
                from services import os_notifications

                await os_notifications.cancel_overdue(aid)
            except Exception:
                logger.debug("notification cancel on submit failed", exc_info=True)
        except Exception as exc:
            await credits.rollback(tx)
            logger.exception("assignment grading failed")
            set_error(f"Couldn't grade your work: {str(exc)[:100]} (status stays submitted)")
            set_stage("ready")

    async def _offer_event(event):
        from services.share_service import offer_share_event

        offer_share_event(page, event)

    # ── Header ──
    title = (assignment or {}).get("title") or "Assignment"
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Text("Assignment", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Body ──
    if stage == "loading":
        body = ProgressState("Loading assignment…")
    elif stage == "grading":
        body = ProgressState(status_text or "Grading your answers…")
    elif stage == "offline":
        body = OfflineState(on_retry=lambda e: _load())
    elif stage == "error" or assignment is None:
        body = ErrorState("Assignment unavailable", error, "Try again", lambda e: _load())
    elif stage == "done" and result:

        def _share(payload):
            from services.share_service import ShareType, show_share_sheet

            show_share_sheet(page, ShareType.ASSIGNMENT_RESULT, payload)

        body = ResultsPanel(
            passed=float(result["pct"]) >= 60,
            score=float(result["pct"]),
            total=100,
            pct=float(result["pct"]),
            feedback_cards=result["cards"],
            retake_label="",
            on_retake=None,
            continue_label="Done",
            on_continue=lambda: controller.go_home(),
            on_share=_share,
            share_payload={
                "pct": float(result["pct"]),
                "subject": course_subject,
                "title": (assignment or {}).get("title", ""),
                "name": app_state.user_name,
            },
        )
    else:
        a_status = assignment.get("status", "pending")
        due_label, overdue = _due_label(assignment.get("due_date") or "")
        status_colour = {
            "pending": AppColors.ACCENT,
            "submitted": AppColors.PRIMARY,
            "graded": AppColors.SUCCESS,
        }.get(a_status, AppColors.ACCENT)

        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text(title, size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
                    ft.Container(
                        content=ft.Text(a_status.capitalize(), size=tokens.FONT_XS, weight=ft.FontWeight.BOLD, color=status_colour),
                        padding=ft.Padding(8, 2, 8, 2),
                        border_radius=tokens.RADIUS_FULL,
                        bgcolor=ft.Colors.with_opacity(0.12, status_colour),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]
        if due_label:
            controls.append(ft.Text(due_label, size=tokens.FONT_XS, color=AppColors.ERROR if overdue else ft.Colors.ON_SURFACE_VARIANT))

        questions = list(assignment.get("questions") or [])
        for i, q in enumerate(questions):

            def _on_image(data: bytes, mime: str, filename: str, qi=i) -> None:
                set_images({**images, qi: (data, mime)})

            controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(controls=[ft.Text(f"Q{i + 1}", size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT, expand=True), _badge(q.get("type", QuestionType.THEORY))]),
                            ft.Text(str(q.get("question") or ""), size=tokens.FONT_MD, weight=ft.FontWeight.W_500, selectable=True),
                            OpenAnswer(
                                q.get("type", QuestionType.THEORY),
                                value=drafts.get(i, ""),
                                on_change=(lambda v, qi=i: set_drafts({**drafts, qi: v})),
                                on_image=_on_image,
                                has_image=bool(images.get(i)),
                                disabled=locked,
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                        tight=True,
                    ),
                    padding=tokens.SPACE_LG,
                    border_radius=tokens.RADIUS_LG,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
                )
            )

        if error and stage == "ready":
            controls.append(ft.Text(error, color=AppColors.ERROR, size=tokens.FONT_SM))

        if not locked:
            controls.append(
                ft.FilledButton(
                    f"Submit Assignment ({COST_ASSIGNMENT_EVAL} credits)",
                    icon=ft.Icons.SEND_ROUNDED,
                    on_click=lambda e: page.run_task(_submit),
                    width=float("inf"),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
                        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
                    ),
                )
            )

        body = ft.Column(controls=controls, spacing=tokens.SPACE_MD, scroll=ft.ScrollMode.AUTO, expand=True)

    return ft.Column(
        controls=[header, ft.Container(content=body, padding=tokens.SPACE_LG, expand=True)],
        spacing=0,
        expand=True,
    )
