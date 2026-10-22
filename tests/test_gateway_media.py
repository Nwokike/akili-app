"""Gateway media tests — contract values with mocked httpx, no live calls."""

import json

import httpx
import pytest

from services import gateway_media as gm


class _Resp:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = json.dumps(self._body)

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


class _Client:
    seen: list = []

    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kwargs):
        type(self).seen.append((url, kwargs))
        if self._exc is not None:
            raise self._exc
        return self._resp


@pytest.fixture(autouse=True)
def _reset_seen():
    _Client.seen = []
    yield
    _Client.seen = []


def _patch(monkeypatch, resp=None, exc=None):
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _Client(resp, exc))


def test_is_failure_convention():
    assert gm.is_failure("[Transcription failed: x]") is True
    assert gm.is_failure("[No audio data]") is True
    assert gm.is_failure("[TRANSCRIPTION]\n2+2=4") is False  # Eye format opens with a bracket
    assert gm.is_failure("hello world") is False


@pytest.mark.asyncio
async def test_analyze_image_contract(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"choices": [{"message": {"content": "[TRANSCRIPTION]\nhi"}}]}))
    text = await gm.analyze_image(b"\x89PNG", "image/png")
    assert text == "[TRANSCRIPTION]\nhi"
    url, kwargs = _Client.seen[0]
    assert url == "https://api.kiri.ng/chat"
    body = kwargs["json"]
    assert body["task_type"] == "multimodal"
    assert body["temperature"] == 0.1
    assert body["max_tokens"] == 3000
    part = body["messages"][0]["content"][1]
    assert part["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_analyze_image_guard_limits():
    assert await gm.analyze_image(b"", "image/png") == "[No image data]"
    assert await gm.analyze_image(b"x" * (gm.MAX_IMAGE_BYTES + 1), "image/png") == "[Image too large (10MB limit)]"


@pytest.mark.asyncio
async def test_analyze_image_gateway_error(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"error": "busy"}))
    assert (await gm.analyze_image(b"x", "image/jpeg")).startswith("[Image analysis failed")


@pytest.mark.asyncio
async def test_analyze_image_empty_choices(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"choices": []}))
    assert await gm.analyze_image(b"x", "image/jpeg") == "[Image analysis failed: no choices returned]"


@pytest.mark.asyncio
async def test_analyze_image_network_failure(monkeypatch):
    _patch(monkeypatch, exc=httpx.ConnectError("down"))
    text = await gm.analyze_image(b"x", "image/jpeg")
    assert text.startswith("[Image analysis failed")


@pytest.mark.asyncio
async def test_transcribe_contract(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"text": "hello"}))
    assert await gm.transcribe_audio(b"WAV", "audio/wav") == "hello"
    url, kwargs = _Client.seen[0]
    assert url == "https://api.kiri.ng/chat"
    assert kwargs["files"] == {"file": ("audio.wav", b"WAV", "audio/wav")}
    assert kwargs["data"] == {"task_type": "audio", "temperature": "0.1"}


@pytest.mark.asyncio
async def test_transcribe_choices_fallback(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"choices": [{"message": {"content": "fallback"}}]}))
    assert await gm.transcribe_audio(b"WAV", "audio/wav") == "fallback"


@pytest.mark.asyncio
async def test_transcribe_empty_result(monkeypatch):
    _patch(monkeypatch, _Resp(200, {"text": ""}))
    assert await gm.transcribe_audio(b"WAV", "audio/wav") == "[Transcription returned empty result]"


@pytest.mark.asyncio
async def test_transcribe_never_raises(monkeypatch):
    _patch(monkeypatch, exc=httpx.ConnectError("down"))
    assert (await gm.transcribe_audio(b"WAV", "audio/wav")).startswith("[Transcription failed")
    assert await gm.transcribe_audio(b"", "audio/wav") == "[No audio data]"
    assert await gm.transcribe_audio(b"x" * (gm.MAX_AUDIO_BYTES + 1), "audio/wav") == "[Audio too large (25MB limit)]"


def test_auth_headers():
    assert gm.COMMON_HEADERS["Authorization"] == "Bearer mobile-v1"
    assert gm.USER_AGENT.startswith("AkiliApp/")
    assert gm.TASK_VISION == "multimodal"
    assert gm.TASK_AUDIO == "audio"
