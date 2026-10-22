"""App state — single global observable.

Ported from Sherlock's state pattern (the house standard).
All components read state via use_context(AppStateCtx) and mutate directly.
Collections are assigned in __init__ so Observable wraps them.
"""

from __future__ import annotations

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
    credits_remaining: int = 100
    credits_date: str = ""  # YYYY-MM-DD of last reset

    # Gamification
    xp_total: int = 0
    level: str = "Freshman"
    current_streak: int = 0
    best_streak: int = 0

    # Navigation
    selected_tab: int = 0
    current_course: dict | None = None
    current_module: dict | None = None
    current_assignment_id: int | None = None

    # Content
    courses: list[dict] = []
    courses_version: int = 0  # render token — bump after any store write
    modules: list[dict] = []

    # Assessments
    quiz_attempts: list[dict] = []
    attempts_version: int = 0  # render token for history/stats

    # Theme
    theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM

    # Connectivity
    is_online: bool = True
    update_available: bool = False
    update_data: dict | None = None

    # Premium (derived only — never persisted directly)
    is_premium: bool = False
    license_status: str = ""
    license_recovery_id: str = ""
    license_product: str = ""
    license_prices: dict = {}

    # AI / router
    ai_model: str = "auto"  # sent verbatim to the router
    ai_mode_enabled: bool = True
    reasoning_effort: str = "auto"  # auto|low|high; auto = param omitted
    router_status: str = "starting"  # starting|ready|stopped|unavailable
    router_port: int | None = None
    context_used_tokens: int = 0
    max_context_tokens: int = 131072
    model_catalog: list[dict] = []
    mcp_tools: list[str] = []

    # Tutor chat
    chat_open: bool = False
    chat_busy: bool = False

    # Injected by AppController
    credit_service: object | None = None

    # Quiz history lock (biometric gate)
    biometric_lock: bool = True
    history_unlocked: bool = False

    # Render token — bump to force re-render
    progress_version: int = 0

    def __init__(self):
        # Assign collections here so Observable wraps them
        self.metadata = {}
        self.education_levels = []
        self.current_course = None
        self.current_module = None
        self.current_assignment_id = None
        self.courses = []
        self.modules = []
        self.quiz_attempts = []
        self.model_catalog = []
        self.mcp_tools = []
        self.license_prices = {}
        self.credit_service = None

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


state = AppState()
