import flet as ft

from core.state import state
from core.theme import AppColors, AppStyles


class NotificationBell(ft.Stack):
    def __init__(self, page: ft.Page, has_unread: bool = False):
        super().__init__()
        self._page = page
        self.has_unread = has_unread

        self.bell_icon = ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_OUTLINED,
            on_click=self.handle_click,
        )

        self.badge = ft.Container(
            width=10,
            height=10,
            bgcolor=ft.Colors.RED_700,
            border_radius=5,
            top=8,
            right=8,
            visible=self.has_unread,
        )

        self.controls = [self.bell_icon, self.badge]

    def handle_click(self, e):
        # Clear the badge
        if self.badge.visible:
            self.badge.visible = False

        # Build notification items
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
                            items if items else [
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
        """Generate contextual notification items based on current state."""
        items = []

        # Daily credit refresh notification
        if self.has_unread:
            items.append(self._notification_tile(
                icon=ft.Icons.SAVINGS_ROUNDED,
                color=AppColors.ACCENT,
                title="Daily Credits Refilled!",
                subtitle=f"You have {state.credits_remaining} credits ready to use today.",
                is_new=True,
            ))

        # Streak reminder
        streak = getattr(state, "daily_streak", 0)
        if streak > 0:
            items.append(self._notification_tile(
                icon=ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                color=ft.Colors.ORANGE_700,
                title=f"🔥 {streak}-day streak!",
                subtitle="Keep learning daily to maintain your streak.",
            ))

        # XP milestone hints
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
            items.append(self._notification_tile(
                icon=ft.Icons.EMOJI_EVENTS_ROUNDED,
                color=AppColors.PRIMARY,
                title=f"{current_level['icon']} {current_level['name']}",
                subtitle=f"{remaining} XP to reach {next_level['icon']} {next_level['name']}",
            ))

        # Study tip
        items.append(self._notification_tile(
            icon=ft.Icons.LIGHTBULB_ROUNDED,
            color=ft.Colors.AMBER_700,
            title="Study Tip",
            subtitle="Use the AI tutor to ask questions about topics you find difficult!",
        ))

        return items

    def _notification_tile(self, icon, color, title, subtitle, is_new=False):
        """Build a single notification row."""
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
        )

    def set_unread(self, status: bool):
        self.badge.visible = status
        self.update()
