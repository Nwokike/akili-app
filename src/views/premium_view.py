import flet as ft

from core.theme import AppColors, AppStyles


def build_premium_view(page: ft.Page, navigate) -> ft.View:
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(navigate, "/dashboard"),
            ),
            ft.Text("Akili Premium", size=20, weight=ft.FontWeight.BOLD),
        ], spacing=4),
        padding=ft.Padding(4, 16, 16, 8),
    )

    content = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.STAR_ROUNDED, size=72, color=AppColors.ACCENT),
                ft.Container(height=16),
                ft.Text("Go Premium", size=26, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Unlock the full power of AI for your learning journey.",
                    size=15, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER
                ),
                ft.Container(height=32),
                
                # Feature List
                ft.Column([
                    _feature_item("1000 Daily AI Credits"),
                    _feature_item("Ad-Free Experience"),
                    _feature_item("Priority Tutor Responses"),
                    _feature_item("Unlimited Course Generations"),
                ], spacing=16),
                
                ft.Container(height=40),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("$4.99 / month", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text("Coming Soon!", size=14, color=ft.Colors.WHITE_70),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=24, border_radius=AppStyles.RADIUS,
                    gradient=ft.LinearGradient(
                        colors=[AppColors.PRIMARY, AppColors.TERTIARY]
                    ),
                    width=float("inf"),
                ),
                
                ft.Container(height=16),
                ft.TextButton(
                    "Notify me when available",
                    on_click=lambda e: _notify(page),
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=32,
            expand=True,
            alignment=ft.Alignment.CENTER
        )
    ], expand=True, spacing=0, scroll=ft.ScrollMode.AUTO)

    return ft.View(
        route="/premium",
        controls=[ft.SafeArea(content, expand=True)],
        padding=0, spacing=0,
    )

def _feature_item(text: str) -> ft.Control:
    return ft.Row([
        ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppColors.SUCCESS, size=24),
        ft.Text(text, size=16, weight=ft.FontWeight.W_500),
    ], spacing=12)

def _notify(page):
    page.snack_bar = ft.SnackBar(
        ft.Text("We'll let you know when Premium launches!", color=ft.Colors.WHITE),
        bgcolor=AppColors.PRIMARY,
    )
    page.snack_bar.open = True
    page.update()
