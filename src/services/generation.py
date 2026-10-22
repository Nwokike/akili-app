"""Structured AI generation — the v2 replacement for v1's chat_with_healing.

Runs a kani turn (tool-enabled for web research, or tool-less) and drives
the v1 extraction + validation + self-healing pipeline over the result.
Prompts are ported verbatim from v1 so the same models produce the same
shapes; only the transport changed (kani over the Kiri router instead of
the old gateway).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

from core.ai_utils import (
    sanitize_lesson_content,
    validate_assignment_questions,
    validate_curriculum,
    validate_subject_list,
)
from core.question_types import get_mix_prompt

logger = logging.getLogger(__name__)

_HEAL_CORRECTION = "CRITICAL: The previous output could not be parsed. Return ONLY the exact, valid output structure requested. No  thinking blocks, no markdown fences, no preamble or commentary."


async def _call_kani(
    messages: list[dict],
    *,
    use_tools: bool,
    on_status: Callable[[str], None] | None = None,
) -> str:
    """Run one kani turn and return the final text.

    `use_tools` routes through run_turn with the read-only search tools
    (agentic web research); otherwise a tool-less single shot.
    """
    from agent import kani_backend
    from agent.tools import build_tools

    system = ""
    body: list[dict] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or "") == "system" and not system:
            system = str(item.get("content") or "")
            continue
        body.append(item)

    if not use_tools:
        result = await kani_backend.complete(body, lambda _t: None, system_prompt=system)
        return result.get("text", "")

    # Tool-enabled: the last user message is the query, the rest is history.
    query = ""
    history: list[dict] = []
    for item in body:
        if str(item.get("role") or "") == "user":
            if query:
                history.append({"role": "user", "content": query})
            query = str(item.get("content") or "")
        else:
            history.append({"role": str(item.get("role") or ""), "content": str(item.get("content") or "")})

    cancel = asyncio.Event()

    def _on_status_emit(kind: str, data: dict) -> None:
        if on_status is not None and kind == "step_start":
            label = str(data.get("label") or "")
            if label:
                with contextlib.suppress(Exception):
                    on_status(label)

    result = await kani_backend.run_turn(
        query,
        history,
        system_prompt=system,
        specs=build_tools(),
        cancel=cancel,
        on_token=lambda _t: None,
        on_thought=None,
    )
    return result.get("text", "")


async def generate_structured(
    messages: list[dict],
    *,
    validator: Callable[[object], object],
    use_tools: bool = False,
    max_healing: int = 2,
    on_status: Callable[[str], None] | None = None,
) -> object | None:
    """Run a turn, validate, and self-heal malformed output.

    Returns the validator's value on success, or None if it never parsed.

    METERING CONTRACT: this function never touches credits — callers own
    it. Metered features (course creation, lesson generation, assignment
    evaluation) reserve their feature cost BEFORE calling and commit/roll
    back around the result; quiz and exam generation are free. A new
    caller that forgets the reserve is a silent giveaway — keep the
    reserve at the call site.
    """
    attempt_messages = list(messages)
    use_tools_now = use_tools

    for attempt in range(max_healing + 1):
        if on_status is not None:
            with contextlib.suppress(Exception):
                on_status("Researching…" if use_tools_now else "Thinking…")
        try:
            text = await _call_kani(attempt_messages, use_tools=use_tools_now, on_status=on_status)
        except Exception as exc:
            logger.warning("generation call failed (attempt %d): %r", attempt + 1, exc)
            if attempt >= max_healing:
                raise
            await asyncio.sleep(1.0)
            continue

        if not text or not text.strip():
            if attempt >= max_healing:
                return None
            continue

        parsed = validator(text)
        if parsed is not None:
            return parsed

        # Heal: append the raw output + a correction, retry tool-less.
        if attempt >= max_healing:
            return None
        attempt_messages = [
            *attempt_messages,
            {"role": "assistant", "content": text},
            {"role": "user", "content": _HEAL_CORRECTION},
        ]
        use_tools_now = False
        logger.info("healing generation (attempt %d)", attempt + 2)

    return None


# ── Feature builders (prompts ported verbatim from v1) ──────────────────────


async def suggest_subjects(level: str, country: str, on_status=None) -> list[str] | None:
    """10 subjects suitable for the student's level and country. Free."""
    prompt = f"Suggest 10 subjects suitable for a {level} student from {country}. Return ONLY a JSON array of strings."

    def _validate(text: str):
        from core.ai_utils import extract_json_array

        arr = extract_json_array(text)
        if not arr:
            return None
        subjects = validate_subject_list(arr)
        return subjects or None

    return await generate_structured(
        [
            {"role": "system", "content": "Return ONLY valid JSON array of subject names. No markdown."},
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=False,
        on_status=on_status,
    )


async def generate_curriculum(subject: str, level: str, country: str, on_status=None) -> dict | None:
    """A structured curriculum — modules named by topic, not by term."""
    prompt = (
        f"You are designing an official, high-quality curriculum for {subject} at {level} level "
        f"specifically tailored to standard curricula in {country}.\n\n"
        f"CRITICAL REQUIREMENTS:\n"
        f"1. Search the web for official curriculum documents and syllabus outlines "
        f"from reputable educational boards in {country} for '{subject}'.\n"
        f"2. Name modules by topic (e.g. genetics, bonding, algebra) — NOT by academic terms like 'First Term'.\n"
        f"3. Structure sequentially from foundational to advanced.\n"
        f"4. Return ONLY valid JSON: {{'modules': [{{'title': '...', 'topics': ['detailed topic 1', '...']}}]}}\n\n"
        f"RESEARCH EFFICIENCY:\n"
        f"- Stop once you have enough material — re-reading the same site doesn't improve quality.\n"
        f"- Use exact URLs from search results. Do NOT guess URLs.\n"
        f"- Emit the final JSON immediately. No preamble or commentary."
    )

    def _validate(text: str):
        from core.ai_utils import extract_json_object

        obj = extract_json_object(text)
        if not obj:
            return None
        curr = validate_curriculum(obj)
        return curr if curr else None

    return await generate_structured(
        [
            {
                "role": "system",
                "content": ("Return ONLY valid JSON with 'modules' list. Each module has 'title' and 'topics' list. If you cannot find info, still try your best to return a JSON structure with general topics."),
            },
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=True,
        on_status=on_status,
    )


async def generate_lesson(module: dict, subject: str, level: str, on_status=None) -> str | None:
    """A comprehensive lesson in clean markdown, cached after the first run."""
    topics = module.get("topics") or []
    topic_list = ", ".join(topics) if topics else module.get("title", "")
    prompt = (
        f"Create a comprehensive lesson for: {module['title']}\n"
        f"Subject: {subject}, Level: {level}\n"
        f"Topics to cover: {topic_list}\n\n"
        f"Requirements:\n"
        f"- Start with clear learning objectives\n"
        f"- Explain each concept step by step\n"
        f"- Use examples and analogies\n"
        f"- Include practice problems where relevant\n"
        f"- Use markdown formatting\n"
        f"- Aim for 800-1200 words\n"
        f"- FORMULA RENDERING CONSTRAINT: Do NOT use LaTeX syntax (like $, $$, \\frac, \\sqrt, etc.) for scientific/mathematical equations. "
        f"Instead, format all equations and formulas using standard Unicode characters, bold/italic text, and sub/superscripts "
        f"(e.g., use 'H₂O', 'x²', '±', '√', 'π', and italics for variables) so they render beautifully and natively in standard markdown.\n"
        f"- VIDEO RECOMMENDATION (OPTIONAL): Use search_videos tool to find relevant educational YouTube videos. "
        f"Only recommend videos returned by the tool. Do NOT guess or construct YouTube URLs. "
        f"If none found, omit this section entirely. "
        f"Format at the very end of the lesson (before Notebook Checkpoint) as: "
        f"`[VIDEO]: Title - YouTube URL`\n"
        f"- END the lesson with a '📓 Notebook Checkpoint' section that lists 5-8 key points "
        f"the student should write down in their notebook. Frame it as: 'Write these in your "
        f"notebook — you will need them for your quiz and assignment.'"
    )

    def _validate(text: str):
        cleaned = sanitize_lesson_content(text)
        return cleaned if cleaned and len(cleaned) > 200 else None

    return await generate_structured(
        [
            {
                "role": "system",
                "content": (
                    f"You are Akili, a helpful AI tutor for {level} students. "
                    "Output ONLY the lesson content in clean markdown. "
                    "Do NOT include any internal reasoning, planning notes, thought process, "
                    "word-count targets, structural outlines, or meta-instructions. "
                    "Begin directly with the lesson heading or learning objectives."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=True,
        on_status=on_status,
    )


async def generate_assignment_questions(
    module: dict,
    course: dict,
    lesson_content: str,
    on_status=None,
) -> list[dict] | None:
    """Two open questions (1 theory + 1 subjective) with sourced material."""
    lesson_excerpt = (lesson_content or "")[:2000]
    prompt = (
        f"Generate an assignment for a {course.get('level', 'Grade 10')} student.\n\n"
        f"Subject: {course.get('subject', 'General')}\n"
        f"Module: {module['title']}\n"
        f"Lesson excerpt: {lesson_excerpt}\n\n"
        f"Create exactly 2 questions:\n- 1 theory question (factual, requires written explanation)\n"
        f"- 1 subjective question (opinion/analysis)\n\n"
        f"CRITICAL: Use search_web to find verified source material for each question.\n"
        f"Each question MUST include 'source_material' and 'source_url'.\n\n"
        f"For theory: include 'reference_answer' and 'key_points' list.\n"
        f"For subjective: include 'marking_guide' and 'sample_answer'.\n\n"
        f"Return as JSON array. Each object has: type, question, source_material, source_url, "
        f"plus type-specific fields. Set max_marks to 10 each."
    )

    def _validate(text: str):
        from core.ai_utils import extract_json_array

        arr = extract_json_array(text)
        if not arr:
            return None
        return validate_assignment_questions(arr)

    return await generate_structured(
        [
            {
                "role": "system",
                "content": "Generate assignment questions with source material. Return ONLY valid JSON array.",
            },
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=True,
        on_status=on_status,
    )


async def generate_quiz_questions(module: dict, level: str, on_status=None) -> list[dict] | None:
    """A 5-question mixed quiz scoped to the lesson cache. Free.

    (Ships in Phase 3 so the prompt/validator pipeline is complete; the
    quiz screen consumes it in Phase 4.)
    """
    from core.ai_utils import extract_json_array, validate_mixed_questions
    from core.question_types import QUIZ_MIX

    lesson = (module.get("lesson_cache") or "")[:3000]
    context = f"\n\nLesson content:\n{lesson}" if lesson else ""
    scope_rule = ("SCOPE RULE: Base EVERY question STRICTLY on the lesson content above. Do NOT introduce topics, facts, or terminology that are not covered in it. ") if lesson else ""
    mix_instructions = get_mix_prompt(QUIZ_MIX)
    total = sum(QUIZ_MIX.values())
    prompt = (
        f"Generate questions about '{module['title']}' for {level} students.{context}\n\n"
        f"{scope_rule}\n\n"
        f"QUESTION MIX (exactly {total} questions):\n{mix_instructions}\n\n"
        f"CRITICAL: For EVERY question, derive 'source_material' from the lesson content above — not from outside knowledge.\n"
        f"FORMULA RENDERING CONSTRAINT: Do NOT use LaTeX (like $, $$, \\frac, \\sqrt). "
        f"Use 'H₂O', 'x²', '±', '√', 'π' and italics for variables.\n\n"
        f"For objective: include 'options' (4 strings), 'correct' (0-based index), 'explanation'.\n"
        f"For theory: include 'reference_answer', 'key_points' list.\n"
        f"For subjective: include 'marking_guide', 'sample_answer'.\n\n"
        f"Return as JSON array. Each object MUST have 'type' field."
    )

    def _validate(text: str):
        arr = extract_json_array(text)
        if not arr:
            return None
        qs = validate_mixed_questions(arr)
        return qs if qs else None

    return await generate_structured(
        [
            {"role": "system", "content": "Return ONLY valid JSON array of mixed question types. No markdown."},
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=False,
        on_status=on_status,
    )


async def generate_exam_questions(course: dict, modules: list[dict], level: str, on_status=None) -> list[dict] | None:
    """A 10-question exam built ONLY from studied material. Free.

    (Ships in Phase 3; the exam screen consumes it in Phase 4.)
    """
    from core.ai_utils import extract_json_array, validate_mixed_questions
    from core.question_types import EXAM_MIX, QuestionType

    blocks: list[str] = []
    for m in modules:
        lesson = (m.get("lesson_cache") or "").strip()
        if lesson:
            blocks.append(f"### {m['title']}\n{lesson[:1500]}")
        else:
            topics = ", ".join(m.get("topics") or [])
            blocks.append(f"### {m['title']} (topics: {topics})\n[Lesson not yet generated for this module]")
    material = "\n\n".join(blocks)[:8000]
    mix = get_mix_prompt(EXAM_MIX)
    total = sum(EXAM_MIX.values())
    subject = course.get("subject", "General")
    prompt = (
        f"You are creating a comprehensive mock exam for '{subject}' at {level} level.\n"
        f"This exam must test ONLY what the student has studied.\n\n"
        f"=== COURSE MATERIAL (the ONLY source you may use) ===\n{material}\n=== END ===\n\n"
        f"CRITICAL REQUIREMENTS:\n"
        f"1. Base EVERY question STRICTLY on the course material above.\n"
        f"2. Spread questions across the modules.\n"
        f"3. Make questions challenging and exam-worthy.\n"
        f"4. Put ALL objective questions FIRST (Section A), then ALL theory/subjective (Section B).\n"
        f"5. Each question must include 'type' and 'source_material'.\n"
        f"6. FORMULA RENDERING CONSTRAINT: Do NOT use LaTeX — use 'H₂O', 'x²', '±', '√', 'π'.\n\n"
        f"EXAM STRUCTURE ({total} questions total):\n{mix}\n\n"
        f"For objective: 'options' (4 strings), 'correct' (0-based), 'explanation'.\n"
        f"For theory: 'reference_answer', 'key_points'.\n"
        f"For subjective: 'marking_guide', 'sample_answer'.\n\n"
        f"Return ONLY a clean JSON array."
    )

    def _validate(text: str):
        arr = extract_json_array(text)
        if not arr:
            return None
        qs = validate_mixed_questions(arr)
        if not qs:
            return None
        obj = [q for q in qs if q["type"] == QuestionType.OBJECTIVE]
        rest = [q for q in qs if q["type"] != QuestionType.OBJECTIVE]
        return obj + rest  # Section A first

    return await generate_structured(
        [
            {"role": "system", "content": "Return ONLY valid JSON array of exam questions. No markdown."},
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=False,
        on_status=on_status,
    )
