import flet as ft
from database.manager import db_manager
from core.theme import AppColors, AppStyles

async def get_quiz_history_view(page: ft.Page):
    history_data = await db_manager.get_quiz_history()
    history_list = ft.ListView(expand=True, spacing=12, padding=0)

    def populate_list(search_term=""):
        history_list.controls.clear()
        if not history_data:
            history_list.controls.append(
                ft.Container(
                    content=ft.Text("No history found", color=ft.Colors.ON_SURFACE_VARIANT),
                    alignment=ft.Alignment.CENTER, padding=40,
                )
            )
        else:
            for item in history_data:
                if search_term.lower() in item["course"].lower():
                    score_pct = int(item.get("score_pct", 0))
                    color = AppColors.SUCCESS if score_pct >= 60 else AppColors.ERROR
                    
                    history_list.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(f"{score_pct}%", size=14, weight=ft.FontWeight.BOLD, color=color),
                                    width=44, height=44, border_radius=22,
                                    bgcolor=ft.Colors.with_opacity(0.05, color),
                                    alignment=ft.Alignment.CENTER,
                                ),
                                ft.Column([
                                    ft.Text(item["course"], weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text(item["date"], size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ], spacing=2, expand=True),
                                ft.Text(item["score"], weight=ft.FontWeight.W_500, size=15),
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=16,
                            border_radius=AppStyles.RADIUS,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        )
                    )
        page.update()

    search_bar = ft.TextField(
        hint_text="Search courses...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        border_radius=AppStyles.RADIUS,
        filled=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        on_change=lambda e: populate_list(e.control.value)
    )

    populate_list()

    return ft.View(
        route="/history",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Row([
                                ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.views.pop() or page.update()),
                                ft.Text("Quiz History", size=20, weight=ft.FontWeight.BOLD),
                            ], spacing=4),
                            padding=ft.Padding(4, 8, 16, 8),
                        ),
                        ft.Container(
                            content=ft.Column([
                                search_bar,
                                ft.Container(height=10),
                                history_list,
                            ], expand=True),
                            padding=20,
                            expand=True,
                        ),
                    ], spacing=0, expand=True),
                    bgcolor=ft.Colors.SURFACE,
                    expand=True,
                ),
                expand=True,
            )
        ],
        padding=0, spacing=0,
    )