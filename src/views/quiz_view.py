"""Quiz view — AI-generated MCQ with scoring, XP, and module pass/fail."""

import json
import random

import flet as ft

from core.constants import XP_REWARDS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.ai_service import ai_service
from services.gamification import gamification_service


def build_quiz_view(page: ft.Page, navigate) -> ft.View:
    module = state.current_module
    course = state.current_course or {}
    if not module:
        return ft.View(route="/quiz", controls=[ft.Text("No module selected")])

    topics = json.loads(module.get("topics_json", "[]"))
    questions: list[dict] = []
    current_q = {"index": 0}
    selected_answer = {"value": None}
    score = {"correct": 0}

    # ── UI refs ──────────────────────────────────────────────
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
            ft.Text("Generating quiz questions...", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, visible=True,
    )
    quiz_content = ft.Column(visible=False, spacing=16, expand=True)
    result_content = ft.Column(visible=False, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _select_option(idx):
        if selected_answer["value"] is not None:
            return  # Already answered
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

        options_col.controls.clear()
        for i, opt in enumerate(q["options"]):
            opt_container = ft.Container(
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
            )
            options_col.controls.append(opt_container)
        page.update()

    async def _show_results():
        quiz_content.visible = False
        total = len(questions)
        pct = (score["correct"] / total * 100) if total else 0
        passed = pct >= 60

        # Save to DB
        await db_manager.save_quiz_attempt(
            module["id"], score["correct"], total,
            json.dumps(questions), 1 if passed else 0,
        )

        # XP
        if passed:
            if pct == 100:
                await gamification_service.award_xp("quiz_perfect")
            else:
                await gamification_service.award_xp("quiz_pass")

        grade = "A" if pct >= 80 else "B" if pct >= 70 else "C" if pct >= 60 else "D" if pct >= 50 else "F"
        color = AppColors.SUCCESS if passed else AppColors.ERROR

        result_content.controls = [
            ft.Icon(
                ft.Icons.CELEBRATION if passed else ft.Icons.SENTIMENT_DISSATISFIED,
                size=64, color=color,
            ),
            ft.Text(
                "🎉 Quiz Passed!" if passed else "Keep Trying!",
                size=22, weight=ft.FontWeight.BOLD,
            ),
            ft.Text(f"{score['correct']}/{total} correct — Grade {grade}", size=16),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"{int(pct)}%", size=40, weight=ft.FontWeight.BOLD, color=color),
                    ft.ProgressBar(value=pct/100, color=color, bgcolor=ft.Colors.SURFACE_CONTAINER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                width=200,
            ),
            ft.Text(
                f"+{XP_REWARDS.get('quiz_perfect' if pct==100 else 'quiz_pass', 0)} XP" if passed else "60% needed to pass",
                size=14, color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Row([
                ft.Button(
                    "Retake Quiz", icon=ft.Icons.REPLAY,
                    on_click=lambda e: page.run_task(_generate_quiz),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                ),
                ft.Button(
                    "Back to Module", icon=ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.run_task(navigate, "/modules"),
                    style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=12),
        ]
        result_content.visible = True
        page.update()

    async def _generate_quiz(e=None):
        loading_col.visible = True
        quiz_content.visible = False
        result_content.visible = False
        page.update()

        topic_list = ", ".join(topics) if topics else module["title"]

        def _on_status(msg):
            if len(loading_col.controls) > 1:
                loading_col.controls[1].value = msg
                page.update()

        response = await ai_service.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"Generate exactly 5 multiple choice questions about: {module['title']}\n"
                    f"Topics: {topic_list}\n"
                    f"Level: {course.get('level', state.education_level or 'SS2')}\n\n"
                    f"Return ONLY a JSON array. Each object must have:\n"
                    f'- "question": the question text\n'
                    f'- "options": array of exactly 4 answer choices\n'
                    f'- "correct": index (0-3) of the correct answer\n\n'
                    f"Example: [{{"
                    f'"question":"What is 2+2?",'
                    f'"options":["3","4","5","6"],'
                    f'"correct":1'
                    f"}}]\n\n"
                    f"Return ONLY the JSON array, no markdown, no explanation."
                ),
            }],
            system_prompt="Generate educational quiz questions. Return ONLY valid JSON array. No markdown code blocks.",
            search_query=f"{module['title']} {course.get('subject','')} quiz questions answers",
            on_status=_on_status,
        )

        content = response.get("content", "")
        parsed = _parse_quiz_json(content)

        if parsed and len(parsed) >= 3:
            questions.clear()
            questions.extend(parsed)
            random.shuffle(questions)
            current_q["index"] = 0
            score["correct"] = 0
            loading_col.visible = False
            quiz_content.visible = True
            _render_question()
        else:
            print(f"[Quiz] Parse failed. Raw: {content[:300]}")
            loading_col.controls[1].value = "⚠️ Quiz generation failed. Try again."
            page.update()

    # ── Header ───────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: page.run_task(navigate, "/modules")),
            ft.Column([
                ft.Text("Quiz", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(module["title"], size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2, expand=True),
        ], spacing=8),
        padding=ft.Padding(8, 8, 16, 8),
    )

    quiz_content.controls = [question_num, question_text, options_col, feedback_text, next_btn]

    page.run_task(_generate_quiz)

    return ft.View(
        route="/quiz",
        controls=[ft.SafeArea(
            ft.Column([header, ft.Container(
                content=ft.Column([loading_col, quiz_content, result_content], spacing=8),
                padding=ft.Padding(16, 8, 16, 16), expand=True,
            )], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )


def _parse_quiz_json(text: str) -> list[dict] | None:
    import re
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Try direct
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [q for q in data if "question" in q and "options" in q and "correct" in q]
    except (json.JSONDecodeError, TypeError):
        pass
    # Try ```json blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            if isinstance(data, list):
                return [q for q in data if "question" in q and "options" in q and "correct" in q]
        except json.JSONDecodeError:
            pass
    # Try first [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end+1])
            if isinstance(data, list):
                return [q for q in data if "question" in q and "options" in q and "correct" in q]
        except json.JSONDecodeError:
            pass
    return None
