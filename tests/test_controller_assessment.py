"""Controller assessment tests — unlock cascade + attempt flow (headless)."""

import pytest

from app_controller import AppController
from tests.conftest import FakePage, FakeStorage

SUBJECT = "Biology"
LEVEL = "SSS 2"
CURRICULUM = {"modules": [{"title": "A", "topics": []}, {"title": "B", "topics": []}]}


def _controller():
    return AppController(FakePage())


@pytest.mark.asyncio
async def test_complete_quiz_pass_unlocks_next():
    ctrl = _controller()
    ctrl.storage = FakeStorage()
    ctrl.course_store = __import__("services.course_store", fromlist=["CourseStore"]).CourseStore(ctrl.storage)
    await ctrl.course_store.initialize()

    cid = await ctrl.course_store.add_course(SUBJECT, LEVEL, CURRICULUM)
    m0 = await ctrl.course_store.add_module(cid, "A", [], 0, unlocked=True)
    await ctrl.course_store.add_module(cid, "B", [], 1, unlocked=False)

    await ctrl.complete_quiz_pass(m0, cid)

    modules = await ctrl.course_store.get_modules(cid)
    assert modules[0]["is_completed"] is True
    assert modules[1]["is_unlocked"] is True


@pytest.mark.asyncio
async def test_complete_quiz_pass_last_module_unlocks_nothing():
    ctrl = _controller()
    ctrl.storage = FakeStorage()
    ctrl.course_store = __import__("services.course_store", fromlist=["CourseStore"]).CourseStore(ctrl.storage)
    await ctrl.course_store.initialize()

    cid = await ctrl.course_store.add_course(SUBJECT, LEVEL, CURRICULUM)
    await ctrl.course_store.add_module(cid, "A", [], 0, unlocked=True)
    m1 = await ctrl.course_store.add_module(cid, "B", [], 1, unlocked=True)

    await ctrl.complete_quiz_pass(m1, cid)  # must not index-error

    course = await ctrl.course_store.get_course(cid)
    assert course["progress_pct"] == 50.0  # 1 of 2 complete


@pytest.mark.asyncio
async def test_load_attempts_publishes_state():
    from core.state import state

    ctrl = _controller()
    ctrl.storage = FakeStorage()
    ctrl.course_store = __import__("services.course_store", fromlist=["CourseStore"]).CourseStore(ctrl.storage)
    await ctrl.course_store.initialize()

    cid = await ctrl.course_store.add_course(SUBJECT, LEVEL, CURRICULUM)
    mid = await ctrl.course_store.add_module(cid, "A", [], 0, unlocked=True)
    await ctrl.course_store.save_quiz_attempt(mid, 12, 15, [{"q": 1}], True)

    rows = await ctrl.load_attempts()
    assert len(rows) == 1
    assert state.attempts_version >= 1


@pytest.mark.asyncio
async def test_open_assignment_sets_id():
    from core.state import state

    ctrl = _controller()
    await ctrl.open_assignment(7)
    assert state.current_assignment_id == 7


@pytest.mark.asyncio
async def test_factory_reset_wipes_study_data_keeps_credits():
    ctrl = _controller()
    ctrl.storage = FakeStorage()
    ctrl.course_store = __import__("services.course_store", fromlist=["CourseStore"]).CourseStore(ctrl.storage)
    await ctrl.course_store.initialize()

    from core.state import state

    cid = await ctrl.course_store.add_course(SUBJECT, LEVEL, CURRICULUM)
    mid = await ctrl.course_store.add_module(cid, "A", [], 0, unlocked=True)
    await ctrl.course_store.save_quiz_attempt(mid, 2, 5, [], True)
    await ctrl.course_store.save_assessment(cid, 2, 5, "F", 60, [])

    state.user_name = "Ada"
    state.education_level = "SSS 2"
    state.is_onboarded = True
    state.xp_total = 120
    state.current_streak = 3
    await ctrl.storage.set("profile", '{"name": "Ada"}')
    await ctrl.storage.set("onboarding_done", "true")
    await ctrl.storage.set("gamification", "{}")
    await ctrl.storage.set("search_history", "[]")
    await ctrl.storage.set("theme", "dark")
    await ctrl.storage.set("akili_credits", "42")

    await ctrl.factory_reset()

    assert state.user_name == ""
    assert state.is_onboarded is False
    assert state.xp_total == 0
    assert state.courses == []
    assert state.current_course is None
    assert await ctrl.course_store.get_courses() == []
    assert await ctrl.course_store.get_quiz_attempts() == []
    assert await ctrl.course_store.get_assessments() == []
    for key in ("profile", "onboarding_done", "gamification", "search_history", "theme"):
        assert await ctrl.storage.get(key) is None
    # v1 parity: the credit ledger survives a reset (no refill-by-reset).
    assert await ctrl.storage.get("akili_credits") == "42"


@pytest.mark.asyncio
async def test_factory_reset_cancels_os_notifications(monkeypatch):
    """Reset must drop scheduled due alarms + the daily nudge (Android)."""
    from services import os_notifications

    cancelled = []

    class _FakeSvc:
        async def cancel_all(self):
            cancelled.append(True)

    monkeypatch.setattr(os_notifications, "_service", _FakeSvc())

    ctrl = _controller()
    ctrl.storage = FakeStorage()
    await ctrl.factory_reset()

    assert cancelled == [True]
