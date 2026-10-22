"""Settings sections — Data, Study links, Troubleshooting, About.

Sherlock rows + patterns, Akili content. The About section carries the
version row (tappable → update dialog), platform-aware links, the usage
agreement, and the privacy-options row (only when UMP says REQUIRED).
"""

from __future__ import annotations

import contextlib

import flet as ft

from components.settings_kit import setting_row, settings_card
from core import tokens
from core.constants import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    CONTACT_EMAIL,
    GITHUB_REPO_URL,
    KIRI_APPS_PLAY_URL,
    KIRI_APPS_URL,
)
from core.state import state
from core.theme import AppColors
from state.controller_ctx import ControllerMethodsCtx

_TERMS_TEXT = """Akili Usage Agreement

Akili is an AI-powered study companion. AI-generated lessons, quizzes,
and answers may contain mistakes — always verify against your textbooks
and teachers. Akili does not replace certified educators or official
curriculum documents.

Your courses, progress, and settings stay on your device. AI requests
are sent to the Kiri router for answering and are not used to identify
you. Purchases are handled by our payment partner; Akili never sees
card numbers.

By using Akili you agree to use it for lawful study purposes."""


def _open_url(page: ft.Page, url: str) -> None:
    try:
        launcher = getattr(page, "url_launcher", None) or ft.UrlLauncher()
        page.run_task(launcher.launch_url, url)
    except Exception:
        pass


def _is_store_device(page: ft.Page | None) -> bool:
    try:
        return page is not None and not page.web and page.platform.is_mobile()
    except Exception:
        return False


@ft.component
def build_data_section(page: ft.Page) -> ft.Control:
    """Clear cache / history / reset + the biometric history toggle."""
    controller = ft.use_context(ControllerMethodsCtx)
    clearing, set_clearing = ft.use_state(False)
    resetting, set_resetting = ft.use_state(False)

    def _toggle_biometric(value: bool):
        # Turning the lock off also drops the unlocked flag so a stale
        # unlock can't survive the setting (Sherlock pattern).
        from core.state import state as _state

        if not value:
            _state.history_unlocked = False
        controller.save("biometric_lock", value)

    async def _clear_history():
        set_clearing(True)
        try:
            await controller.save_setting("history", [])
            await controller.show_snack("History cleared", "success")
        except Exception:
            await controller.show_snack("Couldn't clear history", "error")
        finally:
            set_clearing(False)

    async def _reset_app():
        set_resetting(True)
        try:
            # v1 Factory Reset semantics: study data + profile go, the app
            # returns to onboarding. Credits (anti-refill) and the license
            # survive; see AppController.factory_reset.
            await controller.factory_reset()
            await controller.show_snack("App reset", "success")
        except Exception:
            await controller.show_snack("Couldn't reset the app", "error")
        finally:
            set_resetting(False)

    def _confirm(title: str, message: str, on_yes) -> None:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(title),
                content=ft.Text(message),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Yes, continue", on_click=lambda e: (page.pop_dialog(), page.run_task(on_yes))),
                ],
            )
        )

    return settings_card(
        [
            setting_row(
                ft.Icons.DELETE_OUTLINE_ROUNDED,
                "Clear history",
                "Remove quiz history and recent activity.",
                ft.OutlinedButton(
                    "Clearing…" if clearing else "Clear",
                    disabled=clearing,
                    on_click=lambda e: _confirm("Clear history?", "Your quiz history will be removed.", _clear_history),
                ),
            ),
            setting_row(
                ft.Icons.RESTART_ALT_ROUNDED,
                "Reset app",
                "Delete all courses, progress, and settings.",
                ft.OutlinedButton(
                    "Resetting…" if resetting else "Reset",
                    disabled=resetting,
                    on_click=lambda e: _confirm("Reset everything?", "All courses and progress will be deleted.", _reset_app),
                ),
            ),
            setting_row(
                ft.Icons.FINGERPRINT_ROUNDED,
                "Lock quiz history",
                "Require device unlock to view quiz history.",
                ft.Switch(
                    value=state.biometric_lock,
                    active_color=AppColors.PRIMARY,
                    on_change=lambda e: _toggle_biometric(e.control.value),
                ),
            ),
        ]
    )


@ft.component
def build_study_section(page: ft.Page) -> ft.Control:
    """Timetable + Parent Portal + Quiz History links (the nav v1 never had)."""
    controller = ft.use_context(ControllerMethodsCtx)
    chevron = ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=15, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE))
    return settings_card(
        [
            setting_row(
                ft.Icons.CALENDAR_MONTH_ROUNDED,
                "Timetable",
                "Your weekly class schedule.",
                chevron,
                on_click=lambda e: controller.show_timetable(),
            ),
            setting_row(
                ft.Icons.FAMILY_RESTROOM_ROUNDED,
                "Parent Portal",
                "PIN-gated student overview.",
                chevron,
                on_click=lambda e: controller.show_parent_portal(),
            ),
            setting_row(
                ft.Icons.HISTORY_ROUNDED,
                "Quiz History",
                "Past attempts with scores.",
                chevron,
                on_click=lambda e: controller.show_history(),
            ),
        ]
    )


