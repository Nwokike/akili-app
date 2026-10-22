"""Gamification tests — XP, levels, streaks, badges."""

from datetime import date, timedelta

import pytest

from core.constants import STORAGE_GAMIFICATION, XP_REWARDS
from services.gamification import GamificationService
from tests.conftest import FakeStorage


def _svc(storage=None):
    return GamificationService(storage=storage or FakeStorage())


@pytest.mark.asyncio
async def test_award_xp_basic():
    svc = _svc()
    result = await svc.award_xp("lesson_complete")
    assert result["xp_gained"] == XP_REWARDS["lesson_complete"]
    from core.state import state

    assert state.xp_total == XP_REWARDS["lesson_complete"]


@pytest.mark.asyncio
async def test_award_xp_zero_for_unknown():
    svc = _svc()
    assert (await svc.award_xp("not_a_real_action"))["xp_gained"] == 0


@pytest.mark.asyncio
async def test_level_up_event():
    from core.state import state

    svc = _svc()
    await svc.load_state()
    # Push XP near the Scholar threshold (200), then cross it.
    state.xp_total = 0
    for _ in range(20):
        result = await svc.award_xp("lesson_complete")  # 10 each -> 200
    assert any(ev["type"] == "level_up" for ev in result["events"])
    assert state.level == "Scholar"


@pytest.mark.asyncio
async def test_calculate_level():
    svc = _svc()
    assert svc.calculate_level(0) == "Freshman"
    assert svc.calculate_level(200) == "Scholar"
    assert svc.calculate_level(5000) == "Genius"


@pytest.mark.asyncio
async def test_streak_first_day():
    svc = _svc()
    from core.state import state

    result = await svc.update_streak()
    assert state.current_streak == 1
    assert result["events"] == []  # 1 is not a milestone


@pytest.mark.asyncio
async def test_streak_increments_on_consecutive_day():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    storage = FakeStorage({STORAGE_GAMIFICATION: f'{{"current_streak": 2, "best_streak": 2, "last_active_date": "{yesterday}"}}'})
    svc = GamificationService(storage=storage)
    from core.state import state

    await svc.load_state()
    result = await svc.update_streak()
    assert state.current_streak == 3
    assert any(ev["type"] == "streak" for ev in result["events"])  # 3 is a milestone


@pytest.mark.asyncio
async def test_streak_resets_after_gap():
    old = (date.today() - timedelta(days=5)).isoformat()
    storage = FakeStorage({STORAGE_GAMIFICATION: f'{{"current_streak": 9, "best_streak": 9, "last_active_date": "{old}"}}'})
    svc = GamificationService(storage=storage)
    from core.state import state

    await svc.load_state()
    await svc.update_streak()
    assert state.current_streak == 1
    assert state.best_streak == 9  # best preserved


@pytest.mark.asyncio
async def test_streak_same_day_no_double():
    today = date.today().isoformat()
    storage = FakeStorage({STORAGE_GAMIFICATION: f'{{"current_streak": 4, "last_active_date": "{today}"}}'})
    svc = GamificationService(storage=storage)
    from core.state import state

    await svc.load_state()
    result = await svc.update_streak()
    assert state.current_streak == 4
    assert result["events"] == []


@pytest.mark.asyncio
async def test_badge_awarded_once():
    svc = _svc()
    first = await svc.check_badge("first_course")
    second = await svc.check_badge("first_course")
    assert first is not None
    assert first["data"]["badge_name"] == "First Course"
    assert second is None


@pytest.mark.asyncio
async def test_get_badges_flags():
    svc = _svc()
    await svc.check_badge("first_course")
    badges = await svc.get_badges()
    earned = {b["id"]: b["earned"] for b in badges}
    assert earned["first_course"] is True
    assert earned["perfect_quiz"] is False
