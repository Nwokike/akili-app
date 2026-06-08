import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager


async def build_course_detail_view(page: ft.Page, navigate) -> ft.View:
    ad_service = page.data.get("ad_service")
    course = state.current_course
    if not course:
        return ft.View(route="/modules", controls=[ft.Text("No course selected")])

    modules = await db_manager.get_modules(course["id"])
    color = AppColors.SUBJECT_COLORS[course.get("color_index", 0) % len(AppColors.SUBJECT_COLORS)]

    # Check course completion eligibility
    can_complete, pending_count = await db_manager.can_complete_course(course["id"])

    # Get assignment status per module
    module_assignments = {}
    for mod in modules:
        assignment = await db_manager.get_module_assignment(mod["id"])
        if assignment:
            module_assignments[mod["id"]] = assignment

    # ── Header ───────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, on_click=lambda e: page.run_task(navigate, "/dashboard")),
                        ft.Image(src="/icon.png", width=32, height=32),
                        ft.Column(
                            [
                                ft.Text(course["subject"], size=18, weight=ft.FontWeight.BOLD),
                                ft.Text(f"{len(modules)} Modules", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=0,
                            tight=True,
                        ),
                    ],
                    spacing=12,
                ),
            ]
        ),
        padding=ft.Padding(8, 8, 16, 8),
    )

    # ── Progress Summary ─────────────────────────────────────────
    progress_card = ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Your Progress", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{course.get('progress_pct', 0):.0f}%", size=28, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Stack(
                    [
                        ft.ProgressRing(width=48, height=48, value=course.get("progress_pct", 0) / 100, stroke_width=6, color=color),
                        ft.Container(
                            content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18, color=color),
                            alignment=ft.Alignment.CENTER,
                            width=48,
                            height=48,
                        ),
                    ]
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=24,
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )

    # ── Assignment completion warning ─────────────────────────
    assignment_banner = ft.Container(visible=False)
    if not can_complete and pending_count > 0:
        assignment_banner = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ASSIGNMENT_LATE_ROUNDED, size=18, color=ft.Colors.AMBER_700),
                    ft.Text(
                        f"{pending_count} assignment{'s' if pending_count > 1 else ''} pending — complete all to finish this course",
                        size=12,
                        color=ft.Colors.AMBER_700,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.Padding(16, 10, 16, 10),
            border_radius=AppStyles.RADIUS_SMALL,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.AMBER),
        )

    # ── Mock Exam Button ──────────────────────────────────────
    exam_btn = ft.Container(
        content=ft.FilledButton(
            "📝 Take Mock Exam",
            on_click=lambda e: page.run_task(navigate, "/exam"),
            style=ft.ButtonStyle(
                bgcolor=AppColors.ACCENT,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                padding=14,
            ),
            width=float("inf"),
        ),
        padding=ft.Padding(0, 0, 0, 8),
    )

    module_list = ft.Column(spacing=12, expand=True)

    for i, mod in enumerate(modules):
        is_locked = not mod["is_unlocked"]
        is_done = mod["is_completed"]
        assignment = module_assignments.get(mod["id"])

        # Assignment status indicator
        assignment_indicator = ft.Container()
        if assignment:
            a_status = assignment["status"]
            if a_status == "pending":
                assignment_indicator = ft.Container(
                    content=ft.Text("📋", size=16),
                    tooltip="Assignment pending",
                    on_click=lambda e, a=assignment: page.run_task(_open_assignment, a["id"]),
                )
            elif a_status == "graded":
                assignment_indicator = ft.Container(
                    content=ft.Text("✅", size=16),
                    tooltip="Assignment graded",
                )
            elif a_status == "submitted":
                assignment_indicator = ft.Container(
                    content=ft.Text("📤", size=16),
                    tooltip="Assignment submitted",
                )

        async def on_module_tap(e, m=mod):
            if m["is_unlocked"]:
                state.current_module = m
                await navigate("/lesson")

        card = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.LOCK_ROUNDED if is_locked else ft.Icons.CHECK_CIRCLE_ROUNDED if is_done else ft.Icons.PLAY_CIRCLE_ROUNDED,
                            color=ft.Colors.ON_SURFACE_VARIANT if is_locked else AppColors.SUCCESS if is_done else AppColors.PRIMARY,
                            size=24,
                        ),
                        width=40,
                        height=40,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                mod["title"],
                                size=16,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE if not is_locked else ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                f"Module {i + 1}" if not is_locked else f"Module {i + 1} · Pass the quiz (50%+) to unlock",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    assignment_indicator,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(16, 16, 16, 16),
            border_radius=AppStyles.RADIUS,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if not is_locked else ft.Colors.TRANSPARENT,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)) if is_locked else None,
            on_click=lambda e, m=mod: page.run_task(on_module_tap, e, m),
            disabled=is_locked,
        )
        module_list.controls.append(card)

    async def _open_assignment(assignment_id):
        state.current_assignment_id = assignment_id
        await navigate("/assignment")

    content = ft.Column(
        [
            header,
            ft.Container(
                content=ft.Column(
                    [
                        progress_card,
                        assignment_banner,
                        exam_btn,
                        ft.Container(height=4),
                        ft.Text("Modules", size=18, weight=ft.FontWeight.BOLD),
                        module_list,
                        ad_service.get_banner_ad() if ad_service else ft.Container(),
                    ],
                    spacing=16,
                ),
                padding=20,
                expand=True,
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )

    return ft.View(
        route="/modules",
        controls=[
            ft.SafeArea(
                ft.Container(content=content, bgcolor=ft.Colors.SURFACE, expand=True),
                expand=True,
            )
        ],
        padding=0,
        spacing=0,
    )
