"""Parent stats tests — derived overview on empty and populated data."""

import pytest

from services.course_store import CourseStore
from services.gamification import GamificationService
from services.parent_stats import get_parent_stats
from tests.conftest import FakeStorage


def _stack():
    storage = FakeStorage()
    return storage, CourseStore(storage=storage), GamificationService(storage=storage)


@pytest.mark.asyncio
async def test_empty_stats_base_shape():
    storage, store, gam = _stack()
    await store.initialize()
    stats = await get_parent_stats(store, gam)
    assert stats["total_quizzes"] == 0
    assert stats["avg_score"] == "0%"
    assert stats["last_active"] == "Never"
    assert stats["courses"] == []
    assert stats["recent_quizzes"] == []


@pytest.mark.asyncio
async def test_quiz_average_and_total():
    storage, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", {"modules": []})
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 8, 10, [], True)
    await store.save_quiz_attempt(mid, 6, 10, [], True)
    stats = await get_parent_stats(store, gam)
    assert stats["total_quizzes"] == 2
    assert stats["avg_score"] == "70%"


@pytest.mark.asyncio
async def test_zero_total_attempt_ignored():
    storage, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", {"modules": []})
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 0, 0, [], False)
    stats = await get_parent_stats(store, gam)
    assert stats["avg_score"] == "0%"


@pytest.mark.asyncio
async def test_recent_quizzes_join_subject_and_weak_flag():
    storage, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Chemistry", "SSS 1", {"modules": []})
    mid = await store.add_module(cid, "Bonds", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 3, 10, [], False)
    stats = await get_parent_stats(store, gam)
    assert len(stats["recent_quizzes"]) == 1
    row = stats["recent_quizzes"][0]
    assert row["subject"] == "Chemistry"
    assert row["weak"] is True


@pytest.mark.asyncio
async def test_course_progress_rows():
    storage, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Maths", "JSS 1", {"modules": []})
    m0 = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.add_module(cid, "B", [], 1, unlocked=False)
    await store.complete_module(m0)
    stats = await get_parent_stats(store, gam)
    row = stats["courses"][0]
    assert row["modules_done"] == 1
    assert row["modules_total"] == 2
    assert row["progress_pct"] == 50.0


@pytest.mark.asyncio
async def test_assignments_and_assessments_rollup():
    storage, store, gam = _stack()
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", {"modules": []})
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.create_assignment(mid, cid, "T", "D", [])
    await store.save_assessment(cid, 80, 100, "B", 600, [])
    stats = await get_parent_stats(store, gam)
    assert stats["assignment_counts"]["pending"] == 1
    assert stats["assessments"]["count"] == 1
    assert stats["assessments"]["avg_pct"] == 80.0


@pytest.mark.asyncio
async def test_gamification_section():
    storage, store, gam = _stack()
    await store.initialize()
    await gam.award_xp("quiz_pass")
    stats = await get_parent_stats(store, gam)
    assert stats["gamification"]["xp_total"] == 25
    assert stats["gamification"]["level"] == "Freshman"


@pytest.mark.asyncio
async def test_without_gamification_service():
    storage, store, _ = _stack()
    await store.initialize()
    stats = await get_parent_stats(store, None)
    assert stats["total_quizzes"] == 0
    assert stats["gamification"]["xp_total"] == 0
