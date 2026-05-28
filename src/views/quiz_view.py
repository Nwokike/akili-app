import json
import re

import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service


def build_quiz_view(page: ft.Page, navigate) -> ft.View:
    module = state.current_module
    if not module:
        return ft.View(route="/quiz", controls=[ft.Text("No module selected")])

    questions: list[dict] = []
    current_q = {"index": 0}
    selected_answer = {"value": None}
    score = {"correct": 0}

    question_text = ft.Text("", size=18, weight=ft.FontWeight.W_600)
    question_num = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    options_col = ft.Column(spacing=10)
    feedback_text = ft.Text("", size=14, visible=False, weight=ft.FontWeight.W_500)

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
            ft.Text("Crafting your quiz...", size=14, weight=ft.FontWeight.W_500),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
        visible=True,
    )

    quiz_content = ft.Column(visible=False, spacing=20, expand=True)
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
            explanation = questions[current_q["index"]].get("explanation", "")
            feedback_text.value = f"Correct! {explanation}" if explanation else "Correct! Well done."
            feedback_text.color = AppColors.SUCCESS
        else:
            correct_text = questions[current_q["index"]]["options"][correct_idx]
            explanation = questions[current_q["index"]].get("explanation", "")
            feedback_text.value = f"The correct answer was: {correct_text}. {explanation}" if explanation else f"The correct answer was: {correct_text}"
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
        quiz_content.visible = False
        total = len(questions)
        pct = (score["correct"] / total * 100) if total else 0
        passed = pct >= 60

        await db_manager.save_quiz_attempt(
            module["id"],
            score["correct"],
            total,
            json.dumps(questions),
            1 if passed else 0,
        )

        # Auto-unlock next module on pass
        if passed and state.current_course:
            all_modules = await db_manager.get_modules(state.current_course["id"])
            for i, m in enumerate(all_modules):
                if m["id"] == module["id"] and i + 1 < len(all_modules):
                    await db_manager.unlock_module(all_modules[i + 1]["id"])
                    break

        color = AppColors.SUCCESS if passed else AppColors.ERROR

        result_content.controls = [
            ft.Container(height=40),
            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED if passed else ft.Icons.ERROR_OUTLINE_ROUNDED, size=80, color=color),
            ft.Text("Quiz Completed" if passed else "Keep Practicing", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(f"You scored {score['correct']}/{total}", size=18, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(height=20),
            ft.Row(
                [
                    ft.OutlinedButton("Retake", icon=ft.Icons.REPLAY_ROUNDED, on_click=lambda e: page.run_task(_generate_quiz)),
                    ft.FilledButton(
                        "Continue",
                        icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                        on_click=lambda e: page.run_task(navigate, "/modules"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
        ]
        result_content.visible = True
        page.update()

    async def _generate_quiz(e=None):
        loading_col.visible = True
        quiz_content.visible = False
        result_content.visible = False
        page.update()

        lesson_cache = module.get("lesson_cache", "")
        context = f"\n\nLesson content for reference:\n{lesson_cache[:3000]}" if lesson_cache else ""
        response = await ai_service.chat(
            messages=[{"role": "user", "content": f"Generate 5 MCQs about {module['title']} from lesson content.{context}\n\nReturn a JSON array: each has 'question', 'options' (4 strings), 'correct' (0-based index)."}],
            system_prompt="Return ONLY valid JSON array.",
            use_tools=False,
        )
        parsed = _parse_quiz_json(response.get("content", ""))
        if parsed:
            questions.clear()
            questions.extend(parsed)
            current_q["index"] = 0
            score["correct"] = 0
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
        ft.Container(content=ft.Column([question_num, question_text], spacing=8), padding=ft.Padding(0, 10, 0, 10)),
        options_col,
        ft.Container(height=10),
        feedback_text,
        next_btn,
    ]

    page.run_task(_generate_quiz)

    return ft.View(
        route="/quiz",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            ft.Container(
                                content=ft.Column([loading_col, quiz_content, result_content], scroll=ft.ScrollMode.AUTO),
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


def _parse_quiz_json(text: str) -> list[dict] | None:
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            validated = []
            for q in data:
                if isinstance(q, dict) and "question" in q and "options" in q and "correct" in q:
                    validated.append(q)
            return validated if validated else None
    except Exception:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                validated = []
                for q in data:
                    if isinstance(q, dict) and "question" in q and "options" in q and "correct" in q:
                        validated.append(q)
                return validated if validated else None
        except Exception:
            pass
    return None
