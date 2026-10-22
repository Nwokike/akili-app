"""Model picker — pill + dialog driven by the router catalog.

Ported from DDGS model_picker.py (the house standard).
Honest states: starting / stopped / loading / no chat models.
The picker only DISPLAYS the catalog; model choice is sent verbatim.
"""

from __future__ import annotations

import contextlib

import flet as ft

from agent import engine as router
from core import tokens
from core.constants import STORAGE_AI_MODEL
from core.state import state
from core.theme import AppColors


def _label() -> tuple[str, bool]:
    """(label, active) for the current selection + router status."""
    picker = model_picker_state()
    return (picker["label"], picker["active"])


def model_picker_state() -> dict:
    """One shared derivation for the pill, settings row, and dialog.

    (DDGS pattern: all surfaces agree because they read one function.)
    """
    status = state.router_status
    selected = state.ai_model or "auto"
    catalog = [m for m in (state.model_catalog or []) if m.get("id")]
    ids = {m.get("id") for m in catalog}
    fetched = router.catalog_fetched()

    if status in ("stopped", "unavailable"):
        label, active, message, action = "Offline", False, "The AI router stopped.", "Start router"
    elif selected in ids:
        label = "Auto" if selected == "auto" else selected
        active, message, action = True, "", ""
    elif status == "starting":
        label, active, message, action = "Starting router…", False, "The router is starting.", ""
    elif not fetched:
        label, active, message, action = "Loading models…", False, "Looking for available models…", ""
    elif not catalog:
        label, active, message, action = "Offline", False, "The router reported no chat models.", "Refresh"
    else:
        label, active, message, action = "Offline", False, "Your saved model is gone from the catalog.", "Refresh"
    return {
        "label": label,
        "active": active,
        "message": message,
        "action": action,
        "selected": selected,
        "catalog": catalog,
    }


def model_status_subtitle() -> str:
    """The settings-row subtitle: live hint when active, status otherwise."""
    picker = model_picker_state()
    if picker["active"]:
        return router.model_hint(picker["selected"]) or "Ready"
    return picker["message"] or "No model selected"


def build_model_pill(on_click=None) -> ft.Control:
    """Compact model chip shown in the tutor header."""
    label, active = _label()
    color = AppColors.PRIMARY if active else ft.Colors.ON_SURFACE_VARIANT
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.AUTO_AWESOME_ROUNDED if active else ft.Icons.CLOUD_OFF_ROUNDED,
                    size=tokens.ICON_XS,
                    color=color,
                ),
                ft.Text(label[:26], size=tokens.FONT_XS, weight=ft.FontWeight.W_600, color=color, no_wrap=True),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        padding=ft.Padding(10, 4, 10, 4),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.08, color),
        ink=on_click is not None,
        on_click=on_click,
        tooltip="Choose the AI model (Auto lets the router pick)",
    )


def build_model_dialog(page: ft.Page, on_select=None) -> ft.Control:
    """Filterable model list with per-model hints and honest empty states."""
    label, active = _label()
    catalog = list(state.model_catalog)

    def _rows() -> list[ft.Control]:
        if not catalog:
            if state.router_status in ("stopped", "unavailable"):
                message = "The AI router is offline."
            elif state.router_status == "starting":
                message = "The router is starting…"
            elif not router.catalog_fetched():
                message = "Loading models…"
            else:
                message = "The router reported no chat models."
            return [ft.Text(message, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT)]

        def _pick(model_id: str):
            state.ai_model = model_id
            if on_select:
                on_select(model_id)
            with contextlib.suppress(Exception):
                page.pop_dialog()

        current = state.ai_model or "auto"
        rows: list[ft.Control] = []
        for row in catalog:
            model_id = str(row.get("id") or "")
            hint = str(row.get("hint") or "")
            chosen = model_id == current
            rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED if chosen else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                size=tokens.ICON_SM,
                                color=AppColors.PRIMARY if chosen else ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Auto (recommended)" if model_id == "auto" else model_id,
                                        size=tokens.FONT_MD,
                                        weight=ft.FontWeight.W_600 if chosen else ft.FontWeight.W_400,
                                    ),
                                    ft.Text(hint, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                                expand=True,
                                tight=True,
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(8, 8, 8, 8),
                    border_radius=tokens.RADIUS_SM,
                    ink=True,
                    on_click=lambda e, mid=model_id: _pick(mid),
                )
            )
        return rows

    return ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=AppColors.PRIMARY),
                ft.Text("AI Model", weight=ft.FontWeight.BOLD),
            ],
            spacing=tokens.SPACE_SM,
        ),
        content=ft.Column(
            controls=[
                ft.Text(
                    "Auto lets the router pick and fail over for you.",
                    size=tokens.FONT_XS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Column(controls=_rows(), spacing=2, scroll=ft.ScrollMode.AUTO, height=320),
            ],
            spacing=tokens.SPACE_SM,
            tight=True,
            width=tokens.DIALOG_WIDTH_LG,
        ),
        actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
    )


async def persist_model(storage) -> None:
    """Persist the selected model."""
    if storage is not None:
        await storage.set(STORAGE_AI_MODEL, state.ai_model)
