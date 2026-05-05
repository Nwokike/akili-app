import flet as ft
from database.manager import db_manager

async def get_quiz_history_view(page: ft.Page):
    # Fetch real history from the database
    history_data = await db_manager.get_quiz_history()

    history_list = ft.ListView(expand=True, spacing=10, padding=20)

    def populate_list(search_term=""):
        history_list.controls.clear()
        
        if not history_data:
            history_list.controls.append(
                ft.Container(
                    content=ft.Text("no quiz history yet.", color=ft.Colors.BLACK_54),
                    alignment=ft.Alignment.CENTER,
                    padding=20
                )
            )
        else:
            for item in history_data:
                if search_term.lower() in item["course"].lower():
                    history_list.controls.append(
                        ft.Container(
                            border=ft.border.all(1, ft.Colors.BLACK),
                            border_radius=4,
                            padding=10,
                            content=ft.ListTile(
                                title=ft.Text(item["course"], weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                                subtitle=ft.Text(item["date"], color=ft.Colors.BLACK_54),
                                trailing=ft.Text(item["score"], weight=ft.FontWeight.BOLD, size=18, color=ft.Colors.BLACK)
                            )
                        )
                    )
        page.update()

    search_bar = ft.TextField(
        hint_text="search courses...",
        prefix_icon=ft.Icons.SEARCH,
        border_color=ft.Colors.BLACK,
        cursor_color=ft.Colors.BLACK,
        color=ft.Colors.BLACK,
        on_change=lambda e: populate_list(e.control.value)
    )

    populate_list() # Initial load

    return ft.View(
        route="/history",
        bgcolor=ft.Colors.WHITE,
        appbar=ft.AppBar(
            title=ft.Text("quiz history", color=ft.Colors.BLACK),
            bgcolor=ft.Colors.WHITE,
        ),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    controls=[
                        ft.Container(content=search_bar, padding=ft.padding.symmetric(horizontal=20, vertical=10)),
                        history_list
                    ]
                )
            )
        ]
    )