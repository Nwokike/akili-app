import flet as ft

from components.credit_dialog import show_credits_dialog
from components.notification_bell import NotificationBell
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.credit_service import credit_service


async def build_dashboard_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    courses = await db_manager.get_courses()

    credits_text = ft.Text(f"{state.credits_remaining}", size=12, weight=ft.FontWeight.W_600)
    if not hasattr(state, "credit_text_controls"):
        state.credit_text_controls = []
    state.credit_text_controls.append(credits_text)

    def _toggle_theme(e):
        page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        state.theme_mode = page.theme_mode
        page.update()

    has_unread = await db_manager.check_daily_reward_eligibility()
    pending_assignments = await db_manager.get_pending_assignments()
    notification_bell = NotificationBell(
        page,
        has_unread=has_unread,
        pending_assignments=len(pending_assignments),
        navigate=navigate,
    )
    notification_bell.set_assignments(pending_assignments)

    # ── Header ──────────────────────────────────────────
    header_row = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Image(src="/icon.png", width=36, height=36),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=14, color=AppColors.ACCENT),
                                    credits_text,
                                ],
                                spacing=4,
                            ),
                            padding=ft.Padding(12, 6, 12, 6),
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                            border_radius=AppStyles.RADIUS_SMALL,
                            on_click=lambda e: show_credits_dialog(page, credit_service, ad_service),
                        ),
                        notification_bell,
                        ft.IconButton(
                            icon=ft.Icons.BRIGHTNESS_6_ROUNDED,
                            icon_size=20,
                            on_click=_toggle_theme,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.SETTINGS_ROUNDED,
                            icon_size=20,
                            on_click=lambda e: page.run_task(navigate, "/settings"),
                        ),
                    ],
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(16, 12, 16, 12),
    )

    # ── Welcome Section ─────────────────
    welcome_section = ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Hello,", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(state.user_name or "Student", size=32, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text("🎓", size=32),
                    width=60,
                    height=60,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=30,
                    alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(2, AppColors.PRIMARY),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(24, 10, 24, 20),
    )

    courses_col = ft.Column(spacing=16, expand=True)

    if not courses:
        courses_col.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(height=80),
                        ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Container(height=12),
                        ft.Text("Your courses will appear here", size=16, weight=ft.FontWeight.W_500),
                        ft.Container(height=24),
                        ft.FilledButton(
                            "Create Your First Course",
                            icon=ft.Icons.ADD_ROUNDED,
                            on_click=lambda e: page.run_task(navigate, "/create-course"),
                            style=ft.ButtonStyle(
                                bgcolor=AppColors.PRIMARY,
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                                padding=20,
                            ),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                expand=True,
                alignment=ft.Alignment.CENTER,
            )
        )
    else:
        for course in courses:
            color = AppColors.SUBJECT_COLORS[course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)]
            pct = course.get("progress_pct", 0.0)

            async def on_tap(e, c=course):
                state.current_course = c
                await navigate("/modules")

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(width=4, height=40, border_radius=2, bgcolor=color),
                        ft.Container(width=16),
                        ft.Column(
                            [
                                ft.Text(course["subject"], size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    f"{course['level']} \u00b7 {pct:.0f}% Complete",
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT, size=20),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(20, 20, 20, 20),
                border_radius=AppStyles.RADIUS,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_click=lambda e, c=course: page.run_task(on_tap, e, c),
            )
            courses_col.controls.append(card)

    section_header = ft.Container(
        content=ft.Row(
            [
                ft.Text("My Learning Path", size=18, weight=ft.FontWeight.BOLD),
                ft.IconButton(
                    icon=ft.Icons.ADD_ROUNDED,
                    icon_size=24,
                    icon_color=AppColors.PRIMARY,
                    on_click=lambda e: page.run_task(navigate, "/create-course"),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(24, 16, 12, 4),
    )

    content = ft.Column(
        [
            header_row,
            welcome_section,
            section_header,
            ft.Container(
                content=courses_col,
                padding=ft.Padding(16, 0, 16, 0),
                expand=True,
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )

    async def _nav_change(e):
        idx = e.control.selected_index
        routes = ["/dashboard", "/tutor", "/progress", "/settings"]
        if idx < len(routes) and routes[idx] != "/dashboard":
            await navigate(routes[idx])

    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"),
            ft.NavigationBarDestination(icon=ft.Icons.CHAT_OUTLINED, selected_icon=ft.Icons.CHAT, label="Tutor"),
            ft.NavigationBarDestination(icon=ft.Icons.INSIGHTS_OUTLINED, selected_icon=ft.Icons.INSIGHTS, label="Progress"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Settings"),
        ],
        selected_index=0,
        on_change=lambda e: page.run_task(_nav_change, e),
        bgcolor=ft.Colors.SURFACE,
    )

    banner = ad_service.get_banner_ad() if ad_service else ft.Container()

    return ft.View(
        route="/dashboard",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column([content, banner], expand=True, spacing=0),
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        navigation_bar=nav_bar,
        padding=0,
        spacing=0,
    )