@ft.component
def build_troubleshooting_section(page: ft.Page) -> ft.Control:
    """Log terminal + feedback."""
    controller = ft.use_context(ControllerMethodsCtx)

    def _open_terminal(e):
        from core.logger_handler import MemoryLogHandler, get_telemetry_snapshot

        logs = MemoryLogHandler.get_logs()
        body = ft.Container(
            content=ft.Text(
                "\n".join(logs[-200:]) or "No log entries yet.",
                size=11,
                font_family="Courier New",
                color=AppColors.TERMINAL_GREEN,
                selectable=True,
            ),
            bgcolor=AppColors.TERMINAL_BG,
            border_radius=tokens.RADIUS_MD,
            padding=tokens.SPACE_MD,
            height=320,
        )

        def _copy(_e):
            with contextlib.suppress(Exception):
                page.run_task(ft.Clipboard().set, "\n".join(logs))
            page.run_task(controller.show_snack, "Logs copied", "info")

        def _clear(_e):
            MemoryLogHandler.clear_logs()
            with contextlib.suppress(Exception):
                page.pop_dialog()

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Activity Terminal"),
                content=ft.Column(
                    controls=[
                        ft.Text(get_telemetry_snapshot(), size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                        body,
                    ],
                    spacing=tokens.SPACE_SM,
                    tight=True,
                    width=420,
                ),
                actions=[
                    ft.TextButton("Copy", on_click=_copy),
                    ft.TextButton("Clear", on_click=_clear),
                    ft.TextButton("Close", on_click=lambda ev: page.pop_dialog()),
                ],
            )
        )

    return settings_card(
        [
            setting_row(
                ft.Icons.TERMINAL_ROUNDED,
                "Activity Terminal",
                "Recent app logs for troubleshooting.",
                ft.OutlinedButton("Open", on_click=_open_terminal),
            ),
            setting_row(
                ft.Icons.FEEDBACK_OUTLINED,
                "Send feedback",
                CONTACT_EMAIL,
                None,
                on_click=lambda e: _open_url(page, f"mailto:{CONTACT_EMAIL}"),
            ),
        ]
    )


@ft.component
def build_about_section(page: ft.Page) -> ft.Control:
    """Brand, version (tappable → update dialog), links, legal."""
    controller = ft.use_context(ControllerMethodsCtx)

    def _version_row():
        label = "Update available · tap to view" if state.update_available else f"Version {APP_VERSION}"
        return setting_row(
            ft.Icons.INFO_OUTLINE_ROUNDED,
            label,
            APP_TAGLINE,
            None,
            on_click=lambda e: controller.open_update_dialog(),
        )

    store_device = _is_store_device(page)
    rate_url = "https://play.google.com/store/apps/details?id=ng.kiri.akili" if store_device else GITHUB_REPO_URL
    apps_url = KIRI_APPS_PLAY_URL if store_device else KIRI_APPS_URL

    async def _open_privacy():
        service = getattr(page, "_akili_ad_service", None)
        if service is not None:
            await service.show_privacy_options()

    def _terms():
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Usage Agreement"),
                content=ft.Column(
                    controls=[ft.Text(_TERMS_TEXT, size=tokens.FONT_SM, selectable=True)],
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                    width=420,
                ),
                actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
            )
        )

    rows: list[ft.Control] = [
        ft.Container(
            content=ft.Column(
                controls=[
                    ft.Image(src="/icon.svg", width=48, height=48),
                    ft.Text(APP_NAME, size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_XS,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding(0, tokens.SPACE_MD, 0, tokens.SPACE_SM),
        ),
        _version_row(),
        setting_row(
            ft.Icons.MAIL_OUTLINE_ROUNDED,
            "Contact",
            CONTACT_EMAIL,
            None,
            on_click=lambda e: _open_url(page, f"mailto:{CONTACT_EMAIL}"),
        ),
        setting_row(
            ft.Icons.STAR_OUTLINE_ROUNDED,
            "Rate Akili",
            "Tell others about the app.",
            None,
            on_click=lambda e: _open_url(page, rate_url),
        ),
        setting_row(
            ft.Icons.APPS_ROUNDED,
            "More apps",
            "Other apps from Kiri.",
            None,
            on_click=lambda e: _open_url(page, apps_url),
        ),
        setting_row(
            ft.Icons.DESCRIPTION_OUTLINED,
            "Usage Agreement",
            "What Akili is and isn't.",
            None,
            on_click=lambda e: _terms(),
        ),
    ]
    rows.append(PrivacyOptionsRow(page))
    rows.append(
        ft.Container(
            content=ft.Text(
                "© 2026 Kiri Research Labs",
                size=tokens.FONT_XS,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding(0, tokens.SPACE_SM, 0, tokens.SPACE_MD),
        )
    )
    return settings_card(rows)


@ft.component
def PrivacyOptionsRow(page: ft.Page):
    """Privacy-options row — rendered only when UMP says REQUIRED."""
    required, set_required = ft.use_state(False)

    def _load():
        async def _run():
            service = getattr(page, "_akili_ad_service", None)
            if service is None or service._consent_manager is None:
                set_required(False)
                return
            try:
                from flet_ads import PrivacyOptionsRequirementStatus

                status = await service._consent_manager.get_privacy_options_requirement_status()
                set_required(status == PrivacyOptionsRequirementStatus.REQUIRED)
            except Exception:
                set_required(False)

        page.run_task(_run)

    ft.use_effect(_load, [])

    async def _open():
        service = getattr(page, "_akili_ad_service", None)
        if service is not None:
            await service.show_privacy_options()

    if not required:
        return ft.Container(width=0, height=0)
    return setting_row(
        ft.Icons.PRIVACY_TIP_OUTLINED,
        "Privacy options",
        "Change your ad consent.",
        None,
        on_click=lambda e: page.run_task(_open),
    )
