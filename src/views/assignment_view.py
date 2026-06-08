"""Assignment view — view and submit assignments.

Students can type answers or upload/snap handwritten images.
After submission, answers are evaluated by AI using source material.
Image bytes are discarded after OCR processing (no bloat).
"""

import json

import flet as ft

from core.ai_utils import validate_mixed_questions
from core.question_types import QuestionType
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.credit_service import credit_service
from services.evaluation import evaluate_open_answers
from services.file_picker import FilePickerService
from services.gamification import gamification_service
from services.share_service import ShareType, show_share_sheet
from components.voice_input import VoiceInputHandler


async def build_assignment_view(page: ft.Page, navigate) -> ft.View:
    assignment_id = state.current_assignment_id
    if not assignment_id:
        return ft.View(route="/assignment", controls=[ft.Text("No assignment selected")])

    assignment = await db_manager.get_assignment(assignment_id)
    if not assignment:
        return ft.View(route="/assignment", controls=[ft.Text("Assignment not found")])

    questions = []
    try:
        raw_qs = json.loads(assignment.get("questions_json", "[]"))
        questions = validate_mixed_questions(raw_qs) if raw_qs else []
    except Exception:
        pass

    answers: dict[int, dict] = {}

    is_graded = assignment["status"] == "graded"
    is_submitted = assignment["status"] == "submitted"

    loading_col = ft.Column(
        [ft.ProgressRing(width=36, height=36, stroke_width=3, color=AppColors.PRIMARY), ft.Text("Submitting...", size=14, weight=ft.FontWeight.W_500)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=False,
    )
    result_content = ft.Column(visible=False, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # Build question cards
    question_controls = []
    answer_fields = {}
    image_previews = {}
    image_data_store = {}

    for qi, q in enumerate(questions):

        def _make_image_handler(idx):
            def _on_img(data, mime, filename):
                image_data_store[idx] = {"bytes": data, "mime": mime}
                image_previews[idx].content = ft.Row(
                    [
                        ft.Icon(ft.Icons.IMAGE_ROUNDED, color=AppColors.SUCCESS),
                        ft.Text(f"📷 {filename}", size=13, color=AppColors.SUCCESS, expand=True),
                        ft.IconButton(icon=ft.Icons.CLOSE, icon_size=16, on_click=lambda e, i=idx: _clear_img(i)),
                    ]
                )
                image_previews[idx].visible = True
                page.update()

            return _on_img

        def _clear_img(idx):
            image_data_store.pop(idx, None)
            image_previews[idx].visible = False
            page.update()

        qtype = q.get("type", QuestionType.THEORY)
        badge_text = "Theory" if qtype == QuestionType.THEORY else "Subjective"
        badge_color = AppColors.ACCENT if qtype == QuestionType.THEORY else ft.Colors.PURPLE

        field = ft.TextField(
            label="Type your answer...",
            multiline=True,
            min_lines=3,
            max_lines=10,
            border_radius=AppStyles.RADIUS,
            filled=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_color=ft.Colors.TRANSPARENT,
            disabled=is_graded or is_submitted,
        )
        answer_fields[qi] = field
        voice_handler = VoiceInputHandler(page, field)
        voice_handler.record_btn.visible = not (is_graded or is_submitted)
        voice_handler.set_enabled(state.is_online)

        img_preview = ft.Container(visible=False)
        image_previews[qi] = img_preview

        fp = FilePickerService(page, on_result=_make_image_handler(qi))

        card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(badge_text, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                bgcolor=badge_color,
                                padding=ft.Padding(10, 4, 10, 4),
                                border_radius=12,
                            ),
                            ft.Text(f"Q{qi + 1}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=8,
                    ),
                    ft.Text(q["question"], size=16, weight=ft.FontWeight.W_600),
                    field,
                    voice_handler.status_indicator,
                    ft.Row(
                        [
                            ft.Container(expand=True, height=1, bgcolor=ft.Colors.OUTLINE_VARIANT),
                            ft.Text("OR", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Container(expand=True, height=1, bgcolor=ft.Colors.OUTLINE_VARIANT),
                        ],
                        spacing=8,
                    )
                    if not (is_graded or is_submitted)
                    else ft.Container(),
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "📷 Upload / Snap Answer",
                                icon=ft.Icons.CAMERA_ALT_ROUNDED,
                                on_click=lambda e, p=fp: page.run_task(p.pick_image),
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS)),
                                visible=not (is_graded or is_submitted),
                            ),
                            voice_handler.record_btn,
                            voice_handler.timer_text,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    img_preview,
                ],
                spacing=12,
            ),
            padding=20,
            border_radius=AppStyles.RADIUS,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )
        question_controls.append(card)

    # Show grading results if already graded
    if is_graded:
        try:
            evals = json.loads(assignment.get("evaluation_json", "[]"))
        except Exception:
            evals = []

        for qi, _q in enumerate(questions):
            if qi < len(evals):
                ev = evals[qi]
                question_controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    f"Q{qi + 1} — Score: {ev.get('score', 0):.0f}/{ev.get('max_score', 10):.0f}", size=14, weight=ft.FontWeight.BOLD, color=AppColors.SUCCESS if ev.get("score", 0) >= ev.get("max_score", 10) * 0.6 else AppColors.ERROR
                                ),
                                ft.Text(ev.get("feedback", ""), size=13),
                                ft.Text(f"💡 {ev.get('suggestions', '')}", size=12, color=ft.Colors.ON_SURFACE_VARIANT) if ev.get("suggestions") else ft.Container(),
                            ],
                            spacing=4,
                        ),
                        padding=12,
                        border_radius=AppStyles.RADIUS_SMALL,
                        bgcolor=ft.Colors.with_opacity(0.05, AppColors.SUCCESS),
                    )
                )

    async def _submit_assignment(e):
        from components.offline_retry import OfflineRetryWidget

        if not state.is_online:
            body_container.content = OfflineRetryWidget(page, on_retry=lambda: _submit_assignment(e), message="Akili needs an active internet connection to submit and grade your assignment.")
            page.update()
            return

        body_container.content = normal_layout
        page.update()

        if not await credit_service.can_afford("assignment_eval"):
            page.snack_bar = ft.SnackBar(ft.Text("Not enough credits"), bgcolor=ft.Colors.ERROR)
            page.snack_bar.open = True
            page.update()
            return

        await credit_service.spend("assignment_eval")

        # Collect answers
        for qi in range(len(questions)):
            answers[qi] = {
                "text": answer_fields[qi].value or "",
                "image_bytes": image_data_store.get(qi, {}).get("bytes"),
                "image_mime": image_data_store.get(qi, {}).get("mime"),
            }

        loading_col.visible = True
        page.update()

        # Submit answers to DB (text only)
        submission = [{"text": answers[qi].get("text", ""), "had_image": bool(answers[qi].get("image_bytes"))} for qi in range(len(questions))]
        await db_manager.submit_assignment(assignment_id, json.dumps(submission))

        # Evaluate via AI
        student_answers = [answers[qi] for qi in range(len(questions))]
        evaluations = await evaluate_open_answers(
            questions=questions,
            student_answers=student_answers,
            student_level=state.education_level or "Grade 10",
        )

        # Discard all image bytes — no bloat
        for qi in answers:
            answers[qi]["image_bytes"] = None
        image_data_store.clear()

        # Calculate overall score
        total_earned = sum(ev.get("score", 0) for ev in evaluations)
        total_possible = sum(ev.get("max_score", 10) for ev in evaluations)
        pct = (total_earned / total_possible * 100) if total_possible else 0

        # Grade assignment
        feedback_lines = []
        for i, ev in enumerate(evaluations):
            feedback_lines.append(f"Q{i + 1}: {ev.get('feedback', '')}")

        await db_manager.grade_assignment(
            assignment_id,
            json.dumps(evaluations),
            score=pct,
            feedback="\n".join(feedback_lines),
        )

        # XP reward
        from datetime import datetime

        is_on_time = True
        if assignment.get("due_date"):
            try:
                due = datetime.fromisoformat(assignment["due_date"])
                is_on_time = datetime.now() <= due
            except Exception:
                pass
        if is_on_time:
            await gamification_service.award_xp("assignment_on_time")
        else:
            await gamification_service.award_xp("assignment_late")
        if pct >= 90:
            await gamification_service.award_xp("assignment_perfect")

        loading_col.visible = False

        # Show results
        color = AppColors.SUCCESS if pct >= 60 else AppColors.ERROR
        result_controls = [
            ft.Icon(ft.Icons.TASK_ALT_ROUNDED if pct >= 60 else ft.Icons.ERROR_OUTLINE_ROUNDED, size=64, color=color),
            ft.Text("Assignment Graded!", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(f"Score: {pct:.0f}%", size=20, color=color),
        ]

        for i, ev in enumerate(evaluations):
            result_controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"Q{i + 1}: {ev.get('score', 0):.0f}/{ev.get('max_score', 10):.0f}", size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(ev.get("feedback", ""), size=13),
                        ],
                        spacing=4,
                    ),
                    padding=12,
                    border_radius=AppStyles.RADIUS_SMALL,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                )
            )

        def _share_assignment(e):
            show_share_sheet(
                page,
                ShareType.ASSIGNMENT_RESULT,
                {
                    "pct": pct,
                    "subject": assignment.get("subject", ""),
                    "title": assignment.get("title", ""),
                    "name": state.user_name,
                },
            )

        result_controls.append(ft.Container(height=16))
        result_controls.append(
            ft.Row(
                [
                    ft.FilledButton("Done", on_click=lambda e: page.run_task(navigate, "/dashboard")),
                    ft.TextButton("📤 Share", icon=ft.Icons.SHARE_ROUNDED, on_click=_share_assignment),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
        )

        result_content.controls = result_controls
        result_content.visible = True
        page.update()

    # Determine due date display
    due_text = ""
    if assignment.get("due_date"):
        try:
            from datetime import datetime

            due = datetime.fromisoformat(assignment["due_date"])
            now = datetime.now()
            if now > due:
                due_text = f"⚠️ Overdue (was due {due.strftime('%b %d')})"
            else:
                days_left = (due - now).days
                due_text = f"Due in {days_left} day{'s' if days_left != 1 else ''}"
        except Exception:
            due_text = ""

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                ft.Column(
                    [
                        ft.Text("Assignment", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(assignment.get("subject", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=0,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        padding=ft.Padding(8, 8, 16, 8),
    )

    status_badge_color = {"pending": AppColors.ACCENT, "submitted": AppColors.PRIMARY, "graded": AppColors.SUCCESS}.get(assignment["status"], AppColors.PRIMARY)
    status_label = assignment["status"].capitalize()

    info_section = ft.Container(
        content=ft.Column(
            [
                ft.Text(assignment["title"], size=20, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(status_label, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                            bgcolor=status_badge_color,
                            padding=ft.Padding(10, 4, 10, 4),
                            border_radius=12,
                        ),
                        ft.Text(due_text, size=13, color=ft.Colors.ON_SURFACE_VARIANT) if due_text else ft.Container(),
                    ],
                    spacing=8,
                ),
                ft.Text(assignment.get("description", ""), size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            spacing=8,
        ),
        padding=ft.Padding(20, 0, 20, 16),
    )

    submit_btn = ft.FilledButton(
        "Submit Assignment",
        icon=ft.Icons.SEND_ROUNDED,
        on_click=_submit_assignment,
        style=ft.ButtonStyle(
            bgcolor=AppColors.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
            padding=16,
        ),
        width=float("inf"),
        visible=not (is_graded or is_submitted),
    )

    normal_layout = ft.Column(
        [info_section, *question_controls, ft.Container(height=12), loading_col, submit_btn, result_content, ft.Container(height=20)],
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
    )

    body_container = ft.Container(
        content=normal_layout,
        padding=ft.Padding(16, 0, 16, 0),
        expand=True,
    )

    return ft.View(
        route="/assignment",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column([header, body_container], spacing=0, expand=True),
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
        spacing=0,
    )
