"""Centralized AI output extraction & self-healing utilities.

Multi-layer JSON extraction, thinking tag stripping, and validators
for all question types (objective, theory, subjective), evaluations,
and assignment questions.
"""

import json
import logging
import re

from core.question_types import QuestionType

logger = logging.getLogger(__name__)

# ── Pre-compiled Regexes (compile once, reuse everywhere) ─────────
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_TOOL_CALL_RE = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_GENERIC_BLOCK_RE = re.compile(r"```\s*(.*?)\s*```", re.DOTALL)
_MARKDOWN_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*", re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks and <tool_call> artifacts."""
    if not text:
        return text

    cleaned = _THINK_RE.sub("", text)
    cleaned = _TOOL_CALL_RE.sub("", cleaned)

    # Handle unclosed <think> (model hit token limit mid-thought)
    if "<think>" in cleaned:
        parts = cleaned.split("</think>")
        cleaned = parts[-1].strip()
        if cleaned.startswith("<think>"):
            cleaned = ""

    return cleaned.strip()


# Pre-compiled regexes for lesson content sanitization
_REASONING_LINE_RE = re.compile(
    r"^(?:"
    r"💭.*"                               # thought-bubble lines
    r"|[*_]{0,2}(?:Now|Let's|Let us|We need|We have|We will|We can|We should|I will|I'll|I need|Note:|Note that)\b.*"  # planning starts
    r"|(?:Draft|Craft|Create|Generate|Write|Outline|Structure|Format)\s+(?:lesson|content|the|a|an)\b.*"  # instruction verbs
    r"|(?:Word count|Aim for|Target|Ensure|Check)[:\s].*"                # meta-instructions
    r"|Structure\s*:?\s*$"               # bare "Structure:" headings
    r")$",
    re.IGNORECASE,
)

# A leading block that is clearly a planning section before the real content starts
_PLANNING_BLOCK_RE = re.compile(
    r"^\s*(?:💭[^\n]*\n|[*_]{0,2}(?:Now|Let's|We need|We have)[^\n]*\n)+"
    r"(?:[^\n]*\n)*?"                   # any further planning lines
    r"(?=#{1,3}\s|\*\*Learning Obj)",   # stop before first real heading
    re.IGNORECASE | re.MULTILINE,
)


def sanitize_lesson_content(text: str) -> str:
    """Strip AI internal reasoning / planning leakage from lesson output.

    Removes:
    - Lines starting with 💭 (thought-bubble internal monologue)
    - Lines that are clearly planning/instruction text ("Now craft...",
      "We need to ensure...", "Let's draft...", "Structure:", etc.)
    - Leading planning blocks before the actual lesson starts

    Preserves all real lesson content (headings, paragraphs, lists,
    markdown formatting, video links, notebook checkpoints, etc.) unchanged.
    """
    if not text:
        return text

    # First strip any <think> blocks
    text = strip_thinking(text)

    # Remove leading planning block if present
    text = _PLANNING_BLOCK_RE.sub("", text)

    # Filter line-by-line for any remaining leaked reasoning lines
    lines = text.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep empty lines (preserve paragraph spacing)
        if not stripped:
            clean_lines.append(line)
            continue
        # Drop lines that match reasoning patterns
        if _REASONING_LINE_RE.match(stripped):
            logger.debug("[sanitize] Dropped reasoning line: %r", stripped[:80])
            continue
        clean_lines.append(line)

    # Remove leading/trailing blank lines that might result from stripping
    result = "\n".join(clean_lines).strip()
    return result


