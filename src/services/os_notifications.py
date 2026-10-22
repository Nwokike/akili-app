"""OS notifications — real Android delivery via flet-android-notifications.

The reminders service owns the *what* (overdue assignments, credit notes)
and the *when* (15-minute sweeps, foreground). This module owns the *how*:
showing and scheduling Android notifications that fire even when the app
is asleep or closed.

Android-only by design. The import stays inside a lazy factory so desktop
and web never touch the package (it imports fine there but has no
platform channel). Every public function is safe to call anywhere — on
non-Android it logs and returns.

Verified against the package source (flet-android-notifications 0.11.2):
- No init() step and no data= constructor param — construction +
  page.services.append is the whole registration.
- create_notification_channel takes channel_description= (NOT
  description=); channel importance/sound freeze at creation, so the
  channel is created with the prominence we actually want.
- show/schedule/periodically_show take channel_id= and payload= (str,
  default ""); periodically_show's repeat_interval is a plain string
  ("daily") — there is no RepeatInterval enum in the package.
- schedule_notification's schedule_mode defaults to inexact; exact modes
  need can_schedule_exact_notifications()/request_exact_alarm_permission().
- Taps arrive as on_notification_tap with e.data holding the payload
  (plain string) or a JSON envelope {notification_id, payload, action_id,
  input, response_type}. A killed app launched by a tap is detectable via
  get_notification_app_launch_details() — the controller routes it.
- notification_id=0 is only forbidden for foreground services; our IDs
  (1, 2, 3, 10000+) never collide with that constraint.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime

logger = logging.getLogger("OsNotifications")

CHANNEL_ID = "akili_reminders"
CHANNEL_NAME = "Study reminders"
CHANNEL_DESC = "Assignment due dates and daily study nudges"

_ID_SWEEP = 3  # immediate reminder-sweep notifications (distinct from the periodic nudge)
_ID_STREAK = 2  # daily study nudge (periodically_show)
_ID_OVERDUE_BASE = 10_000  # overdue:<aid> -> base + aid (stable across reschedules)

_service = None
_tap_handler = None


def is_android(page=None) -> bool:
    """True only on a real Android runtime (never desktop/web/test fakes)."""
    try:
        import flet as ft
        from flet import context as _ctx

        live = page or _ctx.page
        if live is None or getattr(live, "web", False):
            return False
        return live.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.ANDROID_TV)
    except Exception:
        return False


def service():
    """The shared FletAndroidNotifications instance (None off Android)."""
    return _service


def init_os_notifications(page, on_tap=None):
    """Create the service once (Android only). Safe to call anywhere.

    Re-entry guard: the first caller wins — a later call with a different
    on_tap keeps the original handler (single caller at boot today).
    """
    global _service, _tap_handler
    if _service is not None:
        return _service
    if not is_android(page):
        logger.debug("OS notifications: not Android, skipping")
        return None
    try:
        from flet_android_notifications import FletAndroidNotifications

        _tap_handler = on_tap

        def _tap(e=None):
            handler = _tap_handler
            if handler is None:
                return
            try:
                payload = parse_tap_payload(getattr(e, "data", None))
                page.run_task(_invoke_tap, handler, payload)
            except Exception:
                logger.debug("notification tap routing failed", exc_info=True)

        _service = FletAndroidNotifications(on_notification_tap=_tap)
        page.services.append(_service)
        logger.info("OS notifications service initialised")
    except Exception as exc:
        logger.warning("OS notifications unavailable: %s", exc)
        _service = None
    return _service


def parse_tap_payload(data) -> str:
    """Extract the payload string from an on_notification_tap event.

    The package documents two shapes: the plain payload string, or a JSON
    envelope {"notification_id", "payload", "action_id", "input",
    "response_type"} (action_id is "" for body taps).
    """
    if isinstance(data, dict):
        return str(data.get("payload") or "")
    if isinstance(data, str):
        text = data.strip()
        if text.startswith("{"):
            try:
                return str(json.loads(text).get("payload") or "")
            except Exception:
                return text
        return text
    if data:
        return str(data)
    return ""


async def _invoke_tap(handler, payload: str) -> None:
    try:
        result = handler(payload)
        if hasattr(result, "__await__"):
            await result
    except Exception:
        logger.debug("notification tap handler failed", exc_info=True)


async def ensure_ready(page=None) -> bool:
    """Request permission + create the channel. Returns True if showable."""
    svc = _service
    if svc is None:
        return False
    try:
        if not await svc.are_notifications_enabled():
            granted = await svc.request_permissions()
            if not granted:
                logger.info("OS notifications: permission denied")
                return False
        # Channel importance freezes at creation — due-date nudges want
        # heads-up prominence, so create it high (per-call importance on
        # show/schedule cannot override an existing channel).
        await svc.create_notification_channel(CHANNEL_ID, CHANNEL_NAME, channel_description=CHANNEL_DESC, importance="high")
        return True
    except Exception as exc:
        logger.warning("OS notifications setup failed: %s", exc)
        return False


async def show(title: str, body: str, notification_id: int = _ID_SWEEP, payload: str = "") -> bool:
    """Fire an immediate notification. False when unavailable/denied."""
    svc = _service
    if svc is None:
        return False
    try:
        await svc.show_notification(
            notification_id,
            title,
            body,
            channel_id=CHANNEL_ID,
            payload=payload or "",
        )
        return True
    except Exception as exc:
        logger.debug("show_notification failed: %s", exc)
        return False


def overdue_id(assignment_id: int) -> int:
    try:
        return _ID_OVERDUE_BASE + int(assignment_id)
    except (TypeError, ValueError):
        return _ID_OVERDUE_BASE


async def schedule_overdue(assignment_id: int, title: str, due_label: str) -> bool:
    """Schedule a one-shot due-date nudge. Returns False off Android."""
    svc = _service
    if svc is None or assignment_id is None:
        return False
    try:
        can_exact = await svc.can_schedule_exact_notifications()
        if not can_exact:
            await svc.request_exact_alarm_permission()
        # Fire at 08:00 local on the due date (morning nudge). Past dates
        # raise in AlarmManager, so guard here.
        from datetime import date as _date

        due = _date.fromisoformat(due_label) if len(due_label) == 10 else None
        if due is None or due < _date.today():
            return False
        when = datetime(due.year, due.month, due.day, 8, 0)
        # Exact when permitted (a "due today" nudge should not drift hours
        # in Doze), inexact otherwise. Naive datetime -> host-local instant.
        await svc.schedule_notification(
            overdue_id(assignment_id),
            "Assignment due today",
            f"{title} — due today. Open Akili to submit.",
            when,
            channel_id=CHANNEL_ID,
            payload=f"assignment:{assignment_id}",
            schedule_mode="exact_allow_while_idle" if can_exact else "inexact_allow_while_idle",
        )
        return True
    except Exception as exc:
        logger.debug("schedule_overdue failed: %s", exc)
        return False


async def cancel_overdue(assignment_id: int) -> None:
    svc = _service
    if svc is None or assignment_id is None:
        return
    with contextlib.suppress(Exception):
        await svc.cancel(overdue_id(assignment_id))


async def cancel_all() -> None:
    """Drop every scheduled/periodic notification (factory reset)."""
    svc = _service
    if svc is None:
        return
    with contextlib.suppress(Exception):
        await svc.cancel_all()


async def daily_nudge(enable: bool) -> None:
    """A daily study nudge (periodically_show, daily repeat).

    periodically_show has no start-time parameter — the first fire is at
    enable time, then every 24h from that anchor. (A fixed 19:00 local
    fire would need schedule_notification with match_date_time_components
    + an IANA time_zone; not worth a timezone dependency for a nudge.)
    """
    svc = _service
    if svc is None:
        return
    try:
        if enable:
            await svc.periodically_show(
                _ID_STREAK,
                "Keep the streak alive 📚",
                "A few minutes of study today keeps your streak going.",
                "daily",
                channel_id=CHANNEL_ID,
                payload="streak",
            )
        else:
            await svc.cancel(_ID_STREAK)
    except Exception as exc:
        logger.debug("daily_nudge failed: %s", exc)


async def reschedule_pending(controller) -> int:
    """Re-schedule due reminders for pending assignments after reboot.

    Called from the boot sweep on Android: AlarmManager schedules die on
    reboot, and RECEIVE_BOOT_COMPLETED lets our boot run again.
    """
    count = 0
    try:
        store = getattr(controller, "course_store", None)
        if store is None:
            return 0
        for assignment in await store.get_pending_assignments():
            due = str(assignment.get("due_date") or "")
            if not due:
                continue
            if await schedule_overdue(assignment.get("id"), assignment.get("title") or "Assignment", due):
                count += 1
    except Exception as exc:
        logger.debug("reschedule_pending failed: %s", exc)
    return count
