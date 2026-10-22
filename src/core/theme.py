"""Theming — AppColors, adaptive getters, AppStyles, AppTheme.

Ported from Sherlock's theme system (the house standard).
Brand colors are static; everything else resolves via is_dark_mode + getters.
"""

from __future__ import annotations

import flet as ft


def is_dark_mode(page: ft.Page | None = None) -> bool:
    """True when the effective theme is dark.

    Resolves page from flet.context.page when omitted. Returns True when
    page is None (safe default for tests / pre-mount).
    """
    if page is None:
        try:
            from flet import context as flet_context

            page = flet_context.page
        except Exception:
            return True
    if page is None:
        return True
    return page.theme_mode == ft.ThemeMode.DARK or (page.theme_mode == ft.ThemeMode.SYSTEM and page.platform_brightness == ft.Brightness.DARK)


class AppColors:
    """Brand + status colors. Adaptive getters resolve via is_dark_mode."""

    # Brand
    PRIMARY = "#6C5CE7"
    PRIMARY_LIGHT = "#A29BFE"
    PRIMARY_DARK = "#4A3DB8"
    ACCENT = "#00B894"

    # Status
    SUCCESS = "#2E7D32"
    WARNING = "#F9A825"
    ERROR = "#D32F2F"
    GREY = "#9E9E9E"

    # Terminal
    TERMINAL_BG = "#0D0D0D"
    TERMINAL_GREEN = "#A6E22E"
    TERMINAL_TEXT = "#ECEFF1"

    # Dark ramp
    DARK_BG_1 = "#0F1114"
    DARK_BG_2 = "#121518"
    DARK_SURFACE = "#1A1D22"
    DARK_SURFACE_2 = "#252A30"
    DARK_BORDER = "#2E3339"
    DARK_TEXT = "#ECEFF1"
    DARK_TEXT_DIM = "#90A4AE"

    # Light ramp
    LIGHT_BG = "#FAFAFA"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_SURFACE_2 = "#F5F5F5"
    LIGHT_BORDER = "#E0E0E0"
    LIGHT_TEXT = "#000000"
    LIGHT_TEXT_DIM = "#424242"

    @staticmethod
    def _resolve_page(page: ft.Page | None = None) -> ft.Page | None:
        if page is None:
            try:
                from flet import context as flet_context

                page = flet_context.page
            except Exception:
                return None
        return page

    @staticmethod
    def get_bg(page: ft.Page | None = None) -> str:
        return AppColors.DARK_BG_1 if is_dark_mode(page) else AppColors.LIGHT_BG

    @staticmethod
    def get_surface(page: ft.Page | None = None) -> str:
        return AppColors.DARK_SURFACE if is_dark_mode(page) else AppColors.LIGHT_SURFACE

    @staticmethod
    def get_surface_2(page: ft.Page | None = None) -> str:
        return AppColors.DARK_SURFACE_2 if is_dark_mode(page) else AppColors.LIGHT_SURFACE_2

    @staticmethod
    def get_border(page: ft.Page | None = None) -> str:
        return AppColors.DARK_BORDER if is_dark_mode(page) else AppColors.LIGHT_BORDER

    @staticmethod
    def get_text(page: ft.Page | None = None) -> str:
        return AppColors.DARK_TEXT if is_dark_mode(page) else AppColors.LIGHT_TEXT

    @staticmethod
    def get_text_dim(page: ft.Page | None = None) -> str:
        return AppColors.DARK_TEXT_DIM if is_dark_mode(page) else AppColors.LIGHT_TEXT_DIM

    @staticmethod
    def grey_dim(page: ft.Page | None = None) -> str:
        return AppColors.DARK_TEXT_DIM if is_dark_mode(page) else "#555555"


class AppStyles:
    """Reusable container styles."""

    RADIUS_SMALL = 8
    RADIUS = 12
    RADIUS_LARGE = 20

    @staticmethod
    def section_card(
        title: str,
        icon: ft.IconData,
        content: list[ft.Control],
        page: ft.Page | None = None,
    ) -> ft.Container:
        card_bg = AppColors.get_surface(page)
        border_color = AppColors.get_border(page)
        header = ft.Row(
            controls=[
                ft.Icon(icon, color=AppColors.PRIMARY, size=20),
                ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        )
        items = [header]
        for i, ctrl in enumerate(content):
            if i > 0:
                items.append(
                    ft.Divider(
                        height=1,
                        color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                        leading_indent=44,
                    )
                )
            items.append(ctrl)
        return ft.Container(
            content=ft.Column(controls=items, spacing=0),
            bgcolor=card_bg,
            border=ft.Border.all(1, border_color),
            border_radius=16,
            padding=ft.Padding(16, 12, 16, 12),
        )

    @staticmethod
    def glass_card(
        content: ft.Control,
        page: ft.Page | None = None,
    ) -> ft.Container:
        is_dark = is_dark_mode(page)
        bg = ft.Colors.with_opacity(0.05, ft.Colors.WHITE if is_dark else ft.Colors.BLACK)
        border = ft.Colors.with_opacity(0.10, ft.Colors.WHITE if is_dark else ft.Colors.BLACK)
        return ft.Container(
            content=content,
            bgcolor=bg,
            border=ft.Border.all(1, border),
            border_radius=16,
            padding=16,
        )

    @staticmethod
    def brand_gradient(page: ft.Page | None = None) -> list[str]:
        return [AppColors.DARK_BG_1, AppColors.DARK_BG_2] if is_dark_mode(page) else ["#F5F5F5", AppColors.LIGHT_BG]


class AppTheme:
    """Full Flet Theme builder."""

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                on_primary=ft.Colors.WHITE,
                primary_container=AppColors.PRIMARY_LIGHT,
                on_primary_container=ft.Colors.WHITE,
                secondary=AppColors.ACCENT,
                on_secondary=ft.Colors.WHITE,
                surface=AppColors.LIGHT_SURFACE,
                on_surface=AppColors.LIGHT_TEXT,
                on_surface_variant=AppColors.LIGHT_TEXT_DIM,
                surface_container=AppColors.LIGHT_SURFACE_2,
                surface_container_highest=AppColors.LIGHT_SURFACE_2,
                outline=AppColors.LIGHT_BORDER,
                error=AppColors.ERROR,
                on_error=ft.Colors.WHITE,
            ),
            font_family="Outfit",
            visual_density=ft.VisualDensity.COMFORTABLE,
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.FADE_UPWARDS,
                ios=ft.PageTransitionTheme.CUPERTINO,
            ),
        )

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                on_primary=ft.Colors.WHITE,
                primary_container=AppColors.PRIMARY_DARK,
                on_primary_container=ft.Colors.WHITE,
                secondary=AppColors.ACCENT,
                on_secondary=ft.Colors.WHITE,
                surface=AppColors.DARK_SURFACE,
                on_surface=AppColors.DARK_TEXT,
                on_surface_variant=AppColors.DARK_TEXT_DIM,
                surface_container=AppColors.DARK_SURFACE_2,
                surface_container_highest=AppColors.DARK_SURFACE_2,
                outline=AppColors.DARK_BORDER,
                error=AppColors.ERROR,
                on_error=ft.Colors.WHITE,
            ),
            font_family="Outfit",
            visual_density=ft.VisualDensity.COMFORTABLE,
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.FADE_UPWARDS,
                ios=ft.PageTransitionTheme.CUPERTINO,
            ),
        )
