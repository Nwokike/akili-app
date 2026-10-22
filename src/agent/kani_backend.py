"""The kani backend — the agent loop is kani's, wrapped not rebuilt.

Ported from DDGS kani_backend.py (the house standard).

kani[openai] speaks the OpenAI wire the Kiri router uses. This module owns
the turn mechanics: engine construction, tool serialization, and the
full_round_stream iteration. chat_agent keeps every outer contract it
needs (emit protocol, credits per model step, step rows, approval gate).

Rules for this backend:
- the thought-tap SSE tee so the Thinking block still sees reasoning deltas;
- the model string passed to the engine verbatim — `auto` is the router's
  to resolve, nothing here substitutes it;
- cancellation at manager boundaries: on_token raising stops a stream
  mid-flight, and a boundary check runs before every model round;
- one billable step == one model stream (kani yields a StreamManager per
  model round and a DummyStream per tool result; only model rounds count).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import httpx
import openai
from kani import AIFunction, ChatMessage, Kani

from agent import engine as router
from agent.engine import mark_model_failed, turn_candidates
from agent.reasoning import ReasoningEngine, ThoughtTap, build_thought_client
from agent.tokenizer import tokenizer_or_heuristic
from core.constants import (
    AGENT_HISTORY_MESSAGES,
    AGENT_MAX_ITERS,
    AGENT_TIMEOUT_S,
    ANSWER_MAX_TOKENS,
    DEFAULT_CONTEXT,
    TEMPERATURE,
    TOOL_OUTPUT_CAP,
)

logger = logging.getLogger(__name__)


class AIUnavailable(Exception):
    """No AI source could answer — callers degrade silently."""


class AIMidStream(Exception):
    """The source died after tokens were delivered — partial answer, no retry."""


class RouterModelFailed(Exception):
    """This model died; another candidate may work."""


_call_id: ContextVar[str] = ContextVar("akili_tool_call_id", default="")


class AkiliKani(Kani):
    """Kani that exposes the active tool_call_id to the tool body.

    The tutor screen matches step_done to step_start by id.
    """

    async def do_function_call(self, call, tool_call_id: str | None = None):
        token = _call_id.set(str(tool_call_id or ""))
        try:
            return await super().do_function_call(call, tool_call_id)
        finally:
            _call_id.reset(token)


@dataclass(frozen=True)
class ToolSpec:
    """One tool: schema for the model, code for us.

    `run` receives parsed arguments and returns the exact JSON text the
    model sees (already serialized). It never raises — every failure
    becomes an error payload.
    """

    name: str
    desc: str
    parameters: dict
    run: Callable[[dict], Awaitable[str]]


def call_id() -> str:
    """The tool_call_id of the call currently executing ("" outside one)."""
    return _call_id.get()


def build_functions(specs: list[ToolSpec]) -> list[AIFunction]:
    """kani AIFunctions from our specs, executing one at a time."""
    lock = asyncio.Lock()
    out: list[AIFunction] = []
    for spec in specs:

        async def inner(spec: ToolSpec = spec, **kwargs: Any) -> str:
            async with lock:
                return await spec.run(kwargs)

        out.append(
            AIFunction(
                inner,
                name=spec.name,
                desc=spec.desc,
                json_schema=spec.parameters,
                auto_truncate=TOOL_OUTPUT_CAP,
            )
        )
    return out


def _chat_messages(items: list[dict], *, limit: int | None = AGENT_HISTORY_MESSAGES) -> list[ChatMessage]:
    """OpenAI-dict transcript -> kani messages."""
    out: list[ChatMessage] = []
    window = items if limit is None else (items or [])[-limit:]
    for item in window:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        role = str(item.get("role") or "")
        if role == "user":
            out.append(ChatMessage.user(content))
        elif role == "assistant":
            out.append(ChatMessage.assistant(content))
    return out


def to_history(history: list[dict]) -> list[ChatMessage]:
    """The per-turn window the model sees."""
    return _chat_messages(history)


async def _build_engine(model: str, on_thought: Callable[[str], None] | None):
    """One engine per turn: router base, thought tap, bounded timeouts."""
    base = await router.router_base()
    if base is None:
        raise AIUnavailable("The AI is reconnecting. Try again shortly.")
    tap = ThoughtTap(on_thought)
    timeout = httpx.Timeout(90.0, connect=4.0)
    raw = build_thought_client(timeout=timeout, tap=tap)
    client = openai.AsyncOpenAI(
        api_key="any",
        base_url=base,
        http_client=raw,
        # The candidate walk in run_turn IS the model-level retry — SDK
        # retries would burn seconds on a dead model before the walk moves
        # on (DDGS sets this to 0 for the same reason).
        max_retries=0,
        timeout=timeout,
    )
    engine = ReasoningEngine(
        client=client,
        model=model,
        api_type="chat_completions",
        max_context_size=DEFAULT_CONTEXT,
        tokenizer=tokenizer_or_heuristic(model),
        temperature=TEMPERATURE,
        tap=tap,
    )
    return engine, tap


def _usage_of(message: Any, text: str, model: str) -> dict | None:
    """Exact in/out token usage for the receipt."""
    extra = getattr(message, "extra", None) or {}
    raw = extra.get("openai_usage")
    if isinstance(raw, dict) and (raw.get("total_tokens") or raw.get("completion_tokens")):
        return {
            "in": int(raw.get("prompt_tokens") or 0),
            "out": int(raw.get("completion_tokens") or 0),
        }
    if text.strip():
        try:
            encoder = tokenizer_or_heuristic(model)
            return {"out": len(encoder.encode(text))}
        except Exception:
            return None
    return None


def _finish_of(completion: Any) -> str:
    """finish_reason off the raw OpenAI completion, best-effort."""
    try:
        raw = getattr(completion, "openai_completion", None)
        choices = getattr(raw, "choices", None) or []
        if choices:
            return str(choices[0].finish_reason or "")
    except Exception:
        pass
    return ""


def _raise_mapped(exc: BaseException, *, delivered: bool) -> None:
    """openai's exception ladder -> this app's consumer words."""
    if isinstance(exc, (AIUnavailable, AIMidStream, RouterModelFailed)):
        raise exc
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code == 429:
            raise RouterModelFailed("Kiri's free tier is busy right now.") from exc
        if exc.status_code >= 500:
            raise RouterModelFailed("The AI had a server problem.") from exc
        raise RouterModelFailed("The AI refused that request. Pick another model.") from exc
    if isinstance(exc, (openai.APITimeoutError,)):
        raise RouterModelFailed("The AI timed out. Try again.") from exc
    if isinstance(exc, (openai.APIConnectionError, openai.APIError)):
        router._mark_router_failed()
        if delivered:
            raise AIMidStream(str(exc)) from exc
        logger.info("router unreachable: %r", exc)
        raise AIUnavailable("Could not reach the AI.") from exc
    raise exc


async def run_turn(
    user_text: str,
    history: list[dict],
    *,
    system_prompt: str,
    specs: list[ToolSpec],
    cancel: asyncio.Event,
    on_token: Callable[[str], None],
    on_thought: Callable[[str], None] | None = None,
    on_round_reset: Callable[[], None] | None = None,
    on_model_step: Callable[[], Awaitable[None]] | None = None,
    on_steps: Callable[[int], None] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    max_iters: int = AGENT_MAX_ITERS,
    timeout_s: float = AGENT_TIMEOUT_S,
) -> dict:
    """Run one full agent turn through kani's full_round_stream.

    The candidate walk is the turn's whole fallback story: the user's
    model first, then the active high/medium pool by latency. When a
    candidate dies (429/5xx/refused/hung) or says nothing, the turn walks
    to the next one with a FRESH engine — and it carries the failed
    candidate's transcript (tool results included) forward, so the next
    model continues from the searches that already ran instead of
    repeating them. kani re-adds the query at the start of every round,
    so it is only passed when the carried history lacks it.

    Returns {"text", "steps", "model", "served_by", "usage"}.
    """
    from agent.chat_agent import ChatCancelled

    chosen = str(model or "auto").strip() or "auto"
    query = user_text[:2000]
    candidates = turn_candidates(chosen)

    t0 = time.monotonic()
    steps = 0
    message: Any = None
    empty_retried = False
    budget = max_tokens or ANSWER_MAX_TOKENS
    round_parts: list[str] = []
    final_text = ""
    last_model_failed: str | None = None

    history: list[dict] = list(history or [])
    prev_kani: AkiliKani | None = None
    tap = None
    attempt_model = chosen

    def _history_has_query(items: list) -> bool:
        return any(str(m.get("role") or "") == "user" and str(m.get("content") or "") == query for m in items)

    try:
        for attempt, attempt_model in enumerate(candidates):
            if cancel.is_set():
                raise ChatCancelled()
            if attempt:
                logger.info(
                    "model %s failed for this turn; trying %s",
                    last_model_failed,
                    attempt_model,
                )
                round_parts.clear()
                if on_round_reset is not None:
                    on_round_reset()
                message = None
                empty_retried = False
                budget = max_tokens or ANSWER_MAX_TOKENS
                if prev_kani is not None:
                    history = [dict(m) for m in _chat_messages(prev_kani.chat_history)]
            engine, tap = await _build_engine(attempt_model, on_thought)
            kani = AkiliKani(
                engine,
                system_prompt=system_prompt or None,
                chat_history=to_history(history),
                functions=build_functions(specs) if specs else None,
                retry_attempts=1,
            )
            prev_kani = kani
            round_query = None if attempt and _history_has_query(history) else query
            try:
                async for manager in kani.full_round_stream(
                    round_query,
                    max_function_rounds=max(0, max_iters - 1),
                    max_tokens=budget,
                ):
                    if cancel.is_set():
                        raise ChatCancelled()
                    if time.monotonic() - t0 > timeout_s or steps >= max_iters:
                        break
                    if "function" in str(getattr(manager, "role", "")).lower():
                        await manager.message()
                        continue
                    if steps and on_model_step is not None:
                        await on_model_step()
                    delivered = False
                    try:
                        async for chunk in manager:
                            if chunk:
                                delivered = True
                                round_parts.append(chunk)
                                on_token(chunk)
                        message = await manager.message()
                    except ChatCancelled:
                        raise
                    except Exception as exc:
                        if delivered:
                            steps += 1
                            if on_steps is not None:
                                on_steps(steps)
                        _raise_mapped(exc, delivered=delivered)
                        raise
                    steps += 1
                    if on_steps is not None:
                        on_steps(steps)
                    if message.tool_calls:
                        round_parts.clear()
                        if on_round_reset is not None:
                            on_round_reset()
                        continue
                    final_text = "".join(round_parts)
                    if not final_text.strip():
                        finish = _finish_of(await manager.completion())
                        if finish == "length" and not empty_retried and steps < max_iters:
                            empty_retried = True
                            budget = (max_tokens or ANSWER_MAX_TOKENS) * 2
                            kani.chat_history.append(ChatMessage.user("Your previous reply hit the token limit before any text appeared. Answer again, briefly."))
                            continue
                    break
            except ChatCancelled:
                raise
            except (openai.APIError, AIUnavailable, AIMidStream, RouterModelFailed) as exc:
                try:
                    _raise_mapped(exc, delivered=False)
                except RouterModelFailed as mapped:
                    # This candidate is done; walk to the next one.
                    last_model_failed = attempt_model
                    mark_model_failed(attempt_model)
                    logger.info("candidate model %s failed: %s", attempt_model, mapped)
                    if attempt + 1 >= len(candidates):
                        raise AIUnavailable("The AI tutor could not answer right now. Try again shortly.") from mapped
                    continue
                raise
            if final_text.strip():
                break
            # Said nothing — the next candidate continues from this
            # candidate's transcript (set above on the next iteration).
            last_model_failed = attempt_model
            mark_model_failed(attempt_model)
            upstream = getattr(tap, "last_error", None)
            if upstream:
                logger.info(
                    "candidate model %s returned an embedded upstream error: %s",
                    attempt_model,
                    upstream.get("message") or upstream,
                )
            logger.info("candidate model %s said nothing; trying the next", attempt_model)
    except ChatCancelled:
        raise
    except asyncio.CancelledError:
        raise

    if cancel.is_set():
        raise ChatCancelled()
    return {
        "text": final_text,
        "steps": steps,
        "model": (tap.last_model if tap else None) or attempt_model,
        "served_by": "router",
        "usage": _usage_of(message, final_text, chosen),
    }


async def complete(
    messages: list[dict],
    on_token: Callable[[str], None],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    system_prompt: str | None = None,
) -> dict:
    """One tool-less shot: structured generation (course/lesson/quiz JSON).

    Same messages-in contract, no tools, no step counting — the caller
    decides whether it is metered. `system_prompt` (when given) takes
    precedence over a system message inside `messages`.
    """
    from agent.chat_agent import ChatCancelled

    chosen = str(model or "auto").strip() or "auto"
    system = system_prompt or ""
    body: list[dict] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or "") == "system" and not system:
            system = str(item.get("content") or "")
            continue
        body.append(item)
    engine, tap = await _build_engine(chosen, None)
    kani = Kani(engine, system_prompt=system or None, chat_history=to_history(body))
    manager = kani.chat_round_stream(None, max_tokens=max_tokens or ANSWER_MAX_TOKENS)
    delivered = False
    try:
        async for chunk in manager:
            if chunk:
                delivered = True
                on_token(chunk)
        message = await manager.message()
    except ChatCancelled:
        raise
    except Exception as exc:
        _raise_mapped(exc, delivered=delivered)
        raise
    return {
        "text": message.text or "",
        "model": tap.last_model or chosen,
        "served_by": "router",
    }
