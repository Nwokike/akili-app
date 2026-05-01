"""Animated splash screen — Akili branding."""

import flet as ft

from core.theme import AppColors


def build_splash_view(page: ft.Page, navigate) -> ft.View:
    """Premium splash with animated logo and gradient background."""

    # Animated icon scale
    logo_icon = ft.Image(
        src="/icon.png",
        width=72,
        height=72,
    )

    logo_container = ft.Container(
        content=logo_icon,
        width=120,
        height=120,
        border_radius=30,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[AppColors.PRIMARY, AppColors.TERTIARY],
        ),
        alignment=ft.Alignment.CENTER,
        animate_scale=ft.Animation(600, ft.AnimationCurve.EASE_OUT_BACK),
        scale=0,
    )

    title_text = ft.Text(
        "Akili",
        size=42,
        weight=ft.FontWeight.BOLD,
        color=AppColors.PRIMARY,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN),
        opacity=0,
    )

    subtitle_text = ft.Text(
        "Learn Smarter with AI",
        size=16,
        color=ft.Colors.ON_SURFACE_VARIANT,
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN),
        opacity=0,
    )

    loading_ring = ft.ProgressRing(
        width=24,
        height=24,
        stroke_width=3,
        color=AppColors.PRIMARY,
        animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_IN),
        opacity=0,
    )

    async def animate_and_navigate():
        import asyncio

        # Stagger animations
        logo_container.scale = 1
        page.update()
        await asyncio.sleep(0.4)

        title_text.opacity = 1
        page.update()
        await asyncio.sleep(0.3)

        subtitle_text.opacity = 1
        page.update()
        await asyncio.sleep(0.3)

        loading_ring.opacity = 1
        page.update()
        await asyncio.sleep(1.0)

        # Navigate based on onboarding status
        from core.state import state
        if state.is_onboarded:
            await navigate("/dashboard")
        else:
            await navigate("/onboarding")

    # Trigger animation after view loads
    page.run_task(animate_and_navigate)

    return ft.View(
        route="/splash",
        controls=[
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(expand=2),
                        logo_container,
                        ft.Container(height=20),
                        title_text,
                        ft.Container(height=8),
                        subtitle_text,
                        ft.Container(expand=2),
                        loading_ring,
                        ft.Container(height=40),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                expand=True,
                alignment=ft.Alignment.CENTER,
            )
        ],
        padding=0,
        spacing=0,
    )
