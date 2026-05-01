import flet as ft


class AppColors:
    """Akili brand palette — premium education aesthetic."""

    # Branding
    PRIMARY = "#6366F1"       # Indigo — trust, intelligence
    SECONDARY = "#10B981"     # Emerald — growth, success
    ACCENT = "#F59E0B"        # Amber — energy, achievement
    TERTIARY = "#8B5CF6"      # Violet — creativity

    # Functional
    SUCCESS = "#10B981"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    INFO = "#3B82F6"

    # Gradients (for premium glassmorphism)
    GRAD_START = "#6366F1"
    GRAD_END = "#8B5CF6"

    # Dark mode
    DARK_BG = "#0F172A"       # Slate 900
    DARK_SURFACE = "#1E293B"  # Slate 800
    DARK_CARD = "#1E293B"
    DARK_TEXT = "#F8FAFC"
    DARK_TEXT_DIM = "#94A3B8"

    # Light mode
    LIGHT_BG = "#F8FAFC"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_CARD = "#FFFFFF"
    LIGHT_TEXT = "#0F172A"
    LIGHT_TEXT_DIM = "#64748B"

    # XP / Gamification
    XP_GOLD = "#F59E0B"
    STREAK_FIRE = "#EF4444"
    BADGE_GLOW = "#8B5CF6"

    # Subject colors (for course cards)
    SUBJECT_COLORS = [
        "#6366F1",  # Indigo
        "#10B981",  # Emerald
        "#F59E0B",  # Amber
        "#EF4444",  # Red
        "#3B82F6",  # Blue
        "#8B5CF6",  # Violet
        "#EC4899",  # Pink
        "#14B8A6",  # Teal
    ]


class AppTheme:
    """Theme configuration matching original Akili design."""

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                tertiary=AppColors.TERTIARY,
                surface=AppColors.DARK_BG,
                surface_container=AppColors.DARK_SURFACE,
                on_surface=AppColors.DARK_TEXT,
                on_surface_variant=AppColors.DARK_TEXT_DIM,
                error=AppColors.ERROR,
                on_primary=ft.Colors.WHITE,
                on_secondary=ft.Colors.BLACK,
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
                surface_container=AppColors.LIGHT_SURFACE,
                on_surface=AppColors.LIGHT_TEXT,
                on_surface_variant=AppColors.LIGHT_TEXT_DIM,
                error=AppColors.ERROR,
                on_primary=ft.Colors.WHITE,
                on_secondary=ft.Colors.BLACK,
            ),
            font_family="Outfit",
        )
