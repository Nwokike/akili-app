"""Device-gate helper — biometric/PIN authentication for locked screens.

Ported from Sherlock's biometric_service.py (the house standard).

Policy: unenforceable codes (no hardware, nothing enrolled, no
credentials) GRANT access with an explicit log so users are never
stranded; cancellations stay locked (return False).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import flet_local_auth as _fla

    _AUTH_AVAILABLE = True
except ImportError:
    _fla = None  # type: ignore[assignment]
    _AUTH_AVAILABLE = False


def _is_unenforceable(code_name: str) -> bool:
    return code_name in (
        "NO_BIOMETRIC_HARDWARE",
        "NO_BIOMETRICS_ENROLLED",
        "NO_CREDENTIALS_SET",
    )


async def authenticate(reason: str = "Unlock Akili") -> bool:
    """Prompt device auth. True = unlocked, False = still locked."""
    if not _AUTH_AVAILABLE:
        return False
    try:
        from flet import context as flet_context

        if flet_context.page is None:
            return False
    except Exception:
        return False
    try:
        svc = _fla.LocalAuthentication()
        try:
            supported = await svc.is_device_supported()
        except AttributeError:
            supported = True
        if not supported:
            logger.info("biometric not supported on this device; granting access")
            return True
        return bool(await svc.authenticate(reason))
    except Exception as exc:
        name = type(exc).__name__
        code = str(getattr(exc, "code", "") or name)
        if _is_unenforceable(code) or _is_unenforceable(name):
            logger.info("biometric unenforceable (%s); granting access", code)
            return True
        logger.info("biometric auth failed/locked: %s", exc)
        return False
