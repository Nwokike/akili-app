"""Assessment component smoke tests — open answer, question card, results."""

from components.open_answer import OpenAnswer
from components.question_card import QuestionCard
from components.results_panel import ResultsPanel
from tests.flet_tree import walk, walk_buttons, walk_texts

OBJECTIVE = {
    "type": "objective",
    "question": "What is 2+2?",
    "options": ["3", "4", "5", "6"],
    "correct": 1,
    "explanation": "2+2 is 4.",
    "source_material": "Basic arithmetic.",
}
OPEN = {
    "type": "theory",
    "question": "Explain photosynthesis.",
    "reference_answer": "Plants convert light…",
}


def test_open_answer_renders():
    ctrl = OpenAnswer("theory", value="draft")
    assert list(walk(ctrl))


def test_open_answer_subjective_label():
    ctrl = OpenAnswer("subjective")
    labels = [t.label for t in walk(ctrl) if hasattr(t, "label")]
    assert any("analysis" in str(label) for label in labels)


def test_question_card_objective_renders():
    card = QuestionCard(OBJECTIVE, 1, 5)
    texts = [t.value for t in walk_texts(card)]
    assert "Question 1 of 5" in texts
    assert "What is 2+2?" in texts


def test_question_card_options_clickable():
    card = QuestionCard(OBJECTIVE, 1, 5, on_select_option=lambda i: None)
    # 4 option containers + the card container have on_click; the card itself is static.
    clickable = [c for c in walk(card) if getattr(c, "on_click", None) is not None]
    assert len(clickable) == 4


def test_question_card_revealed_not_clickable():
    card = QuestionCard(OBJECTIVE, 1, 5, selected=0, revealed=True)
    clickable = [c for c in walk(card) if getattr(c, "on_click", None) is not None]
    assert clickable == []


def test_question_card_open_renders_field():
    card = QuestionCard(OPEN, 2, 5, answer_value="abc")
    assert len(list(walk(card))) > 0


def test_question_card_section_label():
    card = QuestionCard(OBJECTIVE, 1, 10, section_label="Section A — Objectives")
    texts = [t.value for t in walk_texts(card)]
    assert "Section A — Objectives" in texts


def test_results_panel_pass():
    panel = ResultsPanel(passed=True, score=15, total=20, pct=75.0)
    texts = [t.value for t in walk_texts(panel)]
    assert "Passed! 🎉" in texts
    assert any("75%" in t for t in texts)


def test_results_panel_fail():
    panel = ResultsPanel(passed=False, score=5, total=20, pct=25.0)
    texts = [t.value for t in walk_texts(panel)]
    assert "Keep Practicing" in texts


def test_results_panel_grade():
    panel = ResultsPanel(passed=True, score=18, total=20, pct=90.0, grade="A")
    texts = [t.value for t in walk_texts(panel)]
    assert any("Grade: A" in t for t in texts)


def test_results_panel_feedback_cards():
    panel = ResultsPanel(
        passed=True,
        score=18,
        total=20,
        pct=90.0,
        feedback_cards=[{"index": 0, "score": 8, "max_score": 10, "feedback": "Good", "suggestions": "", "met": True}],
    )
    texts = [t.value for t in walk_texts(panel)]
    assert "Good" in texts


def test_results_panel_buttons():
    seen = []
    panel = ResultsPanel(
        passed=True,
        score=15,
        total=20,
        pct=75.0,
        on_retake=lambda: seen.append("retake"),
        on_continue=lambda: seen.append("continue"),
        on_share=lambda p: seen.append(("share", p)),
        share_payload={"pct": 75},
    )
    buttons = list(walk_buttons(panel))
    assert len(buttons) == 3
