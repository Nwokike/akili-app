"""Quiz history — past attempts with score, date, and course search.

The store keeps attempts by module; this screen joins module → course →
subject for display, and filters by the debounced course-name query.
"""

from __future__ import annotations

import flet as ft

from components.empty_state import EmptyState
from core import tokens
from core.theme import AppColors
from hooks.use_debounce import use_debounce
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx


def _pct(attempt: dict) -> float:
    total = float(attempt.get("total") or 0)
    if not total:
        return 0.0
    return float(attempt.get("score") or 0) / total * 100


@ft.component
def QuizHistoryScreen():
    """Past quiz attempts, searchable by course name. Biometric-gated."""
    app_state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    attempts, set_attempts = ft.use_state([])
    course_names, set_course_names = ft.use_state({})
    query, set_query = ft.use_state("")
    debounced, _schedule = use_debounce("", 250)

    _ = app_state.attempts_version
    locked = bool(app_state.biometric_lock) and not app_state.history_unlocked

    async def _unlock():
        from services.biometric_service import authenticate

        if await authenticate("Unlock your quiz history"):
            app_state.history_unlocked = True
            app_state.attempts_version += 1
        else:
            await controller.show_snack("Still locked", "warning")

    if locked:
        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                            ft.Text("Quiz History", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
                        ],
                        spacing=tokens.SPACE_XS,
                    ),
                    padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
                ),
                EmptyState(
                    "History is locked",
                    "Unlock with your device to view past attempts.",
                    "Unlock",
                    on_action=lambda e: ft.context.page.run_task(_unlock),
                    icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _load():
        import asyncio

        async def _run():
            rows = await controller.load_attempts()
            set_attempts(rows)
            store = getattr(ft.context.page, "_akili_course_store", None)
            names: dict[int, str] = {}
            if store is not None:
                courses = await store.get_courses()
                id_to_subject = {c["id"]: c.get("subject", "") for c in courses}
                modules = []
                for c in courses:
                    modules.extend(await store.get_modules(c["id"]))
                id_to_course = {m["id"]: m["course_id"] for m in modules}
                for a in rows:
                    cid = id_to_course.get(a.get("module_id"))
                    names[a.get("id")] = id_to_subject.get(cid, "")
            set_course_names(names)

        asyncio.ensure_future(_run())

    ft.use_effect(_load, [])

    term = (debounced or "").strip().lower()
    rows = [a for a in attempts if not term or term in (course_names.get(a.get("id"), "") or "").lower()]

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: controller.go_home(), tooltip="Back"),
                ft.Text("Quiz History", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, expand=True),
            ],
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
    )

    search = ft.TextField(
        hint_text="Search courses…",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_LG,
            side=ft.BorderSide(0, ft.Colors.TRANSPARENT),
        ),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        value=query,
        on_change=lambda e: (set_query(e.control.value), _schedule(e.control.value)),
    )

    if not rows:
        body = EmptyState(
            "No history found" if term else "No quiz history yet",
            "" if not term else f'No courses match "{term}"',
            icon=ft.Icons.HISTORY_ROUNDED,
        )
    else:
        cards: list[ft.Control] = []
        for a in rows:
            score_pct = _pct(a)
            colour = AppColors.SUCCESS if score_pct >= 60 else AppColors.ERROR
            cards.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(f"{score_pct:.0f}%", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD, color=colour),
                                width=56,
                                height=56,
                                border_radius=28,
                                bgcolor=ft.Colors.with_opacity(0.10, colour),
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        str(course_names.get(a.get("id"), "") or "Course"),
                                        size=tokens.FONT_MD,
                                        weight=ft.FontWeight.W_600,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(str(a.get("timestamp") or ""), size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                                expand=True,
                                tight=True,
                            ),
                            ft.Text(f"{float(a.get('score') or 0):g}/{float(a.get('total') or 0):g}", size=tokens.FONT_SM, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=tokens.SPACE_MD,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=tokens.SPACE_MD,
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.05, ft.Colors.OUTLINE)),
                )
            )
        body = ft.ListView(controls=cards, spacing=tokens.SPACE_MD, expand=True, build_controls_on_demand=True)

    return ft.Column(
        controls=[
            header,
            ft.Container(content=ft.Column(controls=[search, ft.Container(content=body, expand=True)], spacing=tokens.SPACE_MD, expand=True), padding=tokens.SPACE_LG, expand=True),
        ],
        spacing=0,
        expand=True,
    )
