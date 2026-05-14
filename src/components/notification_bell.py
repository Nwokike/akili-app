import flet as ft

from core.theme import AppColors


class NotificationBell(ft.Stack):
    def __init__(self, page: ft.Page, has_unread: bool = False):
        super().__init__()
        self._page = page
        self.has_unread = has_unread

        # Removed hardcoded black color so it adapts to Dark/Light mode
        self.bell_icon = ft.IconButton(icon=ft.Icons.NOTIFICATIONS_OUTLINED, on_click=self.handle_click)

        # The simulated red badge
        self.badge = ft.Container(width=10, height=10, bgcolor=ft.Colors.RED_700, border_radius=5, top=8, right=8, visible=self.has_unread)

        self.controls = [self.bell_icon, self.badge]

    def handle_click(self, e):
        # Clear the badge when clicked
        if self.badge.visible:
            self.badge.visible = False
            self.update()

            # Show the in-app "catch-up" alert using your app's SnackBar pattern
            self._page.snack_bar = ft.SnackBar(
                content=ft.Text("Welcome back! Your daily credits have been refilled.", color=ft.Colors.WHITE),
                bgcolor=AppColors.SUCCESS,
            )
        else:
            self._page.snack_bar = ft.SnackBar(content=ft.Text("No new notifications.", color=ft.Colors.WHITE), bgcolor=ft.Colors.ON_SURFACE_VARIANT)

        self._page.snack_bar.open = True
        self._page.update()

    def set_unread(self, status: bool):
        self.badge.visible = status
        self.update()
