import asyncio
import flet as ft

from core.state import state
from core.theme import AppColors


def build_splash_view(page: ft.Page, navigate) -> ft.View:
    logo = ft.Image(
        src="/icon.png", width=96, height=96,
        animate_opacity=ft.Animation(800, ft.AnimationCurve.EASE_OUT),
        opacity=0,
    )

    tagline = ft.Text(
        "Learn Smarter with Akili",
        size=16, weight=ft.FontWeight.W_500, color=AppColors.PRIMARY,
        animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN),
        opacity=0,
    )

    async def _animate():
        await asyncio.sleep(0.2)
        logo.opacity = 1
        logo.update()
        await asyncio.sleep(0.4)

        tagline.opacity = 1
        tagline.update()
        await asyncio.sleep(1.5)

        if state.is_onboarded:
            await navigate("/dashboard")
        else:
            await navigate("/onboarding")

    page.run_task(_animate)

    return ft.View(
        route="/splash",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Container(expand=2),
                    logo,
                    ft.Container(height=20),
                    tagline,
                    ft.Container(height=40),
                    ft.ProgressRing(width=24, height=24, stroke_width=3, color=AppColors.PRIMARY),
                    ft.Container(expand=3),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[ft.Colors.SURFACE, ft.Colors.with_opacity(0.1, AppColors.PRIMARY)],
                ),
                alignment=ft.Alignment.CENTER,
            )
        ],
        padding=0, spacing=0,
    )
