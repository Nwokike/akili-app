"""Timetable tests — CRUD, weekday order, validation, edit, persistence."""

import json

import pytest

from core.constants import STORAGE_COURSES
from services.course_store import CourseStore, canonical_day
from tests.conftest import FakeStorage


def _store(storage=None):
    return CourseStore(storage=storage or FakeStorage())


def test_canonical_day():
    assert canonical_day("monday") == "Monday"
    assert canonical_day("TUE") == "Tuesday"
    assert canonical_day("  fri ") == "Friday"
    assert canonical_day("Funday") == ""
    assert canonical_day("") == ""


@pytest.mark.asyncio
async def test_add_and_list():
    store = _store()
    await store.initialize()
    eid = await store.add_timetable_entry("Monday", "09:00", "Maths", "Ch 1")
    entries = await store.get_timetable()
    assert len(entries) == 1
    assert entries[0]["id"] == eid
    assert entries[0]["note"] == "Ch 1"


@pytest.mark.asyncio
async def test_weekday_order_not_alphabetical():
    """Sunday sorts last even though 'Sunday' > 'Friday' alphabetically."""
    store = _store()
    await store.initialize()
    await store.add_timetable_entry("Sunday", "09:00", "Art")
    await store.add_timetable_entry("Monday", "08:00", "Maths")
    await store.add_timetable_entry("Friday", "10:00", "Bio")
    entries = await store.get_timetable()
    assert [e["day"] for e in entries] == ["Monday", "Friday", "Sunday"]


@pytest.mark.asyncio
async def test_time_slot_secondary_sort():
    store = _store()
    await store.initialize()
    await store.add_timetable_entry("Monday", "10:00", "B")
    await store.add_timetable_entry("Monday", "08:00", "A")
    entries = await store.get_timetable()
    assert [e["subject"] for e in entries] == ["A", "B"]


@pytest.mark.asyncio
async def test_validation_errors():
    store = _store()
    await store.initialize()
    with pytest.raises(ValueError):
        await store.add_timetable_entry("Funday", "09:00", "Maths")
    with pytest.raises(ValueError):
        await store.add_timetable_entry("Monday", "", "Maths")
    with pytest.raises(ValueError):
        await store.add_timetable_entry("Monday", "09:00", "  ")


@pytest.mark.asyncio
async def test_update_entry():
    store = _store()
    await store.initialize()
    eid = await store.add_timetable_entry("Monday", "09:00", "Maths")
    assert await store.update_timetable_entry(eid, "tue", "10:00", "Physics", "Lab") is True
    entries = await store.get_timetable()
    assert entries[0]["day"] == "Tuesday"
    assert entries[0]["note"] == "Lab"


@pytest.mark.asyncio
async def test_update_missing_returns_false():
    store = _store()
    await store.initialize()
    assert await store.update_timetable_entry(999, "Monday", "09:00", "X") is False


@pytest.mark.asyncio
async def test_delete_entry():
    store = _store()
    await store.initialize()
    eid = await store.add_timetable_entry("Monday", "09:00", "Maths")
    await store.delete_timetable_entry(eid)
    assert await store.get_timetable() == []


@pytest.mark.asyncio
async def test_persistence_round_trip():
    storage = FakeStorage()
    store = CourseStore(storage=storage)
    await store.initialize()
    await store.add_timetable_entry("Wednesday", "08:00", "English")
    raw = json.loads(await storage.get(STORAGE_COURSES))
    assert raw["timetable"][0]["subject"] == "English"
    assert raw["next_timetable_id"] == 2

    store2 = CourseStore(storage=storage)
    await store2.initialize()
    assert (await store2.get_timetable())[0]["day"] == "Wednesday"


@pytest.mark.asyncio
async def test_existing_blob_backfills_timetable():
    """Old blobs without the timetable key still load (initialize merge)."""
    storage = FakeStorage({STORAGE_COURSES: '{"courses": [], "modules": []}'})
    store = CourseStore(storage=storage)
    await store.initialize()
    assert await store.get_timetable() == []
    eid = await store.add_timetable_entry("Monday", "09:00", "Maths")
    assert eid == 1
