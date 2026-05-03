

from datetime import date

from core.constants import CREDIT_COSTS, DAILY_CREDITS
from core.state import state
from database.manager import db_manager


class CreditService:
    async def refresh_credits(self):
        """Check if day changed and reset credits. Load from DB."""
        today = date.today().isoformat()

        if state.credits_date != today:
            state.credits_date = today
            credits_used = await db_manager.get_credits_used_today()
            state.credits_remaining = max(0, DAILY_CREDITS - credits_used)
        return state.credits_remaining

    async def can_afford(self, action: str) -> bool:
        """Check if user has enough credits for action."""
        await self.refresh_credits()
        cost = CREDIT_COSTS.get(action, 0)
        return state.credits_remaining >= cost

    async def spend(self, action: str) -> bool:
        """Spend credits for an action. Returns True if successful."""
        cost = CREDIT_COSTS.get(action, 0)
        if cost == 0:
            return True  # Free actions always pass

        await self.refresh_credits()
        if state.credits_remaining < cost:
            return False

        await db_manager.log_credit_usage(cost, action)
        state.credits_remaining -= cost
        return True

    def get_cost(self, action: str) -> int:
        """Get credit cost for an action."""
        return CREDIT_COSTS.get(action, 0)


credit_service = CreditService()
