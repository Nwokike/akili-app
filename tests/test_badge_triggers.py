"""Badge trigger tests — each condition fires once and only once."""

from datetime import date, timedelta

import pytest

from services.course_store import CourseStore
from services.gamification import GamificationService
from tests.conftest import FakeStorage

CURRICULUM = {"modules": [{"title": "A", "topics": []}]}


def _stack(storage=None):
    storage = storage or FakeStorage()
    return storage, CourseStore(storage=storage), GamificationService(storage=storage)


@pytest.mark.asyncio
async def test_first_course_trigger():
    storage, store, gam = _stack()
    await store.initialize()
    assert await gam.check_earn_conditions(store) == []  # no courses
    await store.add_course("Bio", "SSS 2", CURRICULUM)
    events = await gam.check_earn_conditions(store)
    assert [e["type"] for e in events] == ["badge"]
    assert events[0]["data"]["badge_name"] == "First Course"
    # Second evaluation: already earned, nothing new.
    assert await gam.check_earn_conditions(store) == []


@pytest.mark.asyncio
async def test_perfect_quiz_trigger():
    storage, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 9, 10, [], True)
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Perfect Score" not in names
    await store.save_quiz_attempt(mid, 10, 10, [], True)
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Perfect Score" in names


@pytest.mark.asyncio
async def test_week_streak_trigger(monkeypatch):
    from core.state import state

    _, store, gam = _stack()
    await store.initialize()
    monkeypatch.setattr(state, "current_streak", 7)
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Week Warrior" in names


@pytest.mark.asyncio
async def test_ten_lessons_trigger():
    _, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    for i in range(10):
        mid = await store.add_module(cid, f"M{i}", [], i, unlocked=True)
        await store.complete_module(mid)
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Bookworm" in names


@pytest.mark.asyncio
async def test_first_mock_trigger():
    _, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    await store.save_assessment(cid, 70, 100, "C", 600, [])
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Exam Ready" in names


@pytest.mark.asyncio
async def test_honor_roll_trigger():
    _, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 9, 10, [], True)
    await store.save_quiz_attempt(mid, 9, 10, [], True)
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Honor Roll" in names


@pytest.mark.asyncio
async def test_honor_roll_needs_above_80():
    _, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 8, 10, [], True)  # exactly 80 -> not earned
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Honor Roll" not in names


@pytest.mark.asyncio
async def test_diligent_scholar_trigger():
    _, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    for i in range(10):
        mid = await store.add_module(cid, f"M{i}", [], i, unlocked=True)
        aid = await store.create_assignment(mid, cid, f"T{i}", "D", [])
        await store.submit_assignment(aid, [{"text": "x"}])
        await store.grade_assignment(aid, [{"score": 8}], 80.0, "ok")
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Diligent Scholar" in names


@pytest.mark.asyncio
async def test_diligent_scholar_ignores_late_submit():
    _, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", CURRICULUM)
    # submitted_at is today; force the due date into the past.
    for i in range(10):
        mid = await store.add_module(cid, f"M{i}", [], i, unlocked=True)
        aid = await store.create_assignment(mid, cid, f"T{i}", "D", [])
        await store.submit_assignment(aid, [{"text": "x"}])
        store._data["assignments"][-1]["due_date"] = (date.today() - timedelta(days=5)).isoformat()
        await store.grade_assignment(aid, [{"score": 8}], 80.0, "ok")
    names = [e["data"]["badge_name"] for e in await gam.check_earn_conditions(store)]
    assert "Diligent Scholar" not in names
