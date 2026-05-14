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
}


class GamificationService:
    async def load_state(self):
        """Load gamification data from DB into app state."""
        data = await db_manager.get_gamification()
        state.xp_total = data["xp_total"]
        state.level = data["level"]
        state.current_streak = data["current_streak"]
        state.best_streak = data["best_streak"]

    async def award_xp(self, action: str) -> int:
        """Award XP for an action. Returns XP gained."""
        xp_gain = XP_REWARDS.get(action, 0)
        if xp_gain == 0:
            return 0

        state.xp_total += xp_gain
        new_level = self._calculate_level(state.xp_total)
        state.level = new_level

        await self._save()
        return xp_gain

    async def update_streak(self):
        """Update daily streak. Call once per session."""
        data = await db_manager.get_gamification()
        last_date = data.get("last_active_date")
        today = date.today().isoformat()

        if last_date == today:
            return  # Already counted today

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

    async def check_badge(self, badge_id: str) -> bool:
        """Award a badge if not already earned. Returns True if newly awarded."""
        data = await db_manager.get_gamification()
        badges = json.loads(data.get("badges_json", "[]"))

        if badge_id in badges:
            return False  # Already have it

        badges.append(badge_id)
        await db_manager.update_gamification(
            state.xp_total,
            state.level,
            state.current_streak,
            state.best_streak,
            badges,
        )
        return True

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
