import contextlib

import flet as ft


@ft.observable
class AppState:
    # User profile
    user_name: str = ""
    education_level: str = ""
    country: str = "Global"
    avatar_index: int = 0
    is_onboarded: bool = False

    # Metadata for dynamic UI (subjects, education levels, etc.)
    metadata: dict = {}
    education_levels: list[dict] = []

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
    current_assignment_id: int | None = None

    # Theme
    theme_mode: ft.ThemeMode = ft.ThemeMode.LIGHT

    # AI Search Settings
    search_region: str = "wt-wt"
    safesearch_level: str = "on"

    # Connectivity
    is_online: bool = True

    def __init__(self):
        self.current_course = None
        self.current_module = None
        self.metadata = {}
        self.education_levels = []

    def get_level_progress(self) -> float:
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

    _on_online_change_listeners = []

    def add_online_listener(self, listener):
        if listener not in self._on_online_change_listeners:
            self._on_online_change_listeners.append(listener)

    def update_online_state(self, is_online: bool):
        if self.is_online != is_online:
            self.is_online = is_online
            for listener in self._on_online_change_listeners:
                with contextlib.suppress(Exception):
                    listener(is_online)


state = AppState()


async def check_internet_connection() -> bool:
    """Active, lightweight internet reachability verification to Akili API Gateway."""
    import httpx

    from core.constants import API_GATEWAY

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Reaching gateway URL with short timeout is a true test of DNS + network access
            await client.get(API_GATEWAY, follow_redirects=True)
            return True
    except Exception:
        return False
