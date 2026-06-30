import logging

import flet as ft

from core.state import check_internet_connection, state
from core.theme import AppTheme
from database.manager import db_manager
from services.ad_service import AdService
from services.credit_service import credit_service
from services.gamification import gamification_service
from services.lifecycle import LifecycleManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main(page: ft.Page):
    page.title = "Akili — After-School Learning App"

    def global_error_handler(e):
        page.snack_bar = ft.SnackBar(
            ft.Text("something went wrong. please try again.", color=ft.Colors.WHITE),
            bgcolor=ft.Colors.BLACK,
        )
        page.snack_bar.open = True
        page.update()

    page.on_error = global_error_handler

    page.fonts = {"Outfit": "assets/outfit.css"}
    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.theme_mode = ft.ThemeMode.SYSTEM
    state.theme_mode = page.theme_mode
    page.padding = 0
    page.spacing = 0

    # --- Offline Mode Indicator ---
    def show_banner():
        page.banner.open = True
        page.update()

    def close_banner(e=None):
        page.banner.open = False
        page.update()

    offline_banner = ft.Banner(
        bgcolor=ft.Colors.BLACK,
        content=ft.Text("offline mode: progress is saved locally.", color=ft.Colors.WHITE),
        leading=ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.WHITE),
        actions=[ft.TextButton("dismiss", style=ft.ButtonStyle(color=ft.Colors.WHITE), on_click=close_banner)],
    )
    page.banner = offline_banner

    def on_online_change(is_online: bool):
        if not is_online and not page.banner.open:
            show_banner()
        elif is_online and page.banner.open:
            close_banner()

    state.add_online_listener(on_online_change)

    async def handle_connectivity_change(e: ft.ConnectivityChangeEvent):
        # 'none' indicates no network connection
        is_offline = any(r.value == "none" for r in e.connectivity)
        if is_offline:
            state.update_online_state(False)
        else:
            connected = await check_internet_connection()
            state.update_online_state(connected)

    # Initialize Connectivity (Service, not a Control — no need to add to page)
    connectivity = ft.Connectivity()
    connectivity.on_change = handle_connectivity_change

    # Perform initial active connectivity verification
    initial_connected = await check_internet_connection()
    state.update_online_state(initial_connected)

    # --- Service Initialization ---
    ad_service = AdService(page)
    page.run_task(ad_service.preload_interstitial)
    _lifecycle = LifecycleManager(page)

    await db_manager.init_db()

    # Update login timestamp for the daily notification bell
    await db_manager.update_login_timestamp()

    profile = await db_manager.get_profile()
    if profile:
        state.user_name = profile["name"]
        state.education_level = profile["education_level"]
        state.education_levels = profile.get("education_levels", [])
        state.avatar_index = profile["avatar_index"]
        state.country = profile.get("country", "")
        state.is_onboarded = True
    else:
        state.is_onboarded = False

    await credit_service.refresh_credits()
    await gamification_service.load_state()
    streak_result = await gamification_service.update_streak()

    # Auto-show share sheet on streak milestones
    if streak_result.get("events"):
        for ev in streak_result["events"]:
            if ev["type"] == "streak":
                from services.share_service import ShareType, show_share_sheet

                show_share_sheet(page, ShareType.STREAK, ev["data"])

    # Load AI Search Settings from DB
    state.search_region = await db_manager.get_setting("search_region", "wt-wt")
    state.safesearch_level = await db_manager.get_setting("safesearch_level", "on")

    page.data = {"ad_service": ad_service}

    async def navigate(route: str):
        page.route = route
        # route_change is triggered automatically via on_route_change

    async def route_change(e=None):
        # Preserve view stack when navigating to video player — pop back returns
        # to the correct prior view (tutor, lesson, etc.) instead of always /tutor.
        if not page.route.startswith("/video_player"):
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

        # --- New Routes ---
        elif page.route.startswith("/video_player"):
            from components.immersive_player import ImmersivePlayer

            video_url = page.data.get("playing_video_url") or ""
            video_title = page.data.get("playing_video_title") or "Educational Video"

            async def _close_player():
                if len(page.views) > 1:
                    page.views.pop()
                    top = page.views[-1]
                    page.route = top.route
                    page.update()
                else:
                    await navigate("/tutor")

            player = ImmersivePlayer(
                resource=video_url,
                title=video_title,
                on_close=_close_player,
                ad_service=ad_service,
            )
            page.views.append(
                ft.View(
                    route="/video_player",
                    controls=[player],
                    padding=0,
                )
            )
            page.run_task(player.start_playback)

        elif page.route == "/premium":
            from views.premium_preview import get_premium_preview_view

            page.views.append(get_premium_preview_view(page))

        elif page.route == "/history":
            from views.quiz_history import get_quiz_history_view

            page.views.append(await get_quiz_history_view(page))  # Added await

        elif page.route == "/parent":
            from views.parent_portal import get_parent_portal_view

            page.views.append(await get_parent_portal_view(page))  # Added await

        elif page.route == "/assignment":
            from views.assignment_view import build_assignment_view

            page.views.append(await build_assignment_view(page, navigate))

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
