import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager


def _get_level_options() -> list:
    """Return education level options, preferring AI-detected levels from state."""
    if state.education_levels:
        return [ft.dropdown.Option(key=lvl["id"], text=lvl["name"]) for lvl in state.education_levels]
    # Fallback to K12 template if no AI-detected levels
    return [ft.dropdown.Option(key=f"grade_{i}", text=f"Grade {i}") for i in range(1, 13)]


def build_settings_view(page: ft.Page, navigate) -> ft.View:
    name_field = ft.TextField(
        value=state.user_name,
        label="Name",
        border_radius=AppStyles.RADIUS,
        filled=True,
    )

    manual_level_field = ft.TextField(
        label="Or type your level manually",
        hint_text="e.g. JSS 2, Form 3, Grade 5...",
        border_radius=AppStyles.RADIUS,
        filled=True,
        visible=False,
    )

    level_options = _get_level_options()

    def _toggle_manual(e):
        manual_level_field.visible = not manual_level_field.visible
        level_dropdown.visible = not manual_level_field.visible
        page.update()

    level_dropdown = ft.Dropdown(
        value=state.education_level,
        label="Education Level",
        border_radius=AppStyles.RADIUS,
        options=level_options,
    )

    async def _save(e):
        name = name_field.value.strip()
        level = level_dropdown.value or manual_level_field.value.strip()
        if not name or not level:
            return
        state.user_name = name
        state.education_level = level
        await db_manager.save_profile(name, level, state.education_levels, state.avatar_index)
        page.snack_bar = ft.SnackBar(
            ft.Text("Settings saved successfully", color=ft.Colors.WHITE),
            bgcolor=AppColors.SUCCESS,
        )
        page.snack_bar.open = True
        page.update()

    def _toggle_theme(e):
        page.theme_mode = ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        state.theme_mode = page.theme_mode
        page.update()

    async def _confirm_reset(e):
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset all data?"),
            content=ft.Text("This will permanently delete all courses, progress, and settings."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: _close(dialog)),
                ft.FilledButton(
                    "Delete Everything",
                    on_click=lambda e: page.run_task(_reset),
                    style=ft.ButtonStyle(bgcolor=AppColors.ERROR, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def _close(dialog):
        dialog.open = False
        page.update()

    async def _reset(e=None):
        for overlay in list(page.overlay):
            if isinstance(overlay, ft.AlertDialog):
                overlay.open = False
        page.update()

        await db_manager.close()
        import os

        db_path = db_manager.db_path
        for f in [db_path, db_path + "-shm", db_path + "-wal"]:
            if os.path.exists(f):
                os.remove(f)
        db_manager._conn = None
        await db_manager.init_db()
        state.user_name = ""
        state.education_level = ""
        state.education_levels = []
        state.is_onboarded = False
        state.xp_total = 0
        state.credits_remaining = 150
        await navigate("/onboarding")

    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
            ],
            spacing=4,
        ),
        padding=ft.Padding(4, 8, 16, 8),
    )

    def setting_card(title, content):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                    content,
                ],
                spacing=12,
            ),
            padding=20,
            border_radius=AppStyles.RADIUS,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
        )

    profile_card = setting_card(
        "Profile Info",
        ft.Column(
            [
                name_field,
                level_dropdown,
                manual_level_field,
                ft.Row(
                    [
                        ft.TextButton(
                            "Change level manually" if level_options else "Add level",
                            on_click=_toggle_manual,
                        ),
                    ]
                ),
                ft.FilledButton(
                    "Save Changes",
                    on_click=lambda e: page.run_task(_save),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                    ),
                    width=float("inf"),
                ),
            ],
            spacing=16,
        ),
    )

    appearance_card = setting_card(
        "Appearance",
        ft.Row(
            [
                ft.Text("Dark Mode", size=16, expand=True),
                ft.Switch(
                    value=page.theme_mode == ft.ThemeMode.DARK,
                    on_change=_toggle_theme,
                    active_color=AppColors.PRIMARY,
                ),
            ]
        ),
    )

    danger_card = setting_card(
        "Account Actions",
        ft.Column(
            [
                ft.OutlinedButton(
                    "Reset All Data",
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    on_click=lambda e: page.run_task(_confirm_reset),
                    style=ft.ButtonStyle(color=AppColors.ERROR, shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS)),
                    width=float("inf"),
                ),
            ],
            spacing=8,
        ),
    )

    return ft.View(
        route="/settings",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            ft.Container(
                                content=ft.Column(
                                    [
                                        profile_card,
                                        appearance_card,
                                        danger_card,
                                        ft.Container(
                                            content=ft.Text(
                                                "Akili v1.0 \u00b7 Built with Flet",
                                                size=12,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                            ),
                                            alignment=ft.Alignment.CENTER,
                                            margin=ft.Margin(0, 20, 0, 0),
                                        ),
                                    ],
                                    spacing=16,
                                    scroll=ft.ScrollMode.AUTO,
                                ),
                                padding=20,
                                expand=True,
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ft.Colors.SURFACE, ft.Colors.with_opacity(0.1, AppColors.PRIMARY)],
                    ),
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
        spacing=0,
    )
