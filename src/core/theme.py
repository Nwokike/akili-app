import flet as ft


class AppColors:
    # Premium Bluish Minimalist Palette
    # Using Indigo/Royal Blue which is "absolutely beautiful"
    PRIMARY = "#4F46E5"    # Indigo 600
    SECONDARY = "#4338CA"  # Indigo 700
    ACCENT = "#F59E0B"     # Amber 500 (Gold) - Complements Blue
    
    SUCCESS = "#10B981"    # Emerald (Keep for success)
    WARNING = "#F59E0B"
    ERROR = "#EF4444"

    # Minimalist Backgrounds
    DARK_BG = "#000000"
    DARK_SURFACE = "#0A0A0A"
    DARK_CARD = "#121212"
    DARK_TEXT = "#FFFFFF"
    DARK_TEXT_DIM = "#A0A0A0"

    LIGHT_BG = "#FFFFFF"
    LIGHT_SURFACE = "#F8F8F8"
    LIGHT_CARD = "#FFFFFF"
    LIGHT_TEXT = "#000000"
    LIGHT_TEXT_DIM = "#666666"

    # Subject colors - muted and harmonious with blue
    SUBJECT_COLORS = [
        "#4F46E5", "#06B6D4", "#10B981", "#EAB308",
        "#8B5CF6", "#EC4899", "#F97316", "#3B82F6",
    ]


class AppStyles:
    RADIUS_SMALL = 8
    RADIUS = 12
    RADIUS_LARGE = 20

    PADDING_SMALL = 8
    PADDING = 16
    PADDING_LARGE = 24

    @staticmethod
    def glass_card(content: ft.Control, blur_sigma: int = 10):
        """Minimalist glass card - very subtle."""
        return ft.Container(
            content=content,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            blur=ft.Blur(blur_sigma, blur_sigma, ft.BlurTileMode.MIRROR),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.WHITE)),
            border_radius=AppStyles.RADIUS,
        )

    @staticmethod
    def brand_gradient():
        """Very subtle background gradient using the new blue."""
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER,
            end=ft.Alignment.BOTTOM_CENTER,
            colors=[
                ft.Colors.with_opacity(0.05, AppColors.PRIMARY),
                ft.Colors.TRANSPARENT,
            ],
        )


class AppTheme:

    @staticmethod
    def get_dark_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                surface=AppColors.DARK_BG,
                on_surface=AppColors.DARK_TEXT,
                surface_container=AppColors.DARK_SURFACE,
                surface_container_highest=AppColors.DARK_CARD,
                on_surface_variant=AppColors.DARK_TEXT_DIM,
                error=AppColors.ERROR,
            ),
            font_family="Inter",
            visual_density=ft.VisualDensity.COMFORTABLE,
        )

    @staticmethod
    def get_light_theme() -> ft.Theme:
        return ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                surface=AppColors.LIGHT_BG,
                on_surface=AppColors.LIGHT_TEXT,
                surface_container=AppColors.LIGHT_SURFACE,
                surface_container_highest=AppColors.LIGHT_CARD,
                on_surface_variant=AppColors.LIGHT_TEXT_DIM,
                error=AppColors.ERROR,
            ),
            font_family="Inter",
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
