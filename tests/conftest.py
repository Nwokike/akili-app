"""Test harness — FakePage stub and fixtures.

Ported from Sherlock's test pattern (the house standard).
Components are plain functions so tests call them directly and assert
via flet_tree walkers — no renderer needed.
"""

from __future__ import annotations

import flet as ft
import pytest


class FakePage:
    """Stub ft.Page for unit testing components without a renderer."""

    def __init__(self):
        self.title = ""
        self.padding = 0
        self.spacing = 0
        self.fonts: dict[str, str] = {}
        self.theme = None
        self.dark_theme = None
        self.theme_mode = ft.ThemeMode.SYSTEM
        self.route = "/"
        self.views: list = []
        self.services: list = []
        self.file_picker = None
        self.window = None
        self.web = False
        self.platform = ft.PagePlatform.ANDROID
        self.platform_brightness = ft.Brightness.LIGHT
        self.data = {}
        self._rendered = None
        self._dialogs: list = []
        self._tasks: list = []
        self._updates = 0

    def render(self, component, *args, **kwargs):
        self._rendered = component

    def render_views(self, component, *args, **kwargs):
        self._rendered = component

    def update(self):
        self._updates += 1

    def schedule_update(self):
        self._updates += 1

    def show_dialog(self, dialog):
        self._dialogs.append(dialog)

    def pop_dialog(self):
        if self._dialogs:
            return self._dialogs.pop()
        return None

    def push_route(self, route, **kwargs):
        self.route = route

    def pop_views_until(self, route, result=None):
        pass

    def run_task(self, coro_fn, *args, **kwargs):
        self._tasks.append((coro_fn, args, kwargs))

    def run_thread(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


@pytest.fixture
def fake_page():
    """Provide a fresh FakePage for each test."""
    return FakePage()


class FakeStorage:
    """In-memory storage stand-in for services."""

    def __init__(self, data: dict | None = None):
        self._data = dict(data or {})
        self.flushes = 0

    async def initialize(self) -> None:
        return None

    async def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value) -> None:
        self._data[key] = value

    async def remove(self, key) -> None:
        self._data.pop(key, None)

    async def flush(self) -> None:
        self.flushes += 1

    async def flush_now(self) -> None:
        await self.flush()

    async def clear_all(self) -> None:
        self._data.clear()

    # ── Typed accessors mirroring StorageService (DDGS pattern) ──

    async def get_theme(self) -> str:
        return str(self._data.get("theme", "system") or "system")

    async def set_theme(self, value: str) -> None:
        self._data["theme"] = value

    async def get_onboarding_done(self) -> bool:
        return self._data.get("onboarding_done") == "true"

    async def set_onboarding_done(self, value: bool) -> None:
        self._data["onboarding_done"] = "true" if value else "false"

    async def get_ai_model(self) -> str:
        return str(self._data.get("ai_model", "auto") or "auto")

    async def set_ai_model(self, value: str) -> None:
        self._data["ai_model"] = value or "auto"

    async def get_ai_mode(self) -> bool:
        return self._data.get("ai_mode_enabled", "true") != "false"

    async def set_ai_mode(self, value: bool) -> None:
        self._data["ai_mode_enabled"] = "true" if value else "false"

    async def get_reasoning_effort(self) -> str:
        return str(self._data.get("reasoning_effort", "auto") or "auto")

    async def set_reasoning_effort(self, value: str) -> None:
        self._data["reasoning_effort"] = value or "auto"

    async def get_biometric_lock(self) -> bool:
        return self._data.get("akili_biometric_lock", "true") != "false"

    async def set_biometric_lock(self, value: bool) -> None:
        self._data["akili_biometric_lock"] = "true" if value else "false"

    async def get_history(self) -> list:
        import json

        try:
            parsed = json.loads(self._data.get("search_history", "[]") or "[]")
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    async def set_history(self, value: list) -> None:
        import json

        self._data["search_history"] = json.dumps(value or [])


@pytest.fixture
def fake_storage():
    """Provide a fresh FakeStorage for each test."""
    return FakeStorage()
