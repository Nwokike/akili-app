import contextlib

import flet as ft

from core.state import state
from core.theme import AppColors


class NotificationBell(ft.Stack):
    def __init__(self, page: ft.Page, has_unread: bool = False, pending_assignments: int = 0, navigate=None):
        super().__init__()
        self._page = page
        self.has_unread = has_unread
        self._pending_assignments = pending_assignments
        self._navigate = navigate
        self._assignment_items: list[dict] = []

        self.bell_icon = ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_OUTLINED,
            on_click=self.handle_click,
        )

        total_unread = (1 if has_unread else 0) + pending_assignments
        self.badge = ft.Container(
            width=18,
            height=18,
            bgcolor=ft.Colors.RED_700,
            border_radius=9,
            top=4,
            right=4,
            visible=total_unread > 0,
            content=ft.Text(
                str(total_unread) if total_unread > 0 else "",
                size=10,
                color=ft.Colors.WHITE,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
        )

        self.controls = [self.bell_icon, self.badge]

    def set_assignments(self, assignments: list[dict]):
        """Set pending assignment data for notifications."""
        self._assignment_items = assignments
        self._pending_assignments = len(assignments)
        total_unread = (1 if self.has_unread else 0) + self._pending_assignments
        self.badge.visible = total_unread > 0
        if total_unread > 0:
            self.badge.content = ft.Text(
                str(total_unread),
                size=10,
                color=ft.Colors.WHITE,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
            )
        with contextlib.suppress(Exception):
            self.update()

    def handle_click(self, e):
        if self.badge.visible:
            self.badge.visible = False

        items = self._build_notifications()

        panel = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.NOTIFICATIONS_ROUNDED, size=22, color=AppColors.PRIMARY),
                                    ft.Text("Notifications", size=18, weight=ft.FontWeight.BOLD, expand=True),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE_ROUNDED,
                                        icon_size=20,
                                        on_click=lambda e: _close_panel(),
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=ft.Padding(20, 16, 12, 8),
                        ),
                        ft.Divider(height=1),
                        ft.Column(
                            items
                            if items
                            else [
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=48, color=AppColors.SUCCESS, opacity=0.5),
                                            ft.Text("You're all caught up!", size=16, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
                                            ft.Text("No new notifications right now.", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=8,
                                    ),
                                    padding=40,
                                    alignment=ft.Alignment.CENTER,
                                ),
                            ],
                            scroll=ft.ScrollMode.AUTO,
                            spacing=0,
                        ),
                    ],
                    spacing=0,
                    tight=True,
                ),
                padding=ft.Padding(0, 0, 0, 20),
                border_radius=ft.BorderRadius(20, 20, 0, 0),
            ),
        )

        def _close_panel():
            panel.open = False
            self._page.update()

        self._page.overlay.append(panel)
        panel.open = True
        self._page.update()

    def _build_notifications(self):
        items = []

        # Pending assignments — tappable
        for a in self._assignment_items:
            is_overdue = False
            due_text = ""
            if a.get("due_date"):
                try:
                    from datetime import datetime

                    due = datetime.fromisoformat(a["due_date"])
                    is_overdue = datetime.now() > due
                    due_text = f" (due {due.strftime('%b %d')})" if not is_overdue else f" (overdue since {due.strftime('%b %d')})"
                except Exception:
                    pass

            items.append(
                self._notification_tile(
                    icon=ft.Icons.ASSIGNMENT_LATE_ROUNDED if is_overdue else ft.Icons.ASSIGNMENT_ROUNDED,
                    color=ft.Colors.RED_700 if is_overdue else AppColors.ACCENT,
                    title=f"{'⚠️ Overdue' if is_overdue else '📋 Pending'}: {a.get('subject', 'Assignment')}",
                    subtitle=f"{a.get('title', 'Assignment')}{due_text}",
                    is_new=True,
                    on_tap=lambda e, aid=a["id"]: self._page.run_task(self._open_assignment, aid),
                )
            )

        # Daily credit refresh
        if self.has_unread:
            items.append(
                self._notification_tile(
                    icon=ft.Icons.SAVINGS_ROUNDED,
                    color=AppColors.ACCENT,
                    title="Daily Credits Refilled!",
                    subtitle=f"You have {state.credits_remaining} credits ready to use today.",
                    is_new=True,
                )
            )

        # Streak reminder
        streak = getattr(state, "current_streak", 0)
        if streak > 0:
            items.append(
                self._notification_tile(
                    icon=ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                    color=ft.Colors.ORANGE_700,
                    title=f"🔥 {streak}-day streak!",
                    subtitle="Keep learning daily to maintain your streak.",
                )
            )

        # XP milestone
        xp = getattr(state, "xp_total", 0)
        from core.constants import LEVELS

        current_level = LEVELS[0]
        next_level = None
        for i, lvl in enumerate(LEVELS):
            if xp >= lvl["xp"]:
                current_level = lvl
                if i + 1 < len(LEVELS):
                    next_level = LEVELS[i + 1]

        if next_level:
            remaining = next_level["xp"] - xp
            items.append(
                self._notification_tile(
                    icon=ft.Icons.EMOJI_EVENTS_ROUNDED,
                    color=AppColors.PRIMARY,
                    title=f"{current_level['icon']} {current_level['name']}",
                    subtitle=f"{remaining} XP to reach {next_level['icon']} {next_level['name']}",
                )
            )

        # Study tip
        items.append(
            self._notification_tile(
                icon=ft.Icons.LIGHTBULB_ROUNDED,
                color=ft.Colors.AMBER_700,
                title="Study Tip",
                subtitle="Use the AI tutor to ask questions about topics you find difficult!",
            )
        )

        return items

    async def _open_assignment(self, assignment_id):
        state.current_assignment_id = assignment_id
        if self._navigate:
            await self._navigate("/assignment")

    def _notification_tile(self, icon, color, title, subtitle, is_new=False, on_tap=None):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, size=20, color=ft.Colors.WHITE),
                        width=40,
                        height=40,
                        border_radius=12,
                        bgcolor=color,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(title, size=14, weight=ft.FontWeight.W_600),
                            ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=4,
                        bgcolor=AppColors.PRIMARY if is_new else ft.Colors.TRANSPARENT,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(20, 12, 20, 12),
            ink=True,
            on_click=on_tap,
        )

    def set_unread(self, status: bool):
        self.badge.visible = status
        self.update()
