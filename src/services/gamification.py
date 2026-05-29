import json
from datetime import date, timedelta

from core.constants import LEVELS, XP_REWARDS
from core.state import state
from database.manager import db_manager

BADGE_DEFINITIONS = {
    "first_course": {"name": "First Course", "icon": "🎯", "desc": "Created your first course"},
    "perfect_quiz": {"name": "Perfect Score", "icon": "💯", "desc": "Got 100% on a quiz"},
    "week_streak": {"name": "Week Warrior", "icon": "🔥", "desc": "7-day study streak"},
    "ten_lessons": {"name": "Bookworm", "icon": "📖", "desc": "Completed 10 lessons"},
    "first_mock": {"name": "Exam Ready", "icon": "📝", "desc": "Completed first mock exam"},
    "honor_roll": {"name": "Honor Roll", "icon": "🏆", "desc": "Average score above 80%"},
    "diligent_scholar": {"name": "Diligent Scholar", "icon": "✍️", "desc": "Completed 10 assignments on time"},
}


class GamificationService:
    async def load_state(self):
        """Load gamification data from DB into app state."""
        data = await db_manager.get_gamification()
        state.xp_total = data["xp_total"]
        state.level = data["level"]
        state.current_streak = data["current_streak"]
        state.best_streak = data["best_streak"]

    async def award_xp(self, action: str) -> dict:
        """Award XP for an action. Returns dict with xp_gained + optional share events."""
        xp_gain = XP_REWARDS.get(action, 0)
        if xp_gain == 0:
            return {"xp_gained": 0, "events": []}

        old_level = state.level
        state.xp_total += xp_gain
        new_level = self._calculate_level(state.xp_total)
        state.level = new_level

        await self._save()

        events = []

        # Level up event — shareable
        if new_level != old_level:
            level_info = next((lvl for lvl in LEVELS if lvl["name"] == new_level), {})
            events.append(
                {
                    "type": "level_up",
                    "data": {
                        "level": new_level,
                        "icon": level_info.get("icon", "🎓"),
                        "xp": state.xp_total,
                        "name": state.user_name,
                    },
                }
            )

        # XP milestones — shareable at 100, 500, 1000, 2500, 5000, 10000
        milestones = [100, 500, 1000, 2500, 5000, 10000]
        old_xp = state.xp_total - xp_gain
        for m in milestones:
            if old_xp < m <= state.xp_total:
                events.append(
                    {
                        "type": "xp_milestone",
                        "data": {
                            "xp": state.xp_total,
                            "level": state.level,
                            "name": state.user_name,
                        },
                    }
                )
                break

        return {"xp_gained": xp_gain, "events": events}

    async def update_streak(self) -> dict:
        """Update daily streak. Call once per session. Returns share events."""
        data = await db_manager.get_gamification()
        last_date = data.get("last_active_date")
        today = date.today().isoformat()

        if last_date == today:
            return {"events": []}

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last_date == yesterday:
            state.current_streak += 1
        else:
            state.current_streak = 1  # Reset streak

        state.best_streak = max(state.best_streak, state.current_streak)

        # Streak XP bonus
        if state.current_streak > 0:
            state.xp_total += XP_REWARDS.get("daily_streak", 15)
            state.level = self._calculate_level(state.xp_total)

        await self._save()

        events = []
        # Streak milestones — shareable at 3, 7, 14, 30, 60, 100
        streak_milestones = [3, 7, 14, 30, 60, 100]
        if state.current_streak in streak_milestones:
            events.append(
                {
                    "type": "streak",
                    "data": {
                        "streak": state.current_streak,
                        "name": state.user_name,
                    },
                }
            )

        return {"events": events}

    async def check_badge(self, badge_id: str) -> dict | None:
        """Award a badge if not already earned. Returns badge share data if newly awarded."""
        data = await db_manager.get_gamification()
        badges = json.loads(data.get("badges_json", "[]"))

        if badge_id in badges:
            return None  # Already have it

        badges.append(badge_id)
        await db_manager.update_gamification(
            state.xp_total,
            state.level,
            state.current_streak,
            state.best_streak,
            badges,
        )

        # Return share-ready badge data
        badge_def = BADGE_DEFINITIONS.get(badge_id, {})
        return {
            "type": "badge",
            "data": {
                "badge_name": badge_def.get("name", badge_id),
                "badge_icon": badge_def.get("icon", "🏅"),
                "badge_desc": badge_def.get("desc", ""),
                "name": state.user_name,
            },
        }

    async def get_badges(self) -> list[dict]:
        """Get all earned badges with metadata."""
        data = await db_manager.get_gamification()
        earned_ids = json.loads(data.get("badges_json", "[]"))
        result = []
        for bid, info in BADGE_DEFINITIONS.items():
            result.append({**info, "id": bid, "earned": bid in earned_ids})
        return result

    def _calculate_level(self, xp: int) -> str:
        """Determine level from XP total."""
        current_level = LEVELS[0]["name"]
        for lvl in LEVELS:
            if xp >= lvl["xp"]:
                current_level = lvl["name"]
        return current_level

    async def _save(self):
        """Persist current state to DB."""
        data = await db_manager.get_gamification()
        badges = json.loads(data.get("badges_json", "[]"))
        await db_manager.update_gamification(
            state.xp_total,
            state.level,
            state.current_streak,
            state.best_streak,
            badges,
        )


gamification_service = GamificationService()
