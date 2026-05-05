import flet as ft
from database.manager import db_manager

async def get_parent_portal_view(page: ft.Page):
    DEFAULT_PIN = "1234"
    
    # Fetch real stats from the database
    stats = await db_manager.get_parent_stats()
    
    # --- The Unlocked Dashboard ---
    dashboard_view = ft.Column(
        visible=False,
        expand=True,
        controls=[
            ft.Text("student overview", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
            ft.Divider(color=ft.Colors.BLACK),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("total quizzes taken:", size=16),
                    ft.Text(str(stats["total_quizzes"]), weight=ft.FontWeight.BOLD, size=16), 
                ]
            ),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("average score:", size=16),
                    ft.Text(stats["avg_score"], weight=ft.FontWeight.BOLD, size=16), 
                ]
            ),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("last active:", size=16),
                    ft.Text(str(stats["last_active"] or "Never"), weight=ft.FontWeight.BOLD, size=16), 
                ]
            ),
        ]
    )

    # --- The PIN Lock Screen ---
    pin_input = ft.TextField(
        password=True,
        can_reveal_password=True,
        hint_text="enter 4-digit pin",
        border_color=ft.Colors.BLACK,
        cursor_color=ft.Colors.BLACK,
        text_align=ft.TextAlign.CENTER,
        width=200
    )
    
    error_text = ft.Text("incorrect pin", color=ft.Colors.RED_700, visible=False)

    def verify_pin(e):
        if pin_input.value == DEFAULT_PIN:
            lock_screen.visible = False
            dashboard_view.visible = True
            page.update()
        else:
            error_text.visible = True
            page.update()

    lock_screen = ft.Column(
        visible=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        expand=True,
        controls=[
            ft.Icon(ft.Icons.LOCK_OUTLINE, size=60, color=ft.Colors.BLACK),
            ft.Text("parental gate", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
            ft.Container(height=10),
            pin_input,
            error_text,
            ft.FilledButton(
                "unlock",
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLACK, 
                    color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=4)
                ),
                on_click=verify_pin
            )
        ]
    )

    return ft.View(
        route="/parent",
        bgcolor=ft.Colors.WHITE,
        appbar=ft.AppBar(
            title=ft.Text("parent portal", color=ft.Colors.BLACK),
            bgcolor=ft.Colors.WHITE,
        ),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Stack(
                    controls=[lock_screen, dashboard_view]
                )
            )
        ]
    )