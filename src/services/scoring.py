"""Scoring — pure functions for quiz/exam grading math.

Ported from Akili v1's quiz_view.py / mock_exam.py scoring (verbatim
thresholds), extracted as pure functions so they are unit-testable
instead of buried in view files.
"""

from __future__ import annotations

from core.question_types import DEFAULT_MARKS, QuestionType

QUIZ_PASS_PCT = 50.0
EXAM_PASS_PCT = 60.0


def score_mixed(
    questions: list[dict],
    objective_correct: int,
    evaluations: list[dict],
) -> tuple[float, float, float, bool, float]:
    """Score a mixed quiz.

    Returns (total_score, total_possible, pct, passed, pass_threshold).
    `questions` decides the weighting: objective marks are DEFAULT_MARKS,
    open marks come from the evaluations' max_score.
    `evaluations` must align with the OPEN questions in order.
    """
    obj_count = sum(1 for q in questions if q.get("type") == QuestionType.OBJECTIVE)
    obj_weight = DEFAULT_MARKS[QuestionType.OBJECTIVE]
    open_qs = [q for q in questions if q.get("type") in QuestionType.OPEN]

    open_earned = 0.0
    open_total = 0.0
    for i, q in enumerate(open_qs):
        default_max = float(q.get("max_marks", DEFAULT_MARKS[QuestionType.THEORY]))
        if i < len(evaluations):
            ev = evaluations[i] or {}
            open_earned += float(ev.get("score", 0) or 0)
            open_total += float(ev.get("max_score", 0) or default_max)
        else:
            open_total += default_max

    total_score = objective_correct * obj_weight + open_earned
    total_possible = obj_count * obj_weight + open_total
    pct = (total_score / total_possible * 100) if total_possible else 0.0
    return total_score, total_possible, pct, pct >= QUIZ_PASS_PCT, QUIZ_PASS_PCT


def exam_grade(pct: float) -> tuple[str, bool]:
    """Exam grade bands (v1 verbatim). Returns (grade, passed)."""
    if pct >= 90:
        grade = "A"
    elif pct >= 80:
        grade = "B"
    elif pct >= 70:
        grade = "C"
    elif pct >= 60:
        grade = "D"
    else:
        grade = "F"
    return grade, pct >= EXAM_PASS_PCT


def assignment_pct(evaluations: list[dict]) -> float:
    """Assignment stored score is a 0–100 pct over earned/max."""
    earned = sum(float(ev.get("score", 0) or 0) for ev in evaluations)
    possible = sum(float(ev.get("max_score", 0) or 0) for ev in evaluations)
    if not possible:
        return 0.0
    return earned / possible * 100


def feedback_cards(evaluations: list[dict], threshold: float, questions: list[dict] | None = None) -> list[dict]:
    """Per-open-answer feedback cards; 'met' marks above the threshold.

    `questions` (optional, aligned with the evaluations) adds a truncated
    question snippet per card — v1 shows `Q{i}: {question[:80]}…` on
    quiz/exam/assignment results.
    """
    cards = []
    for i, ev in enumerate(evaluations):
        max_score = float(ev.get("max_score", 0) or 0)
        score = float(ev.get("score", 0) or 0)
        ratio = (score / max_score) if max_score else 0.0
        question = ""
        if questions and i < len(questions):
            question = str(questions[i].get("question") or "").strip()
            if len(question) > 80:
                question = question[:80] + "…"
        cards.append(
            {
                "index": i,
                "question": question,
                "score": score,
                "max_score": max_score,
                "feedback": str(ev.get("feedback", "")),
                "suggestions": str(ev.get("suggestions", "")),
                "key_points_hit": list(ev.get("key_points_hit", []) or []),
                "key_points_missed": list(ev.get("key_points_missed", []) or []),
                "met": ratio >= threshold,
            }
        )
    return cards
