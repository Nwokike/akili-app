"""Timetable screen — the weekly class schedule manager.

Weekday-ordered groups (fixes v1's alphabetical sort), today highlight,
add/edit/delete with inline validation errors (v1 silently returned),
and the note field v1 stored but never had an input for.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import flet as ft

from components.banner_ad import build_banner_ad
from components.empty_state import EmptyState
from core import tokens
from core.constants import (
    LBL_ADD_TIMETABLE_ENTRY,
    LBL_EDIT_TIMETABLE_ENTRY,
    LBL_TIMETABLE_EMPTY,
    LBL_TIMETABLE_EMPTY_DESC,
    LBL_TIMETABLE_TODAY,
)
from core.theme import AppColors
from services.course_store import WEEKDAY_ORDER
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

_TODAY = datetime.now().strftime("%A")


def _entry_row(entry: dict, is_today: bool, on_edit, on_delete) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(str(entry.get("time_slot") or ""), size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                    width=72,
                ),
                ft.Column(
                    controls=[
                        ft.Text(str(entry.get("subject") or ""), size=tokens.FONT_MD, weight=ft.FontWeight.W_500),
                        *([ft.Text(str(entry.get("note") or ""), size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT)] if entry.get("note") else []),
                    ],
                    spacing=1,
                    expand=True,
                    tight=True,
                ),
                ft.IconButton(icon=ft.Icons.EDIT_ROUNDED, icon_size=tokens.ICON_SM, tooltip="Edit", on_click=lambda e: on_edit(entry)),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=tokens.ICON_SM, tooltip="Delete", on_click=lambda e: on_delete(entry)),
            ],
            spacing=tokens.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
        border_radius=tokens.RADIUS_MD,
        bgcolor=ft.Colors.with_opacity(0.08 if is_today else 0.04, AppColors.PRIMARY if is_today else ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.4 if is_today else 0.08, AppColors.PRIMARY if is_today else ft.Colors.ON_SURFACE)),
    )


@ft.component
def TimetableScreen():
    """The weekly schedule."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    entries, set_entries = ft.use_state([])
    editing, set_editing = ft.use_state(None)  # entry dict or "new" or None
    day, set_day = ft.use_state(_TODAY)
    time_slot, set_time = ft.use_state("")
    subject, set_subject = ft.use_state("")
    note, set_note = ft.use_state("")
    form_error, set_form_error = ft.use_state("")
    busy, set_busy = ft.use_state(False)

    _ = app_state.courses_version
    page = ft.context.page

    def _load():
        async def _run():
            set_entries(await controller.load_timetable())

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    def _open_new():
        set_editing("new")
        set_day(_TODAY)
        set_time("")
        set_subject("")
        set_note("")
        set_form_error("")

    def _open_edit(entry: dict):
        set_editing(entry.get("id"))
        set_day(entry.get("day", _TODAY))
        set_time(entry.get("time_slot", ""))
        set_subject(entry.get("subject", ""))
        set_note(entry.get("note", ""))
        set_form_error("")

    async def _save():
        if busy:
            return
        set_busy(True)
        set_form_error("")
        try:
            if editing == "new":
                await controller.save_timetable_entry(None, day, time_slot, subject, note)
            else:
                await controller.save_timetable_entry(editing, day, time_slot, subject, note)
            set_entries(await controller.load_timetable())
            set_editing(None)
        except ValueError as exc:
            set_form_error(str(exc))
        except Exception as exc:
            set_form_error(f"Couldn't save: {str(exc)[:80]}")
        finally:
            set_busy(False)

    async def _remove(entry: dict):
        await controller.delete_timetable_entry(entry.get("id"))
        set_entries(await controller.load_timetable())

    # ── Header ──
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Text("Timetable", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(icon=ft.Icons.ADD_ROUNDED, on_click=lambda e: _open_new(), tooltip=LBL_ADD_TIMETABLE_ENTRY),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    # ── Grouped list ──
    if not entries:
        body: ft.Control = EmptyState(
            LBL_TIMETABLE_EMPTY,
            LBL_TIMETABLE_EMPTY_DESC,
            LBL_ADD_TIMETABLE_ENTRY,
            on_action=lambda e: _open_new(),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
        )
    else:
        groups: list[ft.Control] = []
        current_day = None
        for entry in entries:
            if entry.get("day") != current_day:
                current_day = entry.get("day")
                is_today_group = current_day == _TODAY
                groups.append(
                    ft.Row(
                        controls=[
                            ft.Text(str(current_day), size=tokens.FONT_SM, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                            *(
                                [
                                    ft.Container(
                                        content=ft.Text(LBL_TIMETABLE_TODAY, size=9, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                                        padding=ft.Padding(6, 1, 6, 1),
                                        border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.12, AppColors.PRIMARY),
                                    )
                                ]
                                if is_today_group
                                else []
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            groups.append(_entry_row(entry, entry.get("day") == _TODAY, _open_edit, lambda en: page.run_task(_remove, en)))
            groups.append(ft.Container(height=tokens.SPACE_XS))
        body = ft.Column(controls=groups, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

    # ── Add/edit form ──
    form: ft.Control = ft.Container()
    if editing is not None:
        form_children: list[ft.Control] = [
            ft.Text(LBL_ADD_TIMETABLE_ENTRY if editing == "new" else LBL_EDIT_TIMETABLE_ENTRY, size=tokens.FONT_MD, weight=ft.FontWeight.BOLD),
            ft.Dropdown(
                label="Day",
                options=[ft.dropdown.Option(d) for d in WEEKDAY_ORDER],
                value=day,
                border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_select=lambda e: set_day(e.data or day),
            ),
            ft.Row(
                controls=[
                    ft.TextField(
                        label="Time",
                        hint_text="e.g. 09:00",
                        value=time_slot,
                        expand=True,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        on_change=lambda e: set_time(e.control.value),
                    ),
                    ft.TextField(
                        label="Subject",
                        hint_text="e.g. Mathematics",
                        value=subject,
                        expand=2,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        on_change=lambda e: set_subject(e.control.value),
                    ),
                ],
                spacing=tokens.SPACE_SM,
            ),
            ft.TextField(
                label="Note (optional)",
                value=note,
                border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_change=lambda e: set_note(e.control.value),
            ),
        ]
        if form_error:
            form_children.append(ft.Text(form_error, color=AppColors.ERROR, size=tokens.FONT_SM))
        form_children.append(
            ft.Row(
                controls=[
                    ft.TextButton("Cancel", on_click=lambda e: set_editing(None)),
                    ft.FilledButton(
                        "Saving…" if busy else "Save",
                        on_click=lambda e: page.run_task(_save),
                        disabled=busy,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD)),
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=tokens.SPACE_SM,
            )
        )
        form = ft.Container(
            content=ft.Column(controls=form_children, spacing=tokens.SPACE_SM, tight=True),
            padding=tokens.SPACE_LG,
            border_radius=tokens.RADIUS_LG,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            margin=ft.Margin(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_LG, 0),
        )

    return ft.Column(
        controls=[
            header,
            ft.Container(content=body, padding=tokens.SPACE_LG, expand=True) if not entries else ft.Container(content=body, padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_SM), expand=True),
            form,
            build_banner_ad(page),
        ],
        spacing=0,
        expand=True,
    )
