"""Onboarding — name, education level, avatar selection."""

import flet as ft

from core.constants import EDUCATION_LEVELS
from core.state import state
from core.theme import AppColors
from database.manager import db_manager


AVATARS = [
    {"icon": ft.Icons.FACE, "color": "#6366F1"},
    {"icon": ft.Icons.FACE_2, "color": "#10B981"},
    {"icon": ft.Icons.FACE_3, "color": "#F59E0B"},
    {"icon": ft.Icons.FACE_4, "color": "#EF4444"},
    {"icon": ft.Icons.FACE_5, "color": "#3B82F6"},
    {"icon": ft.Icons.FACE_6, "color": "#8B5CF6"},
]


def build_onboarding_view(page: ft.Page, navigate) -> ft.View:
    """Multi-step onboarding with name → level → avatar."""

    name_field = ft.TextField(
        label="What's your name?",
        hint_text="e.g. Chinedu",
        border_radius=12,
        text_size=16,
        autofocus=True,
    )

    selected_level = {"value": ""}
    selected_avatar = {"value": 0}

    error_text = ft.Text("", color=AppColors.ERROR, size=13)

    # Education level chips
    level_chips = ft.ResponsiveRow(spacing=8, run_spacing=8)
    current_group = {"value": ""}

    for lvl in EDUCATION_LEVELS:
        if lvl["group"] != current_group["value"]:
            current_group["value"] = lvl["group"]
            level_chips.controls.append(
                ft.Container(
                    content=ft.Text(
                        lvl["group"],
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=AppColors.DARK_TEXT_DIM,
                    ),
                    col={"xs": 12},
                    padding=ft.Padding(0, 8, 0, 0),
                )
            )

        def make_level_click(level_id):
            def on_click(e):
                selected_level["value"] = level_id
                # Update chip visuals
                for chip in level_chips.controls:
                    if hasattr(chip, "data") and chip.data:
                        chip.bgcolor = (
                            AppColors.PRIMARY if chip.data == level_id
                            else ft.Colors.SURFACE_CONTAINER
                        )
                        for c in chip.content.controls if hasattr(chip.content, "controls") else []:
                            if isinstance(c, ft.Text):
                                c.color = (
                                    ft.Colors.WHITE if chip.data == level_id
                                    else ft.Colors.ON_SURFACE
                                )
                error_text.value = ""
                page.update()
            return on_click

        level_chips.controls.append(
            ft.Container(
                content=ft.Row(
                    [ft.Text(lvl["name"], size=14)],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=20,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                col={"xs": 4, "sm": 3},
                on_click=make_level_click(lvl["id"]),
                data=lvl["id"],
                ink=True,
            )
        )

    # Avatar selection
    avatar_row = ft.Row(spacing=12, alignment=ft.MainAxisAlignment.CENTER)

    for idx, av in enumerate(AVATARS):
        def make_avatar_click(i):
            def on_click(e):
                selected_avatar["value"] = i
                for j, container in enumerate(avatar_row.controls):
                    container.border = (
                        ft.Border(
                            left=ft.BorderSide(3, AppColors.PRIMARY),
                            top=ft.BorderSide(3, AppColors.PRIMARY),
                            right=ft.BorderSide(3, AppColors.PRIMARY),
                            bottom=ft.BorderSide(3, AppColors.PRIMARY),
                        ) if j == i else None
                    )
                page.update()
            return on_click

        avatar_row.controls.append(
            ft.Container(
                content=ft.Icon(av["icon"], size=36, color=av["color"]),
                width=60,
                height=60,
                border_radius=30,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                alignment=ft.Alignment.CENTER,
                on_click=make_avatar_click(idx),
                border=(
                    ft.Border(
                        left=ft.BorderSide(3, AppColors.PRIMARY),
                        top=ft.BorderSide(3, AppColors.PRIMARY),
                        right=ft.BorderSide(3, AppColors.PRIMARY),
                        bottom=ft.BorderSide(3, AppColors.PRIMARY),
                    ) if idx == 0 else None
                ),
                ink=True,
            )
        )

    async def on_continue(e):
        name = name_field.value.strip()
        if not name:
            error_text.value = "Please enter your name"
            page.update()
            return
        if not selected_level["value"]:
            error_text.value = "Please select your education level"
            page.update()
            return

        # Save profile
        await db_manager.save_profile(name, selected_level["value"], selected_avatar["value"])
        state.user_name = name
        state.education_level = selected_level["value"]
        state.avatar_index = selected_avatar["value"]
        state.is_onboarded = True
        await db_manager.set_setting("is_onboarded", "true")

        await navigate("/dashboard")

    return ft.View(
        route="/onboarding",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(height=20),
                            # Header
                            ft.Image(src="/icon.png", width=64, height=64),
                            ft.Text("Welcome to Akili", size=28, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Let's set up your learning profile",
                                size=14,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Container(height=20),

                            # Name
                            name_field,
                            ft.Container(height=16),

                            # Education Level
                            ft.Text("Education Level", size=16, weight=ft.FontWeight.W_600),
                            ft.Container(height=4),
                            ft.Container(
                                content=level_chips,
                                height=200,
                                # Scrollable if many levels
                            ),
                            ft.Container(height=16),

                            # Avatar
                            ft.Text("Choose your avatar", size=16, weight=ft.FontWeight.W_600),
                            ft.Container(height=8),
                            avatar_row,

                            ft.Container(height=16),
                            error_text,

                            ft.Container(expand=True),

                            # Continue button
                            ft.FilledButton(
                                content=ft.Row(
                                    [
                                        ft.Text("Get Started", size=16, weight=ft.FontWeight.W_600),
                                        ft.Icon(ft.Icons.ARROW_FORWARD, size=20),
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    spacing=8,
                                ),
                                on_click=on_continue,
                                style=ft.ButtonStyle(
                                    bgcolor=AppColors.PRIMARY,
                                    color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                    padding=ft.Padding(0, 16, 0, 16),
                                ),
                                width=float("inf"),
                            ),
                            ft.Container(height=20),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=20,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0,
    )
