import flet as ft


class AppColors:

    PRIMARY = "#6366F1"
    SECONDARY = "#10B981"
    ACCENT = "#F59E0B"
    TERTIARY = "#8B5CF6"

    SUCCESS = "#10B981"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"

    GRAD_START = "#6366F1"
    GRAD_END = "#8B5CF6"

    DARK_BG = "#000000"
    DARK_SURFACE = "#111111"
    DARK_CARD = "#1A1A1A"
    DARK_TEXT = "#FFFFFF"
    DARK_TEXT_DIM = "#888888"

    LIGHT_BG = "#FFFFFF"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_CARD = "#FFFFFF"
    LIGHT_TEXT = "#111111"
    LIGHT_TEXT_DIM = "#666666"

    XP_GOLD = "#F59E0B"
    STREAK_FIRE = "#EF4444"
    BADGE_GLOW = "#8B5CF6"

    SUBJECT_COLORS = [
        "#6366F1",
        "#10B981",
        "#F59E0B",
        "#EF4444",
        "#3B82F6",
        "#8B5CF6",
        "#EC4899",
        "#14B8A6",
    ]


class AppTheme:

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                tertiary=AppColors.TERTIARY,
                surface=AppColors.DARK_BG,
                on_surface="#FFFFFF",
                surface_container="#111111",
                surface_container_highest="#1A1A1A",
                error=AppColors.ERROR,
            ),
            font_family="Outfit",
        )

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                tertiary=AppColors.TERTIARY,
                surface=AppColors.LIGHT_BG,
                on_surface="#111111",
                surface_container="#F5F5F5",
                surface_container_highest="#EEEEEE",
                error=AppColors.ERROR,
            ),
            font_family="Outfit",
        )
