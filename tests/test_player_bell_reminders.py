"""Player, bell, and reminder tests — routing, tiles, sweep rules."""

import pytest


def test_resolve_for_playback_passthrough():
    import asyncio

    from components.lesson_player import resolve_for_playback

    assert asyncio.run(resolve_for_playback("https://cdn.example.com/lesson.mp4")) == "https://cdn.example.com/lesson.mp4"
    assert asyncio.run(resolve_for_playback("")) == ""


@pytest.mark.asyncio
async def test_resolve_youtube_uses_resolver(monkeypatch):
    from components import lesson_player as player

    async def _fake_resolve(url: str) -> str:
        assert "youtube.com" in url
        return "https://direct.example.com/stream.mp4"

    monkeypatch.setattr("services.youtube_resolver.resolve_youtube_url", _fake_resolve)
    assert await player.resolve_for_playback("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "https://direct.example.com/stream.mp4"


@pytest.mark.asyncio
async def test_resolve_youtube_failure_returns_empty(monkeypatch):
    from components import lesson_player as player

    async def _boom(url: str) -> str:
        raise RuntimeError("blocked")

    monkeypatch.setattr("services.youtube_resolver.resolve_youtube_url", _boom)
    assert await player.resolve_for_playback("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == ""


def test_player_sheet_close_dispose():
    # Structural: close() is idempotent and clears the video ref.
    from components.lesson_player import _PlayerSheet

    # Build without a live page render — exercise close() twice.
    sheet = _PlayerSheet.__new__(_PlayerSheet)
    sheet._closed = False
    sheet.video = None
    sheet.page = FakePageShim()
    sheet.close()
    assert sheet._closed is True
    sheet.close()  # idempotent
    assert sheet._closed is True


class FakePageShim:
    def run_task(self, *a, **k):
        pass

    def pop_dialog(self):
        pass


def test_notification_tiles_from_fixtures():
    from components.notification_bell import _build_tiles

    assignments = [
        {"id": 1, "subject": "Bio", "title": "T1", "due_date": "2000-01-01"},  # overdue
        {"id": 2, "subject": "Math", "title": "T2", "due_date": "2999-01-01"},  # pending
    ]
    tiles = _build_tiles(assignments, True, lambda aid: None)
    # 2 assignments + credits + streak? (streak 0 in tests) + XP milestone + tip
    assert len(tiles) >= 4


def test_notification_tiles_empty():
    from components.notification_bell import _build_tiles

    tiles = _build_tiles([], False, lambda aid: None)
    # XP milestone (Freshman, 0 XP) + study tip at minimum.
    assert len(tiles) >= 1


@pytest.mark.asyncio
async def test_reminder_sweep_overdue_once():
    from datetime import date, timedelta

    from services import reminders
    from services.course_store import CourseStore
    from tests.conftest import FakeStorage

    mem = FakeStorage()
    store = CourseStore(storage=mem)
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", {"modules": []})
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.create_assignment(mid, cid, "Past due", "D", [])
    # Force the due date into the past.
    store._data["assignments"][-1]["due_date"] = (date.today() - timedelta(days=2)).isoformat()

    class _Ctrl:
        course_store = store
        storage = mem

    first = await reminders.check_once(_Ctrl())
    assert len(first) == 1
    assert "Overdue" in first[0]

    # Second sweep: already surfaced, silent.
    assert await reminders.check_once(_Ctrl()) == []


@pytest.mark.asyncio
async def test_reminder_sweep_skips_future_due():
    from services import reminders
    from services.course_store import CourseStore
    from tests.conftest import FakeStorage

    mem = FakeStorage()
    store = CourseStore(storage=mem)
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", {"modules": []})
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.create_assignment(mid, cid, "Future", "D", [])

    class _Ctrl:
        course_store = store
        storage = mem

    assert await reminders.check_once(_Ctrl()) == []


@pytest.mark.asyncio
async def test_reminder_sweep_no_store():
    from services import reminders

    class _Ctrl:
        course_store = None
        storage = None

    assert await reminders.check_once(_Ctrl()) == []
