"""Gamification — XP, levels, streaks, badges.

Ported from Akili v1's gamification.py, backed by JSON storage instead of
SQLite. Award helpers return share events (level-up, milestones, badges)
so the UI can offer a share sheet.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, timedelta

from core.constants import BADGE_DEFINITIONS, LEVELS, STORAGE_GAMIFICATION, XP_REWARDS
from core.state import state

logger = logging.getLogger(__name__)

_XP_MILESTONES = (100, 500, 1000, 2500, 5000, 10000)
_STREAK_MILESTONES = (3, 7, 14, 30, 60, 100)


class GamificationService:
    def __init__(self, storage=None):
        self._storage = storage
        self._lock = asyncio.Lock()

    async def _load(self) -> dict:
        raw = await self._storage.get(STORAGE_GAMIFICATION) if self._storage else None
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                logger.warning("gamification data unreadable; resetting", exc_info=True)
        return {"xp_total": 0, "level": LEVELS[0]["name"], "current_streak": 0, "best_streak": 0, "badges": [], "last_active_date": ""}

    async def _save(self, data: dict) -> None:
        if self._storage is not None:
            await self._storage.set(STORAGE_GAMIFICATION, json.dumps(data))

    async def load_state(self) -> dict:
        """Load gamification into observable state."""
        data = await self._load()
        state.xp_total = int(data.get("xp_total", 0))
        state.level = str(data.get("level", LEVELS[0]["name"]))
        state.current_streak = int(data.get("current_streak", 0))
        state.best_streak = int(data.get("best_streak", 0))
        return data

    def calculate_level(self, xp: int) -> str:
        level = LEVELS[0]["name"]
        for lvl in LEVELS:
            if xp >= lvl["xp"]:
                level = lvl["name"]
        return level

    async def award_xp(self, action: str) -> dict:
        """Award XP for an action. Returns {xp_gained, events}."""
        gain = XP_REWARDS.get(action, 0)
        if gain == 0:
            return {"xp_gained": 0, "events": []}

        async with self._lock:
            data = await self._load()
            old_level = data.get("level", LEVELS[0]["name"])
            old_xp = int(data.get("xp_total", 0))
            new_xp = old_xp + gain
            new_level = self.calculate_level(new_xp)
            data.update({"xp_total": new_xp, "level": new_level})
            await self._save(data)

        state.xp_total = new_xp
        state.level = new_level

        events = []
        if new_level != old_level:
            info = next((lvl for lvl in LEVELS if lvl["name"] == new_level), {})
            events.append({"type": "level_up", "data": {"level": new_level, "icon": info.get("icon", "🎓"), "xp": new_xp, "name": state.user_name}})
        for milestone in _XP_MILESTONES:
            if old_xp < milestone <= new_xp:
                events.append({"type": "xp_milestone", "data": {"xp": new_xp, "level": new_level, "name": state.user_name}})
                break
        return {"xp_gained": gain, "events": events}

    async def update_streak(self) -> dict:
        """Update the daily streak. Call once per session."""
        async with self._lock:
            data = await self._load()
            last = data.get("last_active_date", "")
            today = date.today().isoformat()
            if last == today:
                # Sync observable state from storage and stop.
                state.current_streak = int(data.get("current_streak", 0))
                state.best_streak = int(data.get("best_streak", 0))
                return {"events": []}

            yesterday = (date.today() - timedelta(days=1)).isoformat()
            streak = int(data.get("current_streak", 0))
            streak = streak + 1 if last == yesterday else 1
            best = max(int(data.get("best_streak", 0)), streak)
            xp = int(data.get("xp_total", 0)) + XP_REWARDS.get("daily_streak", 15)
            level = self.calculate_level(xp)
            data.update(
                {
                    "current_streak": streak,
                    "best_streak": best,
                    "xp_total": xp,
                    "level": level,
                    "last_active_date": today,
                }
            )
            await self._save(data)

        state.current_streak = streak
        state.best_streak = best
        state.xp_total = xp
        state.level = level

        events = []
        if streak in _STREAK_MILESTONES:
            events.append({"type": "streak", "data": {"streak": streak, "name": state.user_name}})
        return {"events": events}

    async def check_badge(self, badge_id: str) -> dict | None:
        """Award a badge if not already earned. Returns share data if new."""
        async with self._lock:
            data = await self._load()
            badges = list(data.get("badges", []))
            if badge_id in badges:
                return None
            badges.append(badge_id)
            data["badges"] = badges
            await self._save(data)

        info = BADGE_DEFINITIONS.get(badge_id, {})
        return {
            "type": "badge",
            "data": {
                "badge_name": info.get("name", badge_id),
                "badge_icon": info.get("icon", "🏅"),
                "badge_desc": info.get("desc", ""),
                "name": state.user_name,
            },
        }

    async def get_badges(self) -> list[dict]:
        """All badges with earned flags."""
        data = await self._load()
        earned = set(data.get("badges", []))
        return [{**info, "id": bid, "earned": bid in earned} for bid, info in BADGE_DEFINITIONS.items()]

    async def check_earn_conditions(self, store) -> list[dict]:
        """Evaluate all seven badge conditions; return events for newly-earned.

        One place for the trigger logic so screens stay thin. v1's
        check_badge had zero call sites — no badge could ever be earned.
        """
        from core.state import state as _state

        events: list[dict] = []

        async def _maybe(badge_id: str, condition: bool) -> None:
            if condition:
                ev = await self.check_badge(badge_id)
                if ev is not None:
                    events.append(ev)

        courses = await store.get_courses()
        await _maybe("first_course", len(courses) >= 1)

        attempts = await store.get_quiz_attempts(None)
        await _maybe("perfect_quiz", any(float(a.get("total") or 0) > 0 and float(a.get("score") or 0) >= float(a.get("total") or 0) for a in attempts))
        pcts = [float(a.get("score") or 0) / float(a.get("total") or 1) * 100 for a in attempts if float(a.get("total") or 0) > 0]
        await _maybe("honor_roll", bool(pcts) and sum(pcts) / len(pcts) > 80)

        await _maybe("week_streak", int(getattr(_state, "current_streak", 0)) >= 7)
        await _maybe("ten_lessons", await store.get_completed_module_count() >= 10)

        assessments = await store.get_assessments(None)
        await _maybe("first_mock", len(assessments) >= 1)
        await _maybe("diligent_scholar", await store.get_on_time_assignment_count() >= 10)

        return events


_service: GamificationService | None = None


def init_gamification(storage) -> GamificationService:
    global _service
    _service = GamificationService(storage=storage)
    return _service


def get_gamification() -> GamificationService | None:
    return _service
