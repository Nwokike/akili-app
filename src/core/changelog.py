"""Bundled changelog shown by the update dialog when the app is up to
date — works fully offline. One line per release; keep the entry for the
current APP_VERSION in sync when bumping (guarded by tests).

Ported from Sherlock's changelog pattern (the house standard).
"""

CHANGELOG: dict[str, str] = {
    "2.0.0": (
        "• Create courses that build themselves around your class and country\n"
        "• Ask the AI tutor anything — it searches the web and shows sources\n"
        "• Snap a photo of handwritten work and get it graded\n"
        "• Dictate answers with your voice instead of typing\n"
        "• Watch video lessons without leaving the app\n"
        "• 100 free AI credits every day, quizzes and exams always free\n"
        "• Track XP, streaks, and badges — share your wins\n"
        "• Dark mode, offline lessons, and a parent overview with PIN"
    ),
}


def notes_for(version: str) -> str:
    """Changelog entry for a version, falling back to the latest entry."""
    return CHANGELOG.get(version) or next(reversed(CHANGELOG.values()), "")
