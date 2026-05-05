import flet as ft

from core.theme import AppColors, AppStyles
from database.manager import db_manager

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def build_timetable_view(page: ft.Page, navigate) -> ft.View:
    entries = await db_manager.get_timetable()

    day_field = ft.Dropdown(
        label="Day", border_radius=AppStyles.RADIUS,
        options=[ft.dropdown.Option(d) for d in DAYS],
    )
    time_field = ft.TextField(
        label="Time", hint_text="e.g. 09:00",
        border_radius=AppStyles.RADIUS, filled=True,
    )
    subject_field = ft.TextField(
        label="Subject", hint_text="e.g. Mathematics",
        border_radius=AppStyles.RADIUS, filled=True,
    )

    entries_col = ft.Column(spacing=0, expand=True)

    def _refresh_list():
        entries_col.controls.clear()
        current_day = ""
        for entry in entries:
            if entry["day"] != current_day:
                current_day = entry["day"]
                entries_col.controls.append(
                    ft.Container(
                        content=ft.Text(
                            current_day, size=13,
                            weight=ft.FontWeight.BOLD,
                            color=AppColors.PRIMARY,
                        ),
                        padding=ft.Padding(16, 16, 0, 4),
                    )
                )
            entries_col.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(entry["time_slot"], size=13, weight=ft.FontWeight.W_600, width=60),
                        ft.Text(entry["subject"], size=14, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE, icon_size=16,
                            on_click=lambda e, eid=entry["id"]: page.run_task(_delete, eid),
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding(16, 8, 4, 8),
                )
            )
            entries_col.controls.append(ft.Divider(height=1, thickness=0.3))

        if not entries:
            entries_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Container(height=40),
                        ft.Text("No schedule yet", size=16, weight=ft.FontWeight.W_600),
                        ft.Text(
                            "Add your first class below",
                            size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    alignment=ft.Alignment.CENTER,
                )
            )

    _refresh_list()

    async def _add(e):
        day = day_field.value
        time_val = time_field.value.strip()
        subj = subject_field.value.strip()
        if not day or not time_val or not subj:
            return
        await db_manager.add_timetable_entry(day, time_val, subj)
        entries.clear()
        entries.extend(await db_manager.get_timetable())
        day_field.value = None
        time_field.value = ""
        subject_field.value = ""
        _refresh_list()
        page.update()

    async def _delete(entry_id):
        await db_manager.delete_timetable_entry(entry_id)
        entries.clear()
        entries.extend(await db_manager.get_timetable())
        _refresh_list()
        page.update()

    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/dashboard"),
            ),
            ft.Text("Timetable", size=20, weight=ft.FontWeight.BOLD),
        ], spacing=4),
        padding=ft.Padding(4, 16, 16, 8),
    )

    add_section = ft.Container(
        content=ft.Column([
            ft.Text("Add Class", size=14, weight=ft.FontWeight.W_600),
            ft.Row([day_field, time_field], spacing=8),
            ft.Row([
                subject_field,
                ft.IconButton(
                    icon=ft.Icons.ADD, icon_size=24,
                    bgcolor=AppColors.PRIMARY,
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda e: page.run_task(_add),
                ),
            ], spacing=8),
        ], spacing=8),
        padding=ft.Padding(20, 12, 20, 12),
    )

    return ft.View(
        route="/timetable",
        controls=[ft.SafeArea(
            ft.Column([
                header,
                ft.Container(content=entries_col, expand=True),
                ft.Divider(height=1, thickness=0.5),
                add_section,
            ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0),
            expand=True,
        )],
        padding=0, spacing=0,
    )
