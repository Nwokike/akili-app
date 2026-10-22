"""AppController — owns all services, loads state, mounts the declarative UI.

Ported from Sherlock/DDGS controller pattern (the house standard).
The controller never imports UI; the shell injects navigation closures.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import flet as ft

from core.constants import (
    APP_NAME,
    STORAGE_AI_MODEL,
    STORAGE_MCP_SERVERS,
    STORAGE_ONBOARDING_DONE,
    STORAGE_PROFILE,
    STORAGE_THEME,
)
from core.state import state
from core.theme import AppTheme
from services.course_store import init_course_store
from services.credit_service import init_credit_service
from services.gamification import init_gamification
from services.storage import StorageService
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx

logger = logging.getLogger("AppController")


class AppController:
    """Owns all services and business logic. Mounts the declarative UI."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.storage: StorageService | None = None
        self.connectivity: ft.Connectivity | None = None
        self.credit_service = None
        self.mcp_hub = None
        self.course_store = None
        self.gamification = None
        self.premium = None
        self.ad_service = None
        self._reminder_task = None
        self._current_tasks: dict[str, object] = {}

    async def init(self):
        """Initialize page, services, load persisted state, mount UI."""
        # ── Page setup ──
        self.page.title = f"{APP_NAME} — After-School Learning App"
        self.page.fonts = {"Outfit": "assets/outfit.css"}
        self.page.theme = AppTheme.get_light_theme()
        self.page.dark_theme = AppTheme.get_dark_theme()
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.padding = 0
        self.page.spacing = 0

        # Global error handler
        def on_error(e):
            logger.error("Page error: %s", e.data)

        self.page.on_error = on_error

        # ── Connectivity ──
        connectivity = ft.Connectivity()
        self.connectivity = connectivity
        self.page.services.append(connectivity)
        connectivity.on_change = self._on_connectivity_change
        self.page.on_app_lifecycle_state_change = self._on_lifecycle_change
        self.page.run_task(self._init_connectivity)

        # ── Services ──
        self.storage = StorageService(self.page)
        await self.storage.initialize()
        self.page._akili_storage = self.storage

        # ── Storage tiers: temp sweep + tiktoken cache home ──
        try:
            import os

            from core.storage_paths import cache_dir, clear_temp

            removed = await __import__("asyncio").to_thread(clear_temp)
            if removed:
                logger.info("cleared %d temp entries at startup", removed)
            tiktoken_home = str(cache_dir() / "tiktoken_cache")
            os.makedirs(tiktoken_home, exist_ok=True)
            os.environ.setdefault("TIKTOKEN_CACHE_DIR", tiktoken_home)
        except Exception as exc:
            logger.debug("storage tier setup skipped: %s", exc)

        # ── AI: credit economy (balance loads; cap re-checks after premium) ──
        self.credit_service = init_credit_service(self.storage)
        state.credit_service = self.credit_service
        state.credits_remaining = await self.credit_service.initialize()

        # ── Premium FIRST: the offline verdict decides the credit cap ──
        # The daily reset inside credits init above may have used the free
        # cap; if premium proves out, _grant_premium_benefits tops up.
        from services.premium_service import PremiumService

        self.premium = PremiumService(self.page, self.storage)
        self.page.premium = self.premium
        was_premium = False
        try:
            await self.premium.load_local()
            was_premium = state.is_premium
            state.license_recovery_id = await self.premium.license.recovery_id()
        except Exception:
            logger.warning("offline licence check failed", exc_info=True)
        if state.is_premium and not was_premium:
            with contextlib.suppress(Exception):
                await self.premium._grant_premium_benefits(first_time=True)

        # ── Ads (only when not premium) ──
        from services.ad_service import AdService

        self.ad_service = AdService(self.page)
        state.ad_service = self.ad_service
        if not state.is_premium:
            await self.ad_service.gather_consent()
            await self.ad_service.preload_interstitial()

        # ── Content + engagement ──
        self.course_store = init_course_store(self.storage)
        await self.course_store.initialize()
        self.page._akili_course_store = self.course_store
        self.gamification = init_gamification(self.storage)
        await self.gamification.load_state()
        streak_result = await self.gamification.update_streak()
        self.page.run_task(self._offer_boot_events, streak_result)
        await self._init_mcp()
        self.page.run_task(self._router_watchdog)
        self.page.run_task(self._refresh_catalog)
        self.page.run_task(self._init_premium_background)
        self.page.run_task(self._init_notifications)
        self.page.run_task(self._reminder_sweep, "boot")
        self._reminder_task = self.page.run_task(self._reminder_loop)

        # ── Load persisted state ──
        await self._load_settings()

        # ── Mount declarative UI ──
        from app_shell import AppShell

        methods = ControllerMethods(
            check_for_updates=self.check_for_updates,
            open_update_dialog=self.open_update_dialog,
            set_onboarding_done=self.set_onboarding_done,
            save_profile=self.save_profile,
            factory_reset=self.factory_reset,
            show_snack=self.show_snack,
            load_courses=self.load_courses,
            load_modules=self.load_modules,
            create_course=self.create_course,
            delete_course=self.delete_course,
            save_lesson_cache=self.save_lesson_cache,
            load_attempts=self.load_attempts,
            complete_quiz_pass=self.complete_quiz_pass,
            open_assignment=self.open_assignment,
            load_timetable=self.load_timetable,
            save_timetable_entry=self.save_timetable_entry,
            delete_timetable_entry=self.delete_timetable_entry,
            get_parent_overview=self.get_parent_overview,
            check_earn_conditions=self.check_earn_conditions,
            save=self.save,
            save_setting=self.save_setting,
        )
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))
        self.page._akili_controller = self
        self.page.run_task(self.check_for_updates)

    async def _init_premium_background(self) -> None:
        """Post-frame premium work: authoritative reconcile + hourly loop."""
        try:
            await self.premium.reconcile()
            if state.is_premium:
                with contextlib.suppress(Exception):
                    await self.premium._grant_premium_benefits(first_time=True)
            self.premium.start_reconcile_loop()
        except Exception:
            logger.debug("premium background init failed", exc_info=True)

    async def _offer_boot_events(self, streak_result: dict) -> None:
        """Auto-open the share sheet on streak milestones (v1 parity)."""
        try:
            from services.share_service import offer_share_event

            for event in (streak_result or {}).get("events", []) or []:
                if event.get("type") == "streak":
                    offer_share_event(self.page, event)
        except Exception:
            logger.debug("boot share offer failed", exc_info=True)

    async def _init_notifications(self) -> None:
        """Boot OS notifications (Android only; no-op elsewhere).

        Creates the service + channel, re-schedules pending assignment
        due alarms (they die on reboot), and turns on the daily study
        nudge. Tap on an assignment notification opens the assignment;
        anything else goes home.
        """
        try:
            from services import os_notifications

            async def _on_tap(payload: str) -> None:
                try:
                    if payload.startswith("assignment:"):
                        aid = int(payload.split(":", 1)[1])
                        from core.state import state

                        state.current_assignment_id = aid
                        self.show_assignment(aid)  # shell-injected view switch
                    else:
                        self.go_home()  # shell-injected; set during render
                except Exception:
                    logger.debug("notification tap nav failed", exc_info=True)

            if os_notifications.init_os_notifications(self.page, on_tap=_on_tap) is None:
                return
            if not await os_notifications.ensure_ready(self.page):
                return
            # Cold start: the app was launched by tapping a notification
            # while killed — route to whatever was tapped.
            try:
                details = await os_notifications.service().get_notification_app_launch_details()
            except Exception:
                details = None
            resp = (details or {}).get("notification_response") or {}
            if (details or {}).get("did_notification_launch_app") and resp.get("payload"):
                await _on_tap(str(resp["payload"]))
            scheduled = await os_notifications.reschedule_pending(self)
            if scheduled:
                logger.info("OS notifications: re-scheduled %d due alarms", scheduled)
            await os_notifications.daily_nudge(True)
        except Exception as exc:
            logger.debug("notification init failed: %s", exc)

    async def _reminder_sweep(self, _reason: str = "") -> None:
        """One reminder sweep: snackbar in-app + OS notification on Android."""
        try:
            from services import os_notifications, reminders

            for message in await reminders.check_once(self):
                await self.show_snack(message, "warning")
                await os_notifications.show("Akili reminder", message)
        except Exception as exc:
            logger.debug("reminder sweep failed: %s", exc)

    async def _reminder_loop(self) -> None:
        """15-minute foreground loop (cancelled on shutdown)."""
        try:
            from services import reminders

            await reminders.reminder_loop(self, self._surface_reminder)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("reminder loop failed: %s", exc)

    async def _surface_reminder(self, message: str) -> None:
        await self.show_snack(message, "warning")

    async def _init_connectivity(self):
        """Set state.is_online from an initial connectivity probe."""
        try:
            result = await self.connectivity.get_connectivity()
            state.is_online = ft.ConnectivityType.NONE not in result
        except Exception:
            state.is_online = True

    def _on_connectivity_change(self, e):
        """Flip state.is_online on an OS-level connectivity change."""
        try:
            types = getattr(e, "connectivity", None) or [e.data]
        except Exception:
            types = [ft.ConnectivityType.NONE]
        was_online = state.is_online
        state.is_online = ft.ConnectivityType.NONE not in types
        if was_online and not state.is_online:
            self.page.run_task(self.show_snack, "You're offline.", "warning")
        elif not was_online and state.is_online:
            self.page.run_task(self.show_snack, "You're back online.", "info")

    async def _on_lifecycle_change(self, e: ft.AppLifecycleStateChangeEvent):
        """Flush storage when backgrounded; re-probe connectivity when foregrounded."""
        if e.state in (
            ft.AppLifecycleState.HIDE,
            ft.AppLifecycleState.PAUSE,
            ft.AppLifecycleState.DETACH,
        ):
            if self.storage:
                with contextlib.suppress(Exception):
                    await self.storage.flush()
            return
        if e.state not in (ft.AppLifecycleState.RESUME, ft.AppLifecycleState.SHOW):
            return
        try:
            result = await self.connectivity.get_connectivity()
            state.is_online = ft.ConnectivityType.NONE not in result
        except Exception:
            pass
        # Re-check the licence on resume (debounced inside the service).
        if state.is_online and self.premium is not None:
            try:
                await self.premium.reconcile_if_due()
            except Exception as exc:
                logger.debug("licence refresh on resume skipped: %s", exc)
        # Foreground reminder sweep on every resume.
        with contextlib.suppress(Exception):
            await self._reminder_sweep("resume")

    async def _load_settings(self):
        """Load all persisted settings into the observable state."""
        try:
            theme = await self.storage.get(STORAGE_THEME)
            self.page.theme_mode = {
                "dark": ft.ThemeMode.DARK,
                "system": ft.ThemeMode.SYSTEM,
                "light": ft.ThemeMode.LIGHT,
            }.get(theme, ft.ThemeMode.SYSTEM)
            state.theme_mode = self.page.theme_mode

            onboarded = await self.storage.get(STORAGE_ONBOARDING_DONE)
            state.is_onboarded = onboarded == "true"

            profile_raw = await self.storage.get(STORAGE_PROFILE)
            if profile_raw:
                import json

                profile = json.loads(profile_raw)
                state.user_name = profile.get("name", "")
                state.education_level = profile.get("education_level", "")
                state.country = profile.get("country", "Global")
                state.avatar_index = profile.get("avatar_index", 0)

            ai_model = await self.storage.get(STORAGE_AI_MODEL)
            if ai_model:
                state.ai_model = ai_model

            state.ai_mode_enabled = await self.storage.get_ai_mode()
            state.reasoning_effort = await self.storage.get_reasoning_effort()
            state.biometric_lock = await self.storage.get_biometric_lock()

            logger.info("Settings loaded")
        except Exception:
            logger.warning("Settings load failed", exc_info=True)

    # ── Settings persistence (DDGS save bridge) ─────────────────────────

    def _setter_map(self) -> dict:
        """key -> (storage setter coroutine, state attribute name)."""
        return {
            "theme": (self.storage.set_theme, "theme_mode"),
            "onboarding_done": (self.storage.set_onboarding_done, "is_onboarded"),
            "ai_model": (self.storage.set_ai_model, "ai_model"),
            "ai_mode": (self.storage.set_ai_mode, "ai_mode_enabled"),
            "reasoning_effort": (self.storage.set_reasoning_effort, "reasoning_effort"),
            "biometric_lock": (self.storage.set_biometric_lock, "biometric_lock"),
            "history": (self.storage.set_history, "search_history"),
        }

    def save(self, key: str, value):
        """Sync wrapper: apply to state now, persist in the background.

        State updates synchronously so the control the user just touched
        repaints on that tap; the storage write is scheduled separately.
        """
        self._apply_state(key, value)
        self.page.run_task(self.save_setting, key, value)

    def _apply_state(self, key: str, value) -> None:
        entry = self._setter_map().get(key)
        if not entry:
            return
        state_key = entry[1]
        if key == "theme":
            theme_map = {
                "dark": ft.ThemeMode.DARK,
                "system": ft.ThemeMode.SYSTEM,
                "light": ft.ThemeMode.LIGHT,
            }
            self.page.theme_mode = theme_map.get(value, ft.ThemeMode.SYSTEM)
            state.theme_mode = self.page.theme_mode
            return
        setattr(state, state_key, value)

    async def save_setting(self, key: str, value):
        """Persist a single setting and update state."""
        entry = self._setter_map().get(key)
        if not entry:
            return
        setter, state_key = entry
        await setter(value)
        if key != "theme":
            setattr(state, state_key, value)

    async def _init_mcp(self):
        """Build the MCP hub: Exa built-in (always present) + saved extras.

        Exa (primary) and Parallel (fallback) are seeded at boot and can
        never be removed — only enabled/disabled and per-tool toggled from
        Settings. Saved extras (from STORAGE_MCP_SERVERS) are appended after.
        """
        import json

        from agent.mcp_hub import MCPHub, MCPServerConfig, builtin_exa_server, builtin_parallel_server

        builtin_names = {builtin_exa_server().name, builtin_parallel_server().name}
        servers: list[MCPServerConfig] = [builtin_exa_server(), builtin_parallel_server()]
        raw = await self.storage.get(STORAGE_MCP_SERVERS)
        if raw:
            try:
                for item in json.loads(raw):
                    extra = MCPServerConfig.from_dict(item)
                    if extra.name not in builtin_names:
                        servers.append(extra)
            except Exception:
                logger.warning("MCP servers config unreadable; builtins only", exc_info=True)

        is_mobile = not self.page.web and self.page.platform.is_mobile()
        self.mcp_hub = MCPHub(servers=servers, is_mobile=is_mobile, on_status=self._on_mcp_status)
        self.page._akili_mcp_hub = self.mcp_hub
        self.page.run_task(self.mcp_hub.serve)

    def _on_mcp_status(self, names, error):
        """MCP hub status callback — publish tool names, surface failures."""
        try:
            state.mcp_tools = list(names or [])
            if error:
                logger.warning("MCP: %s", error)
        except Exception:
            pass

    async def _refresh_catalog(self):
        """Snapshot the router's active models for the picker."""
        from agent import engine as router

        try:
            await router.refresh_catalog()
        except Exception:
            logger.debug("initial catalog refresh failed", exc_info=True)

    async def _router_watchdog(self):
        """Poll router health so the model picker can report the truth."""
        import asyncio

        from agent import engine as router

        while True:
            try:
                status, port = await router.probe_router()
                if state.router_status != status or state.router_port != port:
                    logger.info("router status: %s (port %s)", status, port)
                    if state.chat_open:
                        pass  # chat pill rebuilds from observable state
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("router watchdog tick failed: %s", exc)
            await asyncio.sleep(3)

    async def set_onboarding_done(self):
        """Mark onboarding as complete."""
        state.is_onboarded = True
        if self.storage:
            await self.storage.set(STORAGE_ONBOARDING_DONE, "true")

    async def save_profile(self, name: str, level: str, country: str):
        """Persist the student profile."""
        import json

        profile = {
            "name": name,
            "education_level": level,
            "country": country,
            "avatar_index": state.avatar_index,
        }
        state.user_name = name
        state.education_level = level
        state.country = country
        if self.storage:
            await self.storage.set(STORAGE_PROFILE, json.dumps(profile))
            await self.storage.flush()

    async def factory_reset(self):
        """Wipe study data and the profile, return to onboarding (v1
        Factory Reset parity: 'Clears all study logs and profile databases').

        Preserved on purpose:
        - credit ledger + last-reset marker (v1 keeps credits_log so a
          reset can't mint free credits),
        - license / premium state (a purchase must survive a reset),
        - device + agent configuration (biometric lock, MCP servers,
          AI model/mode/reasoning).
        Theme is wiped (v1 wiped its settings table), returning to system
        default.
        """
        import contextlib as _cl

        from core.constants import STORAGE_GAMIFICATION, STORAGE_HISTORY

        if self.course_store is not None:
            await self.course_store.reset()
        if self.storage is not None:
            for key in (STORAGE_PROFILE, STORAGE_ONBOARDING_DONE, STORAGE_GAMIFICATION, STORAGE_HISTORY, STORAGE_THEME):
                await self.storage.remove(key)
            await self.storage.flush()

        # Profile + onboarding
        state.user_name = ""
        state.education_level = ""
        state.country = "Global"
        state.avatar_index = 0
        state.is_onboarded = False

        # Gamification (the shell now shows onboarding again)
        state.xp_total = 0
        state.level = "Freshman"
        state.current_streak = 0
        state.best_streak = 0

        # Content + navigation
        state.courses = []
        state.modules = []
        state.current_course = None
        state.current_module = None
        state.current_assignment_id = None
        state.courses_version += 1

        # Theme back to system default (key removed; the boot read defaults
        # get_theme() to "system")
        state.theme_mode = ft.ThemeMode.SYSTEM
        with _cl.suppress(Exception):
            self.page.theme_mode = ft.ThemeMode.SYSTEM

        # Drop any OS notifications/scheduled alarms (Android) — a reset
        # must not leave "due today" alarms pointing at deleted assignments.
        try:
            from services import os_notifications

            if os_notifications.service() is not None:
                await os_notifications.cancel_all()
        except Exception:
            logger.debug("notification cancel_all failed", exc_info=True)

    # ── Content (courses / modules / lessons) ───────────────────────────

    async def load_courses(self) -> list:
        """Load courses into observable state and bump the render token."""
        if self.course_store is None:
            return []
        courses = await self.course_store.get_courses()
        state.courses = courses
        state.courses_version += 1
        return courses

    async def load_modules(self, course_id: int) -> list:
        """Load a course's modules into observable state."""
        if self.course_store is None:
            return []
        modules = await self.course_store.get_modules(course_id)
        state.modules = modules
        state.courses_version += 1
        return modules

    async def save_lesson_cache(self, module_id: int, content: str) -> None:
        """Cache a generated lesson and refresh the module list."""
        if self.course_store is None:
            return
        await self.course_store.save_lesson(module_id, content)
        course = state.current_course
        if course:
            await self.load_modules(course["id"])

    async def create_course(self, subject: str, level: str, curriculum: dict, color_index: int) -> dict:
        """Persist a course + its modules, then return the course dict.

        Module 0 is unlocked; the rest stay locked until a quiz is passed
        (v1 parity). Progress starts at zero.
        """
        assert self.course_store is not None
        course_id = await self.course_store.add_course(subject, level, curriculum, color_index)
        for i, mod in enumerate(curriculum.get("modules") or []):
            await self.course_store.add_module(
                course_id,
                mod.get("title", f"Module {i + 1}"),
                mod.get("topics") or [],
                order_num=i,
                unlocked=(i == 0),
            )
        course = await self.course_store.get_course(course_id)
        await self.load_courses()
        return course or {}

    async def delete_course(self, course_id: int) -> None:
        """Delete a course and its modules, then refresh."""
        if self.course_store is None:
            return
        # Cancel any scheduled due-date notifications for the course's
        # assignments before they cascade away.
        try:
            from services import os_notifications

            for assignment in await self.course_store.get_all_assignments(course_id):
                await os_notifications.cancel_overdue(assignment.get("id"))
        except Exception:
            logger.debug("notification cancel on delete failed", exc_info=True)
        await self.course_store.delete_course(course_id)
        if state.current_course and state.current_course.get("id") == course_id:
            state.current_course = None
            state.current_module = None
        await self.load_courses()

    # ── Assessments ───────────────────────────────────────────────────────

    async def load_attempts(self, module_id: int | None = None) -> list:
        """Load quiz attempts into observable state and bump the token."""
        if self.course_store is None:
            return []
        attempts = await self.course_store.get_quiz_attempts(module_id)
        state.quiz_attempts = attempts
        state.attempts_version += 1
        return attempts

    async def complete_quiz_pass(self, module_id: int, course_id: int) -> None:
        """Mark a module complete and unlock its immediate successor.

        v1 parity: strict-sequence gating — only the next module unlocks.
        """
        if self.course_store is None:
            return
        await self.course_store.complete_module(module_id)
        modules = await self.course_store.get_modules(course_id)
        ids = [m["id"] for m in modules]
        if module_id in ids:
            nxt = ids.index(module_id) + 1
            if nxt < len(ids):
                await self.course_store.unlock_module(ids[nxt])
        await self.load_modules(course_id)

    async def open_assignment(self, assignment_id: int) -> None:
        """Set the current assignment for the assignment view."""
        state.current_assignment_id = assignment_id

    # ── Engagement (timetable / parent / share triggers) ────────────────

    async def load_timetable(self) -> list:
        """Load timetable entries (weekday-ordered)."""
        if self.course_store is None:
            return []
        return await self.course_store.get_timetable()

    async def save_timetable_entry(self, entry_id: int | None, day: str, time_slot: str, subject: str, note: str = "") -> dict | None:
        """Add (entry_id None) or edit a timetable entry. Validates via the store."""
        if self.course_store is None:
            raise ValueError("Storage unavailable.")
        if entry_id is None:
            eid = await self.course_store.add_timetable_entry(day, time_slot, subject, note)
            entries = await self.course_store.get_timetable()
            return next((e for e in entries if e.get("id") == eid), None)
        ok = await self.course_store.update_timetable_entry(entry_id, day, time_slot, subject, note)
        if not ok:
            raise ValueError("That entry no longer exists.")
        entries = await self.course_store.get_timetable()
        return next((e for e in entries if e.get("id") == entry_id), None)

    async def delete_timetable_entry(self, entry_id: int) -> None:
        if self.course_store is not None:
            await self.course_store.delete_timetable_entry(entry_id)

    async def get_parent_overview(self) -> dict:
        """The derived parent dashboard."""
        from services.parent_stats import get_parent_stats

        return await get_parent_stats(self.course_store, self.gamification)

    async def check_earn_conditions(self) -> list:
        """Evaluate badge triggers; returns events for newly-earned badges."""
        if self.gamification is None or self.course_store is None:
            return []
        return await self.gamification.check_earn_conditions(self.course_store)

    async def check_for_updates(self):
        """Check for app updates via the update service."""
        from core.constants import (
            APP_BUILD_NUMBER,
            GITHUB_REPO_URL,
            PLAYSTORE_URL,
            UPDATE_CONFIG_URL,
        )
        from services.update_service import UpdateService

        service = UpdateService(UPDATE_CONFIG_URL, APP_BUILD_NUMBER, GITHUB_REPO_URL, PLAYSTORE_URL)
        data = await service.check_for_update()
        if data:
            state.update_available = True
            state.update_data = data
            with contextlib.suppress(Exception):
                self.page.update()
            if data.get("mandatory"):
                self.open_update_dialog()

    def open_update_dialog(self):
        """Show the update dialog."""
        from components.update_dialog import show_update_dialog

        show_update_dialog(self.page)

    async def show_snack(self, message: str, level: str = "info"):
        """Show a SnackBar notification."""
        from core.notify import show_snack as _show_snack
        from core.theme import AppColors

        bg = {
            "error": AppColors.ERROR,
            "success": AppColors.SUCCESS,
            "warning": AppColors.WARNING,
        }.get(level, AppColors.PRIMARY)

        _show_snack(self.page, message, bgcolor=bg)

    def on_app_close(self, e=None):
        """Synchronous exit hook: stop services, flush storage."""
        try:
            from agent import engine as router

            router.shutdown()
        except Exception:
            pass
        if self.mcp_hub is not None:
            with contextlib.suppress(Exception):
                self.mcp_hub.request_stop()
        if self.premium is not None:
            with contextlib.suppress(Exception):
                self.premium.shutdown()
        if self._reminder_task is not None:
            with contextlib.suppress(Exception):
                self._reminder_task.cancel()
            self._reminder_task = None
        session = getattr(self.page, "_tutor_session", None)
        if session is not None:
            with contextlib.suppress(Exception):
                session.shutdown()
        if self.storage:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.storage.flush())
                else:
                    loop.run_until_complete(self.storage.flush())
            except Exception:
                pass
