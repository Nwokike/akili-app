"""Settings sections — Premium (KTV structure + DDGS credit grant).

Status-first card: what Premium is, live-catalog prices, recovery ID,
restore. Typing lives in dialogs that only exist once asked for.
Platform-honest subtitles — "no ads" only where ads run.
"""

from __future__ import annotations

import contextlib
import re
import time

import flet as ft

from components.settings_kit import setting_row, settings_card
from core import tokens
from core.constants import DAILY_FREE_CREDITS, PREMIUM_DAILY_CREDITS
from core.state import state
from core.theme import AppColors
from services.premium_service import page_has_ads

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _paid_subtitle(page, claims) -> str:
    has_ads = page_has_ads(page)
    base = f"Ads removed · {PREMIUM_DAILY_CREDITS} credits a day" if has_ads else f"{PREMIUM_DAILY_CREDITS} credits a day"
    paid_through = getattr(claims, "paid_through", None) if claims else None
    if not paid_through:
        return f"{base} · thank you!"
    try:
        # paid_through may be ms or s epoch — normalise by magnitude.
        ts = int(paid_through)
        if ts > 10**12:
            ts //= 1000
        moment = time.gmtime(ts)
        label = f"{moment.tm_mday} {_MONTHS[moment.tm_mon - 1]} {moment.tm_year}"
    except Exception:
        return f"{base} · thank you!"
    product = str(getattr(claims, "product", "") or "")
    renewal = {"monthly": "renews monthly", "yearly": "renews yearly"}.get(product, "renews automatically")
    return f"{base} · active until {label} · {renewal}"


def _pitch_subtitle(page) -> str:
    if page_has_ads(page):
        return f"Removes ads and raises AI credits from {DAILY_FREE_CREDITS} to {PREMIUM_DAILY_CREDITS} a day"
    return f"Raises AI credits from {DAILY_FREE_CREDITS} to {PREMIUM_DAILY_CREDITS} a day"


def _premium_service(page):
    return getattr(page, "premium", None)


