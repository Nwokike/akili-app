"""Quiz view — mixed question types: objective + theory + subjective.

Objective questions get instant feedback on tap.
Open questions (theory/subjective) accept typed text OR uploaded/snapped images.
After all questions, open answers are batch-evaluated by AI using source material.
"""

import json

import flet as ft

from core.ai_utils import extract_json_array, validate_mixed_questions
from core.question_types import QUIZ_MIX, QuestionType, get_mix_prompt
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
from services.evaluation import evaluate_open_answers
from services.file_picker import FilePickerService
from services.share_service import ShareType, show_share_sheet
from components.voice_input import VoiceInputHandler


def build_quiz_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    module = state.current_module
    if not module:
        return ft.View(route="/quiz", controls=[ft.Text("No module selected")])

    questions: list[dict] = []
    current_q = {"index": 0}
    score = {"correct": 0, "open_total": 0.0, "open_earned": 0.0}
    # Store student answers for open questions: {q_index: {"text": str, "image_bytes": bytes|None, "image_mime": str|None}}
    open_answers: dict[int, dict] = {}

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
        [ft.ProgressRing(width=36, height=36, stroke_width=3, color=AppColors.PRIMARY), ft.Text("Crafting your quiz...", size=14, weight=ft.FontWeight.W_500)],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=True,
    )

    quiz_content = ft.Column(visible=False, spacing=16, expand=True)
    result_content = ft.Column(visible=False, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _select_option(idx):
        q = questions[current_q["index"]]
        if q["type"] != QuestionType.OBJECTIVE:
            return
        if current_q.get("answered"):
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
            explanation = q.get("explanation", "")
            feedback_text.value = f"✅ Correct! {explanation}" if explanation else "✅ Correct!"
            feedback_text.color = AppColors.SUCCESS
        else:
            correct_text = q["options"][correct_idx]
            explanation = q.get("explanation", "")
            feedback_text.value = f"❌ The answer was: {correct_text}. {explanation}" if explanation else f"❌ The answer was: {correct_text}"
            feedback_text.color = AppColors.ERROR

        feedback_text.visible = True
        next_btn.visible = True
        page.update()

    def _save_open_answer():
        """Save current open answer before moving to next question."""
        idx = current_q["index"]
        q = questions[idx]
        if q["type"] in QuestionType.OPEN:
            open_answers[idx] = {
                "text": answer_field.value or "",
                "image_bytes": answer_image_data["bytes"],
                "image_mime": answer_image_data["mime"],
            }
            # Clear for next question — bytes stay in open_answers dict temporarily
            answer_field.value = ""
            _clear_image()

    def _next_question():
        _save_open_answer()
        current_q["index"] += 1
        current_q["answered"] = False
        if current_q["index"] >= len(questions):
            page.run_task(_finalize_quiz)
        else:
            _render_question()

    def _render_question():
        q = questions[current_q["index"]]
        qtype = q["type"]
        question_num.value = f"Question {current_q['index'] + 1} of {len(questions)}"
        question_text.value = q["question"]
        feedback_text.visible = False
        current_q["answered"] = False

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

        # Show/hide controls based on type
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
            # Open question: show text field + upload, always show Next
            answer_field.label = "Type your answer..." if qtype == QuestionType.THEORY else "Share your analysis..."
            next_btn.visible = True
            next_btn.text = "Submit Answer" if current_q["index"] == len(questions) - 1 else "Next Question"

        page.update()

    async def _finalize_quiz():
        """After all questions: evaluate open answers via AI, then show results."""
        # Collect open questions and their answers
        open_qs = []
        open_ans = []
        for idx, q in enumerate(questions):
            if q["type"] in QuestionType.OPEN:
                open_qs.append(q)
                ans = open_answers.get(idx, {"text": "", "image_bytes": None})
                open_ans.append(ans)

        evaluations = []
        if open_qs:
            from components.offline_retry import OfflineRetryWidget

            if not state.is_online:
                body_container.content = OfflineRetryWidget(page, on_retry=_finalize_quiz, message="Akili needs an active internet connection to evaluate your answers.")
                page.update()
                return

            body_container.content = normal_layout
            loading_col.controls[1].value = "📝 Evaluating your answers..."
            loading_col.visible = True
            quiz_content.visible = False
            page.update()

            evaluations = await evaluate_open_answers(
                questions=open_qs,
                student_answers=open_ans,
                student_level=state.education_level or "Grade 10",
            )

            # Discard all image bytes now — no bloat
            for ans in open_ans:
                ans["image_bytes"] = None

            # Sum open scores
            for ev in evaluations:
                score["open_earned"] += ev.get("score", 0)
                score["open_total"] += ev.get("max_score", 10)

            loading_col.visible = False

        await _show_results(evaluations)

    async def _show_results(evaluations: list):
        quiz_content.visible = False
        obj_count = sum(1 for q in questions if q["type"] == QuestionType.OBJECTIVE)
        total_score = score["correct"] + score["open_earned"]
        total_possible = obj_count + score["open_total"]
        pct = (total_score / total_possible * 100) if total_possible else 0
        passed = pct >= 60

        # Serialize answers for DB (text only, no bytes)
        answers_for_db = []
        for idx in range(len(questions)):
            ans = open_answers.get(idx, {})
            answers_for_db.append({"text": ans.get("text", ""), "had_image": bool(ans.get("image_bytes"))})

        await db_manager.save_quiz_attempt(
            module["id"],
            total_score,
            total_possible,
            json.dumps(questions),
            1 if passed else 0,
            answers_json=json.dumps(answers_for_db),
            evaluations_json=json.dumps(evaluations),
        )

        if passed and state.current_course:
            all_modules = await db_manager.get_modules(state.current_course["id"])
            for i, m in enumerate(all_modules):
                if m["id"] == module["id"] and i + 1 < len(all_modules):
                    await db_manager.unlock_module(all_modules[i + 1]["id"])
                    break

        color = AppColors.SUCCESS if passed else AppColors.ERROR
        result_controls = [
            ft.Container(height=20),
            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED if passed else ft.Icons.ERROR_OUTLINE_ROUNDED, size=80, color=color),
            ft.Text("Quiz Completed" if passed else "Keep Practicing", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(f"Score: {total_score:.0f} / {total_possible:.0f} ({pct:.0f}%)", size=18, color=ft.Colors.ON_SURFACE_VARIANT),
        ]

        # Show per-question feedback for open questions
        if evaluations:
            result_controls.append(ft.Container(height=16))
            result_controls.append(ft.Text("Open Answer Feedback", size=16, weight=ft.FontWeight.BOLD))
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

        def _share_result(e):
            course_data = state.current_course or {}
            show_share_sheet(
                page,
                ShareType.QUIZ_RESULT,
                {
                    "pct": pct,
                    "subject": course_data.get("subject", ""),
                    "module": module["title"],
                    "name": state.user_name,
                },
            )

        result_controls.extend(
            [
                ft.Container(height=20),
                ft.Row(
                    [
                        ft.OutlinedButton("Retake", icon=ft.Icons.REPLAY_ROUNDED, on_click=lambda e: page.run_task(_generate_quiz)),
                        ft.FilledButton("Continue", icon=ft.Icons.ARROW_FORWARD_ROUNDED, on_click=lambda e: page.run_task(navigate, "/modules")),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=16,
                ),
                ft.TextButton("📤 Share Result", icon=ft.Icons.SHARE_ROUNDED, on_click=_share_result),
                ad_service.get_banner_ad() if ad_service else ft.Container(),
            ]
        )

        result_content.controls = result_controls
        result_content.visible = True
        page.update()

    async def _generate_quiz(e=None):
        from components.offline_retry import OfflineRetryWidget

        if not state.is_online:
            body_container.content = OfflineRetryWidget(page, on_retry=_generate_quiz, message="Akili needs an active internet connection to generate your custom quiz.")
            page.update()
            return

        body_container.content = normal_layout
        page.update()

        loading_col.visible = True
        loading_col.controls[1].value = "Crafting your quiz..."
        quiz_content.visible = False
        result_content.visible = False
        page.update()

        # Reset state
        questions.clear()
        open_answers.clear()
        current_q["index"] = 0
        current_q["answered"] = False
        score["correct"] = 0
        score["open_total"] = 0.0
        score["open_earned"] = 0.0

        lesson_cache = module.get("lesson_cache", "")
        context = f"\n\nLesson content:\n{lesson_cache[:3000]}" if lesson_cache else ""

        mix_instructions = get_mix_prompt(QUIZ_MIX)
        prompt = (
            f"Generate questions about '{module['title']}' for {state.education_level or 'Grade 10'} students.{context}\n\n"
            f"QUESTION MIX (exactly {sum(QUIZ_MIX.values())} questions):\n{mix_instructions}\n\n"
            f"CRITICAL: For EVERY question, include 'source_material' with verified facts.\n"
            f"FORMULA RENDERING CONSTRAINT: Do NOT use LaTeX syntax (like $, $$, \\frac, \\sqrt, etc.) for scientific/mathematical equations. "
            f"Instead, format all equations and formulas using standard Unicode characters, bold/italic text, and sub/superscripts "
            f"(e.g., use 'H₂O', 'x²', '±', '√', 'π', and italics for variables) so they render beautifully and natively in standard markdown.\n\n"
            f"For objective: include 'options' (4 strings), 'correct' (0-based index), 'explanation'.\n"
            f"For theory: include 'reference_answer', 'key_points' list.\n"
            f"For subjective: include 'marking_guide', 'sample_answer'.\n\n"
            f"Return as JSON array. Each object MUST have 'type' field."
        )

        def val_quiz(text):
            arr = extract_json_array(text)
            if not arr:
                return None
            valid = validate_mixed_questions(arr)
            return valid if valid else None

        response = await ai_service.chat_with_healing(
            messages=[{"role": "user", "content": prompt}],
            validation_func=val_quiz,
            system_prompt="Return ONLY valid JSON array of mixed question types. No markdown.",
            use_tools=False,
        )
        parsed = response.get("parsed")
        if parsed:
            questions.extend(parsed)
            loading_col.visible = False
            quiz_content.visible = True
            _render_question()
        else:
            loading_col.controls[1].value = "⚠️ Failed to generate quiz."
            page.update()

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/modules")),
                ft.Column(
                    [
                        ft.Text("Knowledge Check", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(module["title"], size=12, color=ft.Colors.ON_SURFACE_VARIANT),
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

    quiz_content.controls = [
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
        ft.Container(height=8),
        feedback_text,
        next_btn,
        ad_service.get_banner_ad() if ad_service else ft.Container(),
    ]

    normal_layout = ft.Column([loading_col, quiz_content, result_content], scroll=ft.ScrollMode.AUTO)
    body_container = ft.Container(
        content=normal_layout,
        padding=20,
        expand=True,
    )

    page.run_task(_generate_quiz)

    return ft.View(
        route="/quiz",
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
