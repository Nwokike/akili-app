"""Akili v2 — entry point.

After-School Learning App for Everyone.
Built on Flet 1.0.2 with React-in-Flet components.
"""

from __future__ import annotations

import flet as ft

from app_controller import AppController


async def main(page: ft.Page):
    controller = AppController(page)
    await controller.init()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
