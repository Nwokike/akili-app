"""BannerAd — canonical banner ad builder.

Ported from Sherlock's banner_ad pattern (the house standard).
Mobile-only: returns zero-size Container on desktop/web.
"""

from __future__ import annotations

import flet as ft
from flet import Control

from core import tokens
from core.constants import AD_BANNER_UNIT_ID


def build_banner_ad(page: ft.Page | None = None) -> Control:
    """Build a banner ad container, or a zero-size placeholder off-mobile."""
    if page is None:
        try:
            from flet import context as flet_context

            page = flet_context.page
        except Exception:
            page = None

    if page is None or page.web or not page.platform.is_mobile():
        return ft.Container(width=0, height=0)

    try:
        import flet_ads as ads
    except ImportError:
        return ft.Container(width=0, height=0)

    banner = ads.BannerAd(
        unit_id=AD_BANNER_UNIT_ID,
        on_load=lambda e: None,
        on_error=lambda e: None,
    )

    return ft.Container(
        content=ft.Row(
            controls=[banner],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_MD,
            right=tokens.SPACE_MD,
            top=tokens.SPACE_XS,
            bottom=tokens.SPACE_XS,
        ),
    )
