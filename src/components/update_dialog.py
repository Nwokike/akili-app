"""Update dialog — changelog when up to date, update info when available.

Ported from Sherlock's update_dialog pattern (the house standard), with
a live Check-for-Updates re-check and platform-aware store buttons.
"""

from __future__ import annotations

import contextlib

import flet as ft

from core import tokens
from core.changelog import notes_for
from core.constants import (
    APP_VERSION,
    GITHUB_REPO_URL,
    LBL_CHECK_FOR_UPDATES,
    PLAYSTORE_URL,
)
from core.theme import AppColors


def _is_android(page: ft.Page | None) -> bool:
    try:
        return page is not None and not page.web and page.platform == ft.PagePlatform.ANDROID
    except Exception:
        return False


def _open_url(page: ft.Page):
    def _launch(url: str):
        def handler(e):
            try:
                launcher = getattr(page, "url_launcher", None) or ft.UrlLauncher()
                page.run_task(launcher.launch_url, url)
            except Exception:
                pass

        return handler

    return _launch


def show_update_dialog(page: ft.Page, notice: str = "") -> None:
    """Show the update dialog (changelog or update available).

    `notice` is a one-line status shown under the changelog (e.g. after a
    manual re-check). Plain function — no hooks, so re-checks rebuild.
    """
    from core.state import state

    is_update = state.update_available and state.update_data is not None
    launch = _open_url(page)
    android = _is_android(page)

    if is_update:
        data = state.update_data or {}
        title = data.get("title", "Update Available")
        notes = data.get("release_notes", "")
        mandatory = data.get("mandatory", False)

        actions: list[ft.Control] = []
        if not mandatory:
            actions.append(ft.TextButton("Later", on_click=lambda e: page.pop_dialog()))

        actions.append(
            ft.FilledButton(
                "Google Play" if android else "Download from GitHub",
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                on_click=launch(PLAYSTORE_URL if android else GITHUB_REPO_URL),
            )
        )
        if android:
            # Direct APK as the second option on Android.
            actions.append(ft.OutlinedButton("Direct APK (GitHub)", on_click=launch(GITHUB_REPO_URL)))

        dlg = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, color=AppColors.PRIMARY),
                    ft.Text(title, expand=True),
                ],
                spacing=tokens.SPACE_SM,
            ),
            content=ft.Column(
                controls=[
                    ft.Markdown(notes, selectable=True),
                ],
                scroll=ft.ScrollMode.AUTO,
                width=tokens.DIALOG_WIDTH_LG,
            ),
            actions=actions,
            modal=mandatory,
        )
    else:
        notes = notes_for(APP_VERSION)

        async def _recheck():
            try:
                controller = getattr(page, "_akili_controller", None)
                if controller is None:
                    raise RuntimeError("no controller")
                await controller.check_for_updates()
                from core.state import state as _state

                with contextlib.suppress(Exception):
                    page.pop_dialog()
                if _state.update_available:
                    show_update_dialog(page)
                else:
                    show_update_dialog(page, notice=f"Akili v{APP_VERSION} is up to date!")
            except Exception:
                with contextlib.suppress(Exception):
                    page.pop_dialog()
                show_update_dialog(page, notice="Couldn't reach the update service.")

        content_controls: list[ft.Control] = [
            ft.Text(
                f"Version {APP_VERSION}",
                size=tokens.FONT_MD,
                weight=ft.FontWeight.W_600,
            ),
            ft.Markdown(notes, selectable=True),
        ]
        if notice:
            content_controls.append(ft.Text(notice, size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT))

        dlg = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=AppColors.SUCCESS),
                    ft.Text("You're up to date!"),
                ],
                spacing=tokens.SPACE_SM,
            ),
            content=ft.Column(
                controls=content_controls,
                scroll=ft.ScrollMode.AUTO,
                width=tokens.DIALOG_WIDTH_LG,
                spacing=tokens.SPACE_SM,
            ),
            actions=[
                ft.OutlinedButton(
                    LBL_CHECK_FOR_UPDATES,
                    on_click=lambda e: page.run_task(_recheck),
                ),
                ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
            ],
        )

    page.show_dialog(dlg)
