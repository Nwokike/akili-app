"""OS notifications tests — Android gating, service wiring, scheduling.

The real flet-android-notifications package is never imported in tests
(desktop CI); the service is faked at the module boundary.
"""

import sys
import types
from datetime import date, timedelta

import pytest

from services import os_notifications


class _Plat:
    """Stands in for ft.PagePlatform — equality by enum value."""

    def __init__(self, name):
        self._name = name

    def __eq__(self, other):
        # Real PagePlatform members compare by their string value.
        return self._name == getattr(other, "value", other)

    def __hash__(self):
        return hash(self._name)


class _Page:
    def __init__(self, web=False, platform_name="android"):
        self.web = web
        self.platform = _Plat(platform_name)
        self.services = []


@pytest.fixture(autouse=True)
def _reset_service():
    os_notifications._service = None
    os_notifications._tap_handler = None
    yield
    os_notifications._service = None
    os_notifications._tap_handler = None


class _FakeService:
    def __init__(self, on_notification_tap=None):
        self.tap = on_notification_tap
        self.shown = []
        self.scheduled = []
        self.cancelled = []
        self.channels = []
        self.permission_granted = True
        self.exact_ok = True
        self.cancelled_all = False

    async def are_notifications_enabled(self):
        return self.permission_granted

    async def request_permissions(self):
        return self.permission_granted

    async def can_schedule_exact_notifications(self):
        return self.exact_ok

    async def request_exact_alarm_permission(self):
        self.exact_ok = True

    async def create_notification_channel(self, channel_id, channel_name, channel_description=None, importance="default"):
        self.channels.append((channel_id, channel_name, channel_description, importance))

    async def show_notification(self, notification_id, title, body, channel_id="", payload=None):
        self.shown.append((notification_id, title, body, channel_id, payload))

    async def schedule_notification(self, notification_id, title, body, when, channel_id="", payload=None, schedule_mode="inexact_allow_while_idle"):
        self.scheduled.append((notification_id, title, body, when, channel_id, payload, schedule_mode))

    async def cancel(self, notification_id):
        self.cancelled.append(notification_id)

    async def cancel_all(self):
        self.cancelled_all = True

    async def periodically_show(self, notification_id, title, body, repeat_interval, channel_id="", payload=None):
        self.scheduled.append((notification_id, title, body, repeat_interval, channel_id, payload))


def _install_fake_service(monkeypatch):
    fake = _FakeService()
    monkeypatch.setattr(os_notifications, "_service", fake)
    return fake


# ── Platform gating ────────────────────────────────────────────────


def test_is_android_true_on_android():
    assert os_notifications.is_android(_Page(False, "android")) is True
    assert os_notifications.is_android(_Page(False, "android_tv")) is True


def test_is_android_false_elsewhere():
    assert os_notifications.is_android(_Page(True, "android")) is False  # web
    assert os_notifications.is_android(_Page(False, "windows")) is False
    assert os_notifications.is_android(_Page(False, "macos")) is False
    assert os_notifications.is_android(_Page(False, "ios")) is False
    assert os_notifications.is_android(None) is False


# ── No-service safety (desktop/web/test) ────────────────────────────


@pytest.mark.asyncio
async def test_show_without_service_is_false():
    assert await os_notifications.show("t", "b") is False


@pytest.mark.asyncio
async def test_schedule_overdue_without_service_is_false():
    assert await os_notifications.schedule_overdue(1, "T", "2999-01-01") is False


@pytest.mark.asyncio
async def test_cancel_overdue_without_service_is_quiet():
    await os_notifications.cancel_overdue(1)  # must not raise


@pytest.mark.asyncio
async def test_daily_nudge_without_service_is_quiet():
    await os_notifications.daily_nudge(True)  # must not raise


@pytest.mark.asyncio
async def test_reschedule_pending_without_service_is_zero():
    class _Ctrl:
        course_store = None

    assert await os_notifications.reschedule_pending(_Ctrl()) == 0


