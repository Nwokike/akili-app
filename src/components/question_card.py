"""QuestionCard — one question renderer shared by quiz and exam.

Type badge + question + (objective options | open answer field).
Pure display + callback hooks. The screen owns state.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft
from flet import Control

from components.open_answer import OpenAnswer
from core import tokens
from core.question_types import QuestionType

_BADGE_STYLE = {
    QuestionType.OBJECTIVE: ("Objective", None),  # PRIMARY resolved at build
    QuestionType.THEORY: ("Theory", None),
    QuestionType.SUBJECTIVE: ("Subjective", None),
}


def _badge(qtype: str) -> Control:
    from core.theme import AppColors

    label, _ = _BADGE_STYLE.get(qtype, ("Objective", None))
    colour = {
        QuestionType.OBJECTIVE: AppColors.PRIMARY,
        QuestionType.THEORY: AppColors.ACCENT,
        QuestionType.SUBJECTIVE: "#9B59B6",
    }.get(qtype, AppColors.PRIMARY)
    return ft.Container(
        content=ft.Text(label, size=tokens.FONT_XS - 1, weight=ft.FontWeight.BOLD, color=colour),
        padding=ft.Padding(8, 2, 8, 2),
        border_radius=tokens.RADIUS_FULL,
        bgcolor=ft.Colors.with_opacity(0.12, colour),
    )


def _option_row(
    letter: str,
    text: str,
    index: int,
    *,
    selected: int | None,
    revealed: bool,
    correct: int | None,
    on_select: Callable[[int], None] | None,
) -> Control:
    """One MCQ option. Colours reveal correct/wrong only after answering."""
    from core.theme import AppColors

    if revealed and correct is not None:
        if index == correct:
            border, bg = AppColors.SUCCESS, ft.Colors.with_opacity(0.10, AppColors.SUCCESS)
        elif index == selected:
            border, bg = AppColors.ERROR, ft.Colors.with_opacity(0.10, AppColors.ERROR)
        else:
            border, bg = None, ft.Colors.SURFACE_CONTAINER_HIGHEST
    elif selected == index:
        border, bg = AppColors.PRIMARY, ft.Colors.with_opacity(0.08, AppColors.PRIMARY)
    else:
        border, bg = None, ft.Colors.SURFACE_CONTAINER_HIGHEST

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(letter, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    width=28,
                    height=28,
                    border_radius=14,
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(text, size=tokens.FONT_MD, expand=True),
            ],
            spacing=tokens.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
        border_radius=tokens.RADIUS_MD,
        bgcolor=bg,
        border=ft.Border.all(2, border) if border else None,
        ink=not revealed and on_select is not None,
        on_click=(lambda e: on_select(index)) if (not revealed and on_select) else None,
    )


def QuestionCard(
    question: dict,
    q_number: int,
    q_total: int,
    *,
    selected: int | None = None,
    revealed: bool = False,
    show_correct: bool = True,
    section_label: str | None = None,
    feedback: str = "",
    on_select_option: Callable[[int], None] | None = None,
    answer_value: str = "",
    on_answer_change: Callable[[str], None] | None = None,
    on_answer_image: Callable[[bytes, str, str], None] | None = None,
    answer_has_image: bool = False,
    disabled: bool = False,
) -> Control:
    """One question.

    - `section_label` shows Section A/B (exam).
    - `feedback` is the instant-feedback line (quiz shows it; exam passes "").
    - `show_correct` controls whether the correct option is highlighted on
      reveal. Quiz reveals it; the exam highlights only right/wrong.
    - Open questions embed the OpenAnswer field (typing + voice + photo).
    """
    qtype = question.get("type", QuestionType.OBJECTIVE)
    is_open = qtype in QuestionType.OPEN

    controls: list[ft.Control] = [
        ft.Row(
            controls=[
                ft.Text(
                    f"Question {q_number} of {q_total}",
                    size=tokens.FONT_XS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    expand=True,
                ),
                _badge(qtype),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    ]
    if section_label:
        from core.theme import AppColors

        controls.append(ft.Text(section_label, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD, color=AppColors.ACCENT))
    controls.append(ft.Text(question.get("question", ""), size=tokens.FONT_MD, weight=ft.FontWeight.W_500, selectable=True))

    if is_open:
        controls.append(
            OpenAnswer(
                qtype,
                value=answer_value,
                on_change=on_answer_change,
                on_image=on_answer_image,
                has_image=answer_has_image,
                disabled=disabled or revealed,
            )
        )
    else:
        letters = ("A", "B", "C", "D")
        options = list(question.get("options") or [])
        correct_idx = question.get("correct") if (revealed and show_correct) else None
        for i, opt in enumerate(options):
            controls.append(
                _option_row(
                    letters[i] if i < len(letters) else str(i + 1),
                    str(opt),
                    i,
                    selected=selected,
                    revealed=revealed,
                    correct=correct_idx,
                    on_select=on_select_option,
                )
            )
        if feedback:
            controls.append(ft.Text(feedback, size=tokens.FONT_SM, selectable=True, color=ft.Colors.ON_SURFACE_VARIANT))

    source = (question.get("source_material") or "").strip()
    if source and not is_open:
        controls.append(ft.Text(f"Source: {source[:160]}", size=tokens.FONT_XS - 1, italic=True, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)))

    return ft.Container(
        content=ft.Column(controls=controls, spacing=tokens.SPACE_SM, tight=True),
        padding=tokens.SPACE_LG,
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
    )
