"""Evaluation tests — the AI grader wiring (mocked backend)."""

import pytest

from services import evaluation


def _valid_payload():
    return [
        {
            "score": 8,
            "max_score": 10,
            "feedback": "Well done",
            "suggestions": "Revise X",
            "key_points_hit": ["a"],
            "key_points_missed": ["b"],
        }
    ]


def _questions():
    return [
        {
            "type": "theory",
            "question": "What is photosynthesis?",
            "reference_answer": "Plants convert light…",
            "key_points": ["light", "chlorophyll"],
            "source_material": "Plants use light.",
        }
    ]


@pytest.mark.asyncio
async def test_evaluate_open_answers_validates(monkeypatch):
    import json

    from services import generation

    calls: dict = {}

    async def _fake(messages, *, use_tools, on_status=None):
        calls["prompt"] = messages[-1]["content"]
        calls["use_tools"] = use_tools
        return json.dumps(_valid_payload())

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await evaluation.evaluate_open_answers(_questions(), [{"text": "Plants use light"}], "SSS 2")
    assert len(result) == 1
    assert result[0]["score"] == 8.0
    assert result[0]["feedback"] == "Well done"
    # The grader reads the reference + source and may verify facts.
    assert "photosynthesis" in calls["prompt"].lower()
    assert "Plants convert light" in calls["prompt"]
    assert calls["use_tools"] is True


@pytest.mark.asyncio
async def test_evaluate_empty_answer_gets_zero_prompt(monkeypatch):
    from services import generation

    seen: dict = {}

    async def _fake(messages, *, use_tools, on_status=None):
        seen["prompt"] = messages[-1]["content"]
        import json

        return json.dumps([{"score": 0, "max_score": 10, "feedback": "No answer", "suggestions": "Try"}])

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await evaluation.evaluate_open_answers(_questions(), [{"text": "   "}], "SSS 2")
    assert result[0]["score"] == 0.0
    assert "[No answer]" in seen["prompt"]


@pytest.mark.asyncio
async def test_evaluate_neutral_fallback_on_failure(monkeypatch):
    from services import generation

    async def _fake(messages, *, use_tools, on_status=None):
        return "not json at all"

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await evaluation.evaluate_open_answers(
        _questions(),
        [{"text": "x"}],
        "SSS 2",
    )
    assert len(result) == 1
    assert result[0]["score"] == 5  # v1 neutral fallback
    assert "teacher" in result[0]["feedback"].lower()


@pytest.mark.asyncio
async def test_evaluate_pads_to_question_count(monkeypatch):
    import json

    from services import generation

    async def _fake(messages, *, use_tools, on_status=None):
        return json.dumps(_valid_payload())  # one eval for two questions

    monkeypatch.setattr(generation, "_call_kani", _fake)
    qs = _questions() + [_questions()[0]]
    result = await evaluation.evaluate_open_answers(qs, [{"text": "a"}, {"text": "b"}], "SSS 2")
    assert len(result) == 2
    assert result[1]["score"] == 0  # padded neutral


@pytest.mark.asyncio
async def test_evaluate_raises_on_backend_failure(monkeypatch):
    from services import generation

    async def _fake(messages, *, use_tools, on_status=None):
        raise RuntimeError("router down")

    monkeypatch.setattr(generation, "_call_kani", _fake)
    with pytest.raises(RuntimeError):
        await evaluation.evaluate_open_answers(_questions(), [{"text": "x"}], "SSS 2")