# ── Service-present behaviour ───────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_ready_creates_channel(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    assert await os_notifications.ensure_ready() is True
    assert fake.channels and fake.channels[0][0] == os_notifications.CHANNEL_ID
    # channel_description= (not description=) and high prominence.
    assert fake.channels[0][2] == os_notifications.CHANNEL_DESC
    assert fake.channels[0][3] == "high"


@pytest.mark.asyncio
async def test_ensure_ready_denied_permission(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.permission_granted = False
    assert await os_notifications.ensure_ready() is False


@pytest.mark.asyncio
async def test_show_fires_notification(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    assert await os_notifications.show("Akili reminder", "⚠️ Overdue: T", notification_id=2) is True
    assert fake.shown[0][0] == 2
    assert "Overdue" in fake.shown[0][1] or "Overdue" in fake.shown[0][2]


@pytest.mark.asyncio
async def test_overdue_id_stable():
    assert os_notifications.overdue_id(7) == os_notifications.overdue_id(7)
    assert os_notifications.overdue_id(7) != os_notifications.overdue_id(8)


@pytest.mark.asyncio
async def test_schedule_overdue_future_date(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    due = (date.today() + timedelta(days=3)).isoformat()
    assert await os_notifications.schedule_overdue(5, "Photosynthesis", due) is True
    assert fake.scheduled[0][0] == os_notifications.overdue_id(5)
    assert "Photosynthesis" in fake.scheduled[0][1] or "Photosynthesis" in fake.scheduled[0][2]
    assert fake.scheduled[0][5] == "assignment:5"
    # Exact alarm permitted -> exact mode (a due-today nudge must not drift in Doze).
    assert fake.scheduled[0][6] == "exact_allow_while_idle"


@pytest.mark.asyncio
async def test_schedule_overdue_inexact_when_exact_denied(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    fake.exact_ok = False
    due = (date.today() + timedelta(days=3)).isoformat()
    assert await os_notifications.schedule_overdue(5, "T", due) is True
    assert fake.scheduled[0][6] == "inexact_allow_while_idle"


@pytest.mark.asyncio
async def test_schedule_overdue_none_id_refuses(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    assert await os_notifications.schedule_overdue(None, "T", "2999-01-01") is False
    assert fake.scheduled == []


@pytest.mark.asyncio
async def test_show_empty_payload_is_string(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    assert await os_notifications.show("t", "b") is True
    assert fake.shown[0][4] == ""  # payload: str, never None


@pytest.mark.asyncio
async def test_cancel_all(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    await os_notifications.cancel_all()
    assert fake.cancelled_all is True


@pytest.mark.asyncio
async def test_schedule_overdue_past_date_refuses(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    past = (date.today() - timedelta(days=1)).isoformat()
    assert await os_notifications.schedule_overdue(5, "T", past) is False
    assert fake.scheduled == []


@pytest.mark.asyncio
async def test_cancel_overdue_cancels(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    await os_notifications.cancel_overdue(9)
    assert fake.cancelled == [os_notifications.overdue_id(9)]


@pytest.mark.asyncio
async def test_daily_nudge_schedules_and_cancels(monkeypatch):
    fake = _install_fake_service(monkeypatch)
    await os_notifications.daily_nudge(True)
    assert fake.scheduled and fake.scheduled[0][0] == os_notifications._ID_STREAK
    await os_notifications.daily_nudge(False)
    assert os_notifications._ID_STREAK in fake.cancelled


@pytest.mark.asyncio
async def test_reschedule_pending_schedules_due_alarms(monkeypatch):
    from services.course_store import CourseStore
    from tests.conftest import FakeStorage

    fake = _install_fake_service(monkeypatch)
    mem = FakeStorage()
    store = CourseStore(storage=mem)
    await store.initialize()
    cid = await store.add_course("Bio", "SSS 2", {"modules": []})
    mid = await store.add_module(cid, "A", [], 0, unlocked=True)
    await store.create_assignment(mid, cid, "Due soon", "D", [])

    class _Ctrl:
        course_store = store

    assert await os_notifications.reschedule_pending(_Ctrl()) == 1
    assert fake.scheduled and fake.scheduled[0][0] == os_notifications.overdue_id(1)


# ── init_os_notifications ───────────────────────────────────────────


def test_init_skips_non_android(monkeypatch):
    monkeypatch.setattr(os_notifications, "is_android", lambda page=None: False)
    assert os_notifications.init_os_notifications(_Page(False, "android")) is None
    assert os_notifications.service() is None


def test_init_creates_service_on_android(monkeypatch):
    fake_mod = types.ModuleType("flet_android_notifications")

    class _Svc:
        def __init__(self, on_notification_tap=None):
            self.tap = on_notification_tap

    fake_mod.FletAndroidNotifications = _Svc
    monkeypatch.setitem(sys.modules, "flet_android_notifications", fake_mod)
    monkeypatch.setattr(os_notifications, "is_android", lambda page=None: True)

    page = _Page(False, "android")
    svc = os_notifications.init_os_notifications(page, on_tap=lambda p: None)
    assert svc is not None
    assert svc in page.services
    assert os_notifications.service() is svc
    # Second call is idempotent.
    assert os_notifications.init_os_notifications(page) is svc


def test_init_survives_import_failure(monkeypatch):
    monkeypatch.setattr(os_notifications, "is_android", lambda page=None: True)
    monkeypatch.setitem(sys.modules, "flet_android_notifications", None)  # import raises
    assert os_notifications.init_os_notifications(_Page(False, "android")) is None


# ── Tap payload parsing ─────────────────────────────────────────────


def test_parse_tap_payload_plain_string():
    assert os_notifications.parse_tap_payload("assignment:12") == "assignment:12"


def test_parse_tap_payload_json_envelope():
    # The package documents a JSON-string envelope for action taps.
    env = '{"notification_id": 10012, "payload": "assignment:12", "action_id": "", "input": "", "response_type": "default"}'
    assert os_notifications.parse_tap_payload(env) == "assignment:12"


def test_parse_tap_payload_dict():
    assert os_notifications.parse_tap_payload({"payload": "streak"}) == "streak"


def test_parse_tap_payload_empty():
    assert os_notifications.parse_tap_payload("") == ""
    assert os_notifications.parse_tap_payload(None) == ""


# ── Cold-start routing (controller wiring) ──────────────────────────


@pytest.mark.asyncio
async def test_init_notifications_routes_cold_start_tap(monkeypatch):
    """A killed app launched by a due-alarm tap opens the assignment."""
    from app_controller import AppController
    from core.state import state
    from tests.conftest import FakePage

    monkeypatch.setattr(os_notifications, "is_android", lambda page=None: True)
    monkeypatch.setattr(os_notifications, "init_os_notifications", lambda page, on_tap=None: _FakeService(on_tap))

    fake = _FakeService()
    monkeypatch.setattr(os_notifications, "_service", fake)

    async def _launch_details():
        return {
            "did_notification_launch_app": True,
            "notification_response": {"payload": "assignment:7", "notification_id": 10007},
        }

    fake.get_notification_app_launch_details = _launch_details

    ctrl = AppController(FakePage())
    navigated = []
    ctrl.show_assignment = lambda aid: navigated.append(aid)
    state.current_assignment_id = None

    await ctrl._init_notifications()

    assert navigated == [7]
    assert state.current_assignment_id == 7
    # Boot re-scheduling + daily nudge ran too.
    assert fake.scheduled  # daily nudge scheduled


@pytest.mark.asyncio
async def test_init_notifications_no_cold_start(monkeypatch):
    from app_controller import AppController
    from core.state import state
    from tests.conftest import FakePage

    monkeypatch.setattr(os_notifications, "is_android", lambda page=None: True)
    monkeypatch.setattr(os_notifications, "init_os_notifications", lambda page, on_tap=None: _FakeService(on_tap))

    fake = _FakeService()
    monkeypatch.setattr(os_notifications, "_service", fake)

    async def _launch_details():
        return {"did_notification_launch_app": False, "notification_response": None}

    fake.get_notification_app_launch_details = _launch_details

    ctrl = AppController(FakePage())
    navigated = []
    ctrl.show_assignment = lambda aid: navigated.append(aid)
    state.current_assignment_id = None

    await ctrl._init_notifications()

    assert navigated == []  # no routing when the app was not launched by a tap
    assert state.current_assignment_id is None
