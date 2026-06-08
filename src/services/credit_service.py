from datetime import date

from core.constants import CREDIT_COSTS, DAILY_CREDITS
from core.state import state
from database.manager import db_manager


def update_credit_displays():
    active_controls = []
    for control in getattr(state, "credit_text_controls", []):
        try:
            if "100" in getattr(control, "value", "") or "Today" in getattr(control, "value", ""):
                control.value = f"{state.credits_remaining} / 100 Today"
            else:
                control.value = f"{state.credits_remaining}"
            control.update()
            active_controls.append(control)
        except Exception:
            pass
    state.credit_text_controls = active_controls


class CreditService:
    async def refresh_credits(self, force: bool = False):
        """Check if day changed and reset credits. Load from DB."""
        today = date.today().isoformat()

        if force or state.credits_date != today:
            state.credits_date = today
            credits_used = await db_manager.get_credits_used_today()
            state.credits_remaining = max(0, DAILY_CREDITS - credits_used)
            update_credit_displays()
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
        update_credit_displays()
        return True

    def get_cost(self, action: str) -> int:
        """Get credit cost for an action."""
        return CREDIT_COSTS.get(action, 0)

    async def add_credits(self, amount: int) -> int:
        """Add credits dynamically (e.g. via rewarded ads)."""
        await self.refresh_credits()
        await db_manager.log_credit_usage(-amount, "rewarded_ad")
        state.credits_remaining += amount
        update_credit_displays()
        return state.credits_remaining


credit_service = CreditService()
