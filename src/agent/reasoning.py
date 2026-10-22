"""SSE tee for reasoning capture — kani discards reasoning deltas.

Ported from DDGS reasoning.py (the house standard).

kani's chat-completions path reads delta.content and throws away
reasoning_content/reasoning/reasoning_details, so the tutor's Thinking
block would go dark. Capture happens on the raw SSE bytes; the original
bytes pass through untouched.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import httpx
from kani.engines.openai import OpenAIEngine

from core.constants import APP_VERSION

logger = logging.getLogger(__name__)

_REASONING_KEYS = ("reasoning_content", "reasoning", "reasoning_details")


class ThoughtTap:
    """Mutable holder retargeted per turn without rebuilding the HTTP client.

    `last_model` records the router's rewrite of `auto` → the real served id.
    """

    def __init__(self, callback: Callable[[str], None] | None = None):
        self.callback = callback
        self.last_model: str = ""
        self.last_error: dict | None = None

    def feed(self, text: str) -> None:
        if not text:
            return
        if self.callback is None:
            return
        try:
            self.callback(text)
        except Exception as exc:
            # A UI callback failure must never kill the turn.
            logger.warning("thought callback failed: %r", exc)


def _flatten(value) -> str:
    """Flatten a reasoning payload (str / list-of-parts / dict) to text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        for key in ("text", "content", "reasoning", "summary"):
            if key in value:
                return _flatten(value[key])
        return ""
    return ""


def _reasoning_from_frame(payload: dict) -> str:
    """Extract reasoning text from one SSE JSON frame."""
    # Responses-API style events
    etype = str(payload.get("type") or "")
    if "reasoning" in etype and "choices" not in payload:
        delta = payload.get("delta") or {}
        if isinstance(delta, dict):
            return _flatten(delta.get("text"))
        return _flatten(payload.get("text"))
    # Chat-completions style
    out: list[str] = []
    for choice in payload.get("choices") or []:
        for key in ("delta", "message"):
            obj = choice.get(key)
            if isinstance(obj, dict):
                for rk in _REASONING_KEYS:
                    if rk in obj:
                        out.append(_flatten(obj[rk]))
    return "".join(out)


class _TeeStream(httpx.AsyncByteStream):
    """Accumulate SSE chunks, scan frames, yield bytes untouched."""

    def __init__(self, stream: httpx.AsyncByteStream, tap: ThoughtTap):
        self._stream = stream
        self._tap = tap
        self._buf = b""

    async def __aiter__(self):
        async for chunk in self._stream:
            self._scan(chunk)
            yield chunk
        self._scan_final()

    def _scan(self, chunk: bytes) -> None:
        self._buf += chunk
        while b"\n\n" in self._buf:
            frame, self._buf = self._buf.split(b"\n\n", 1)
            self._scan_frame(frame)

    def _scan_final(self) -> None:
        if self._buf:
            self._scan_frame(self._buf)
            self._buf = b""

    def _scan_frame(self, frame: bytes) -> None:
        for line in frame.split(b"\n"):
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if raw == b"[DONE]" or not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            model = payload.get("model")
            if isinstance(model, str) and model:
                self._tap.last_model = model
            response = payload.get("response")
            if isinstance(response, dict) and isinstance(response.get("model"), str):
                self._tap.last_model = response["model"]
            # Embedded upstream error (HTTP 200, empty stream, error body) —
            # the candidate walk logs this so a sick model is distinguishable
            # from silence.
            error = payload.get("error")
            if isinstance(error, dict):
                self._tap.last_error = error
            text = _reasoning_from_frame(payload)
            if text:
                self._tap.feed(text)

    async def aclose(self) -> None:
        await self._stream.aclose()


class ThoughtTapTransport(httpx.AsyncHTTPTransport):
    """Tee only text/event-stream responses."""

    def __init__(self, tap: ThoughtTap, **kwargs):
        super().__init__(**kwargs)
        self._tap = tap

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await super().handle_async_request(request)
        ctype = response.headers.get("content-type", "")
        if "text/event-stream" in ctype and response.stream is not None:
            response.stream = _TeeStream(response.stream, self._tap)
        return response


class ReasoningEngine(OpenAIEngine):
    """An OpenAIEngine that also carries the thought tap.

    Subclassing keeps kani's isinstance(engine, OpenAIEngine) checks alive
    while letting the caller retarget on_thought per turn.
    """

    def __init__(self, *args, tap: ThoughtTap | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tap = tap

    @property
    def on_thought(self) -> Callable[[str], None] | None:
        return self._tap.callback if self._tap else None

    @on_thought.setter
    def on_thought(self, callback: Callable[[str], None] | None) -> None:
        if self._tap is not None:
            self._tap.callback = callback


def build_thought_client(
    *,
    timeout: httpx.Timeout,
    tap: ThoughtTap,
) -> httpx.AsyncClient:
    """httpx client that tees SSE for reasoning. Retries ride on OpenAI()."""
    return httpx.AsyncClient(
        transport=ThoughtTapTransport(tap),
        timeout=timeout,
        headers={"User-Agent": f"AkiliApp/{APP_VERSION}"},
    )
