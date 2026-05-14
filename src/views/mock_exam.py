import time

import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service
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

    timer_text = ft.Text("00:00", size=14, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)
    question_text = ft.Text("", size=18, weight=ft.FontWeight.W_600)
    question_num = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    options_col = ft.Column(spacing=10)

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
        [
            ft.ProgressRing(width=36, height=36, stroke_width=3, color=AppColors.PRIMARY),
            ft.Text("Preparing exam...", size=14, weight=ft.FontWeight.W_500),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=True,
    )

    exam_content = ft.Column(visible=False, spacing=20, expand=True)
    result_content = ft.Column(visible=False, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _select_option(idx):
        if selected_answer["value"] is not None:
            return
        selected_answer["value"] = idx
        correct_idx = questions[current_q["index"]]["correct"]

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
        next_btn.visible = False

        # Timer update
        elapsed = int(time.time() - start_time["t"])
        mins, secs = divmod(elapsed, 60)
        timer_text.value = f"{mins:02d}:{secs:02d}"

        options_col.controls.clear()
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
        page.update()

    async def _show_results():
        exam_content.visible = False
        total = len(questions)
        pct = (score["correct"] / total * 100) if total else 0
        passed = pct >= 60

        await db_manager.save_quiz_attempt(course["id"], score["correct"], total, "", 1 if passed else 0)
        if passed:
            await gamification_service.award_xp("exam_pass")

        color = AppColors.SUCCESS if passed else AppColors.ERROR

        result_content.controls = [
            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED if passed else ft.Icons.ERROR_OUTLINE_ROUNDED, size=80, color=color),
            ft.Text("Exam Completed", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(f"Score: {score['correct']} / {total}", size=20, weight=ft.FontWeight.W_600, color=color),
            ft.FilledButton("Return Home", on_click=lambda e: page.run_task(navigate, "/dashboard")),
        ]
        result_content.visible = True
        page.update()

    async def _generate_exam():
        loading_col.visible = True
        page.update()
        response = await ai_service.chat(
            messages=[{"role": "user", "content": f"Generate 10 MCQ for {course['subject']}. Return JSON array."}],
            system_prompt="Return ONLY valid JSON array. No markdown.",
            use_tools=False,
        )
        from views.quiz_view import _parse_quiz_json

        parsed = _parse_quiz_json(response.get("content", ""))
        if parsed:
            questions.clear()
            questions.extend(parsed)
            current_q["index"] = 0
            score["correct"] = 0
            start_time["t"] = time.time()
            loading_col.visible = False
            exam_content.visible = True
            _render_question()
        else:
            loading_col.controls[1].value = "⚠️ Generation failed."
            page.update()

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
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
        ft.Container(content=ft.Column([question_num, question_text], spacing=8), padding=ft.Padding(0, 10, 0, 10)),
        options_col,
        next_btn,
    ]

    page.run_task(_generate_exam)

    return ft.View(
        route="/exam",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            ft.Container(
                                content=ft.Column([loading_col, exam_content, result_content], scroll=ft.ScrollMode.AUTO),
                                padding=20,
                                expand=True,
                            ),
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
