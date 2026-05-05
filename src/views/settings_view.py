import flet as ft

from core.constants import EDUCATION_LEVELS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager


def build_settings_view(page: ft.Page, navigate) -> ft.View:
    name_field = ft.TextField(
        value=state.user_name, label="Name",
        border_radius=12, filled=True,
    )

    level_options = [
        ft.dropdown.Option(key=lvl["id"], text=lvl["name"])
        for lvl in EDUCATION_LEVELS
    ]
    level_dropdown = ft.Dropdown(
        value=state.education_level,
        label="Education Level",
        border_radius=12,
        options=level_options,
    )

    async def _save(e):
        name = name_field.value.strip()
        level = level_dropdown.value
        if not name or not level:
            return
        state.user_name = name
        state.education_level = level
        await db_manager.save_profile(name, level, state.avatar_index)
        page.snack_bar = ft.SnackBar(
            ft.Text("Saved", color=ft.Colors.WHITE),
            bgcolor=AppColors.SUCCESS,
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

    def _invite_friends(e):
        # Client-side workaround for referrals
        page.set_clipboard("Join me on Akili! Download the app: https://akili.app/download")
        page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text("Invite link copied to clipboard!"),
                bgcolor=ft.Colors.BLACK
            )
        )

    async def _confirm_reset(e):
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Reset all data?"),
            content=ft.Text(
                "This will permanently delete all courses, "
                "progress, and settings."
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: _close(dialog),
                ),
                ft.FilledButton(
                    "Delete Everything",
                    on_click=lambda e: page.run_task(_reset),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.ERROR,
                        color=ft.Colors.WHITE,
                    ),
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
        state.is_onboarded = False
        state.xp_total = 0
        state.credits_remaining = 150
        await navigate("/onboarding")

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/dashboard"),
            ),
            ft.Text("Settings", size=18, weight=ft.FontWeight.BOLD),
        ], spacing=4),
        padding=ft.Padding(4, 8, 16, 8),
    )

    profile = ft.Container(
        content=ft.Column([
            name_field,
            level_dropdown,
            ft.FilledButton(
                "Save",
                on_click=lambda e: page.run_task(_save),
                style=ft.ButtonStyle(
                    bgcolor=AppColors.PRIMARY,
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
            ),
        ], spacing=12),
        padding=20, border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    appearance = ft.Container(
        content=ft.Row([
            ft.Text("Dark mode", size=14, expand=True),
            ft.Switch(
                value=page.theme_mode == ft.ThemeMode.DARK,
                on_change=_toggle_theme,
                active_color=AppColors.PRIMARY,
            ),
        ]),
        padding=20, border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )
    
    # --- New Referrals & Premium Section ---
    extras = ft.Container(
        content=ft.Column([
            ft.Text("Extras", size=14, weight=ft.FontWeight.W_600),
            ft.OutlinedButton(
                "Invite Friends",
                icon=ft.Icons.GROUP_ADD,
                on_click=_invite_friends,
                style=ft.ButtonStyle(color=ft.Colors.BLACK, shape=ft.RoundedRectangleBorder(radius=4))
            ),
            ft.OutlinedButton(
                "Get Premium",
                icon=ft.Icons.STAR,
                on_click=lambda e: page.run_task(navigate, "/premium"),
                style=ft.ButtonStyle(color=ft.Colors.BLACK, shape=ft.RoundedRectangleBorder(radius=4))
            ),
        ], spacing=12),
        padding=20, border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    about = ft.Container(
        content=ft.Column([
            ft.Text("Akili v1.0", size=14, weight=ft.FontWeight.W_600),
            ft.Text(
                "AI-powered learning platform",
                size=13, color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ], spacing=4),
        padding=20, border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    danger = ft.Container(
        content=ft.Column([
            ft.Text("Danger Zone", size=14, weight=ft.FontWeight.W_600, color=AppColors.ERROR),
            ft.OutlinedButton(
                "Reset All Data",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=lambda e: page.run_task(_confirm_reset),
                style=ft.ButtonStyle(color=AppColors.ERROR),
            ),
        ], spacing=12),
        padding=20, border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )

    return ft.View(
        route="/settings",
        controls=[ft.SafeArea(
            ft.Column([
                header,
                ft.Container(
                    content=ft.Column([
                        profile, appearance, extras, about, danger,
                    ], spacing=16),
                    padding=ft.Padding(16, 8, 16, 16),
                    expand=True,
                ),
            ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )