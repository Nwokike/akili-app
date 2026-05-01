"""Mock exam — timed assessment with AI-generated questions across all modules."""

import json
import random
import time

import flet as ft

from core.constants import XP_REWARDS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.ai_service import ai_service
from services.credit_service import credit_service
from services.gamification import gamification_service


def build_mock_exam_view(page: ft.Page, navigate) -> ft.View:
    course = state.current_course or {}
    if not course.get("id"):
        return ft.View(route="/exam", controls=[ft.Text("No course selected")])

    questions: list[dict] = []
    current_q = {"index": 0}
    selected_answer = {"value": None}
    score = {"correct": 0}
    start_time = {"t": 0}

    # ── UI refs ──────────────────────────────────────────────
    timer_text = ft.Text("00:00", size=14, weight=ft.FontWeight.BOLD, color=AppColors.ACCENT)
    question_text = ft.Text("", size=16, weight=ft.FontWeight.W_500)
    question_num = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    options_col = ft.Column(spacing=8)
    feedback_text = ft.Text("", size=14, visible=False)
    next_btn = ft.Button(
        "Next →", visible=False,
        style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=lambda e: _next_question(),
    )
    loading_col = ft.Column(
        [
            ft.ProgressRing(width=36, height=36, stroke_width=3),
            ft.Text("Generating exam...", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, visible=True,
    )
    exam_content = ft.Column(visible=False, spacing=16, expand=True)
    result_content = ft.Column(visible=False, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _select_option(idx):
        if selected_answer["value"] is not None:
            return
        selected_answer["value"] = idx
        correct_idx = questions[current_q["index"]]["correct"]

        for i, ctrl in enumerate(options_col.controls):
            if i == correct_idx:
                ctrl.bgcolor = "#1B5E20"
                ctrl.content.controls[0].color = ft.Colors.WHITE
            elif i == idx and idx != correct_idx:
                ctrl.bgcolor = "#B71C1C"
                ctrl.content.controls[0].color = ft.Colors.WHITE

        if idx == correct_idx:
            score["correct"] += 1
            feedback_text.value = "✅ Correct!"
            feedback_text.color = AppColors.SUCCESS
        else:
            correct_text = questions[current_q["index"]]["options"][correct_idx]
            feedback_text.value = f"❌ Answer: {correct_text}"
            feedback_text.color = AppColors.ERROR

        feedback_text.visible = True
        next_btn.visible = True
        page.update()

    def _next_question():
        current_q["index"] += 1
        if current_q["index"] >= len(questions):
            page.run_task(_show_results)
        else:
            _render_question()

    def _render_question():
        q = questions[current_q["index"]]
        question_num.value = f"Question {current_q['index'] + 1} of {len(questions)}"
        question_text.value = q["question"]
        selected_answer["value"] = None
        feedback_text.visible = False
        next_btn.visible = False

        # Update timer
        elapsed = int(time.time() - start_time["t"])
        mins, secs = divmod(elapsed, 60)
        timer_text.value = f"{mins:02d}:{secs:02d}"

        options_col.controls.clear()
        for i, opt in enumerate(q["options"]):
            options_col.controls.append(ft.Container(
                content=ft.Row([ft.Text(f"{chr(65+i)}. {opt}", size=14)]),
                padding=ft.Padding(16, 12, 16, 12),
                border_radius=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border=ft.Border(
                    left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                ),
                on_click=lambda e, idx=i: _select_option(idx),
                ink=True,
            ))
        page.update()

    async def _show_results():
        exam_content.visible = False
        total = len(questions)
        pct = (score["correct"] / total * 100) if total else 0
        elapsed = int(time.time() - start_time["t"])
        mins, secs = divmod(elapsed, 60)
        grade = "A" if pct >= 80 else "B" if pct >= 70 else "C" if pct >= 60 else "D" if pct >= 50 else "F"
        color = AppColors.SUCCESS if pct >= 60 else AppColors.ERROR

        await db_manager.save_assessment(course["id"], score["correct"], total, grade, elapsed)
        await gamification_service.award_xp("mock_exam_complete")

        result_content.controls = [
            ft.Icon(ft.Icons.SCHOOL, size=64, color=color),
            ft.Text("Mock Exam Results", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"Grade: {grade}", size=32, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(f"{score['correct']}/{total} • {int(pct)}%", size=16),
                    ft.Text(f"Time: {mins:02d}:{secs:02d}", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.ProgressBar(value=pct/100, color=color, bgcolor=ft.Colors.SURFACE_CONTAINER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                padding=20, width=250,
            ),
            ft.Text(f"+{XP_REWARDS['mock_exam_complete']} XP", size=14, color=AppColors.ACCENT),
            ft.Button(
                "Back to Course", icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/modules"),
                style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
            ),
        ]
        result_content.visible = True
        
        # Show interstitial ad
        ad_service = page.data.get("ad_service")
        if ad_service:
            await ad_service.show_interstitial()
            
        page.update()

    async def _generate_exam(e=None):
        ok = await credit_service.spend("mock_exam")
        if not ok:
            loading_col.controls[1].value = "⚠️ Not enough credits"
            page.update()
            return

        loading_col.visible = True
        exam_content.visible = False
        result_content.visible = False
        page.update()

        subject = course.get("subject", "General")
        level = course.get("level", state.education_level or "SS2")

        def _on_status(msg):
            if len(loading_col.controls) > 1:
                loading_col.controls[1].value = msg
                page.update()

        response = await ai_service.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"Generate 10 multiple choice exam questions for {subject} at {level} level.\n"
                    f"Cover all major topics in the curriculum.\n"
                    f"Return ONLY a JSON array where each object has:\n"
                    f'"question", "options" (4 choices), "correct" (0-3 index)\n'
                    f"No markdown, no explanation, just the JSON array."
                ),
            }],
            system_prompt="Generate exam questions. Return ONLY valid JSON array.",
            search_query=f"{subject} {level} exam questions past papers",
            on_status=_on_status,
        )

        from views.quiz_view import _parse_quiz_json
        parsed = _parse_quiz_json(response.get("content", ""))

        if parsed and len(parsed) >= 5:
            questions.clear()
            questions.extend(parsed)
            random.shuffle(questions)
            current_q["index"] = 0
            score["correct"] = 0
            start_time["t"] = time.time()
            loading_col.visible = False
            exam_content.visible = True
            _render_question()
        else:
            loading_col.controls[1].value = "⚠️ Exam generation failed. Try again."
            page.update()

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: page.run_task(navigate, "/modules")),
            ft.Column([
                ft.Text("Mock Exam", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(course.get("subject", ""), size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=2, expand=True),
            ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.TIMER, size=16), timer_text], spacing=4),
                padding=ft.Padding(8, 4, 8, 4),
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
            ),
        ], spacing=8),
        padding=ft.Padding(8, 8, 16, 8),
    )

    exam_content.controls = [question_num, question_text, options_col, feedback_text, next_btn]
    page.run_task(_generate_exam)

    return ft.View(
        route="/exam",
        controls=[ft.SafeArea(
            ft.Column([header, ft.Container(
                content=ft.Column([loading_col, exam_content, result_content], spacing=8),
                padding=ft.Padding(16, 8, 16, 16), expand=True,
            )], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )
