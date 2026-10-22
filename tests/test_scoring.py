"""Scoring tests — the pure grading math v1 buried in its views."""

from services.scoring import (
    EXAM_PASS_PCT,
    QUIZ_PASS_PCT,
    assignment_pct,
    exam_grade,
    feedback_cards,
    score_mixed,
)

OBJ = [
    {"type": "objective", "question": "1"},
    {"type": "objective", "question": "2"},
    {"type": "objective", "question": "3"},
]
OPEN = [
    {"type": "theory", "question": "t", "max_marks": 10},
    {"type": "subjective", "question": "s", "max_marks": 10},
]
MIXED = OBJ + OPEN


def test_quiz_pass_threshold():
    assert QUIZ_PASS_PCT == 50.0
    assert EXAM_PASS_PCT == 60.0


def test_score_mixed_all_objective():
    total, possible, pct, passed, _ = score_mixed(OBJ, 2, [])
    assert (total, possible) == (6, 9)
    assert abs(pct - 66.67) < 0.01
    assert passed is True


def test_score_mixed_boundary_pass():
    # 3 obj (9) + 2 open (20) = 29 possible. Need 50%: e.g. 2 obj (6) + 9 open = 15/29.
    evals = [{"score": 5, "max_score": 10}, {"score": 4, "max_score": 10}]
    total, possible, pct, passed, _ = score_mixed(MIXED, 2, evals)
    assert possible == 9 + 20
    assert total == 6 + 9
    assert passed is True


def test_score_mixed_fail():
    total, possible, pct, passed, _ = score_mixed(MIXED, 0, [{"score": 0, "max_score": 10}, {"score": 0, "max_score": 10}])
    assert passed is False
    assert pct == 0.0


def test_score_mixed_missing_evals_use_default_max():
    # Evaluations missing -> max still counted so pct degrades honestly.
    total, possible, pct, passed, _ = score_mixed(OPEN[:1], 0, [])
    assert possible == 10
    assert pct == 0.0


def test_score_mixed_zero_questions():
    total, possible, pct, passed, _ = score_mixed([], 0, [])
    assert (total, possible, pct, passed) == (0, 0, 0.0, False)


def test_exam_grade_bands():
    assert exam_grade(95) == ("A", True)
    assert exam_grade(90) == ("A", True)
    assert exam_grade(85) == ("B", True)
    assert exam_grade(75) == ("C", True)
    assert exam_grade(65) == ("D", True)
    assert exam_grade(60) == ("D", True)
    assert exam_grade(59.9) == ("F", False)
    assert exam_grade(0) == ("F", False)


def test_assignment_pct():
    assert assignment_pct([{"score": 8, "max_score": 10}, {"score": 9, "max_score": 10}]) == 85.0
    assert assignment_pct([]) == 0.0
    assert assignment_pct([{"score": 0, "max_score": 0}]) == 0.0


def test_feedback_cards_threshold():
    evs = [
        {"score": 8, "max_score": 10, "feedback": "good", "suggestions": "more"},
        {"score": 2, "max_score": 10, "feedback": "weak", "suggestions": "revise"},
    ]
    cards = feedback_cards(evs, 0.5)
    assert cards[0]["met"] is True
    assert cards[1]["met"] is False
    assert cards[0]["feedback"] == "good"
    assert cards[1]["key_points_missed"] == []


def test_feedback_cards_question_snippet():
    long_q = "Explain how photosynthesis converts light energy into chemical energy " * 3
    cards = feedback_cards([{"score": 4, "max_score": 10}], 0.5, questions=[{"question": long_q}])
    assert cards[0]["question"].startswith("Explain how photosynthesis")
    assert cards[0]["question"].endswith("…")
    assert len(cards[0]["question"]) == 81  # 80 chars + ellipsis (v1 truncation)


def test_feedback_cards_no_questions_no_snippet():
    cards = feedback_cards([{"score": 4, "max_score": 10}], 0.5)
    assert cards[0]["question"] == ""


def test_feedback_cards_short_question_kept_whole():
    cards = feedback_cards([{"score": 4, "max_score": 10}], 0.5, questions=[{"question": "Define osmosis."}])
    assert cards[0]["question"] == "Define osmosis."
