"""Context exposing AppController callbacks to the component tree.

AppShell is rendered via page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))
so AppController cannot pass callbacks into AppShell's constructor.
Instead, AppController builds a mutable ControllerMethods dataclass with
its actual methods, then AppShell injects view-local closures (go_home,
back, etc.) by mutating the same instance.  Components read callbacks
via use_context(ControllerMethodsCtx).

Defaults are no-ops so the shell renders safely even before the provider
is mounted (e.g. inside unit tests that instantiate AppShell directly).

Ported from Sherlock's controller bridge (the house standard).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import flet as ft


async def _noop_async() -> None:
    """No-op async default."""


def _noop_sync() -> None:
    """No-op sync default."""


def _noop_dialog(_dialog) -> None:
    """No-op open_sheet(dialog) default (use_dialog portal)."""


@dataclass
class ControllerMethods:
    """Subset of AppController methods exposed to the component tree.

    Mutable (not frozen) so AppController can build it incrementally.
    AppShell further mutates it with view-local closures (go_home,
    back, etc.) during its render.
    """

    # AppController-populated (heavy, async)
    check_for_updates: Callable[[], Awaitable[None]] = _noop_async
    open_update_dialog: Callable[[], None] = _noop_sync
    set_onboarding_done: Callable[[], Awaitable[None]] = _noop_async
    save_profile: Callable[[str, str, str], Awaitable[None]] = lambda _n, _l, _c: _noop_async()
    factory_reset: Callable[[], Awaitable[None]] = _noop_async
    show_snack: Callable[[str, str], None] = lambda _msg, _level: None

    # Content (courses / modules / lessons)
    load_courses: Callable[[], Awaitable[list]] = _noop_async
    load_modules: Callable[[int], Awaitable[list]] = lambda _cid: _noop_async()
    create_course: Callable[[str, str, dict, int], Awaitable[dict]] = lambda _s, _l, _cur, _ci: _noop_async()
    delete_course: Callable[[int], Awaitable[None]] = lambda _cid: _noop_async()
    save_lesson_cache: Callable[[int, str], Awaitable[None]] = lambda _mid, _c: _noop_async()

    # Assessments
    load_attempts: Callable[[int | None], Awaitable[list]] = lambda _mid: _noop_async()
    complete_quiz_pass: Callable[[int, int], Awaitable[None]] = lambda _mid, _cid: _noop_async()
    open_assignment: Callable[[int], Awaitable[None]] = lambda _aid: _noop_async()

    # Settings persistence (DDGS save bridge)
    save: Callable[[str, object], None] = lambda _k, _v: None
    save_setting: Callable[[str, object], Awaitable[None]] = lambda _k, _v: _noop_async()

    # Engagement (timetable / parent / share triggers)
    load_timetable: Callable[[], Awaitable[list]] = _noop_async
    save_timetable_entry: Callable[[int | None, str, str, str, str], Awaitable[dict | None]] = lambda _eid, _d, _t, _s, _n: _noop_async()
    delete_timetable_entry: Callable[[int], Awaitable[None]] = lambda _eid: _noop_async()
    get_parent_overview: Callable[[], Awaitable[dict]] = _noop_async
    check_earn_conditions: Callable[[], Awaitable[list]] = _noop_async

    # AppShell-populated (view-local, sync closures)
    go_home: Callable[[], None] = _noop_sync
    back: Callable[[], None] = _noop_sync
    navigate_tab: Callable[[int], None] = lambda _idx: None
    open_tutor: Callable[[], None] = _noop_sync
    show_create_course: Callable[[], None] = _noop_sync
    show_course: Callable[[dict], None] = lambda _c: None
    show_lesson: Callable[[dict, dict], None] = lambda _c, _m: None
    show_quiz: Callable[[dict, dict], None] = lambda _c, _m: None
    show_exam: Callable[[dict], None] = lambda _c: None
    show_assignment: Callable[[int], None] = lambda _aid: None
    show_history: Callable[[], None] = _noop_sync
    show_timetable: Callable[[], None] = _noop_sync
    show_parent_portal: Callable[[], None] = _noop_sync
    open_sheet: Callable[[object], None] = _noop_dialog
    close_dialog: Callable[[], None] = _noop_sync
    handle_system_back: Callable[[], None] = _noop_sync


ControllerMethodsCtx = ft.create_context(ControllerMethods())

__all__ = ["ControllerMethods", "ControllerMethodsCtx"]
