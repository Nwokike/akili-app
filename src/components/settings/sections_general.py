"""Settings sections — Appearance + Learning.

Sherlock rows, Akili content.
"""

from __future__ import annotations

import contextlib

import flet as ft

from components.settings_kit import setting_row, settings_card
from core import tokens
from core.state import state
from core.theme import AppColors
from state.controller_ctx import ControllerMethodsCtx


def _theme_card(page: ft.Page, controller, mode: str, label: str, icon: ft.IconData) -> ft.Control:
    selected = (mode == "dark" and page.theme_mode == ft.ThemeMode.DARK) or (mode == "light" and page.theme_mode == ft.ThemeMode.LIGHT) or (mode == "system" and page.theme_mode == ft.ThemeMode.SYSTEM)

    def _pick(e):
        controller.save("theme", mode)

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Icon(icon, size=tokens.ICON_LG, color=AppColors.PRIMARY if selected else ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(label, size=tokens.FONT_XS, weight=ft.FontWeight.W_600),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
            tight=True,
        ),
        padding=tokens.SPACE_MD,
        border_radius=tokens.RADIUS_MD,
        bgcolor=ft.Colors.with_opacity(0.10, AppColors.PRIMARY) if selected else ft.Colors.TRANSPARENT,
        border=ft.Border.all(2 if selected else 1, AppColors.PRIMARY if selected else ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
        ink=True,
        on_click=_pick,
        expand=True,
    )


@ft.component
def build_appearance_section(page: ft.Page) -> ft.Control:
    """Theme Light/Dark/System cards."""
    controller = ft.use_context(ControllerMethodsCtx)
    return settings_card(
        [
            ft.Container(
                content=ft.Row(
                    controls=[
                        _theme_card(page, controller, "light", "Light", ft.Icons.LIGHT_MODE_ROUNDED),
                        _theme_card(page, controller, "dark", "Dark", ft.Icons.DARK_MODE_ROUNDED),
                        _theme_card(page, controller, "system", "System", ft.Icons.SETTINGS_SYSTEM_DAYDREAM_ROUNDED),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
                padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
            )
        ]
    )


@ft.component
def build_learning_section(page: ft.Page) -> ft.Control:
    """Name + education level + country (v1 'Student Profile' card)."""

    def _save_name(value: str):
        state.user_name = value
        page.run_task(_persist_profile)

    def _save_level(value: str):
        state.education_level = value
        page.run_task(_persist_profile)

    def _save_country(value: str):
        state.country = value
        page.run_task(_persist_profile)

    async def _persist_profile():
        try:
            storage = getattr(page, "_akili_storage", None)
            if storage is None:
                return
            import json

            profile = {
                "name": state.user_name,
                "education_level": state.education_level,
                "country": state.country,
                "avatar_index": state.avatar_index,
            }
            await storage.set("profile", json.dumps(profile))
        except Exception:
            pass

    return settings_card(
        [
            setting_row(
                ft.Icons.PERSON_ROUNDED,
                "Full name",
                "Shown on your dashboard greeting.",
                ft.TextButton(
                    state.user_name or "Set name",
                    on_click=lambda e: _edit_text(page, "Full name", state.user_name, _save_name),
                ),
            ),
            setting_row(
                ft.Icons.SCHOOL_ROUNDED,
                "Education level",
                "Used to tailor courses and lessons.",
                ft.TextButton(
                    state.education_level or "Set level",
                    on_click=lambda e: _edit_text(page, "Education level", state.education_level, _save_level),
                ),
            ),
            setting_row(
                ft.Icons.PUBLIC_ROUNDED,
                "Country",
                "Used for curriculum research.",
                ft.TextButton(
                    state.country or "Set country",
                    on_click=lambda e: _edit_text(page, "Country", state.country, _save_country),
                ),
            ),
        ]
    )


def _edit_text(page: ft.Page, title: str, current: str, on_save) -> None:
    """A small text-edit dialog shared by the learning rows."""
    field = ft.TextField(value=current or "", autofocus=True)

    def _commit(e):
        value = (field.value or "").strip()
        if value:
            on_save(value)
        with contextlib.suppress(Exception):
            page.pop_dialog()

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(title),
            content=field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                ft.FilledButton("Save", on_click=_commit),
            ],
        )
    )
