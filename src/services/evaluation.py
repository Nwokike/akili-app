"""Evaluation service — grades open (theory/subjective) answers using AI.

Used by quizzes, mock exams, and assignments. The generating AI already
embeds source_material into each question, so the evaluating AI has
verified reference material and doesn't rely on its own knowledge.

Image answers are OCR'd via Vision first, then evaluated as text.
All image bytes are ephemeral — discarded after processing (no bloat).
"""

import json
import logging

from core.ai_utils import extract_json_array, validate_evaluation
from core.question_types import QuestionType
from services.ai_service import ai_service

logger = logging.getLogger(__name__)


async def evaluate_open_answers(
    questions: list[dict],
    student_answers: list[dict],
    student_level: str,
    on_status=None,
) -> list[dict]:
    """Evaluate open (theory/subjective) answers against source material.

    Args:
        questions: Question dicts with source_material, reference_answer, etc.
        student_answers: List of {"text": str, "image_bytes": bytes|None, "image_mime": str|None}
        student_level: e.g. "SS2" for age-appropriate feedback
        on_status: Optional callback for UI status updates

    Returns:
        List of evaluation dicts: {score, max_score, feedback, suggestions, ...}
        Image bytes are NOT stored — only the extracted text is kept.
    """
    if not questions or not student_answers:
        return []

    def _status(msg):
        if on_status:
            on_status(msg)
        print(f"[Evaluation] {msg}", flush=True)

    # Step 1: OCR any image answers via Vision
    processed_answers = []
    for i, ans in enumerate(student_answers):
        answer_text = ans.get("text", "").strip()

        if ans.get("image_bytes"):
            _status(f"👁️ Reading handwritten answer {i + 1}...")
            try:
                ocr_text = await ai_service.analyze_image(ans["image_bytes"], ans.get("image_mime", "image/jpeg"))
                if ocr_text and not ocr_text.startswith("["):
                    answer_text = f"{answer_text}\n\n[From uploaded image]: {ocr_text}" if answer_text else ocr_text
            except Exception as e:
                logger.warning("OCR failed for answer %d: %s", i + 1, e)

            # Discard image bytes immediately after OCR — no bloat
            ans["image_bytes"] = None

        processed_answers.append(answer_text)

    # Step 2: Build evaluation prompt
    eval_items = []
    for i, (q, ans_text) in enumerate(zip(questions, processed_answers, strict=False)):
        qtype = q.get("type", QuestionType.THEORY)
        item = {
            "question_number": i + 1,
            "type": qtype,
            "question": q["question"],
            "student_answer": ans_text or "[No answer provided]",
            "source_material": q.get("source_material", ""),
        }

        if qtype == QuestionType.THEORY:
            item["reference_answer"] = q.get("reference_answer", "")
            item["key_points"] = q.get("key_points", [])
        elif qtype == QuestionType.SUBJECTIVE:
            item["marking_guide"] = q.get("marking_guide", "")
            item["sample_answer"] = q.get("sample_answer", "")

        item["max_marks"] = q.get("max_marks", 10)
        eval_items.append(item)

    if not eval_items:
        return []

    _status("📝 Evaluating your answers...")

    prompt = (
        f"You are grading open-ended answers for a {student_level} student.\n\n"
        f"ANSWERS TO EVALUATE:\n{json.dumps(eval_items, indent=2)}\n\n"
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

    def _validate(text):
        arr = extract_json_array(text)
        if not arr:
            return None
        evals = validate_evaluation(arr)
        return evals if evals else None

    response = await ai_service.chat_with_healing(
        messages=[{"role": "user", "content": prompt}],
        validation_func=_validate,
        system_prompt="You are a fair, encouraging exam grader. Return ONLY valid JSON array.",
        use_tools=True,  # Allow search as fallback verification
        on_status=on_status,
    )

    if response.get("_error"):
        raise Exception(response.get("content", "AI evaluation request failed."))

    parsed = response.get("parsed", [])
    if not parsed:
        # Fallback: give neutral scores
        logger.warning("Evaluation AI failed. Returning neutral scores.")
        parsed = [{"score": 5, "max_score": 10, "feedback": "Could not evaluate automatically. Please review with your teacher.", "suggestions": "", "key_points_hit": [], "key_points_missed": []} for _ in eval_items]

    return parsed