@ft.component
def build_premium_section(page: ft.Page) -> ft.Control:
    """The Premium card."""
    from state.controller_ctx import ControllerMethodsCtx

    controller = ft.use_context(ControllerMethodsCtx)
    is_premium, set_is_premium = ft.use_state(state.is_premium)
    products, set_products = ft.use_state([])
    recovery_id, set_recovery_id = ft.use_state(state.license_recovery_id)
    busy, set_busy = ft.use_state(False)
    narrow = bool(page and getattr(page, "width", None) and page.width < 600)

    def _sync_premium():
        set_is_premium(state.is_premium)

    def _watch():
        premium = _premium_service(page)
        if premium is not None:
            premium.add_listener(_sync_premium)
            _sync_premium()

            async def _load():
                with contextlib.suppress(Exception):
                    set_products(await premium.kiri_catalog())
                with contextlib.suppress(Exception):
                    set_recovery_id(await premium.license.recovery_id())

            page.run_task(_load)

        def _cleanup():
            if premium is not None:
                premium.remove_listener(_sync_premium)

        return _cleanup

    ft.on_mounted(_watch)

    # ── Dialogs ──
    def _ask_email(product_id: str, product_label: str):
        field = ft.TextField(
            label="Email for your receipt",
            hint_text="you@example.com",
            keyboard_type=ft.KeyboardType.EMAIL,
            width=320,
        )

        async def _start(product_label_inner, field_inner):
            email = (field_inner.value or "").strip()
            if not _EMAIL_RE.match(email):
                await controller.show_snack("Enter a valid email address", "warning")
                return
            with contextlib.suppress(Exception):
                page.pop_dialog()
            set_busy(True)
            try:
                premium = _premium_service(page)
                checkout = await premium.kiri_checkout(product_id, email)
                set_recovery_id(checkout.recovery_id)
                launcher = getattr(page, "url_launcher", None) or ft.UrlLauncher()
                await launcher.launch_url(checkout.checkout_url)
                await controller.show_snack("Complete the payment. This screen unlocks itself when it lands", "info")
            except Exception as ex:
                await controller.show_snack(str(ex) or "Could not start the payment", "warning")
            finally:
                set_busy(False)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Unlock Akili Premium — {product_label}", size=15),
                content=ft.Column(
                    controls=[
                        field,
                        ft.Text(
                            "Card, bank transfer and USDC are handled by our payment partner. Akili never sees the card number.",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    tight=True,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Continue", on_click=lambda e: page.run_task(_start, product_label, field)),
                ],
            )
        )

    def _ask_recovery():
        field = ft.TextField(
            label="Recovery ID",
            hint_text=recovery_id or "AKILI-…",
            width=320,
        )

        async def _redeem(field_inner):
            code = (field_inner.value or "").strip() or recovery_id
            if not code:
                await controller.show_snack("Enter the recovery ID from your purchase email", "warning")
                return
            with contextlib.suppress(Exception):
                page.pop_dialog()
            set_busy(True)
            try:
                premium = _premium_service(page)
                status = await premium.kiri_restore(code)
                if state.is_premium:
                    await controller.show_snack("Premium unlocked!", "success")
                else:
                    await controller.show_snack(f"License status: {status.status}", "info")
            except Exception as ex:
                await controller.show_snack(str(ex) or "Restore failed", "warning")
            finally:
                set_busy(False)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Restore purchases", size=15),
                content=ft.Column(
                    controls=[
                        field,
                        ft.Text(
                            "Your recovery ID is in your receipt email. It is also stored on this device.",
                            size=tokens.FONT_XS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    tight=True,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                    ft.FilledButton("Restore", on_click=lambda e: page.run_task(_redeem, field)),
                ],
            )
        )

    # ── Rows ──
    premium = _premium_service(page)
    if premium is None or not premium.available:
        return settings_card([setting_row(ft.Icons.VERIFIED_ROUNDED, "Premium", "Purchases are not available in this build.", None)])

    claims = premium.license.claims if premium is not None else None
    rows: list[ft.Control] = [
        setting_row(
            ft.Icons.VERIFIED_ROUNDED,
            "Akili Premium" if is_premium else "Go Premium",
            _paid_subtitle(page, claims) if is_premium else _pitch_subtitle(page),
            ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if is_premium else ft.Icons.CIRCLE_OUTLINED,
                size=tokens.ICON_MD,
                color=AppColors.PRIMARY if is_premium else ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE),
            ),
            stacked=narrow,
        )
    ]

    if not is_premium:
        if products:
            for product in products:
                icon = ft.Icons.LOCK_OPEN_ROUNDED if product.id == "lifetime" else ft.Icons.AUTORENEW_ROUNDED
                label = product.id.capitalize()

                def _buy(e, pid=product.id, plabel=label):
                    _ask_email(pid, plabel)

                rows.append(
                    setting_row(
                        icon,
                        label,
                        product.description or product.price_label,
                        ft.FilledButton(product.price_label, disabled=busy, on_click=_buy),
                        stacked=narrow,
                    )
                )
        else:
            rows.append(
                setting_row(
                    ft.Icons.CLOUD_OFF_ROUNDED,
                    "Unlock options unavailable",
                    "Could not reach the license service. Check your connection.",
                    None,
                    stacked=narrow,
                )
            )

    if recovery_id:

        def _copy(e):
            with contextlib.suppress(Exception):
                page.run_task(ft.Clipboard().set, recovery_id)
            page.run_task(controller.show_snack, "Recovery ID copied", "info")

        rows.append(
            setting_row(
                ft.Icons.KEY_ROUNDED,
                "Recovery ID",
                recovery_id,
                ft.OutlinedButton("Copy", on_click=_copy),
                stacked=narrow,
            )
        )

    rows.append(
        setting_row(
            ft.Icons.RESTORE_ROUNDED,
            "Restore purchases",
            "Re-check ownership (new device / reinstall)",
            ft.OutlinedButton("Restore", disabled=busy, on_click=lambda e: _ask_recovery()),
            stacked=narrow,
        )
    )

    return settings_card(rows)
