"""Settings view — profile edit, theme toggle, data management."""

import flet as ft

from core.state import state
from core.theme import AppColors
from database.manager import db_manager


def build_settings_view(page: ft.Page, navigate) -> ft.View:
    name_field = ft.TextField(
        value=state.user_name, label="Name", border_radius=12, filled=True,
    )
    level_dropdown = ft.Dropdown(
        value=state.education_level, label="Education Level",
        border_radius=12,
        options=[
            ft.dropdown.Option("JSS 1"), ft.dropdown.Option("JSS 2"), ft.dropdown.Option("JSS 3"),
            ft.dropdown.Option("SS 1"), ft.dropdown.Option("SS 2"), ft.dropdown.Option("SS 3"),
            ft.dropdown.Option("100 Level"), ft.dropdown.Option("200 Level"),
            ft.dropdown.Option("300 Level"), ft.dropdown.Option("400 Level"),
        ],
    )

    async def _save_profile(e):
        name = name_field.value.strip()
        level = level_dropdown.value
        if not name or not level:
            return
        state.user_name = name
        state.education_level = level
        await db_manager.save_profile(name, level, state.avatar_index)
        page.snack_bar = ft.SnackBar(
            ft.Text("✅ Profile saved!", color=ft.Colors.WHITE), bgcolor=AppColors.SUCCESS,
        )
        page.snack_bar.open = True
        page.update()

    def _toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.DARK
        state.theme_mode = page.theme_mode
        page.update()

    async def _clear_data(e):
        # Confirmation via snackbar
        await db_manager.close()
        import os
        db_path = db_manager.db_path
        if os.path.exists(db_path):
            os.remove(db_path)
        db_manager._conn = None
        await db_manager.init_db()
        state.user_name = ""
        state.education_level = ""
        state.is_onboarded = False
        state.xp_total = 0
        state.credits_remaining = 150
        await navigate("/onboarding")

    # ── Sections ─────────────────────────────────────────────
    profile_section = ft.Container(
        content=ft.Column([
            ft.Text("Profile", size=16, weight=ft.FontWeight.BOLD),
            name_field,
            level_dropdown,
            ft.Button(
                "Save Profile", icon=ft.Icons.SAVE,
                on_click=lambda e: page.run_task(_save_profile),
                style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
            ),
        ], spacing=12),
        padding=20, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    appearance_section = ft.Container(
        content=ft.Column([
            ft.Text("Appearance", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Text("Dark Mode", size=14, expand=True),
                ft.Switch(
                    value=page.theme_mode == ft.ThemeMode.DARK,
                    on_change=_toggle_theme,
                    active_color=AppColors.PRIMARY,
                ),
            ]),
        ], spacing=12),
        padding=20, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    about_section = ft.Container(
        content=ft.Column([
            ft.Text("About", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("Akili v2.0", size=14),
            ft.Text("AI-powered educational platform", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(f"Credits: {state.credits_remaining}/150", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text(f"XP: {state.xp_total} • Level: {state.level}", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=6),
        padding=20, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    danger_section = ft.Container(
        content=ft.Column([
            ft.Text("Danger Zone", size=16, weight=ft.FontWeight.BOLD, color=AppColors.ERROR),
            ft.Button(
                "Reset All Data", icon=ft.Icons.DELETE_FOREVER,
                on_click=lambda e: page.run_task(_clear_data),
                style=ft.ButtonStyle(bgcolor=AppColors.ERROR, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=12)),
            ),
        ], spacing=12),
        padding=20, border_radius=16, bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: page.run_task(navigate, "/dashboard")),
            ft.Text("Settings", size=18, weight=ft.FontWeight.BOLD),
        ], spacing=8),
        padding=ft.Padding(8, 8, 16, 8),
    )

    return ft.View(
        route="/settings",
        controls=[ft.SafeArea(
            ft.Column([
                header,
                ft.Container(
                    content=ft.Column([
                        profile_section, appearance_section, about_section, danger_section,
                    ], spacing=16),
                    padding=ft.Padding(16, 8, 16, 16),
                    expand=True,
                ),
            ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )
