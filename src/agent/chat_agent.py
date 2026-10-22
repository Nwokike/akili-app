"""Tutor agent turn — Akili tools, hard caps, COST_STEP per model step.

Ported from DDGS chat_agent.py (the house standard), education-flavoured.

The model gets its read-only tools (search_web, search_videos, fetch_page)
plus any tools the user's MCP servers expose. Billing is COST_STEP credits
per MODEL STEP, not per message: a turn that takes two steps costs
2 * COST_STEP. The Settings copy and the receipt are both generated from
that constant, so they cannot drift from what is charged.

Emit protocol (the tutor screen consumes these, throttled):
    user                {"text"}
    assistant_start     {}
    nudge               {"text"}
    text_partial        {"text"}          # full buffer so far
    thought             {"text"}          # full reasoning buffer so far
    step_start          {"label", "id"}
    step_done           {"label", "id", "count"}
    step_error          {"label", "id", "error"}
    results             {"kind", "results: list[SearchResult]"}
    text_final          {"text", "model", "steps", "cost", "tokens"}
    stopped             {"partial", "steps", "cost"}
    error               {"kind": credits|unavailable|midstream|empty}
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime

from agent import kani_backend
from agent.kani_backend import AIMidStream, AIUnavailable
from agent.search import SearchResult
from agent.tools import build_tools, pretty_label
from core.constants import AGENT_MAX_TOOLS, COST_STEP
from core.state import state

logger = logging.getLogger(__name__)


class ChatCancelled(Exception):
    """User pressed Stop."""


SYSTEM_PROMPT = (
    "You are Akili, a patient, encouraging AI tutor for students. "
    "For anything factual, current, or curriculum-related, call your tools "
    "FIRST (search_web, search_videos, fetch_page) and answer ONLY from what "
    "you find — never invent sources. Cite claims with [1], [2] … matching "
    "the order of the results you actually used. "
    "Explain step by step at the student's level; prefer short paragraphs and "
    "worked examples. If a tool returns an error or no results, retry ONCE "
    "with a broader query, then say plainly what you could not verify. "
    "\n\nFORMATTING: use clean Markdown. Do NOT use LaTeX ($, $$, \\frac, "
    "\\sqrt). Write maths with Unicode: H₂O, x², ±, √, π, and italics for "
    "variables, so it renders natively. "
    "Keep answers focused; ask a short follow-up question when it helps the "
    "student learn. If no tool is needed (greetings, simple arithmetic, "
    "opinions), just answer."
)


def with_clock(system_prompt: str) -> str:
    """Prepend the current date/time so stale-date answers are impossible."""
    moment = datetime.now().astimezone()
    offset = moment.strftime("%z")
    if len(offset) == 5:
        offset = f"{offset[:3]}:{offset[3:]}"
    zone = moment.tzname() or "local"
    line = f"Current date and time: {moment.strftime('%Y-%m-%d %H:%M:%S')} ({offset} {zone}, {moment.strftime('%A')}). Treat 'today', 'this week' and 'recently' relative to THIS timestamp, never your training data."
    return line + "\n\n" + (system_prompt or "").strip()


async def settle_turn(credits, tx_id: str | None, steps: int, flat_fee: int = 0) -> int:
    """Charge COST_STEP credits per delivered step, plus an optional flat fee.

    The flat fee (e.g. media handling) is charged only when steps > 0 —
    an answer-less turn refunds the whole hold, fee included.

    Never breaks the user's work: a finished/partial message is always
    settled (overdraft clamps at zero); zero delivered steps refunds the
    hold entirely.
    """
    amount = max(0, steps) * COST_STEP + (flat_fee if steps > 0 else 0)
    if credits is None:
        return 0
    if not tx_id:
        if amount:
            return await credits.charge(amount)
        return await credits.get_balance()
    if steps <= 0:
        await credits.rollback(tx_id)
        return await credits.get_balance()
    return await credits.commit_amount(tx_id, amount)


def _charged_steps(steps: int, content_parts: list[str]) -> int:
    """Steps to bill: one floor whenever the user actually saw text.

    The Stop button delivers CancelledError before `steps` increments, so a
    branch billing raw steps refunded delivered tokens. Delivered work is
    worth one step, whatever ended the turn.
    """
    delivered = bool("".join(content_parts).strip())
    return max(steps, 1) if delivered else steps


def _error_text(exc: BaseException) -> str:
    """A message a human can act on for any exception."""
    text = str(exc).strip()
    if text:
        return text[:300]
    if isinstance(exc, TimeoutError):
        return "timed out"
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled"
    name = type(exc).__name__
    return name if name else "failed"


def _result_kind(name: str) -> str:
    return {"search_videos": "videos", "search_web": "web"}.get(name, "web")


def _tool_source(spec):
    """Normalize a tool: our ToolSpec or a kani AIFunction from the MCP hub.

    Returns (name, desc, parameters, source_run) where source_run(args)
    executes the underlying implementation. The hub's tools are
    AIFunctions — schema in .json_schema, implementation in .inner(**kwargs).
    """
    if isinstance(spec, kani_backend.ToolSpec):

        async def source_run(args: dict) -> str:
            return await spec.run(args)

        return spec.name, spec.desc, spec.parameters, source_run

    async def source_run(args: dict) -> str:
        return await spec.inner(**args)

    return spec.name, spec.desc or "", spec.json_schema or {}, source_run


async def run_turn(
    user_text: str,
    history: list[dict],
    emit: Callable[[str, dict], None],
    cancel: asyncio.Event,
    on_thought: Callable[[str], None] | None = None,
    extra_tools: list | None = None,
    media_surcharge: int = 0,
) -> None:
    """One agent turn — COST_STEP credits per model step, settled on every exit.

    `media_surcharge` is a flat fee (image/audio handling) reserved up
    front and charged only when the turn delivered text. An answer-less
    turn refunds everything, surcharge included.

    Soft metering: a low balance is never a mid-run kill switch; the turn
    always finishes (balance may clamp to 0). A 0 balance starts blocked.
    """
    credits = getattr(state, "credit_service", None)
    # The question is recorded before any gate: an out-of-credits turn still
    # shows the user what they asked, and Retry can re-send it.
    emit("user", {"text": user_text})
    if credits is None:
        emit("error", {"kind": "unavailable", "steps": 0, "cost": 0})
        return
    balance = await credits.get_balance()
    if balance <= 0:
        emit("error", {"kind": "credits", "balance": 0, "steps": 0, "cost": 0})
        return
    # Best-effort hold; at balance 1 the hold fails and we run hold-less.
    tx = await credits.reserve(COST_STEP + media_surcharge)

    emit("assistant_start", {})
    if balance < COST_STEP * 3:
        emit("nudge", {"text": "Low credit balance. This message finishes regardless."})

    seen_urls: list[str] = []
    served_model = ""
    content_parts: list[str] = []
    final_text = ""
    steps = 0
    tools_used = 0

    def on_token(token: str) -> None:
        if cancel.is_set():
            raise ChatCancelled()
        content_parts.append(token)
        emit("text_partial", {"text": "".join(content_parts)})

    def on_round_reset() -> None:
        # A tool round's text never belongs to the final answer.
        content_parts.clear()

    def on_steps(n: int) -> None:
        nonlocal steps
        steps = n

    async def on_model_step() -> None:
        # Fires before every model call after the first. Best-effort.
        if tx:
            await credits.reserve_more(tx, COST_STEP)

    def _spec_from(spec) -> kani_backend.ToolSpec:
        """Wrap one tool: same dispatch, emits, approval as the source."""
        name, desc, parameters, source_run = _tool_source(spec)

        async def run(args: dict) -> str:
            nonlocal tools_used
            if cancel.is_set():
                return '{"error": "turn stopped"}'
            if tools_used >= AGENT_MAX_TOOLS:
                return '{"error": "tool limit reached; nothing else was run"}'
            label = pretty_label(name, args)
            step_id = kani_backend.call_id()
            emit("step_start", {"label": label, "id": step_id})
            try:
                # A hung tool (e.g. a wedged MCP server) becomes a
                # model-visible error result, not a turn-killer — the model
                # can recover with its next call (lm-router GuardedKani).
                try:
                    async with asyncio.timeout(30.0):
                        model_out = await source_run(args)
                except TimeoutError:
                    model_out = json.dumps({"error": f"Tool {name} timed out after 30s"})
            except Exception as exc:
                logger.info("tool %s failed: %r", name, exc)
                emit("step_error", {"label": label, "id": step_id, "error": _error_text(exc)})
                model_out = json.dumps({"error": _error_text(exc)})
            else:
                count = _count_results(model_out)
                emit("step_done", {"label": label, "id": step_id, "count": count})
                _emit_results(emit, name, model_out, seen_urls)
            tools_used += 1
            return model_out

        return kani_backend.ToolSpec(
            name=name,
            desc=desc,
            parameters=parameters,
            run=run,
        )

    specs = list(build_tools())
    if extra_tools:
        specs.extend(extra_tools)
    wrapped = [_spec_from(s) for s in specs]

    try:
        result = await kani_backend.run_turn(
            user_text,
            history,
            system_prompt=with_clock(SYSTEM_PROMPT),
            specs=wrapped,
            cancel=cancel,
            on_token=on_token,
            on_thought=on_thought,
            on_round_reset=on_round_reset,
            on_model_step=on_model_step,
            on_steps=on_steps,
            model=getattr(state, "ai_model", "auto"),
        )
        steps = result["steps"]
        final_text = result["text"]
        served_model = result.get("model") or served_model
        if cancel.is_set():
            raise ChatCancelled()
        if not final_text.strip():
            # The model was called and said nothing: an answer-less turn is
            # not settled (settle 0 rolls the whole hold back).
            await settle_turn(credits, tx, 0)
            logger.info("tutor turn produced no answer after %d step(s); not charged", steps)
            emit("error", {"kind": "empty", "model": served_model, "steps": 0, "cost": 0})
            return
        charge = _charged_steps(steps, content_parts)
        emit(
            "text_final",
            {
                "text": final_text,
                "model": served_model,
                "steps": charge,
                "cost": charge * COST_STEP + (media_surcharge if charge > 0 else 0),
                "tokens": result.get("usage"),
            },
        )
        await settle_turn(credits, tx, charge, media_surcharge)
    except ChatCancelled:
        charge = _charged_steps(steps, content_parts)
        await settle_turn(credits, tx, charge, media_surcharge)
        emit("stopped", {"partial": "".join(content_parts), "steps": charge, "cost": charge * COST_STEP + (media_surcharge if charge > 0 else 0)})
    except AIMidStream:
        charge = _charged_steps(steps, content_parts)
        await settle_turn(credits, tx, charge, media_surcharge)
        emit("error", {"kind": "midstream", "partial": "".join(content_parts), "steps": charge, "cost": charge * COST_STEP + (media_surcharge if charge > 0 else 0)})
    except AIUnavailable as exc:
        charge = _charged_steps(steps, content_parts)
        await settle_turn(credits, tx, charge, media_surcharge)
        logger.info("tutor turn unavailable: %s", exc)
        emit("error", {"kind": "unavailable", "message": str(exc).strip(), "partial": "".join(content_parts), "steps": charge, "cost": charge * COST_STEP + (media_surcharge if charge > 0 else 0)})
    except asyncio.CancelledError:
        charge = _charged_steps(steps, content_parts)
        await settle_turn(credits, tx, charge, media_surcharge)
        logger.info("tutor turn cancelled after %d step(s)", charge)
        emit("stopped", {"partial": "".join(content_parts), "steps": charge, "cost": charge * COST_STEP + (media_surcharge if charge > 0 else 0)})
        raise
    except Exception:
        charge = _charged_steps(steps, content_parts)
        await settle_turn(credits, tx, charge, media_surcharge)
        logger.exception("tutor turn failed")
        emit("error", {"kind": "unavailable", "partial": "".join(content_parts), "steps": charge, "cost": charge * COST_STEP + (media_surcharge if charge > 0 else 0)})


def _count_results(model_out: str) -> int:
    """How many results a tool returned (for the step row)."""
    try:
        payload = json.loads(model_out)
    except Exception:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _emit_results(emit, name: str, model_out: str, seen_urls: list[str]) -> None:
    """Surface parsed results as a live card block."""
    kind = _result_kind(name)
    if kind not in ("web", "videos"):
        return
    try:
        payload = json.loads(model_out)
    except Exception:
        return
    if not isinstance(payload, list):
        return
    results = [
        SearchResult(
            title=str(row.get("title") or ""),
            url=str(row.get("url") or ""),
            snippet=str(row.get("snippet") or ""),
            kind=kind,
            thumbnail=str(row.get("thumbnail") or ""),
            duration=str(row.get("duration") or ""),
            meta={"channel": row.get("channel", "")},
        )
        for row in payload
        if isinstance(row, dict)
    ]
    if not results:
        return
    emit("results", {"kind": kind, "results": results})
    for r in results:
        if r.url and r.url not in seen_urls:
            seen_urls.append(r.url)
