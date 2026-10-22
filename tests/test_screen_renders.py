"""Screen render tests — mount every screen through the Flet Renderer.

Regression guard: the DashboardScreen Column(padding=) crash shipped
because no test ever instantiated a @ft.component screen. Constructor
TypeErrors (invalid kwargs like padding on Column) throw at build time,
so mounting each screen catches the whole class.

Pattern ported from Sherlock's test_screens_audit_polish.py.
"""

from __future__ import annotations

from flet.components.component import Component, Renderer

from core.state import state
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
from tests.conftest import FakePage


def _mount(comp_fn):
    """Render a screen component with live contexts, expanding the tree.

    Binds a FakePage into flet's page ContextVar so component bodies
    calling ft.context.page resolve (mirrors a live session).
    Returns the flattened control list. Any constructor TypeError inside
    the screen propagates — that is the assertion.
    """
    from flet.controls.context import _context_page

    from tests.flet_tree import walk as _walk  # noqa: F401 (documents traversal)

    methods = ControllerMethods()
    token = _context_page.set(FakePage())
    try:
        renderer = Renderer()
        root_comp = renderer.render(lambda: ControllerMethodsCtx(methods, lambda: AppStateCtx(state, comp_fn)))

        def expand(node):
            if isinstance(node, Component):
                node.before_update()
                if getattr(node, "_b", None) is not None:
                    yield from expand(node._b)
            elif isinstance(node, list):
                for item in node:
                    yield from expand(item)
            else:
                yield node
                for ch in getattr(node, "controls", None) or []:
                    yield from expand(ch)
                content = getattr(node, "content", None)
                if content is not None:
                    yield from expand(content)

        return list(expand(root_comp))
    finally:
        _context_page.reset(token)


def test_dashboard_renders():
    from screens.dashboard_screen import DashboardScreen

    nodes = _mount(DashboardScreen)
    assert len(nodes) > 0


def test_onboarding_renders():
    from screens.onboarding_screen import OnboardingScreen

    nodes = _mount(OnboardingScreen)
    assert len(nodes) > 0


def test_course_detail_renders():
    from screens.course_detail_screen import CourseDetailScreen

    state.current_course = {"id": 1, "subject": "Biology", "level": "SSS 2", "progress_pct": 0.0, "color_index": 0}
    state.modules = []
    try:
        nodes = _mount(CourseDetailScreen)
        assert len(nodes) > 0
    finally:
        state.current_course = None
        state.modules = []


def test_lesson_renders_cached():
    from screens.lesson_screen import LessonScreen

    state.current_course = {"id": 1, "subject": "Biology", "level": "SSS 2"}
    state.current_module = {"id": 1, "title": "Genetics", "lesson_cache": "# Hello\n\nBody text here."}
    try:
        nodes = _mount(LessonScreen)
        assert len(nodes) > 0
    finally:
        state.current_course = None
        state.current_module = None


def test_quiz_history_renders():
    from screens.quiz_history_screen import QuizHistoryScreen

    state.quiz_attempts = []
    try:
        nodes = _mount(QuizHistoryScreen)
        assert len(nodes) > 0
    finally:
        state.quiz_attempts = []


def test_progress_renders():
    from screens.progress_screen import ProgressScreen

    nodes = _mount(ProgressScreen)
    assert len(nodes) > 0


def test_timetable_renders():
    from screens.timetable_screen import TimetableScreen

    nodes = _mount(TimetableScreen)
    assert len(nodes) > 0


def test_parent_portal_renders_locked():
    from screens.parent_portal_screen import ParentPortalScreen

    nodes = _mount(ParentPortalScreen)
    assert len(nodes) > 0


def test_settings_sections_render():
    import flet as ft

    from components.settings.sections_ai import build_ai_section
    from components.settings.sections_general import build_appearance_section, build_learning_section
    from components.settings.sections_misc import (
        build_about_section,
        build_data_section,
        build_study_section,
        build_troubleshooting_section,
    )
    from components.settings.sections_premium import build_premium_section

    for builder in (
        build_appearance_section,
        build_learning_section,
        build_ai_section,
        build_premium_section,
        build_data_section,
        build_study_section,
        build_troubleshooting_section,
        build_about_section,
    ):
        nodes = _mount(lambda b=builder: b(ft.context.page))
        assert len(nodes) > 0, builder.__name__
