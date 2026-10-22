"""Open-answer evaluation — grades written answers against references.

Ported from Akili v1's evaluation.py onto v2's generation pipeline,
prompt verbatim. The grader compares each answer against the
reference/marking guide AND the question's source material, awards
partial credit fairly, and may use web search to verify facts.

Image answers are OCR'd through the gateway before grading (v1 parity);
bytes are discarded immediately. Image answers are free like typed ones.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from core.ai_utils import extract_json_array, validate_evaluation
from core.question_types import QuestionType
from services import generation

logger = logging.getLogger(__name__)

_NEUTRAL_FEEDBACK = "Could not evaluate automatically. Please review this answer with a teacher."


async def evaluate_open_answers(
    questions: list[dict],
    answers: list[dict],
    student_level: str,
    on_status: Callable[[str], None] | None = None,
) -> list[dict]:
    """Grade open (theory/subjective) questions. Same order as `questions`.

    Each answer is {"text": ...} plus optional {"image_bytes", "image_mime"}
    for a photo of handwritten work (OCR'd, then discarded). Returns
    validated evaluation dicts. Raises on backend failure (the caller
    decides the UX); an unparseable result becomes the v1 neutral
    fallback instead.
    """
    from services.gateway_media import analyze_image, is_failure

    items: list[dict] = []
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else {}
        answer_text = (ans.get("text") or "").strip()
        # OCR step (v1 verbatim): image answers are read, merged, discarded.
        if ans.get("image_bytes"):
            ocr_text = await analyze_image(ans["image_bytes"], ans.get("image_mime", "image/jpeg"))
            if ocr_text and not is_failure(ocr_text):
                answer_text = f"{answer_text}\n\n[From uploaded image]: {ocr_text}" if answer_text else ocr_text
            ans["image_bytes"] = None  # ephemeral — never persisted
        answer_text = answer_text.strip() or "[No answer]"
        qtype = q.get("type", QuestionType.THEORY)
        item = {
            "question_number": i + 1,
            "type": qtype,
            "question": str(q.get("question", "")),
            "student_answer": answer_text,
            "source_material": str(q.get("source_material", "")),
            "max_marks": q.get("max_marks", 10),
        }
        if qtype == QuestionType.THEORY:
            item["reference_answer"] = str(q.get("reference_answer", ""))
            item["key_points"] = q.get("key_points", [])
        else:
            item["marking_guide"] = str(q.get("marking_guide", ""))
            item["sample_answer"] = str(q.get("sample_answer", ""))
        items.append(item)

    prompt = (
        f"You are grading open-ended answers for a {student_level} student.\n\n"
        f"ANSWERS TO EVALUATE:\n{json.dumps(items, indent=2)}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Compare each student answer against the reference_answer/marking_guide AND source_material provided.\n"
        f"2. Award partial credit fairly — students at {student_level} level should be graded appropriately.\n"
        f"3. If the student provided no answer, give 0 marks.\n"
        f"4. Be encouraging but honest in feedback.\n"
        f"5. If source_material seems insufficient, you MAY use search_web to verify facts.\n\n"
        f"Return a JSON array with one object per question:\n"
        f'{{"score": <number>, "max_score": <number>, "feedback": "<encouraging feedback>", '
        f'"suggestions": "<what to study>", "key_points_hit": [...], "key_points_missed": [...]}}'
    )

    def _validate(text: str):
        arr = extract_json_array(text)
        if not arr:
            return None
        evs = validate_evaluation(arr)
        return evs if evs else None

    result = await generation.generate_structured(
        [
            {
                "role": "system",
                "content": "You are a fair, encouraging exam grader. Return ONLY valid JSON array.",
            },
            {"role": "user", "content": prompt},
        ],
        validator=_validate,
        use_tools=True,
        on_status=on_status,
    )
    if result:
        # Pad or trim to the question count so the caller can zip safely.
        result = list(result)
        while len(result) < len(questions):
            result.append({"score": 0, "max_score": 10, "feedback": _NEUTRAL_FEEDBACK, "suggestions": "", "key_points_hit": [], "key_points_missed": []})
        return result[: len(questions)]

    return [{"score": 5, "max_score": 10, "feedback": _NEUTRAL_FEEDBACK, "suggestions": "", "key_points_hit": [], "key_points_missed": []} for _ in questions]
