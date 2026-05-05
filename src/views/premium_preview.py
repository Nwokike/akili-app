import flet as ft
from core.theme import AppColors, AppStyles

def get_premium_preview_view(page: ft.Page):
    # We use a PageView for the swipeable carousel
    carousel = ft.PageView(
        expand=True,
        horizontal=True,
        # Snaps exactly to the bounds of the page after a drag
        snap=True,
        controls=[
            # Slide 1: No Ads
            ft.Container(
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.BLOCK, size=80, color=ft.Colors.ON_SURFACE),
                        ft.Text("ad-free experience", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("focus on learning without any interruptions.", text_align=ft.TextAlign.CENTER),
                    ]
                )
            ),
            # Slide 2: 10x Credits
            ft.Container(
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.BOLT, size=80, color=ft.Colors.ON_SURFACE),
                        ft.Text("10x daily credits", size=24, weight=ft.FontWeight.BOLD),
                        ft.Text("take more mock exams and quizzes every single day.", text_align=ft.TextAlign.CENTER),
                    ]
                )
            ),
            # Slide 3: CTA
            ft.Container(
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ROCKET_LAUNCH, size=80, color=ft.Colors.ON_SURFACE),
                        ft.Text("premium is coming soon", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(height=20),
                        ft.FilledButton(
                            "notify me when it's ready",
                            style=ft.ButtonStyle(
                                bgcolor=AppColors.PRIMARY, 
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS)
                            ),
                            on_click=lambda e: page.show_snack_bar(
                                ft.SnackBar(content=ft.Text("you're on the list!"))
                            )
                        )
                    ]
                )
            )
        ]
    )

    return ft.View(
        route="/premium",
        appbar=ft.AppBar(
            title=ft.Text("premium"),
        ),
        controls=[
            ft.SafeArea(
                expand=True,
                content=carousel
            )
        ]
    )