"""Course store tests — CRUD, unlock cascade, progress, persistence."""

import json

import pytest

from core.constants import STORAGE_COURSES
from services.course_store import CourseStore
from tests.conftest import FakeStorage

CURRICULUM = {"modules": [{"title": "Intro", "topics": ["A"]}, {"title": "Advanced", "topics": ["B"]}]}


def _store(storage=None):
    return CourseStore(storage=storage or FakeStorage())


@pytest.mark.asyncio
async def test_add_and_get_course():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Biology", "SSS 2", CURRICULUM, 3)
    course = await store.get_course(cid)
    assert course["subject"] == "Biology"
    assert course["level"] == "SSS 2"
    assert course["color_index"] == 3
    assert course["progress_pct"] == 0.0


@pytest.mark.asyncio
async def test_duplicate_guard_case_insensitive():
    store = _store()
    await store.initialize()
    await store.add_course("Biology", "SSS 2", CURRICULUM)
    assert await store.get_course_by_subject_level("  biology ", "sss 2") is not None
    assert await store.get_course_by_subject_level("Biology", "SSS 3") is None


@pytest.mark.asyncio
async def test_modules_start_with_only_first_unlocked():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    for i, mod in enumerate(CURRICULUM["modules"]):
        await store.add_module(cid, mod["title"], mod["topics"], i, unlocked=(i == 0))
    modules = await store.get_modules(cid)
    assert modules[0]["is_unlocked"] is True
    assert modules[1]["is_unlocked"] is False
    assert [m["order_num"] for m in modules] == [0, 1]


@pytest.mark.asyncio
async def test_complete_module_recomputes_progress():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    m0 = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.add_module(cid, "B", [], 1, unlocked=False)
    await store.complete_module(m0)
    course = await store.get_course(cid)
    assert course["progress_pct"] == 50.0
    modules = await store.get_modules(cid)
    assert modules[0]["is_completed"] is True


@pytest.mark.asyncio
async def test_unlock_module():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    m1 = await store.add_module(cid, "B", [], 1, unlocked=False)
    await store.unlock_module(m1)
    assert (await store.get_module(m1))["is_unlocked"] is True


@pytest.mark.asyncio
async def test_save_lesson_cache():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    m0 = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_lesson(m0, "# Lesson\nBody")
    assert (await store.get_module(m0))["lesson_cache"] == "# Lesson\nBody"


@pytest.mark.asyncio
async def test_delete_course_cascades():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.create_assignment(mid, cid, "T", "D", [{"type": "theory", "question": "q"}])
    await store.save_quiz_attempt(mid, 2, 5, [], True)
    await store.save_assessment(cid, 2, 5, "F", 60, [])
    await store.delete_course(cid)
    assert await store.get_courses() == []
    assert await store.get_modules(cid) == []
    assert await store.get_all_assignments(cid) == []
    # History cascades too, or Quiz History shows ghosts of the dead course.
    assert await store.get_quiz_attempts() == []
    assert await store.get_assessments() == []


@pytest.mark.asyncio
async def test_assignment_lifecycle():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    aid = await store.create_assignment(mid, cid, "T", "D", [{"type": "theory", "question": "q"}])
    assert (await store.get_assignment(aid))["status"] == "pending"
    assert (await store.get_module_assignment(mid))["id"] == aid

    can_complete, pending = await store.can_complete_course(cid)
    assert can_complete is False
    assert pending == 1

    await store.submit_assignment(aid, [{"text": "ans"}])
    assert (await store.get_assignment(aid))["status"] == "submitted"

    await store.grade_assignment(aid, [{"score": 8}], 80.0, "Good")
    a = await store.get_assignment(aid)
    assert a["status"] == "graded"
    assert a["score"] == 80.0

    can_complete, pending = await store.can_complete_course(cid)
    assert can_complete is True


@pytest.mark.asyncio
async def test_persistence_round_trip():
    storage = FakeStorage()
    store = CourseStore(storage=storage)
    await store.initialize()
    cid = await store.add_course("Physics", "SSS 1", CURRICULUM, 2)
    await store.add_module(cid, "Motion", ["Speed"], 0, unlocked=True)

    raw = await storage.get(STORAGE_COURSES)
    assert raw is not None
    data = json.loads(raw)
    assert data["courses"][0]["subject"] == "Physics"
    assert data["modules"][0]["title"] == "Motion"
    assert data["next_course_id"] == 2

    # A fresh store reads it back.
    store2 = CourseStore(storage=storage)
    await store2.initialize()
    assert len(await store2.get_courses()) == 1
    assert (await store2.get_modules(cid))[0]["title"] == "Motion"


@pytest.mark.asyncio
async def test_attempts_and_assessments_persist():
    store = _store()
    await store.initialize()
    cid = await store.add_course("Math", "JSS 1", CURRICULUM)
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.save_quiz_attempt(mid, 12, 15, [{"q": 1}], True)
    await store.save_assessment(cid, 80, 100, "B", 600, [{"q": 1}])
    assert len(await store.get_quiz_attempts(mid)) == 1
    assert len(await store.get_assessments(cid)) == 1


@pytest.mark.asyncio
async def test_reset_clears():
    store = _store()
    await store.initialize()
    await store.add_course("Math", "JSS 1", CURRICULUM)
    await store.reset()
    assert await store.get_courses() == []
