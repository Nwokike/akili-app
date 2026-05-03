import flet as ft

from core.constants import EDUCATION_LEVELS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager


def build_onboarding_view(page: ft.Page, navigate) -> ft.View:
    name_field = ft.TextField(
        label="Your name",
        hint_text="e.g. Alex",
        border_radius=12,
        text_size=16,
        autofocus=True,
    )

    selected_level = {"value": ""}
    error_text = ft.Text("", color=AppColors.ERROR, size=13)

    level_list = ft.Column(spacing=0)

    def _select_level(level_id: str):
        selected_level["value"] = level_id
        for ctrl in level_list.controls:
            if hasattr(ctrl, "data") and ctrl.data:
                is_sel = ctrl.data == level_id
                ctrl.bgcolor = AppColors.PRIMARY if is_sel else ft.Colors.TRANSPARENT
                if hasattr(ctrl.content, "controls"):
                    for c in ctrl.content.controls:
                        if isinstance(c, ft.Text):
                            c.color = ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE
        error_text.value = ""
        page.update()

    current_group = ""
    for lvl in EDUCATION_LEVELS:
        if lvl["group"] != current_group:
            current_group = lvl["group"]
            level_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        lvl["group"], size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    padding=ft.Padding(16, 12, 0, 4),
                )
            )

        level_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(lvl["name"], size=14),
                ]),
                padding=ft.Padding(16, 12, 16, 12),
                border_radius=8,
                on_click=lambda e, lid=lvl["id"]: _select_level(lid),
                data=lvl["id"],
                ink=True,
            )
        )

    async def _continue(e):
        name = name_field.value.strip()
        if not name:
            error_text.value = "Please enter your name"
            page.update()
            return
        if not selected_level["value"]:
            error_text.value = "Please select your education level"
            page.update()
            return

        await db_manager.save_profile(name, selected_level["value"])
        state.user_name = name
        state.education_level = selected_level["value"]
        state.is_onboarded = True
        await db_manager.set_setting("is_onboarded", "true")
        await navigate("/dashboard")

    return ft.View(
        route="/onboarding",
        controls=[ft.SafeArea(
            ft.Container(
                content=ft.Column([
                    ft.Container(height=24),
                    ft.Image(src="/icon.png", width=56, height=56),
                    ft.Container(height=12),
                    ft.Text("welcome", size=22, weight=ft.FontWeight.W_500),
                    ft.Text(
                        "set up your profile to get started",
                        size=14, color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(height=24),
                    name_field,
                    ft.Container(height=20),
                    ft.Text("Education Level", size=15, weight=ft.FontWeight.W_600),
                    ft.Container(
                        content=level_list,
                        height=240,
                        border_radius=12,
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                    ),
                    ft.Container(height=8),
                    error_text,
                    ft.Container(expand=True),
                    ft.FilledButton(
                        content=ft.Text("Get Started", size=16, weight=ft.FontWeight.W_600),
                        on_click=lambda e: page.run_task(_continue, e),
                        style=ft.ButtonStyle(
                            bgcolor=AppColors.PRIMARY,
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=12),
                            padding=ft.Padding(0, 16, 0, 16),
                        ),
                        width=float("inf"),
                    ),
                    ft.Container(height=20),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   scroll=ft.ScrollMode.AUTO),
                padding=24, expand=True,
            ),
            expand=True,
        )],
        padding=0,
    )
