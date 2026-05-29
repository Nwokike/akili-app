"""Assignment service — generates assignments after module completion.

Assignments are auto-created by the system (not the tutor) after a student
finishes reading a lesson. Each assignment contains 1-2 theory/subjective
questions with source material from web research.
"""

import json
import logging

from core.ai_utils import extract_json_array, validate_mixed_questions
from core.question_types import QuestionType
from database.manager import db_manager
from services.ai_service import ai_service

logger = logging.getLogger(__name__)


async def generate_assignment(
    module: dict,
    course: dict,
    lesson_content: str,
    on_status=None,
) -> int | None:
    """Generate and save an assignment for a completed module.

    Creates 1-2 theory/subjective questions based on the lesson content.
    Uses web search to find source material for each question.

    Returns:
        assignment_id if created, None if generation failed or assignment already exists.
    """
    # Don't create duplicate assignments
    existing = await db_manager.get_module_assignment(module["id"])
    if existing:
        logger.info("Assignment already exists for module %d", module["id"])
        return existing["id"]

    def _status(msg):
        if on_status:
            on_status(msg)
        print(f"[Assignment] {msg}", flush=True)

    _status("📋 Creating assignment...")

    # Truncate lesson content to keep prompt manageable
    lesson_excerpt = lesson_content[:2000] if lesson_content else ""

    prompt = (
        f"Generate an assignment for a {course.get('level', 'Grade 10')} student.\n\n"
        f"Subject: {course.get('subject', 'General')}\n"
        f"Module: {module['title']}\n"
        f"Lesson excerpt: {lesson_excerpt}\n\n"
        f"Create exactly 2 questions:\n"
        f"- 1 theory question (factual, requires written explanation)\n"
        f"- 1 subjective question (opinion/analysis)\n\n"
        f"CRITICAL: Use search_web to find verified source material for each question.\n"
        f"Each question MUST include 'source_material' and 'source_url'.\n\n"
        f"For theory: include 'reference_answer' and 'key_points' list.\n"
        f"For subjective: include 'marking_guide' and 'sample_answer'.\n\n"
        f"Return as JSON array. Each object has: type, question, source_material, "
        f"source_url, plus type-specific fields. Set max_marks to 10 each."
    )

    def _validate(text):
        arr = extract_json_array(text)
        if not arr:
            return None
        valid = validate_mixed_questions(arr)
        # Only keep theory/subjective for assignments
        open_qs = [q for q in valid if q["type"] in QuestionType.OPEN]
        return open_qs if open_qs else None

    response = await ai_service.chat_with_healing(
        messages=[{"role": "user", "content": prompt}],
        validation_func=_validate,
        system_prompt="Generate assignment questions with source material. Return ONLY valid JSON array.",
        use_tools=True,
        on_status=on_status,
    )

    parsed = response.get("parsed")
    if not parsed:
        logger.warning("Assignment generation failed for module %d", module["id"])
        return None

    # Save to DB
    title = f"{module['title']} — Assignment"
    description = f"Complete the following questions based on your {course.get('subject', '')} lesson on {module['title']}."

    assignment_id = await db_manager.create_assignment(
        module_id=module["id"],
        course_id=course["id"],
        title=title,
        description=description,
        questions_json=json.dumps(parsed),
        due_days=3,
    )

    _status("✅ Assignment created!")
    logger.info("Assignment %d created for module %d (%d questions)", assignment_id, module["id"], len(parsed))
    return assignment_id
