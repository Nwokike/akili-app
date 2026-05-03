import flet as ft

from core.state import state
from core.theme import AppColors
from database.manager import db_manager


async def build_dashboard_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    courses = await db_manager.get_courses()

    def _toggle_theme(e):
        page.theme_mode = (
            ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK
            else ft.ThemeMode.DARK
        )
        state.theme_mode = page.theme_mode
        page.update()

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_6, icon_size=20,
                on_click=_toggle_theme,
            ),
            ft.Container(expand=True),
            ft.Image(src="/icon.png", width=36, height=36),
            ft.Container(expand=True),
            ft.PopupMenuButton(
                content=ft.Container(
                    content=ft.Text(
                        (state.user_name or "?")[0].upper(),
                        size=14, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    width=34, height=34, border_radius=10,
                    gradient=ft.LinearGradient(
                        colors=[AppColors.PRIMARY, AppColors.TERTIARY],
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
                items=[
                    ft.PopupMenuItem(
                        content=ft.Text(state.user_name or "Student"),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text(f"Credits: {state.credits_remaining}",
                                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ),
                    ft.PopupMenuItem(),
                    ft.PopupMenuItem(
                        content=ft.Text("Timetable"),
                        icon=ft.Icons.CALENDAR_TODAY_OUTLINED,
                        on_click=lambda e: page.run_task(navigate, "/timetable"),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Settings"),
                        icon=ft.Icons.SETTINGS_OUTLINED,
                        on_click=lambda e: page.run_task(navigate, "/settings"),
                    ),
                ],
            ),
        ]),
        padding=ft.Padding(12, 8, 12, 8),
    )

    courses_col = ft.Column(spacing=0, expand=True)

    if not courses:
        courses_col.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Container(height=80),
                    ft.Text("No courses yet", size=17, weight=ft.FontWeight.W_600),
                    ft.Container(height=4),
                    ft.Text(
                        "Tap + to create your first course",
                        size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(height=20),
                    ft.FilledButton(
                        "Create Course",
                        icon=ft.Icons.ADD,
                        on_click=lambda e: page.run_task(navigate, "/create-course"),
                        style=ft.ButtonStyle(
                            bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=12),
                        ),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                expand=True, alignment=ft.Alignment.CENTER,
            )
        )
    else:
        for course in courses:
            color = AppColors.SUBJECT_COLORS[
                course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)
            ]
            pct = course.get("progress_pct", 0.0)

            async def on_tap(e, c=course):
                state.current_course = c
                await navigate("/modules")

            card = ft.Container(
                content=ft.Row([
                    ft.Container(width=4, height=44, border_radius=2, bgcolor=color),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(
                            course["subject"], size=15, weight=ft.FontWeight.W_600,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            f"{course['level']} · {pct:.0f}%",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], spacing=2, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ft.Colors.ON_SURFACE_VARIANT, size=20),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(16, 14, 12, 14),
                on_click=lambda e, c=course: page.run_task(on_tap, e, c),
                ink=True,
            )
            courses_col.controls.append(card)
            courses_col.controls.append(ft.Divider(height=1, thickness=0.3))

    section_header = ft.Container(
        content=ft.Row([
            ft.Text("My Courses", size=16, weight=ft.FontWeight.BOLD),
            ft.IconButton(
                icon=ft.Icons.ADD, icon_size=22,
                on_click=lambda e: page.run_task(navigate, "/create-course"),
                tooltip="New Course",
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding(20, 4, 12, 4),
    )

    content = ft.Column([
        header,
        section_header,
        ft.Container(
            content=courses_col,
            padding=ft.Padding(16, 0, 16, 0),
            expand=True,
        ),
    ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

    async def _nav_change(e):
        idx = e.control.selected_index
        routes = ["/dashboard", "/tutor", "/progress", "/settings"]
        if idx < len(routes) and routes[idx] != "/dashboard":
            await navigate(routes[idx])

    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.SCHOOL_OUTLINED, selected_icon=ft.Icons.SCHOOL,
                label="Courses",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.CHAT_OUTLINED, selected_icon=ft.Icons.CHAT,
                label="Tutor",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.INSIGHTS_OUTLINED, selected_icon=ft.Icons.INSIGHTS,
                label="Progress",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS,
                label="Settings",
            ),
        ],
        selected_index=0,
        on_change=lambda e: page.run_task(_nav_change, e),
    )

    banner = ad_service.get_banner_ad() if ad_service else ft.Container()

    return ft.View(
        route="/dashboard",
        controls=[
            ft.SafeArea(
                ft.Column([content, banner], expand=True, spacing=0),
                expand=True,
            ),
        ],
        navigation_bar=nav_bar,
        padding=0, spacing=0,
    )
