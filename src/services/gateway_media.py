"""Gateway media transport — vision + transcription via api.kiri.ng.

Split-brain AI by design: TEXT and tool turns stay on the Kiri router
(kani, Phase 2). The router cannot guarantee multimodal, so IMAGE and
AUDIO go here — a thin transport module with v1's contract verbatim,
and deliberately NOT an agent loop (no healing, no tools, no chat).

Contract (from Akili v1 ai_service.py):
- POST https://api.kiri.ng/chat, Bearer mobile-v1, AkiliApp UA.
- Vision: JSON {messages, task_type "multimodal", temperature 0.1,
  max_tokens 3000}, 5× backoff, 120s timeout, "[...]" sentinels.
- Transcription: multipart file/audio.wav + string form fields,
  30s timeout, no retry, "[...]" sentinels, never raises.
"""

from __future__ import annotations

import base64
import logging
import random

import httpx

from core.constants import APP_VERSION

logger = logging.getLogger(__name__)

API_GATEWAY = "https://api.kiri.ng"
GATEWAY_SECRET = "mobile-v1"
USER_AGENT = f"AkiliApp/{APP_VERSION}"

COMMON_HEADERS = {
    "Authorization": f"Bearer {GATEWAY_SECRET}",
    "User-Agent": USER_AGENT,
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024

TASK_VISION = "multimodal"
TASK_AUDIO = "audio"


async def _post_with_backoff(payload: dict) -> dict:
    """POST JSON with exponential backoff (vision path)."""
    max_retries = 5
    base_delay = 2.0
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(
                headers=COMMON_HEADERS,
                timeout=httpx.Timeout(120.0, connect=10.0),
            ) as client:
                resp = await client.post(f"{API_GATEWAY}/chat", json=payload)
                if 400 <= resp.status_code < 500:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = {"error": resp.text[:300]}
                    if isinstance(detail, dict) and detail.get("error"):
                        return {"error": detail["error"]}
                    return {"error": f"Request failed: {resp.status_code}"}
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as ex:
            last_error = ex
        except httpx.RequestError as ex:
            last_error = ex
        if attempt < max_retries - 1:
            delay = min(30.0, base_delay**attempt + random.uniform(0.5, 2.0))
            import asyncio

            await asyncio.sleep(delay)
    return {"error": f"Network overloaded after 5 attempts. {last_error}"}


async def analyze_image(media_data: bytes, mime_type: str) -> str:
    """Transcribe/describe an image via the gateway. Never raises."""
    if not media_data:
        return "[No image data]"
    if len(media_data) > MAX_IMAGE_BYTES:
        return "[Image too large (10MB limit)]"
    b64_image = base64.b64encode(media_data).decode("utf-8")
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are Akili Eye — a meticulous academic document reader.\n\n"
                            "TRANSCRIBE this image with EXTREME precision. Capture:\n"
                            "1. EVERY word exactly as written — preserve spelling (including errors)\n"
                            "2. ALL punctuation marks exactly as they appear (commas, periods, apostrophes)\n"
                            "3. The EXACT ordering of content (paragraphs, numbered lists, bullet points)\n"
                            "4. Letter/essay FORMAT if present (date, address, salutation, body, closing, signature)\n"
                            "5. ALL mathematical formulas, equations, chemical symbols, diagrams\n"
                            "6. Handwriting QUALITY observations (legibility, neatness, crossed-out words)\n"
                            "7. Any drawings, diagrams, or tables — describe their structure and labels\n"
                            "8. Margin notes, corrections, or annotations\n\n"
                            "OUTPUT FORMAT:\n"
                            "[TRANSCRIPTION]\n(exact text as written)\n\n"
                            "[OBSERVATIONS]\n(handwriting quality, formatting style, any notable issues)\n\n"
                            "Be forensically precise. Every detail matters for grading."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                ],
            }
        ],
        "task_type": TASK_VISION,
        "temperature": 0.1,
        "max_tokens": 3000,
    }
    try:
        resp = await _post_with_backoff(payload)
    except Exception as ex:
        logger.warning("image analysis transport failed: %s", ex)
        return f"[Image analysis failed: {ex}]"
    if "error" in resp:
        return f"[Image analysis failed: {resp['error']}]"
    choices = resp.get("choices", [])
    if not choices:
        return "[Image analysis failed: no choices returned]"
    return choices[0].get("message", {}).get("content", "[Image analysis failed]")


async def transcribe_audio(media_data: bytes, mime_type: str) -> str:
    """Transcribe audio via the gateway Whisper route. Never raises."""
    if not media_data:
        return "[No audio data]"
    if len(media_data) > MAX_AUDIO_BYTES:
        return "[Audio too large (25MB limit)]"
    files = {"file": ("audio.wav", media_data, mime_type)}
    data = {"task_type": TASK_AUDIO, "temperature": "0.1"}
    try:
        async with httpx.AsyncClient(
            headers=COMMON_HEADERS,
            timeout=httpx.Timeout(30.0),
        ) as client:
            resp = await client.post(f"{API_GATEWAY}/chat", files=files, data=data)
            if resp.status_code != 200:
                logger.warning("Whisper HTTP %d: %s", resp.status_code, resp.text[:200])
                resp.raise_for_status()
            data_resp = resp.json()
            transcript = data_resp.get("text", "")
            if not transcript:
                choices = data_resp.get("choices", [])
                if choices:
                    transcript = choices[0].get("message", {}).get("content", "")
            if transcript:
                return transcript
            return "[Transcription returned empty result]"
    except Exception as ex:
        logger.warning("audio transcription failed: %s", ex)
        return f"[Transcription failed: {ex}]"


_FAILURE_PREFIXES = (
    "[Image analysis failed",
    "[Transcription failed",
    "[Transcription returned empty",
    "[No image data]",
    "[No audio data]",
    "[Image too large",
    "[Audio too large",
)


def is_failure(text: str) -> bool:
    """True when gateway output is a failure sentinel.

    v1 checked `startswith("[")`, which also rejects successful
    transcriptions — the Akili Eye format OPENS with `[TRANSCRIPTION]`.
    Match the known sentinels instead.
    """
    stripped = (text or "").strip()
    return any(stripped.startswith(prefix) for prefix in _FAILURE_PREFIXES)
