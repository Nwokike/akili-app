"""Capture + OCR + credit-branching tests (no hardware, mocked backends)."""

import pytest

from services.file_picker import MAX_IMAGE_BYTES, detect_mime


def test_detect_mime():
    assert detect_mime("a.png") == "image/png"
    assert detect_mime("a.PNG") == "image/png"
    assert detect_mime("a.webp") == "image/webp"
    assert detect_mime("a.jpg") == "image/jpeg"
    assert detect_mime("a.jpeg") == "image/jpeg"
    assert detect_mime("a.bmp") == "image/jpeg"
    assert detect_mime("") == "image/jpeg"


def test_image_byte_limit_constant():
    assert MAX_IMAGE_BYTES == 10 * 1024 * 1024


def test_pcm_to_wav_round_trip():
    import wave

    from services.audio import _pcm_to_wav

    pcm = b"\x00\x01" * 44100  # 1s of mono 16-bit @44.1kHz
    wav = _pcm_to_wav(pcm)
    assert wav[:4] == b"RIFF"
    with wave.open(__import__("io").BytesIO(wav), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 44100
        assert handle.readframes(44100) == pcm


def test_audio_limits():
    from services import audio as audio_mod

    assert audio_mod.MAX_VOICE_DURATION_SEC == 60
    assert audio_mod.MAX_AUDIO_SIZE_BYTES == 25 * 1024 * 1024
    assert audio_mod.PCM_SAMPLE_RATE == 44100
    assert audio_mod.PCM_CHANNELS == 1


@pytest.mark.asyncio
async def test_evaluation_ocr_merge_and_discard(monkeypatch):
    from services import evaluation

    seen = {}

    async def _fake_analyze(data: bytes, mime: str) -> str:
        seen["bytes"] = data
        seen["mime"] = mime
        return "[TRANSCRIPTION]\n2+2=4"

    # Bypass generate_structured: feed the OCR'd text through the validator path.
    from services import generation

    async def _fake_gen(messages, *, validator, use_tools=False, on_status=None, max_healing=2):
        import json as _json

        seen["prompt"] = messages[-1]["content"]
        # Simulate one kani round returning valid JSON.
        text = _json.dumps([{"score": 8, "max_score": 10, "feedback": "Good", "suggestions": ""}])
        return validator(text)

    monkeypatch.setattr("services.gateway_media.analyze_image", _fake_analyze)
    monkeypatch.setattr(generation, "generate_structured", _fake_gen)

    questions = [{"type": "theory", "question": "q", "reference_answer": "r"}]
    answers = [{"text": "", "image_bytes": b"img", "image_mime": "image/png"}]
    result = await evaluation.evaluate_open_answers(questions, answers, "SSS 2")
    assert seen["bytes"] == b"img"
    assert seen["mime"] == "image/png"
    assert "2+2=4" in seen["prompt"]  # OCR text merged into the answer
    assert result[0]["score"] == 8.0
    # Bytes discarded after OCR.
    assert answers[0]["image_bytes"] is None


@pytest.mark.asyncio
async def test_evaluation_typed_plus_image_merges_with_marker(monkeypatch):
    from services import evaluation, generation

    async def _fake_analyze(data: bytes, mime: str) -> str:
        return "[TRANSCRIPTION]\n2+2=4"

    async def _fake_gen(messages, *, validator, use_tools=False, on_status=None, max_healing=2):
        import json as _json

        seen_prompt = messages[-1]["content"]
        assert "[From uploaded image]:" in seen_prompt
        return validator(_json.dumps([{"score": 9, "max_score": 10, "feedback": "Great", "suggestions": ""}]))

    monkeypatch.setattr("services.gateway_media.analyze_image", _fake_analyze)
    monkeypatch.setattr(generation, "generate_structured", _fake_gen)

    questions = [{"type": "theory", "question": "q", "reference_answer": "r"}]
    answers = [{"text": "typed", "image_bytes": b"img", "image_mime": "image/png"}]
    result = await evaluation.evaluate_open_answers(questions, answers, "SSS 2")
    assert result[0]["score"] == 9.0


@pytest.mark.asyncio
async def test_evaluation_ocr_failure_keeps_text(monkeypatch):
    from services import evaluation, generation

    async def _fake_analyze(data: bytes, mime: str) -> str:
        return "[Image analysis failed: busy]"

    async def _fake_gen(messages, *, validator, use_tools=False, on_status=None, max_healing=2):
        import json as _json

        return validator(_json.dumps([{"score": 5, "max_score": 10, "feedback": "ok", "suggestions": ""}]))

    monkeypatch.setattr("services.gateway_media.analyze_image", _fake_analyze)
    monkeypatch.setattr(generation, "generate_structured", _fake_gen)

    questions = [{"type": "theory", "question": "q", "reference_answer": "r"}]
    answers = [{"text": "typed", "image_bytes": b"img", "image_mime": "image/png"}]
    result = await evaluation.evaluate_open_answers(questions, answers, "SSS 2")
    assert result[0]["score"] == 5.0  # typed answer still graded


@pytest.mark.asyncio
async def test_media_surcharge_settlement():
    """3-credit media fee: charged when delivered, refunded when empty."""
    from datetime import UTC, datetime

    from agent.chat_agent import settle_turn
    from services.credit_service import CreditService
    from tests.conftest import FakeStorage

    today = datetime.now(tz=UTC).date().isoformat()
    storage = FakeStorage({"akili_credits": "100", "akili_last_reset": today})
    credits = CreditService(storage=storage)
    await credits.initialize()

    tx = await credits.reserve(1 + 3)
    assert tx is not None
    # Delivered turn: 1 step + 3 fee.
    assert await settle_turn(credits, tx, 1, flat_fee=3) == 96

    tx2 = await credits.reserve(1 + 3)
    # Empty turn: full refund.
    assert await settle_turn(credits, tx2, 0, flat_fee=3) == 96


def test_tutor_media_cost_constant():
    from core.constants import COST_TUTOR_MEDIA

    assert COST_TUTOR_MEDIA == 3
