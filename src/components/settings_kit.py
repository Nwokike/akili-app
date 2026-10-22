"""Settings kit — row primitives for the settings screen.

Ported from Sherlock's _setting_row + _settings_card (the house standard).
`stacked` moves the trailing control below the text on narrow screens.
Every Phase 6 section consumes these — no ad-hoc rows.
"""

from __future__ import annotations

import flet as ft
from flet import Control

from core import tokens


def setting_row(
    icon: ft.IconData,
    title: str,
    subtitle: str,
    trailing: Control | None = None,
    stacked: bool = False,
    on_click=None,
) -> ft.Container:
    """One settings row: icon + text + trailing control.

    `on_click` makes the whole row tappable (Contact/Rate/link rows).
    `trailing` is None-safe by design.
    """
    icon_box = ft.Container(
        content=ft.Icon(icon, size=tokens.ICON_MD, color=ft.Colors.ON_SURFACE_VARIANT),
        width=tokens.ICON_BACKDROP,
        height=tokens.ICON_BACKDROP,
        border_radius=tokens.ICON_BACKDROP_RADIUS,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_LIGHT, ft.Colors.ON_SURFACE),
        alignment=ft.Alignment.CENTER,
    )
    text_col = ft.Column(
        controls=[
            ft.Text(title, size=tokens.FONT_MD, weight=ft.FontWeight.W_500),
            ft.Text(
                subtitle,
                size=tokens.FONT_XS,
                color=ft.Colors.with_opacity(tokens.OPACITY_DIM, ft.Colors.ON_SURFACE),
            ),
        ],
        spacing=tokens.SPACE_XXS,
        expand=True,
    )
    if stacked and trailing is not None:
        stretches = isinstance(trailing, (ft.Slider, ft.SegmentedButton))
        trailing_line = ft.Row(
            controls=[
                ft.Container(width=tokens.ICON_BACKDROP + tokens.SPACE_MD),
                (ft.Row(controls=[trailing], expand=True) if stretches else trailing),
            ],
            spacing=0,
        )
        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[icon_box, text_col],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                trailing_line,
            ],
            spacing=tokens.SPACE_XS,
        )
    elif trailing is not None:
        content = ft.Row(
            controls=[icon_box, text_col, trailing],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    else:
        content = ft.Row(
            controls=[icon_box, text_col],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    return ft.Container(
        content=content,
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_MD,
            bottom=tokens.SPACE_MD,
        ),
        ink=on_click is not None,
        on_click=on_click,
    )


def settings_card(controls: list[Control]) -> ft.Container:
    """A grouped settings card with dividers between rows."""
    items: list[Control] = []
    for i, ctrl in enumerate(controls):
        if i > 0:
            items.append(
                ft.Divider(
                    height=1,
                    color=ft.Colors.with_opacity(tokens.OPACITY_SUBTLE, ft.Colors.OUTLINE),
                )
            )
        items.append(ctrl)
    return ft.Container(
        content=ft.Column(controls=items, spacing=0),
        margin=ft.Margin(tokens.SPACE_XL, 0, tokens.SPACE_XL, tokens.SPACE_SM),
        border_radius=tokens.RADIUS_LG,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.all(
            width=1,
            color=ft.Colors.with_opacity(tokens.OPACITY_SUBTLE, ft.Colors.OUTLINE),
        ),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
