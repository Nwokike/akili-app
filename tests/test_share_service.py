"""Share service tests — payloads, cards, event mapping."""

from services.share_service import (
    ShareType,
    build_share_card,
    build_share_text,
    offer_share_event,
)


def _quiz():
    return {"pct": 85, "subject": "Biology", "module": "Genetics", "name": "Ada"}


def test_quiz_result_thresholds():
    assert "🏆" in build_share_text(ShareType.QUIZ_RESULT, {**_quiz(), "pct": 95})
    assert "⭐" in build_share_text(ShareType.QUIZ_RESULT, {**_quiz(), "pct": 75})
    assert "📊" in build_share_text(ShareType.QUIZ_RESULT, {**_quiz(), "pct": 40})
    assert "💯 Perfect Score!" in build_share_text(ShareType.QUIZ_RESULT, {**_quiz(), "pct": 100})


def test_quiz_text_has_subject_and_footer():
    text = build_share_text(ShareType.QUIZ_RESULT, _quiz())
    assert "Biology — Genetics" in text
    assert "play.google.com" in text
    assert "#AkiliApp" in text


def test_exam_result_grade_and_time():
    text = build_share_text(ShareType.EXAM_RESULT, {"grade": "A", "pct": 92, "subject": "Math", "duration": 630, "name": "Ada"})
    assert "Grade: A (92%)" in text
    assert "10m 30s" in text


def test_exam_result_non_a_emoji():
    assert "🌟" in build_share_text(ShareType.EXAM_RESULT, {"grade": "B", "pct": 82, "subject": "M", "name": "A"})
    assert "📝" in build_share_text(ShareType.EXAM_RESULT, {"grade": "D", "pct": 62, "subject": "M", "name": "A"})


def test_assignment_result_text():
    text = build_share_text(ShareType.ASSIGNMENT_RESULT, {"pct": 80, "subject": "Bio", "title": "M — Assignment", "name": "Ada"})
    assert "Assignment Graded" in text
    assert "80%" in text


def test_xp_milestone_text():
    text = build_share_text(ShareType.XP_MILESTONE, {"xp": 1000, "level": "Academic", "name": "Ada"})
    assert "1,000" in text
    assert "Academic" in text


def test_streak_text():
    text = build_share_text(ShareType.STREAK, {"streak": 7, "name": "Ada"})
    assert "7-Day" in text


def test_badge_text():
    text = build_share_text(ShareType.BADGE, {"badge_name": "First Course", "badge_icon": "🎯", "badge_desc": "Created one", "name": "Ada"})
    assert "First Course" in text
    assert "Created one" in text


def test_level_up_text():
    text = build_share_text(ShareType.LEVEL_UP, {"level": "Scholar", "icon": "📚", "xp": 200, "name": "Ada"})
    assert "Scholar" in text


def test_course_complete_text():
    text = build_share_text(ShareType.COURSE_COMPLETE, {"subject": "Biology", "name": "Ada"})
    assert "Biology" in text


def test_unknown_type_falls_back():
    text = build_share_text("nope", {})
    assert "Akili" in text
    assert "play.google.com" in text


def test_cards_build_for_all_types():
    payloads = {
        ShareType.QUIZ_RESULT: _quiz(),
        ShareType.EXAM_RESULT: {"grade": "B", "pct": 82, "subject": "M", "name": "A"},
        ShareType.ASSIGNMENT_RESULT: {"pct": 80, "subject": "B", "title": "T", "name": "A"},
        ShareType.XP_MILESTONE: {"xp": 500, "level": "Rising Star", "name": "A"},
        ShareType.STREAK: {"streak": 7, "name": "A"},
        ShareType.BADGE: {"badge_name": "B", "badge_icon": "🎯", "badge_desc": "d", "name": "A"},
        ShareType.LEVEL_UP: {"level": "Scholar", "icon": "📚", "xp": 200, "name": "A"},
        ShareType.COURSE_COMPLETE: {"subject": "Bio", "name": "A"},
    }
    for share_type, data in payloads.items():
        card = build_share_card(share_type, data)
        assert card is not None


def test_offer_share_event_mapping(monkeypatch):
    shown = []
    import services.share_service as svc

    monkeypatch.setattr(svc, "show_share_sheet", lambda page, t, d: shown.append((t, d)))
    assert offer_share_event(object(), {"type": "level_up", "data": {"level": "S"}}) is True
    assert shown[-1][0] == ShareType.LEVEL_UP
    assert offer_share_event(object(), {"type": "xp_milestone", "data": {}}) is True
    assert offer_share_event(object(), {"type": "streak", "data": {}}) is True
    assert offer_share_event(object(), {"type": "badge", "data": {}}) is True
    assert offer_share_event(object(), {"type": "nope", "data": {}}) is False
    assert offer_share_event(object(), None) is False
