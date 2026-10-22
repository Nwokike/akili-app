"""ai_utils tests — the extraction + validation pipeline generation relies on."""

from core.ai_utils import (
    extract_json_array,
    extract_json_object,
    sanitize_lesson_content,
    strip_thinking,
    validate_assignment_questions,
    validate_curriculum,
    validate_evaluation,
    validate_mixed_questions,
    validate_subject_list,
)
from core.question_types import QuestionType


def test_extract_json_object_direct():
    assert extract_json_object('{"modules": []}') == {"modules": []}


def test_extract_json_object_from_fence():
    text = 'Here you go:\n```json\n{"modules": [{"title": "A"}]}\n```\nDone.'
    assert extract_json_object(text) == {"modules": [{"title": "A"}]}


def test_extract_json_object_after_thinking():
    text = '<think>let me plan this</think>\n{"modules": [{"title": "B"}]}'
    assert extract_json_object(text) == {"modules": [{"title": "B"}]}


def test_extract_json_object_bracket_match():
    text = 'blah {"modules": [{"title": "C"}]} trailing noise'
    assert extract_json_object(text) == {"modules": [{"title": "C"}]}


def test_extract_json_array_from_wrapper_object():
    text = '{"questions": [{"q": 1}]}'
    assert extract_json_array(text) == [{"q": 1}]


def test_extract_json_returns_none_on_garbage():
    assert extract_json_object("no json here at all") is None


def test_strip_thinking_removes_blocks():
    assert strip_thinking("a <think>secret</think> b") == "a  b"


def test_strip_thinking_removes_unclosed_block():
    # Model hit the token limit mid-thought — nothing but reasoning came back.
    assert strip_thinking("<think>partial reasoning, no close tag") == ""


def test_strip_thinking_keeps_plain_text():
    # The word "thinking" in normal prose must not be touched.
    assert strip_thinking("I am thinking about DNA") == "I am thinking about DNA"


# ── Validators ──


def test_validate_curriculum_canonical():
    data = {"modules": [{"title": "Genetics", "topics": ["DNA", "RNA"]}]}
    result = validate_curriculum(data)
    assert result == {"modules": [{"title": "Genetics", "topics": ["DNA", "RNA"]}]}


def test_validate_curriculum_aliases():
    data = {"curriculum": [{"name": "Bonding", "lessons": ["Ionic"]}]}
    result = validate_curriculum(data)
    assert result == {"modules": [{"title": "Bonding", "topics": ["Ionic"]}]}


def test_validate_curriculum_drops_malformed():
    data = {"modules": [{"title": "Good"}, {"no_title": True}, "junk"]}
    result = validate_curriculum(data)
    assert len(result["modules"]) == 1


def test_validate_curriculum_none_when_empty():
    assert validate_curriculum({"modules": []}) is None
    assert validate_curriculum({}) is None


def test_validate_subject_list_caps_at_ten():
    assert len(validate_subject_list([f"S{i}" for i in range(20)])) == 10


def test_validate_subject_list_accepts_dicts():
    assert validate_subject_list([{"name": "Biology"}]) == ["Biology"]


def test_validate_mixed_questions_objective():
    data = [{"type": "objective", "question": "2+2?", "options": ["3", "4"], "correct": 1, "explanation": "x"}]
    result = validate_mixed_questions(data)
    assert len(result) == 1
    assert result[0]["type"] == QuestionType.OBJECTIVE
    assert result[0]["correct"] == 1


def test_validate_mixed_questions_normalizes_letter_correct():
    data = [{"type": "mcq", "question": "q", "options": ["a", "b", "c", "d"], "correct": "C"}]
    result = validate_mixed_questions(data)
    assert result[0]["correct"] == 2


def test_validate_mixed_questions_drops_bad_objective():
    # correct out of range -> dropped
    data = [{"type": "objective", "question": "q", "options": ["a", "b"], "correct": 5}]
    assert validate_mixed_questions(data) == []


def test_validate_mixed_questions_theory_and_subjective():
    data = [
        {"type": "theory", "question": "t", "reference_answer": "r", "key_points": ["k"]},
        {"type": "subjective", "question": "s", "marking_guide": "m", "sample_answer": "sa"},
    ]
    result = validate_mixed_questions(data)
    assert result[0]["type"] == QuestionType.THEORY
    assert result[1]["type"] == QuestionType.SUBJECTIVE
    assert result[0]["max_marks"] == 10


def test_validate_assignment_questions_requires_open():
    data = [{"type": "objective", "question": "q", "options": ["a", "b"], "correct": 0}]
    assert validate_assignment_questions(data) is None


def test_validate_evaluation_coerces_numbers():
    result = validate_evaluation([{"score": "7", "max_score": "10", "feedback": "ok"}])
    assert result[0]["score"] == 7.0
    assert result[0]["max_score"] == 10.0


# ── Lesson sanitize ──


def test_sanitize_lesson_strips_thought_lines():
    text = "💭 I should plan this\n# Lesson\nReal content here."
    result = sanitize_lesson_content(text)
    assert "💭" not in result
    assert "Real content here." in result


def test_sanitize_lesson_keeps_content():
    text = "# Photosynthesis\n\nPlants convert light into energy.\n\n- Point one\n- Point two"
    assert sanitize_lesson_content(text) == text


def test_sanitize_lesson_strips_planning_preamble():
    text = "Now let's draft the lesson.\nWe need to ensure quality.\n# Actual Lesson\nContent."
    result = sanitize_lesson_content(text)
    assert result.startswith("# Actual Lesson")
