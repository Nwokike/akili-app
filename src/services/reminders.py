"""Reminder scheduler — foreground nudges for due work.

While the app is open, a 15-minute loop checks for newly-overdue
assignments and day-boundary credit resets, then surfaces a snackbar.
Surfaced keys ({assignment_id, date}) persist in storage so a resume
never re-spams. On Android the same sweep also fires an OS notification
(services.os_notifications), and assignment creation schedules a due-date
alarm that fires even when the app is closed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import date

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 15 * 60
STORAGE_SURFACED = "akili_reminders_surfaced"


async def _surfaced(storage) -> dict:
    if storage is None:
        return {}
    try:
        raw = await storage.get(STORAGE_SURFACED, "{}")
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def _mark_surfaced(storage, key: str) -> None:
    if storage is None:
        return
    try:
        seen = await _surfaced(storage)
        seen[key] = date.today().isoformat()
        # Cap the blob: drop oldest beyond 200 entries.
        if len(seen) > 200:
            seen = dict(list(seen.items())[-200:])
        await storage.set(STORAGE_SURFACED, json.dumps(seen))
    except Exception as exc:
        logger.debug("reminder mark failed: %s", exc)


async def check_once(controller) -> list[str]:
    """One sweep. Returns the messages surfaced (for tests/notifiers)."""
    surfaced_messages: list[str] = []
    try:
        store = getattr(controller, "course_store", None)
        storage = getattr(controller, "storage", None)
        if store is None:
            return surfaced_messages
        seen = await _surfaced(storage)
        today = date.today().isoformat()

        pending = await store.get_pending_assignments()
        for assignment in pending:
            aid = assignment.get("id")
            due = str(assignment.get("due_date") or "")
            if not due or due > today:
                continue  # not yet due
            key = f"overdue:{aid}:{due}"
            if key in seen:
                continue
            title = assignment.get("title") or "Assignment"
            message = f"⚠️ Overdue: {title} (was due {due})"
            surfaced_messages.append(message)
            await _mark_surfaced(storage, key)

        # Day-boundary credit note: if the stored reset date rolled while
        # open, the lazy reset already refilled — just mention it once.
        reset_key = f"credits:{today}"
        if reset_key not in seen:
            try:
                from core.constants import STORAGE_LAST_RESET

                last = await storage.get(STORAGE_LAST_RESET, "") if storage else ""
                if last == today:
                    await _mark_surfaced(storage, reset_key)
            except Exception:
                pass
    except Exception as exc:
        logger.debug("reminder sweep failed: %s", exc)
    return surfaced_messages


async def reminder_loop(controller, show) -> None:
    """15-minute foreground loop. `show(message)` surfaces each nudge."""
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_SEC)
        except asyncio.CancelledError:
            raise
        try:
            for message in await check_once(controller):
                with contextlib.suppress(Exception):
                    await show(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("reminder loop tick failed: %s", exc)
