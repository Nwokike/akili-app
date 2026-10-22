"""Debounce hook — delays value propagation until changes stop.

Ported from Sherlock's use_debounce pattern (the house standard).
"""

from __future__ import annotations

import flet as ft


def use_debounce(value, delay_ms: int = 250):
    """Returns a debounced value that updates after delay_ms of no changes.

    Usage:
        debounced, set_debounced = use_debounce("", 250)
        # set_debounced(newValue) schedules an update after delay_ms
    """
    debounced, set_debounced = ft.use_state(value)

    def _schedule(new_value):
        import asyncio

        async def _apply():
            await asyncio.sleep(delay_ms / 1000)
            set_debounced(new_value)

        try:
            import flet as _ft

            page = _ft.context.page
            page.run_task(_apply)
        except Exception:
            pass

    return debounced, _schedule
