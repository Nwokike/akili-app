"""Generation tests — validator gating and the healing retry (mocked backend)."""

import pytest

from services import generation


@pytest.mark.asyncio
async def test_generate_structured_returns_validator_value(monkeypatch):
    async def _fake(messages, *, use_tools, on_status=None):
        return '{"modules": [{"title": "A", "topics": ["t"]}]}'

    monkeypatch.setattr(generation, "_call_kani", _fake)

    result = await generation.generate_structured(
        [{"role": "user", "content": "go"}],
        validator=lambda text: {"ok": True},
    )
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_generate_structured_heals_then_succeeds(monkeypatch):
    calls = {"n": 0}

    async def _fake(messages, *, use_tools, on_status=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "sorry, I could not produce JSON"
        return '{"modules": [{"title": "B"}]}'

    monkeypatch.setattr(generation, "_call_kani", _fake)

    def _validator(text: str):
        from core.ai_utils import extract_json_object, validate_curriculum

        obj = extract_json_object(text)
        return validate_curriculum(obj) if obj else None

    result = await generation.generate_structured(
        [{"role": "user", "content": "go"}],
        validator=_validator,
        max_healing=2,
    )
    assert result == {"modules": [{"title": "B", "topics": []}]}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_generate_structured_gives_up(monkeypatch):
    async def _fake(messages, *, use_tools, on_status=None):
        return "still not json"

    monkeypatch.setattr(generation, "_call_kani", _fake)

    result = await generation.generate_structured(
        [{"role": "user", "content": "go"}],
        validator=lambda text: None,
        max_healing=2,
    )
    assert result is None


@pytest.mark.asyncio
async def test_heal_retry_drops_tools(monkeypatch):
    """The healing pass must retry tool-less (v1 parity)."""
    seen: list[bool] = []

    async def _fake(messages, *, use_tools, on_status=None):
        seen.append(use_tools)
        return "nope"

    monkeypatch.setattr(generation, "_call_kani", _fake)
    await generation.generate_structured(
        [{"role": "user", "content": "go"}],
        validator=lambda text: None,
        use_tools=True,
        max_healing=2,
    )
    assert seen == [True, False, False]


@pytest.mark.asyncio
async def test_suggest_subjects_validates(monkeypatch):
    async def _fake(messages, *, use_tools, on_status=None):
        return '["Biology", "Chemistry", "Physics"]'

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await generation.suggest_subjects("SSS 2", "Nigeria")
    assert result == ["Biology", "Chemistry", "Physics"]


@pytest.mark.asyncio
async def test_generate_curriculum_validates(monkeypatch):
    async def _fake(messages, *, use_tools, on_status=None):
        return '{"curriculum": [{"name": "Genetics", "lessons": ["DNA"]}]}'

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await generation.generate_curriculum("Biology", "SSS 2", "Nigeria")
    assert result == {"modules": [{"title": "Genetics", "topics": ["DNA"]}]}


@pytest.mark.asyncio
async def test_generate_lesson_sanitizes(monkeypatch):
    async def _fake(messages, *, use_tools, on_status=None):
        return "💭 planning\n# Real Lesson\n" + ("Real content. " * 30)

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await generation.generate_lesson({"title": "Photosynthesis", "topics": ["light"]}, "Biology", "SSS 2")
    assert result is not None
    assert "💭" not in result
    assert result.startswith("# Real Lesson")


@pytest.mark.asyncio
async def test_generate_quiz_orders_sections(monkeypatch):
    async def _fake(messages, *, use_tools, on_status=None):
        return '[{"type": "theory", "question": "t", "reference_answer": "r"}, {"type": "objective", "question": "o", "options": ["a", "b"], "correct": 0}]'

    monkeypatch.setattr(generation, "_call_kani", _fake)
    result = await generation.generate_quiz_questions({"title": "M", "lesson_cache": "x"}, "SSS 2")
    assert result is not None
    assert len(result) == 2


@pytest.mark.asyncio
async def test_toolless_path_passes_system_prompt(monkeypatch):
    """Regression: complete() must accept system_prompt= (course subjects,
    quiz, exam all go through the tool-less path — it raised TypeError)."""
    import agent.kani_backend as kb

    captured = {}

    class _FakeEngine:
        pass

    class _FakeKani:
        def __init__(self, engine, system_prompt=None, chat_history=None):
            captured["system_prompt"] = system_prompt
            captured["chat_history"] = chat_history

        def chat_round_stream(self, _text, max_tokens=None):
            class _Mgr:
                async def __aiter__(self):
                    yield "ok"

                async def message(self):
                    class _Msg:
                        text = "done"

                    return _Msg()

            return _Mgr()

    class _Tap:
        last_model = "test-model"

    monkeypatch.setattr(kb, "Kani", _FakeKani)

    async def _fake_engine(chosen, _tap):
        return _FakeEngine(), _Tap()

    monkeypatch.setattr(kb, "_build_engine", _fake_engine)

    result = await kb.complete(
        [{"role": "user", "content": "go"}],
        lambda _t: None,
        system_prompt="Return ONLY JSON.",
    )
    assert result["text"] == "done"
    assert captured["system_prompt"] == "Return ONLY JSON."
