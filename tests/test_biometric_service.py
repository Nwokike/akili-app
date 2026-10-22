"""Biometric service tests — grant/deny matrix with mocked local-auth."""

import pytest

import services.biometric_service as bio
from tests.conftest import FakePage


@pytest.fixture()
def live_page():
    """Bind a FakePage into flet's context var for the test body."""
    from flet.controls import context as flet_context

    var = flet_context._context_page
    token = var.set(FakePage())
    yield
    var.reset(token)


class _Svc:
    def __init__(self, supported=True, ok=True, exc=None):
        self._supported = supported
        self._ok = ok
        self._exc = exc

    async def is_device_supported(self):
        return self._supported

    async def authenticate(self, reason):
        if self._exc is not None:
            raise self._exc
        return self._ok


@pytest.mark.asyncio
async def test_unavailable_package_denies(monkeypatch):
    monkeypatch.setattr(bio, "_AUTH_AVAILABLE", False)
    assert await bio.authenticate() is False


@pytest.mark.asyncio
async def test_success_unlocks(monkeypatch, live_page):
    monkeypatch.setattr(bio, "_AUTH_AVAILABLE", True)
    monkeypatch.setattr(bio._fla, "LocalAuthentication", lambda: _Svc(ok=True))
    assert await bio.authenticate() is True


@pytest.mark.asyncio
async def test_user_cancel_stays_locked(monkeypatch, live_page):
    class _Cancel(Exception):
        code = "USER_CANCEL"

    monkeypatch.setattr(bio, "_AUTH_AVAILABLE", True)
    monkeypatch.setattr(bio._fla, "LocalAuthentication", lambda: _Svc(exc=_Cancel()))
    assert await bio.authenticate() is False


@pytest.mark.asyncio
async def test_unenforceable_grants(monkeypatch, live_page):
    class _NoHw(Exception):
        code = "NO_BIOMETRIC_HARDWARE"

    class _NoEnrolled(Exception):
        code = "NO_BIOMETRICS_ENROLLED"

    class _NoCreds(Exception):
        code = "NO_CREDENTIALS_SET"

    monkeypatch.setattr(bio, "_AUTH_AVAILABLE", True)
    for exc in (_NoHw(), _NoEnrolled(), _NoCreds()):
        monkeypatch.setattr(bio._fla, "LocalAuthentication", lambda exc=exc: _Svc(exc=exc))
        assert await bio.authenticate() is True


@pytest.mark.asyncio
async def test_unsupported_device_grants(monkeypatch, live_page):
    monkeypatch.setattr(bio, "_AUTH_AVAILABLE", True)
    monkeypatch.setattr(bio._fla, "LocalAuthentication", lambda: _Svc(supported=False))
    assert await bio.authenticate() is True


def test_is_unenforceable_matrix():
    assert bio._is_unenforceable("NO_BIOMETRIC_HARDWARE") is True
    assert bio._is_unenforceable("NO_BIOMETRICS_ENROLLED") is True
    assert bio._is_unenforceable("NO_CREDENTIALS_SET") is True
    assert bio._is_unenforceable("USER_CANCEL") is False
    assert bio._is_unenforceable("") is False
