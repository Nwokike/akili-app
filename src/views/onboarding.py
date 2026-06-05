import flet as ft

from core.constants import COUNTRIES
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager


def build_onboarding_view(page: ft.Page, navigate) -> ft.View:
    name_field = ft.TextField(
        label="Full Name",
        hint_text="e.g. John Sarki",
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        text_size=16,
    )

    level_field = ft.TextField(
        label="Your Class / Level",
        hint_text="e.g. JSS 1, Form 3, Grade 5, SSS 2, University Year 2...",
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        text_size=16,
    )

    error_text = ft.Text("", color=AppColors.ERROR, size=13)

    country_dropdown = ft.Dropdown(
        label="Your Country",
        options=[ft.dropdown.Option(c) for c in COUNTRIES],
        value="Nigeria",
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
    )

    async def _on_complete(e):
        name = name_field.value.strip()
        country = country_dropdown.value
        level = level_field.value.strip()

        if not name or not level:
            error_text.value = "Please enter your name and class/level"
            page.update()
            return

        state.user_name = name
        state.country = country
        state.education_level = level
        state.education_levels = []
        state.is_onboarded = True

        await db_manager.save_profile(name, level, country=country, avatar_index=0)
        await navigate("/dashboard")

    return ft.View(
        route="/onboarding",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(height=20),
                            ft.Image(src="/icon.png", width=64, height=64),
                            ft.Text("Personalize Akili", size=26, weight=ft.FontWeight.BOLD),
                            ft.Text("Tell us about your learning journey.", size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Container(height=20),
                            name_field,
                            ft.Container(height=10),
                            country_dropdown,
                            ft.Container(height=10),
                            level_field,
                            ft.Container(height=5),
                            ft.Text(
                                "Examples: JSS 1, SSS 2, Primary 5, Form 3, Grade 7, Year 2, University Year 1...",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            error_text,
                            ft.Container(height=20),
                            ft.FilledButton(
                                "Get Started",
                                on_click=lambda e: page.run_task(_on_complete, e),
                                style=ft.ButtonStyle(
                                    bgcolor=AppColors.PRIMARY,
                                    color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                                    padding=24,
                                ),
                                width=float("inf"),
                            ),
                            ft.Container(height=40),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        spacing=10,
                    ),
                    padding=20,
                ),
            )
        ],
        bgcolor=ft.Colors.SURFACE,
    )
