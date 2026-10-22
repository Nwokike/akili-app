"""Onboarding screen — name, country, education level.

Declarative (React-in-Flet): all fields are use_state; controls are frozen
after render, so nothing is mutated imperatively.
"""

from __future__ import annotations

import flet as ft

from core import tokens
from core.constants import (
    COUNTRIES,
    LBL_ERROR_NAME_LEVEL,
    LBL_GET_STARTED,
    LBL_LEVEL_EXAMPLES,
    LBL_ONBOARDING_SUBTITLE,
    LBL_ONBOARDING_TITLE,
    LBL_YOUR_COUNTRY,
    LBL_YOUR_LEVEL,
    LBL_YOUR_NAME,
)
from core.theme import AppColors
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx


@ft.component
def OnboardingScreen():
    """Onboarding form — name, country, level."""
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    name, set_name = ft.use_state("")
    level, set_level = ft.use_state("")
    country, set_country = ft.use_state("Nigeria")
    error, set_error = ft.use_state("")

    page = ft.context.page

    _field_border = ft.OutlineInputBorder(
        border_radius=tokens.RADIUS_MD,
        side=ft.BorderSide(0, ft.Colors.TRANSPARENT),
    )

    async def _complete(e):
        if not name.strip() or not level.strip():
            set_error(LBL_ERROR_NAME_LEVEL)
            return
        set_error("")
        state.user_name = name.strip()
        state.country = country
        state.education_level = level.strip()
        state.education_levels = []
        state.is_onboarded = True
        await controller.save_profile(name.strip(), level.strip(), country)
        await controller.set_onboarding_done()

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(height=20),
                ft.Image(src="/icon.svg", width=64, height=64),
                ft.Text(LBL_ONBOARDING_TITLE, size=tokens.FONT_XXL + 1, weight=ft.FontWeight.BOLD),
                ft.Text(LBL_ONBOARDING_SUBTITLE, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=20),
                ft.TextField(
                    label=LBL_YOUR_NAME,
                    hint_text="e.g. John Sarki",
                    border=_field_border,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    text_size=16,
                    value=name,
                    on_change=lambda e: set_name(e.control.value),
                ),
                ft.Container(height=10),
                ft.Dropdown(
                    label=LBL_YOUR_COUNTRY,
                    options=[ft.dropdown.Option(c) for c in COUNTRIES],
                    value=country,
                    border=_field_border,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_select=lambda e: set_country(e.data or country),
                ),
                ft.Container(height=10),
                ft.TextField(
                    label=LBL_YOUR_LEVEL,
                    hint_text="e.g. JSS 1, Form 3, Grade 5, SSS 2, University Year 2...",
                    border=_field_border,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    text_size=16,
                    value=level,
                    on_change=lambda e: set_level(e.control.value),
                ),
                ft.Container(height=5),
                ft.Text(LBL_LEVEL_EXAMPLES, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(error, color=AppColors.ERROR, size=13),
                ft.Container(height=20),
                ft.FilledButton(
                    LBL_GET_STARTED,
                    on_click=lambda e: page.run_task(_complete, e),
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
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
        expand=True,
    )
