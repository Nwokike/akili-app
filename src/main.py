import flet as ft

from core.state import state
from core.theme import AppTheme
from database.manager import db_manager
from services.ad_service import AdService
from services.credit_service import credit_service
from services.gamification import gamification_service
from services.lifecycle import LifecycleManager


async def main(page: ft.Page):
    page.title = "Akili"

    def global_error_handler(e):
        page.snack_bar = ft.SnackBar(
            ft.Text("Something went wrong. Please try again."),
            bgcolor="#EF4444",
        )
        page.snack_bar.open = True
        page.update()

    page.on_error = global_error_handler

    page.fonts = {
        "Outfit": "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap"
    }
    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    state.theme_mode = page.theme_mode
    page.padding = 0
    page.spacing = 0

    ad_service = AdService(page)
    page.run_task(ad_service.preload_interstitial)
    _lifecycle = LifecycleManager(page)

    await db_manager.init_db()

    profile = await db_manager.get_profile()
    if profile:
        state.user_name = profile["name"]
        state.education_level = profile["education_level"]
        state.avatar_index = profile["avatar_index"]
        state.is_onboarded = True
    else:
        state.is_onboarded = False

    await credit_service.refresh_credits()
    await gamification_service.load_state()
    await gamification_service.update_streak()

    page.data = {"ad_service": ad_service}

    async def navigate(route: str):
        page.route = route
        await route_change()

    async def route_change(e=None):
        page.views.clear()

        if page.route in ("/splash", "/"):
            from views.splash import build_splash_view
            page.views.append(build_splash_view(page, navigate))

        elif page.route == "/onboarding":
            from views.onboarding import build_onboarding_view
            page.views.append(build_onboarding_view(page, navigate))

        elif page.route == "/dashboard":
            from views.dashboard import build_dashboard_view
            page.views.append(await build_dashboard_view(page, navigate))

        elif page.route == "/create-course":
            from views.course_creation import build_course_creation_view
            page.views.append(build_course_creation_view(page, navigate))

        elif page.route == "/modules":
            from views.course_detail import build_course_detail_view
            page.views.append(await build_course_detail_view(page, navigate))

        elif page.route == "/lesson":
            from views.lesson_view import build_lesson_view
            page.views.append(await build_lesson_view(page, navigate))

        elif page.route == "/quiz":
            from views.quiz_view import build_quiz_view
            page.views.append(build_quiz_view(page, navigate))

        elif page.route == "/exam":
            from views.mock_exam import build_mock_exam_view
            page.views.append(build_mock_exam_view(page, navigate))

        elif page.route == "/tutor":
            from views.tutor_chat import build_tutor_chat_view
            page.views.append(build_tutor_chat_view(page, navigate))

        elif page.route == "/progress":
            from views.progress_view import build_progress_view
            page.views.append(await build_progress_view(page, navigate))

        elif page.route == "/settings":
            from views.settings_view import build_settings_view
            page.views.append(build_settings_view(page, navigate))

        elif page.route == "/timetable":
            from views.timetable_view import build_timetable_view
            page.views.append(await build_timetable_view(page, navigate))

        page.update()

    async def view_pop(e):
        page.views.pop()
        if page.views:
            top = page.views[-1]
            page.route = top.route
        page.update()

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    await navigate("/splash")


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
