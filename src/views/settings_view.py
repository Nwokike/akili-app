import flet as ft

from components.credit_dialog import show_credits_dialog
from core.constants import COUNTRIES
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.credit_service import credit_service


def build_settings_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    credits_text = ft.Text(f"{state.credits_remaining} / 100 Today", size=12, weight=ft.FontWeight.W_600)
    if not hasattr(state, "credit_text_controls"):
        state.credit_text_controls = []
    state.credit_text_controls.append(credits_text)

    # (Removed avatar selection)

    # --- Profile Inputs ---
    name_field = ft.TextField(
        value=state.user_name,
        label="Full Name",
        border_radius=AppStyles.RADIUS_SMALL,
        filled=True,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border_color=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
    )

    # Class / Level free-form field (removed rigid education system)
    class_field = ft.TextField(
        value=state.education_level,
        label="Class / Grade / Level",
        border_radius=AppStyles.RADIUS_SMALL,
        filled=True,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border_color=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
    )

    country_dropdown = ft.Dropdown(
        value=state.country or "Global",
        label="Country",
        border_radius=AppStyles.RADIUS_SMALL,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border_color=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
        options=[ft.DropdownOption("Global")] + [ft.DropdownOption(c) for c in COUNTRIES],
    )

    # --- AI Settings Inputs ---
    REGIONS = {
        "wt-wt": "Global (No Region Filter)",
        "us-en": "United States (US)",
        "uk-en": "United Kingdom (UK)",
        "ng-en": "Nigeria (NG)",
        "za-en": "South Africa (ZA)",
        "gh-en": "Ghana (GH)",
        "ca-en": "Canada (CA)",
    }

    region_dropdown = ft.Dropdown(
        value=state.search_region or "wt-wt",
        label="Tutor Search Region",
        border_radius=AppStyles.RADIUS_SMALL,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border_color=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
        options=[ft.DropdownOption(k, text=v) for k, v in REGIONS.items()],
    )

    safesearch_dropdown = ft.Dropdown(
        value=state.safesearch_level or "on",
        label="Content Filtering (SafeSearch)",
        border_radius=AppStyles.RADIUS_SMALL,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border_color=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
        options=[
            ft.DropdownOption("on", text="Strict (Filter everything)"),
            ft.DropdownOption("moderate", text="Moderate (Filter explicit files)"),
            ft.DropdownOption("off", text="Off (Unfiltered search)"),
        ],
    )

    # (Removed avatar row)

    # --- Save Handler ---
    async def _save_all(e):
        name = name_field.value.strip()
        level = class_field.value.strip()
        country = country_dropdown.value
        region = region_dropdown.value
        safesearch = safesearch_dropdown.value

        if not name or not level:
            page.snack_bar = ft.SnackBar(
                ft.Text("Please fill out name and class level"),
                bgcolor=AppColors.ERROR,
            )
            page.snack_bar.open = True
            page.update()
            return

        # Update local states
        state.user_name = name
        state.education_level = level
        state.country = country
        state.avatar_index = 0
        state.search_region = region
        state.safesearch_level = safesearch

        # Persist profile settings to db
        await db_manager.save_profile(
            name=name,
            education_level=level,
            education_levels=state.education_levels,
            avatar_index=0,
            country=country,
            education_system="",
        )

        # Persist AI search settings to db
        await db_manager.set_setting("search_region", region)
        await db_manager.set_setting("safesearch_level", safesearch)

        page.snack_bar = ft.SnackBar(
            ft.Text("Preferences saved successfully", color=ft.Colors.WHITE),
            bgcolor=AppColors.SUCCESS,
        )
        page.snack_bar.open = True
        page.update()

    # --- Appearance (Theme changed) ---
    def _on_theme_changed(mode_str):
        if mode_str == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        elif mode_str == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
        state.theme_mode = page.theme_mode
        page.update()

    current_theme = "system"
    if page.theme_mode == ft.ThemeMode.DARK:
        current_theme = "dark"
    elif page.theme_mode == ft.ThemeMode.LIGHT:
        current_theme = "light"

    # --- Clear Chats Action ---
    async def _handle_clear_chats(e):
        async def do_clear(e=None):
            await db_manager.clear_all_chats()
            _close_dialog(dialog)
            page.snack_bar = ft.SnackBar(ft.Text("Chat history cleared"), bgcolor=AppColors.SUCCESS)
            page.snack_bar.open = True
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Clear Chats?"),
            content=ft.Text("Are you sure you want to delete all cached chats? This cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: _close_dialog(dialog)),
                ft.FilledButton(
                    "Clear All",
                    on_click=lambda e: page.run_task(do_clear),
                    style=ft.ButtonStyle(bgcolor=AppColors.ERROR, color=ft.Colors.WHITE),
                ),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # --- Reset All Data Actions ---
    async def _confirm_reset(e):
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Factory Reset Platform?"),
            content=ft.Text("This will permanently delete all courses, credentials, chat sessions, streaks, and progress."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: _close_dialog(dialog)),
                ft.FilledButton(
                    "Reset Everything",
                    on_click=lambda e: page.run_task(_reset),
                    style=ft.ButtonStyle(bgcolor=AppColors.ERROR, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def _close_dialog(dialog):
        dialog.open = False
        page.update()

    async def _reset(e=None):
        for overlay in list(page.overlay):
            if isinstance(overlay, ft.AlertDialog):
                overlay.open = False
        page.update()

        # Reset database tables safely without file permission conflicts
        await db_manager.reset_database()

        # Reset states
        state.user_name = ""
        state.education_level = ""
        state.education_levels = []
        state.is_onboarded = False
        state.xp_total = 0
        await credit_service.refresh_credits(force=True)
        state.current_streak = 0
        state.best_streak = 0
        await navigate("/onboarding")

    # --- Section Builder Helpers ---
    def build_section_card(title: str, icon: str, content: ft.Control):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=AppColors.PRIMARY, size=20),
                            ft.Text(title, size=15, weight=ft.FontWeight.W_600),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
                    content,
                ],
                spacing=12,
            ),
            padding=16,
            border_radius=AppStyles.RADIUS,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)),
        )

    # Header Layout
    header = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    on_click=lambda e: page.run_task(navigate, "/dashboard"),
                ),
                ft.Text("Platform Preferences", size=18, weight=ft.FontWeight.BOLD),
            ],
            spacing=4,
        ),
        padding=ft.Padding(4, 8, 16, 8),
    )

    # 1. Profile Config Section
    profile_content = ft.Column(
        [
            name_field,
            class_field,
            country_dropdown,
        ],
        spacing=12,
    )

    # 2. AI Tutor Config Section
    ai_content = ft.Column(
        [
            region_dropdown,
            safesearch_dropdown,
        ],
        spacing=12,
    )

    # 3. Theme Section
    def create_theme_card(mode: str, label: str, icon: str):
        is_sel = current_theme == mode
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, color=AppColors.PRIMARY if is_sel else ft.Colors.ON_SURFACE_VARIANT, size=18),
                    ft.Text(label, size=12, weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL, color=AppColors.PRIMARY if is_sel else ft.Colors.ON_SURFACE),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=8,
            border=ft.Border.all(2, AppColors.PRIMARY) if is_sel else ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_sel else ft.Colors.SURFACE_CONTAINER_LOW,
            expand=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e: page.run_task(change_theme_and_update, mode),
        )

    light_btn = create_theme_card("light", "Light", ft.Icons.LIGHT_MODE_ROUNDED)
    dark_btn = create_theme_card("dark", "Dark", ft.Icons.DARK_MODE_ROUNDED)
    system_btn = create_theme_card("system", "System", ft.Icons.SETTINGS_SYSTEM_DAYDREAM_ROUNDED)

    async def change_theme_and_update(mode_str):
        nonlocal current_theme
        current_theme = mode_str
        _on_theme_changed(mode_str)

        for m, btn in [("light", light_btn), ("dark", dark_btn), ("system", system_btn)]:
            is_sel = m == mode_str
            btn.border = ft.Border.all(2, AppColors.PRIMARY) if is_sel else ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
            btn.bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_sel else ft.Colors.SURFACE_CONTAINER_LOW
            btn.content.controls[0].color = AppColors.PRIMARY if is_sel else ft.Colors.ON_SURFACE_VARIANT
            btn.content.controls[1].color = AppColors.PRIMARY if is_sel else ft.Colors.ON_SURFACE
            btn.content.controls[1].weight = ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL

        page.update()

    theme_selector = ft.Row(
        [light_btn, dark_btn, system_btn],
        spacing=8,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    theme_content = ft.Container(
        content=theme_selector,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding(0, 4, 0, 4),
    )

    # 4. Study Stats Info Section (Read Only)
    stats_content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(f"Current Level: {state.level}", weight=ft.FontWeight.W_600, size=13),
                    ft.Text(f"{state.xp_total} XP Total", size=12, color=AppColors.PRIMARY, weight=ft.FontWeight.W_500),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ProgressBar(value=state.get_level_progress(), color=AppColors.PRIMARY, height=6, border_radius=3),
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)),
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, color=AppColors.ACCENT, size=18),
                            ft.Text("Daily Streak:", size=12),
                        ]
                    ),
                    ft.Text(f"{state.current_streak} Days (Best: {state.best_streak} Days)", size=12, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=AppColors.SUCCESS, size=18),
                                ft.Text("Remaining Credits:", size=12),
                            ]
                        ),
                        credits_text,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                on_click=lambda e: show_credits_dialog(page, credit_service, ad_service),
            ),
        ],
        spacing=8,
    )

    # 5. Data Actions Card
    actions_content = ft.Column(
        [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, color=AppColors.PRIMARY),
                title=ft.Text("Clear Chat History", size=13, weight=ft.FontWeight.W_500),
                subtitle=ft.Text("Deletes all local chat threads and caches", size=11),
                on_click=_handle_clear_chats,
                dense=True,
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.DELETE_FOREVER_ROUNDED, color=AppColors.ERROR),
                title=ft.Text("Factory Reset", size=13, weight=ft.FontWeight.W_500, color=AppColors.ERROR),
                subtitle=ft.Text("Clears all study logs and profile databases", size=11),
                on_click=_confirm_reset,
                dense=True,
            ),
        ],
        spacing=4,
    )

    # Assemble everything into scrollable body
    settings_body = ft.Container(
        content=ft.Column(
            [
                build_section_card("Student Profile", ft.Icons.PERSON_ROUNDED, profile_content),
                build_section_card("AI Tutor Options", ft.Icons.AUTO_AWESOME_ROUNDED, ai_content),
                build_section_card("Display Theme", ft.Icons.COLOR_LENS_ROUNDED, theme_content),
                build_section_card("Academics & Streak", ft.Icons.AUTO_STORIES_ROUNDED, stats_content),
                build_section_card("Maintenance & Storage", ft.Icons.STORAGE_ROUNDED, actions_content),
                ft.FilledButton(
                    "Save & Apply Changes",
                    icon=ft.Icons.CHECK_ROUNDED,
                    on_click=_save_all,
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS_SMALL),
                    ),
                    height=50,
                    width=float("inf"),
                ),
                ft.Container(
                    content=ft.Text("Akili Studio • v1.0.0", size=11, text_align=ft.TextAlign.CENTER, color=AppColors.LIGHT_TEXT_DIM),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding(0, 10, 0, 20),
                ),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=20,
        expand=True,
    )

    return ft.View(
        route="/settings",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            header,
                            settings_body,
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
        spacing=0,
    )
