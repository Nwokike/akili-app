import asyncio

import flet as ft

from core.state import state


def build_splash_view(page: ft.Page, navigate) -> ft.View:
    logo = ft.Image(
        src="/icon.png", width=72, height=72,
        animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_OUT),
        opacity=0,
    )

    tagline = ft.Text(
        "learn smarter with ai",
        size=13, color=ft.Colors.ON_SURFACE_VARIANT,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN),
        opacity=0,
    )

    async def _animate():
        logo.opacity = 1
        page.update()
        await asyncio.sleep(0.6)

        tagline.opacity = 1
        page.update()
        await asyncio.sleep(1.2)

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
                    ft.Container(height=12),
                    tagline,
                    ft.Container(expand=3),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True,
                alignment=ft.Alignment.CENTER,
            )
        ],
        padding=0, spacing=0,
    )
