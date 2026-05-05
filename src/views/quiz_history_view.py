import flet as ft

from core.theme import AppColors
from database.manager import db_manager


async def build_quiz_history_view(page: ft.Page, navigate) -> ft.View:
    history = await db_manager.get_quiz_history()
    
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/progress"),
            ),
            ft.Text("Quiz History", size=20, weight=ft.FontWeight.BOLD),
        ], spacing=4),
        padding=ft.Padding(4, 16, 16, 8),
    )

    history_col = ft.Column(spacing=0, expand=True)
    
    if not history:
        history_col.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.HISTORY, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=8),
                    ft.Text("No quizzes taken yet", size=16, weight=ft.FontWeight.W_600),
                    ft.Text("Complete a module quiz to see your history here.", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True, alignment=ft.Alignment.CENTER, padding=32
            )
        )
    else:
        for item in history:
            score_pct = (item["score"] / item["total"]) * 100 if item["total"] > 0 else 0
            passed = item["passed"] == 1
            
            icon = ft.Icons.CHECK_CIRCLE if passed else ft.Icons.CANCEL
            icon_color = AppColors.SUCCESS if passed else AppColors.ERROR
            
            card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon, color=icon_color, size=24),
                        width=48, height=48, border_radius=24,
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        alignment=ft.Alignment.CENTER
                    ),
                    ft.Container(width=12),
                    ft.Column([
                        ft.Text(item["module_title"], size=15, weight=ft.FontWeight.W_600),
                        ft.Text(item["course_subject"], size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(item["timestamp"][:16], size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2, expand=True),
                    ft.Column([
                        ft.Text(f"{int(score_pct)}%", size=18, weight=ft.FontWeight.BOLD, color=icon_color),
                        ft.Text(f"{item['score']}/{item['total']}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=0)
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(16, 12, 16, 12),
            )
            history_col.controls.append(card)
            history_col.controls.append(ft.Divider(height=1, thickness=0.3))

    content = ft.Column([
        header,
        ft.Container(
            content=history_col,
            expand=True,
        )
    ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

    return ft.View(
        route="/quiz-history",
        controls=[ft.SafeArea(content, expand=True)],
        padding=0, spacing=0,
    )
