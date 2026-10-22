"""AppShell — single-view shell with tab navigation.

Ported from Sherlock's AppShell pattern (the house standard).

page.render() mounts this component into views[0].controls, so it returns
CONTENT (a SafeArea), not a View. App bar / navigation bar / FAB chrome is
attached imperatively to page.views[0] from a use_effect.

No page.views routing. Tab state + view state + dialog state.
System back maps to view→dashboard→tab→home.
"""

from __future__ import annotations

import logging

import flet as ft

from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger("AppShell")

_TAB_NAMES = ("Home", "Progress", "Settings")
_TAB_ICONS = (
    ft.Icons.HOME_ROUNDED,
    ft.Icons.LEADERBOARD_ROUNDED,
    ft.Icons.SETTINGS_ROUNDED,
)

# Views that own the whole screen (no nav bar, no FAB).
_FULLSCREEN_VIEWS = ("tutor", "create-course", "course", "lesson", "quiz", "exam", "assignment", "quiz-history", "timetable", "parent-portal")


@ft.component
def AppShell():
    """Single-view shell — branches between onboarding, dashboard, and content views."""
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    active_tab, set_active_tab = ft.use_state(0)
    active_view, set_active_view = ft.use_state("dashboard")
    active_dialog, set_active_dialog = ft.use_state(None)
    ft.use_dialog(active_dialog)

    # ── Navigation closures ──
    controller.go_home = lambda: (set_active_view("dashboard"), set_active_tab(0))
    controller.back = lambda: set_active_view("dashboard")
    controller.navigate_tab = lambda idx: (set_active_view("dashboard"), set_active_tab(idx))
    controller.open_tutor = lambda: set_active_view("tutor")
    controller.show_create_course = lambda: set_active_view("create-course")
    controller.show_course = lambda _c: set_active_view("course")
    controller.show_lesson = lambda _c, _m: set_active_view("lesson")
    controller.show_quiz = lambda _c, _m: set_active_view("quiz")
    controller.show_exam = lambda _c: set_active_view("exam")
    controller.show_assignment = lambda _aid: set_active_view("assignment")
    controller.show_history = lambda: set_active_view("quiz-history")
    controller.show_timetable = lambda: set_active_view("timetable")
    controller.show_parent_portal = lambda: set_active_view("parent-portal")
    controller.open_sheet = lambda d: set_active_dialog(d)
    controller.close_dialog = lambda: set_active_dialog(None)

    def _handle_system_back():
        if active_view == "lesson":
            set_active_view("course")
        elif active_view in ("quiz", "exam"):
            set_active_view("lesson")
        elif active_view in ("course", "create-course") or active_view != "dashboard":
            set_active_view("dashboard")
        elif active_tab != 0:
            set_active_tab(0)

    controller.handle_system_back = _handle_system_back

    state.chat_open = active_view == "tutor"

    # ── Chrome sync (navigation bar + FAB live on views[0]) ──
    # Deliberate escape hatch for page-level chrome, exactly as DDGS does:
    # mutate views[0], then push with an explicit page.update(). Without the
    # update the mutation never reaches the client until the next
    # event-driven update — chrome silently missing on first frame.
    def _sync_chrome():
        try:
            page = ft.context.page
            if not page or not page.views:
                return
            view = page.views[0]
            if not state.is_onboarded or active_view in _FULLSCREEN_VIEWS:
                if view.navigation_bar is not None or view.floating_action_button is not None:
                    view.navigation_bar = None
                    view.floating_action_button = None
                    page.update()
                return
            view.navigation_bar = ft.NavigationBar(
                selected_index=active_tab,
                destinations=[ft.NavigationBarDestination(icon=icon, label=name) for icon, name in zip(_TAB_ICONS, _TAB_NAMES, strict=True)],
                on_change=lambda e: set_active_tab(e.control.selected_index),
                bgcolor=ft.Colors.SURFACE,
                indicator_color=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
            )
            if active_tab == 0:
                if view.floating_action_button is None:
                    view.floating_action_button = ft.FloatingActionButton(
                        icon=ft.Icons.CHAT_BUBBLE_ROUNDED,
                        bgcolor=ft.Colors.PRIMARY,
                        foreground_color=ft.Colors.WHITE,
                        mini=True,
                        tooltip="Ask the AI tutor",
                        on_click=lambda e: set_active_view("tutor"),
                    )
            elif view.floating_action_button is not None:
                view.floating_action_button = None
            page.update()
        except Exception:
            logger.exception("Chrome sync failed")

    ft.use_effect(
        _sync_chrome,
        [active_tab, active_view, state.is_onboarded, state.theme_mode],
    )

    # ── Body ──
    if not state.is_onboarded:
        from screens.onboarding_screen import OnboardingScreen

        return ft.SafeArea(OnboardingScreen(), expand=True)

    if active_view == "tutor":
        from screens.tutor_screen import TutorScreen

        return ft.SafeArea(TutorScreen(), expand=True)

    if active_view == "create-course":
        from screens.course_creation_screen import CourseCreationScreen

        return ft.SafeArea(CourseCreationScreen(), expand=True)

    if active_view == "course":
        from screens.course_detail_screen import CourseDetailScreen

        return ft.SafeArea(CourseDetailScreen(), expand=True)

    if active_view == "lesson":
        from screens.lesson_screen import LessonScreen

        return ft.SafeArea(LessonScreen(), expand=True)

    if active_view == "quiz":
        from screens.quiz_screen import QuizScreen

        return ft.SafeArea(QuizScreen(), expand=True)

    if active_view == "exam":
        from screens.exam_screen import ExamScreen

        return ft.SafeArea(ExamScreen(), expand=True)

    if active_view == "assignment":
        from screens.assignment_screen import AssignmentScreen

        return ft.SafeArea(AssignmentScreen(), expand=True)

    if active_view == "quiz-history":
        from screens.quiz_history_screen import QuizHistoryScreen

        return ft.SafeArea(QuizHistoryScreen(), expand=True)

    if active_view == "timetable":
        from screens.timetable_screen import TimetableScreen

        return ft.SafeArea(TimetableScreen(), expand=True)

    if active_view == "parent-portal":
        from screens.parent_portal_screen import ParentPortalScreen

        return ft.SafeArea(ParentPortalScreen(), expand=True)

    return ft.SafeArea(_dashboard_body(active_tab, controller), expand=True)


def _dashboard_body(active_tab: int, controller) -> ft.Control:
    """The dashboard tab content (header + body + banner)."""
    from components.app_header import AppHeader
    from components.banner_ad import build_banner_ad
    from components.credit_pill import build_credit_pill, build_wallet_dialog
    from components.notification_bell import NotificationBell
    from screens.dashboard_screen import DashboardScreen
    from screens.progress_screen import ProgressScreen
    from screens.settings_screen import SettingsScreen

    page = ft.context.page

    if active_tab == 0:
        body = DashboardScreen()
    elif active_tab == 1:
        body = ProgressScreen()
    else:
        body = SettingsScreen()

    return ft.Column(
        controls=[
            AppHeader(
                page,
                title="Akili",
                subtitle="After-School Learning App",
                show_settings=True,
                on_settings=lambda e: controller.navigate_tab(2),
                extra_actions=(
                    # v1 header order: credit pill, then notification bell —
                    # theme toggle + settings are appended inside AppHeader.
                    [build_credit_pill(on_click=lambda e: page.show_dialog(build_wallet_dialog(page))), NotificationBell()] if active_tab == 0 else None
                ),
            ),
            ft.Container(expand=True, content=body),
            build_banner_ad(page),
        ],
        spacing=0,
        expand=True,
    )
