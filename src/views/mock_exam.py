"""Mock exam view — mirrors Nigerian exam format with sections.

Section A: Objectives (MCQ) — instant feedback
Section B: Theory (theory + subjective) — typed or image answers
After completion, open answers are evaluated by AI with source material.
"""

import asyncio
import contextlib
import json

import flet as ft

from components.voice_input import VoiceInputHandler
from core.ai_utils import extract_json_array, validate_mixed_questions
from core.question_types import DEFAULT_MARKS, EXAM_MIX, QuestionType, get_mix_prompt
from core.state import check_internet_connection, state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.evaluation import evaluate_open_answers
from services.file_picker import FilePickerService
from services.gamification import gamification_service
from services.share_service import ShareType, show_share_sheet


def build_mock_exam_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    course = state.current_course or {}
    if not course.get("id"):
        return ft.View(route="/exam", controls=[ft.Text("No course selected")])

    questions: list[dict] = []
    current_q = {"index": 0, "answered": False}
    score = {"correct": 0, "open_total": 0.0, "open_earned": 0.0}
    time_remaining = 900
    timer_running = {"active": False}
    open_answers: dict[int, dict] = {}

    timer_text = ft.Text("15:00", size=14, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)
    section_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=AppColors.ACCENT)
    question_text = ft.Text("", size=18, weight=ft.FontWeight.W_600)
    question_num = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    question_type_badge = ft.Container(visible=False)
    options_col = ft.Column(spacing=10)
    feedback_text = ft.Text("", size=14, visible=False, weight=ft.FontWeight.W_500)

    answer_field = ft.TextField(
        label="Type your answer here...",
        multiline=True,
        min_lines=3,
        max_lines=8,
        border_radius=AppStyles.RADIUS,
        filled=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        visible=False,
    )
    voice_handler = VoiceInputHandler(page, answer_field)
    image_preview = ft.Container(visible=False)
    answer_image_data = {"bytes": None, "mime": None}

    def _on_answer_image(data, mime, filename):
        answer_image_data["bytes"] = data
        answer_image_data["mime"] = mime
        image_preview.content = ft.Row(
            [
                ft.Icon(ft.Icons.IMAGE_ROUNDED, color=AppColors.SUCCESS),
                ft.Text(f"📷 {filename}", size=13, color=AppColors.SUCCESS, expand=True),
                ft.IconButton(icon=ft.Icons.CLOSE, icon_size=16, on_click=lambda e: _clear_image()),
            ]
        )
        image_preview.visible = True
        page.update()

    def _clear_image():
        answer_image_data["bytes"] = None
        answer_image_data["mime"] = None
        image_preview.visible = False
        page.update()

    file_picker = FilePickerService(page, on_result=_on_answer_image)

    upload_btn = ft.OutlinedButton(
        "📷 Upload / Snap Answer",
        icon=ft.Icons.CAMERA_ALT_ROUNDED,
        on_click=lambda e: page.run_task(file_picker.pick_image),
        visible=False,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS)),
    )
    upload_row = ft.Row(
        [
            upload_btn,
            voice_handler.record_btn,
            voice_handler.timer_text,
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    or_divider = ft.Row(
        [ft.Container(expand=True, height=1, bgcolor=ft.Colors.OUTLINE_VARIANT), ft.Text("OR", size=11, color=ft.Colors.ON_SURFACE_VARIANT), ft.Container(expand=True, height=1, bgcolor=ft.Colors.OUTLINE_VARIANT)],
        spacing=8,
        visible=False,
    )

    next_btn = ft.FilledButton(
        "Next Question",
        visible=False,
        on_click=lambda e: _next_question(),
        style=ft.ButtonStyle(
            bgcolor=AppColors.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
            padding=ft.Padding(0, 16, 0, 16),
        ),
        width=float("inf"),
    )

    loading_col = ft.Column(
        [ft.ProgressRing(width=36, height=36, stroke_width=3, color=AppColors.PRIMARY), ft.Text("Preparing exam...", size=14, weight=ft.FontWeight.W_500)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=True,
    )

    exam_content = ft.Column(visible=False, spacing=16, expand=True)
    result_content = ft.Column(visible=False, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _get_section_label(q_index: int) -> str:
        q = questions[q_index]
        if q["type"] == QuestionType.OBJECTIVE:
            return "Section A — Objectives"
        return "Section B — Theory"

    def _select_option(idx):
        q = questions[current_q["index"]]
        if q["type"] != QuestionType.OBJECTIVE or current_q["answered"]:
            return
        current_q["answered"] = True
        correct_idx = q["correct"]

        for i, ctrl in enumerate(options_col.controls):
            if i == correct_idx:
                ctrl.bgcolor = ft.Colors.with_opacity(0.1, AppColors.SUCCESS)
                ctrl.border = ft.Border.all(2, AppColors.SUCCESS)
            elif i == idx and idx != correct_idx:
                ctrl.bgcolor = ft.Colors.with_opacity(0.1, AppColors.ERROR)
                ctrl.border = ft.Border.all(2, AppColors.ERROR)

        if idx == correct_idx:
            score["correct"] += 1
        next_btn.visible = True
        page.update()

    def _save_open_answer():
        idx = current_q["index"]
        if idx >= len(questions):
            return
        q = questions[idx]
        if q["type"] in QuestionType.OPEN:
            open_answers[idx] = {
                "text": answer_field.value or "",
                "image_bytes": answer_image_data["bytes"],
                "image_mime": answer_image_data["mime"],
            }
            answer_field.value = ""
            _clear_image()

    def _next_question():
        _save_open_answer()
        current_q["index"] += 1
        current_q["answered"] = False
        if current_q["index"] >= len(questions):
            page.run_task(_finalize_exam)
        else:
            _render_question()

    async def _handle_back(e=None):
        timer_running["active"] = False
        await navigate("/dashboard")

    async def countdown_timer_task():
        nonlocal time_remaining
        timer_running["active"] = True
        while time_remaining > 0 and timer_running["active"] and page.route == "/exam":
            await asyncio.sleep(1)
            if not timer_running["active"] or page.route != "/exam":
                break
            time_remaining -= 1
            mins, secs = divmod(time_remaining, 60)
            timer_text.value = f"{mins:02d}:{secs:02d}"
            if time_remaining < 120:
                timer_text.color = AppColors.ERROR
            else:
                timer_text.color = AppColors.PRIMARY
            with contextlib.suppress(Exception):
                timer_text.update()

        if time_remaining <= 0 and timer_running["active"] and page.route == "/exam":
            timer_running["active"] = False
            page.run_task(_finalize_exam)

    def _render_question():
        q = questions[current_q["index"]]
        qtype = q["type"]
        current_q["answered"] = False

        # Timer
        mins, secs = divmod(time_remaining, 60)
        timer_text.value = f"{mins:02d}:{secs:02d}"
        if time_remaining < 120:
            timer_text.color = AppColors.ERROR
        else:
            timer_text.color = AppColors.PRIMARY

        # Section label
        section_text.value = _get_section_label(current_q["index"])

        question_num.value = f"Question {current_q['index'] + 1} of {len(questions)}"
        question_text.value = q["question"]
        feedback_text.visible = False

        # Type badge
        if qtype == QuestionType.OBJECTIVE:
            badge_text, badge_color = "Objective", AppColors.PRIMARY
        elif qtype == QuestionType.THEORY:
            badge_text, badge_color = "Theory", AppColors.ACCENT
        else:
            badge_text, badge_color = "Subjective", ft.Colors.PURPLE
        question_type_badge.content = ft.Text(badge_text, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        question_type_badge.bgcolor = badge_color
        question_type_badge.padding = ft.Padding(10, 4, 10, 4)
        question_type_badge.border_radius = 12
        question_type_badge.visible = True

        is_open = qtype in QuestionType.OPEN
        options_col.controls.clear()
        options_col.visible = not is_open
        answer_field.visible = is_open
        or_divider.visible = is_open
        upload_btn.visible = is_open
        voice_handler.record_btn.visible = is_open
        voice_handler.set_enabled(state.is_online)
        image_preview.visible = False

        if qtype == QuestionType.OBJECTIVE:
            next_btn.visible = False
            for i, opt in enumerate(q["options"]):
                opt_container = ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(chr(65 + i), size=12, weight=ft.FontWeight.BOLD),
                                width=24,
                                height=24,
                                border_radius=12,
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Text(opt, size=15, expand=True),
                        ],
                        spacing=12,
                    ),
                    padding=ft.Padding(16, 16, 16, 16),
                    border_radius=AppStyles.RADIUS,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, idx=i: _select_option(idx),
                )
                options_col.controls.append(opt_container)
        else:
            answer_field.label = "Type your answer..." if qtype == QuestionType.THEORY else "Share your analysis..."
            next_btn.visible = True
            next_btn.text = "Finish Exam" if current_q["index"] == len(questions) - 1 else "Next Question"

        page.update()

    async def _finalize_exam():
        timer_running["active"] = False
        _save_open_answer()
        open_qs = []
        open_ans = []
        for idx, q in enumerate(questions):
            if q["type"] in QuestionType.OPEN:
                open_qs.append(q)
                open_ans.append(open_answers.get(idx, {"text": "", "image_bytes": None}))

        evaluations = []
        if open_qs:
            from components.offline_retry import OfflineRetryWidget

            is_connected = await check_internet_connection()
            state.is_online = is_connected
            if not is_connected:
                body_container.content = OfflineRetryWidget(page, on_retry=_finalize_exam, message="Akili needs an active internet connection to evaluate your mock exam answers.")
                page.update()
                return

            body_container.content = normal_layout
            loading_col.controls[1].value = "📝 Evaluating your answers..."
            loading_col.visible = True
            exam_content.visible = False
            page.update()

            try:
                evaluations = await evaluate_open_answers(
                    questions=open_qs,
                    student_answers=open_ans,
                    student_level=state.education_level or "Grade 10",
                )
            except Exception as e:
                loading_col.visible = False
                body_container.content = OfflineRetryWidget(page, on_retry=_finalize_exam, message=f"Evaluation failed: {str(e)[:150]}")
                page.update()
                return

            for ans in open_ans:
                ans["image_bytes"] = None
            for ev in evaluations:
                score["open_earned"] += ev.get("score", 0)
                score["open_total"] += ev.get("max_score", 10)
            loading_col.visible = False

        await _show_results(evaluations)

    async def _show_results(evaluations: list):
        exam_content.visible = False
        duration = 900 - time_remaining
        obj_count = sum(1 for q in questions if q["type"] == QuestionType.OBJECTIVE)
        obj_weight = DEFAULT_MARKS[QuestionType.OBJECTIVE]
        total_score = (score["correct"] * obj_weight) + score["open_earned"]
        total_possible = (obj_count * obj_weight) + score["open_total"]
        pct = (total_score / total_possible * 100) if total_possible else 0

        grade = "F"
        if pct >= 90:
            grade = "A"
        elif pct >= 80:
            grade = "B"
        elif pct >= 70:
            grade = "C"
        elif pct >= 60:
            grade = "D"

        passed = pct >= 60

        answers_for_db = []
        for idx in range(len(questions)):
            ans = open_answers.get(idx, {})
            answers_for_db.append({"text": ans.get("text", ""), "had_image": bool(ans.get("image_bytes"))})

        await db_manager.save_assessment(
            course_id=course["id"],
            score=total_score,
            total=total_possible,
            grade=grade,
            duration_seconds=duration,
            questions_json=json.dumps(questions),
            answers_json=json.dumps(answers_for_db),
            evaluations_json=json.dumps(evaluations),
        )
        if passed:
            await gamification_service.award_xp("mock_exam_complete")

        color = AppColors.SUCCESS if passed else AppColors.ERROR

        result_controls = [
            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED if passed else ft.Icons.ERROR_OUTLINE_ROUNDED, size=80, color=color),
            ft.Text("Exam Completed", size=28, weight=ft.FontWeight.BOLD),
            ft.Row(
                [
                    ft.Text(f"Grade: {grade}", size=32, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(f"({pct:.0f}%)", size=20, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            ft.Text(f"Score: {total_score:.0f} / {total_possible:.0f}", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(f"Time: {duration // 60}m {duration % 60}s", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
        ]

        if evaluations:
            result_controls.append(ft.Container(height=12))
            result_controls.append(ft.Text("Section B Feedback", size=16, weight=ft.FontWeight.BOLD))
            open_idx = 0
            for idx, q in enumerate(questions):
                if q["type"] in QuestionType.OPEN and open_idx < len(evaluations):
                    ev = evaluations[open_idx]
                    result_controls.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(f"Q{idx + 1}: {q['question'][:80]}...", size=13, weight=ft.FontWeight.W_600, max_lines=2),
                                    ft.Text(f"Score: {ev.get('score', 0):.0f}/{ev.get('max_score', 10):.0f}", size=13, color=AppColors.SUCCESS if ev.get("score", 0) >= ev.get("max_score", 10) * 0.6 else AppColors.ERROR),
                                    ft.Text(ev.get("feedback", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            padding=12,
                            border_radius=AppStyles.RADIUS_SMALL,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        )
                    )
                    open_idx += 1

        def _share_exam(e):
            dur_str = f"{duration // 60}m {duration % 60}s"
            show_share_sheet(
                page,
                ShareType.EXAM_RESULT,
                {
                    "grade": grade,
                    "pct": pct,
                    "subject": course.get("subject", ""),
                    "duration": dur_str,
                    "name": state.user_name,
                },
            )

        result_controls.append(ft.Container(height=16))
        result_controls.append(
            ft.Row(
                [
                    ft.FilledButton("Return Home", on_click=lambda e: page.run_task(navigate, "/dashboard")),
                    ft.TextButton("📤 Share", icon=ft.Icons.SHARE_ROUNDED, on_click=_share_exam),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
        )
        if ad_service:
            result_controls.append(ad_service.get_banner_ad())

        result_content.controls = result_controls
        result_content.visible = True
        page.update()

    async def _generate_exam():
        nonlocal time_remaining
        from components.offline_retry import OfflineRetryWidget

        is_connected = await check_internet_connection()
        state.is_online = is_connected
        if not is_connected:
            body_container.content = OfflineRetryWidget(page, on_retry=_generate_exam, message="Akili needs an active internet connection to generate your mock exam.")
            page.update()
            return

        body_container.content = normal_layout
        page.update()

        loading_col.visible = True
        page.update()

        questions.clear()
        open_answers.clear()
        current_q["index"] = 0
        current_q["answered"] = False
        score["correct"] = 0
        score["open_total"] = 0.0
        score["open_earned"] = 0.0

        mix_instructions = get_mix_prompt(EXAM_MIX)
        prompt = (
            f"You are creating an official, high-stakes mock exam for '{course['subject']}' at {course.get('level', state.education_level)} level.\n"
            f"To ensure maximum rigor and high standards, search the web specifically for actual past questions and curricula "
            f"from reputable national and international exam bodies (e.g., WAEC, JAMB, GCSE, SAT, AP, NECO) related to '{course['subject']}'.\n\n"
            f"CRITICAL REQUIREMENTS:\n"
            f"1. Search specifically for actual past papers or standardized questions. Do NOT generate simple, shallow, or easy textbook questions.\n"
            f"2. Every question must be challenging, authentic, and align perfectly with standard curricula (like WAEC, JAMB, or GCSE).\n"
            f"3. Put ALL objective questions FIRST (Section A), then ALL theory/subjective (Section B).\n"
            f"4. Use search_web to find and verify the questions, real source material, and actual solutions/explanations.\n"
            f"5. Each question must include 'type', 'source_material', 'source_url'.\n"
            f"6. FORMULA RENDERING CONSTRAINT: Do NOT use LaTeX syntax (like $, $$, \\frac, \\sqrt, etc.) for scientific/mathematical equations. "
            f"Instead, format all equations and formulas using standard Unicode characters, bold/italic text, and sub/superscripts "
            f"(e.g., use 'H₂O', 'x²', '±', '√', 'π', and italics for variables) so they render beautifully and natively in standard markdown.\n\n"
            f"EXAM STRUCTURE ({sum(EXAM_MIX.values())} questions total):\n{mix_instructions}\n\n"
            f"For objective: 'options' (4 strings), 'correct' (0-based), 'explanation'.\n"
            f"For theory: 'reference_answer', 'key_points'.\n"
            f"For subjective: 'marking_guide', 'sample_answer'.\n\n"
            f"Return ONLY a clean JSON array containing the generated questions."
        )

        def val_exam(text):
            arr = extract_json_array(text)
            if not arr:
                return None
            valid = validate_mixed_questions(arr)
            return valid if valid else None

        def _update_status(msg):
            loading_col.controls[1].value = msg
            page.update()

        try:
            response = await ai_service.chat_with_healing(
                messages=[{"role": "user", "content": prompt}],
                validation_func=val_exam,
                system_prompt="Generate a rigorous mock exam with verified source material. Return ONLY valid JSON array.",
                use_tools=True,
                on_status=_update_status,
            )
            parsed = response.get("parsed")
        except Exception as e:
            parsed = None
            response = {"content": str(e)}

        if parsed:
            # Sort: objectives first, then open questions
            obj_qs = [q for q in parsed if q["type"] == QuestionType.OBJECTIVE]
            open_qs = [q for q in parsed if q["type"] in QuestionType.OPEN]
            questions.extend(obj_qs + open_qs)

            time_remaining = 900
            loading_col.visible = False
            exam_content.visible = True
            _render_question()
            page.run_task(countdown_timer_task)
        else:
            loading_col.visible = False
            from components.offline_retry import OfflineRetryWidget

            err_msg = response.get("content", "Failed to generate exam.") if response else "Failed to generate exam."
            body_container.content = OfflineRetryWidget(page, on_retry=_generate_exam, message=f"Generation failed: {err_msg}")
            page.update()

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(_handle_back)),
                ft.Column(
                    [
                        ft.Text("Mock Exam", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(course["subject"], size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=0,
                    tight=True,
                    expand=True,
                ),
                timer_text,
            ],
            spacing=8,
        ),
        padding=ft.Padding(8, 8, 16, 8),
    )

    exam_content.controls = [
        section_text,
        ft.Container(
            content=ft.Column(
                [
                    ft.Row([question_type_badge, question_num], spacing=8),
                    question_text,
                ],
                spacing=8,
            ),
            padding=ft.Padding(0, 10, 0, 10),
        ),
        options_col,
        answer_field,
        voice_handler.status_indicator,
        or_divider,
        upload_row,
        image_preview,
        feedback_text,
        next_btn,
        ad_service.get_banner_ad() if ad_service else ft.Container(),
    ]

    normal_layout = ft.Column([loading_col, exam_content, result_content], scroll=ft.ScrollMode.AUTO)
    body_container = ft.Container(
        content=normal_layout,
        padding=20,
        expand=True,
    )

    page.run_task(_generate_exam)

    return ft.View(
        route="/exam",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            body_container,
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
