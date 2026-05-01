import flet as ft


@ft.observable
class AppState:
    """Reactive app state — KTV @ft.observable pattern."""

    # User profile
    user_name: str = ""
    education_level: str = ""
    avatar_index: int = 0
    is_onboarded: bool = False

    # Loading / status
    is_loading: bool = False
    status_message: str = ""

    # Credits (daily)
    credits_remaining: int = 150
    credits_date: str = ""  # YYYY-MM-DD of last reset

    # Gamification
    xp_total: int = 0
    level: str = "Freshman"
    current_streak: int = 0
    best_streak: int = 0

    # Navigation
    current_course: dict | None = None
    current_module: dict | None = None

    # Theme
    theme_mode: ft.ThemeMode = ft.ThemeMode.DARK

    def __init__(self):
        self.current_course = None
        self.current_module = None

    def get_level_progress(self) -> float:
        """Progress toward next level (0.0 to 1.0)."""
        from core.constants import LEVELS

        current_idx = 0
        for i, lvl in enumerate(LEVELS):
            if lvl["name"] == self.level:
                current_idx = i
                break

        if current_idx >= len(LEVELS) - 1:
            return 1.0

        current_xp_threshold = LEVELS[current_idx]["xp"]
        next_xp_threshold = LEVELS[current_idx + 1]["xp"]
        progress_range = next_xp_threshold - current_xp_threshold

        if progress_range <= 0:
            return 1.0

        return min(1.0, (self.xp_total - current_xp_threshold) / progress_range)


state = AppState()
