"""Parent stats — the parent dashboard, derived live from existing data.

v1 precedent: get_parent_stats computes on demand (no parent table).
v2 keeps that contract and extends the shape: the base v1 triple
(total_quizzes / avg_score / last_active) plus the course, assignment,
recent-quiz, assessment, and gamification detail a parent overview needs.
No writes, no new keys.
"""

from __future__ import annotations


async def get_parent_stats(store, gamification=None) -> dict:
    """Compute the parent overview from store + gamification data."""
    attempts = await store.get_quiz_attempts(None)
    total = len(attempts)
    pcts = [(float(a.get("score") or 0) / float(a.get("total") or 1) * 100) for a in attempts if float(a.get("total") or 0) > 0]
    avg = (sum(pcts) / len(pcts)) if pcts else 0.0

    gamification_state = {"xp_total": 0, "level": "Freshman", "current_streak": 0, "best_streak": 0, "last_active_date": ""}
    badges_earned = 0
    if gamification is not None:
        try:
            loaded = await gamification.load_state()
            gamification_state = {
                "xp_total": int(loaded.get("xp_total", 0)),
                "level": str(loaded.get("level", "Freshman")),
                "current_streak": int(loaded.get("current_streak", 0)),
                "best_streak": int(loaded.get("best_streak", 0)),
                "last_active_date": str(loaded.get("last_active_date", "")),
            }
            badges_earned = sum(1 for b in await gamification.get_badges() if b.get("earned"))
        except Exception:
            pass

    last_active = gamification_state.get("last_active_date") or "Never"

    courses = await store.get_courses()
    course_rows = []
    for course in courses:
        modules = await store.get_modules(course["id"])
        done = sum(1 for m in modules if m.get("is_completed"))
        course_rows.append(
            {
                "id": course["id"],
                "subject": course.get("subject", ""),
                "level": course.get("level", ""),
                "progress_pct": float(course.get("progress_pct", 0.0)),
                "modules_done": done,
                "modules_total": len(modules),
            }
        )

    # module_id -> subject for recent-quiz joins (replaces v1's SQL JOIN).
    id_to_subject: dict[int, str] = {}
    for course in courses:
        for module in await store.get_modules(course["id"]):
            id_to_subject[module["id"]] = str(course.get("subject", ""))

    recent = sorted(attempts, key=lambda a: str(a.get("timestamp", "")), reverse=True)[:10]
    recent_quizzes = []
    for a in recent:
        total_marks = float(a.get("total") or 0)
        pct = (float(a.get("score") or 0) / total_marks * 100) if total_marks else 0.0
        recent_quizzes.append(
            {
                "subject": id_to_subject.get(a.get("module_id"), ""),
                "score": float(a.get("score") or 0),
                "total": total_marks,
                "pct": pct,
                "passed": bool(a.get("passed")),
                "weak": not bool(a.get("passed")),
                "timestamp": str(a.get("timestamp") or ""),
            }
        )

    assessments = await store.get_assessments(None)
    assessment_pcts = [(float(s.get("score") or 0) / float(s.get("total") or 1) * 100) for s in assessments if float(s.get("total") or 0) > 0]

    return {
        # v1 base shape (parity)
        "total_quizzes": total,
        "avg_score": f"{avg:.0f}%",
        "last_active": last_active,
        # v2 extensions
        "avg_pct": avg,
        "courses": course_rows,
        "assignment_counts": await store.get_assignment_counts(),
        "pending_assignments": await store.get_pending_assignments(),
        "recent_quizzes": recent_quizzes,
        "assessments": {
            "count": len(assessments),
            "avg_pct": (sum(assessment_pcts) / len(assessment_pcts)) if assessment_pcts else 0.0,
        },
        "gamification": {
            **gamification_state,
            "badges_earned": badges_earned,
        },
    }
