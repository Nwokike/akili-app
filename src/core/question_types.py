"""Question type definitions and schema constants for Akili v2.

Three question types mirror Nigerian exam formats (WAEC/NECO):
- Objective (MCQ) — Section A style
- Theory (factual written) — Section B style
- Subjective (opinion/analysis) — Section B style

Every question carries source_material from web research
so evaluating AI never relies on its own knowledge alone.
"""


class QuestionType:
    OBJECTIVE = "objective"
    THEORY = "theory"
    SUBJECTIVE = "subjective"

    ALL = (OBJECTIVE, THEORY, SUBJECTIVE)
    OPEN = (THEORY, SUBJECTIVE)  # Types that need written answers


# Default marks per question type
DEFAULT_MARKS = {
    QuestionType.OBJECTIVE: 3,
    QuestionType.THEORY: 10,
    QuestionType.SUBJECTIVE: 10,
}

# Question mix ratios
QUIZ_MIX = {QuestionType.OBJECTIVE: 3, QuestionType.THEORY: 1, QuestionType.SUBJECTIVE: 1}  # 5 total
EXAM_MIX = {QuestionType.OBJECTIVE: 6, QuestionType.THEORY: 2, QuestionType.SUBJECTIVE: 2}  # 10 total


def get_mix_prompt(mix: dict) -> str:
    """Build the question mix instruction for AI prompts."""
    parts = []
    for qtype, count in mix.items():
        if qtype == QuestionType.OBJECTIVE:
            parts.append(f"- {count} objective (MCQ with 4 options, 0-based correct index)")
        elif qtype == QuestionType.THEORY:
            parts.append(f"- {count} theory (factual, requires a written answer)")
        elif qtype == QuestionType.SUBJECTIVE:
            parts.append(f"- {count} subjective (opinion/analysis, requires a written answer)")
    return "\n".join(parts)