def extract_json(text: str) -> dict | list | None:
    """Multi-layer JSON extraction — never crashes, always returns parsed data or None.

    Layers: direct parse → strip thinking → fenced blocks → bracket matching.
    """
    if not text:
        return None

    # Layer 1: Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Layer 2: Strip artifacts then try
    cleaned = strip_thinking(text)
    cleaned = _MARKDOWN_FENCE_RE.sub("", cleaned)
    cleaned = cleaned.replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Layer 3: Extract from ```json``` fenced block
    json_match = _JSON_BLOCK_RE.search(text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except Exception:
            pass

    # Layer 4: Find outermost brackets
    first_brace = cleaned.find("{")
    first_bracket = cleaned.find("[")

    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        end_bracket = cleaned.rfind("]")
        if end_bracket != -1 and end_bracket > first_bracket:
            try:
                return json.loads(cleaned[first_bracket : end_bracket + 1])
            except Exception:
                pass

    if first_brace != -1:
        end_brace = cleaned.rfind("}")
        if end_brace != -1 and end_brace > first_brace:
            try:
                return json.loads(cleaned[first_brace : end_brace + 1])
            except Exception:
                pass

    # Layer 5: Generic fenced block
    generic_match = _GENERIC_BLOCK_RE.search(text)
    if generic_match:
        try:
            return json.loads(generic_match.group(1).strip())
        except Exception:
            pass

    return None


def extract_json_array(text: str) -> list | None:
    """Extract a JSON array from AI output."""
    result = extract_json(text)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("items", "questions", "modules", "subjects", "data", "results"):
            if key in result and isinstance(result[key], list):
                return result[key]
    return None


def extract_json_object(text: str) -> dict | None:
    """Extract a JSON object from AI output."""
    result = extract_json(text)
    if isinstance(result, dict):
        return result
    return None


# ── Question Validators ──────────────────────────────────────────


def _normalize_correct(val) -> int | None:
    """Normalize 'correct' field — handles int, str letter, str number."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.strip().upper()
        if val in ("A", "B", "C", "D"):
            return ord(val) - ord("A")
        try:
            return int(val)
        except ValueError:
            return None
    return None


def validate_mixed_questions(data: list) -> list[dict]:
    """Validate array of mixed question types (objective + theory + subjective).

    Each question is validated for its type-specific required fields.
    Malformed entries are silently dropped.
    """
    validated = []
    for q in data:
        if not isinstance(q, dict):
            continue
        if "question" not in q:
            continue

        qtype = q.get("type", QuestionType.OBJECTIVE)

        # Normalize type aliases
        if qtype in ("mcq", "multiple_choice", "obj"):
            qtype = QuestionType.OBJECTIVE
        elif qtype in ("essay", "written", "long_answer"):
            qtype = QuestionType.THEORY
        elif qtype in ("opinion", "analysis", "short_answer"):
            qtype = QuestionType.SUBJECTIVE

        if qtype not in QuestionType.ALL:
            qtype = QuestionType.OBJECTIVE

        if qtype == QuestionType.OBJECTIVE:
            if "options" not in q or not isinstance(q["options"], list) or len(q["options"]) < 2:
                continue
            if "correct" not in q:
                continue
            correct = _normalize_correct(q["correct"])
            if correct is None or correct >= len(q["options"]):
                continue
            validated.append(
                {
                    "type": QuestionType.OBJECTIVE,
                    "question": str(q["question"]),
                    "options": [str(o) for o in q["options"]],
                    "correct": correct,
                    "explanation": str(q.get("explanation", "")),
                    "source_material": str(q.get("source_material", "")),
                    "source_url": str(q.get("source_url", "")),
                }
            )

        elif qtype == QuestionType.THEORY:
            validated.append(
                {
                    "type": QuestionType.THEORY,
                    "question": str(q["question"]),
                    "reference_answer": str(q.get("reference_answer", q.get("answer", ""))),
                    "key_points": q.get("key_points", []),
                    "source_material": str(q.get("source_material", "")),
                    "source_url": str(q.get("source_url", "")),
                    "max_marks": q.get("max_marks", 10),
                }
            )

        elif qtype == QuestionType.SUBJECTIVE:
            validated.append(
                {
                    "type": QuestionType.SUBJECTIVE,
                    "question": str(q["question"]),
                    "marking_guide": str(q.get("marking_guide", "")),
                    "sample_answer": str(q.get("sample_answer", q.get("answer", ""))),
                    "source_material": str(q.get("source_material", "")),
                    "source_url": str(q.get("source_url", "")),
                    "max_marks": q.get("max_marks", 10),
                }
            )

    return validated


def validate_quiz_questions(data: list) -> list[dict]:
    """Backward-compatible validator — treats all as objective if no type field."""
    # If any item has a 'type' field, use mixed validation
    if any(isinstance(q, dict) and "type" in q for q in data):
        return validate_mixed_questions(data)

    # Legacy: all objective
    validated = []
    for q in data:
        if not isinstance(q, dict):
            continue
        if "question" not in q or "options" not in q or "correct" not in q:
            continue
        correct = _normalize_correct(q["correct"])
        if correct is None:
            continue
        if isinstance(q["options"], list) and len(q["options"]) >= 2:
            validated.append(
                {
                    "type": QuestionType.OBJECTIVE,
                    "question": str(q["question"]),
                    "options": [str(o) for o in q["options"]],
                    "correct": correct,
                    "explanation": str(q.get("explanation", "")),
                    "source_material": str(q.get("source_material", "")),
                    "source_url": str(q.get("source_url", "")),
                }
            )
    return validated


def validate_evaluation(data: dict | list) -> list[dict]:
    """Validate AI evaluation results for open answers."""
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []

    validated = []
    for ev in data:
        if not isinstance(ev, dict):
            continue
        validated.append(
            {
                "score": float(ev.get("score", 0)),
                "max_score": float(ev.get("max_score", 10)),
                "feedback": str(ev.get("feedback", "")),
                "suggestions": str(ev.get("suggestions", "")),
                "key_points_hit": ev.get("key_points_hit", []),
                "key_points_missed": ev.get("key_points_missed", []),
            }
        )
    return validated


def validate_curriculum(data: dict) -> dict | None:
    """Validate and normalize a curriculum JSON object."""
    if not isinstance(data, dict):
        return None

    modules = data.get("modules")
    if not modules or not isinstance(modules, list):
        for key in ("curriculum", "course", "data"):
            nested = data.get(key)
            if isinstance(nested, dict) and "modules" in nested:
                modules = nested["modules"]
                break
            elif isinstance(nested, list):
                modules = nested
                break

    if not modules or not isinstance(modules, list):
        return None

    validated_modules = []
    for mod in modules:
        if not isinstance(mod, dict):
            continue
        title = mod.get("title") or mod.get("name") or mod.get("module")
        if not title:
            continue
        topics = mod.get("topics") or mod.get("lessons") or mod.get("subtopics") or []
        if isinstance(topics, str):
            topics = [topics]
        validated_modules.append(
            {
                "title": str(title),
                "topics": [str(t) if isinstance(t, str) else t.get("title", str(t)) for t in topics] if isinstance(topics, list) else [],
            }
        )

    if not validated_modules:
        return None

    return {"modules": validated_modules}


def validate_subject_list(data: list) -> list[str]:
    """Validate and normalize a list of subject name strings."""
    validated = []
    for item in data:
        if isinstance(item, str):
            validated.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("subject") or item.get("title")
            if name:
                validated.append(str(name).strip())
    return [s for s in validated if s][:10]
