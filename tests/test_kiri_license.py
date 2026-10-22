"""Kiri license client tests — refusal/token-cache/recovery rules.

Transport is faked at the httpx level; tokens are signed with the same
throwaway P-256 helper as test_license_token.
"""

import base64
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from services.kiri_license import (
    Checkout,
    KiriLicenseService,
    LicenseUnavailable,
    status_refusal,
)
from services.license_token import ISSUER
from tests.conftest import FakeStorage

APP_ID = "ng.kiri.akili-test"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.fixture()
def keypair():
    private = ec.generate_private_key(ec.SECP256R1())
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    pub = _b64url(private.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo))
    return private, pub


def _token(private, status="active", exp_offset=86400, **over):
    now = int(time.time())
    payload = {
        "ent": "e1",
        "app": APP_ID,
        "product": "monthly",
        "scope": "premium",
        "mode": "subscription",
        "status": status,
        "paid_through": (now + exp_offset) * 1000,
        "iat": now - 60,
        "exp": now + exp_offset,
        "iss": ISSUER,
        "v": 1,
    }
    payload.update(over)
    raw = json.dumps(payload, separators=(",", ":")).encode()
    segment = _b64url(raw)
    der = private.sign(segment.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return f"v1.{segment}.{_b64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def _svc(keypair, routes: dict, storage=None):
    """A service whose httpx calls are answered from `routes`.

    routes: {(method, path): (status_code, json_body)}.
    """
    storage = storage if storage is not None else FakeStorage()
    svc = KiriLicenseService(storage=storage, app_id=APP_ID, public_key=keypair[1])

    real_client = httpx.AsyncClient

    class FakeResponse:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self._body = body

        def json(self):
            if isinstance(self._body, Exception):
                raise self._body
            return self._body

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=None, response=self)

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, **k):
            key = ("GET", url.split("license.kiri.ng")[-1])
            code, body = routes.get(key, (404, {"error": "not found"}))
            return FakeResponse(code, body)

        async def post(self, url, **k):
            key = ("POST", url.split("license.kiri.ng")[-1])
            code, body = routes.get(key, (404, {"error": "not found"}))
            return FakeResponse(code, body)

    httpx.AsyncClient = FakeClient
    return svc, storage, real_client


@pytest.fixture()
def restore_httpx():
    real = httpx.AsyncClient
    yield
    httpx.AsyncClient = real


def test_status_refusal_codes():
    assert not status_refusal(400)  # a malformed request is OUR bug — never revoke
    assert status_refusal(402) and status_refusal(403) and status_refusal(404)
    assert not status_refusal(429)  # throttling must never revoke
    assert not status_refusal(500)


@pytest.mark.asyncio
async def test_restore_caches_token_and_unlocks(keypair, restore_httpx):
    token = _token(keypair[0])
    svc, storage, _ = _svc(keypair, {("POST", "/restore"): (200, {"status": "active", "product": "monthly", "recovery_id": "R1", "token": token})})
    status = await svc.restore("R1")
    assert status.unlocks is True
    assert svc.unlocked is True
    assert await storage.get("akili_license_token") == token


@pytest.mark.asyncio
async def test_refusal_drops_unlock(keypair, restore_httpx):
    svc, storage, _ = _svc(keypair, {("POST", "/restore"): (403, {"error": "nope"})})
    svc._unlocked = True  # simulate a standing unlock
    with pytest.raises(LicenseUnavailable):
        await svc.restore("R1")
    assert svc.unlocked is False
    assert svc.claims is None


@pytest.mark.asyncio
async def test_429_preserves_local_verdict(keypair, restore_httpx):
    svc, _, _ = _svc(keypair, {("POST", "/restore"): (429, {"error": "slow down"})})
    svc._unlocked = True
    with pytest.raises(LicenseUnavailable):
        await svc.restore("R1")
    assert svc.unlocked is True  # throttling never revokes


@pytest.mark.asyncio
async def test_unverifiable_token_rejected_even_when_active(keypair, restore_httpx):
    other = ec.generate_private_key(ec.SECP256R1())
    bad = _token(other)  # signed by the wrong key
    svc, _, _ = _svc(keypair, {("POST", "/restore"): (200, {"status": "active", "recovery_id": "R1", "token": bad})})
    with pytest.raises(LicenseUnavailable):
        await svc.restore("R1")
    assert svc.unlocked is False


@pytest.mark.asyncio
async def test_valid_token_for_revoked_status_not_cached(keypair, restore_httpx):
    token = _token(keypair[0], status="active")
    svc, storage, _ = _svc(keypair, {("POST", "/restore"): (200, {"status": "revoked", "recovery_id": "R1", "token": token})})
    status = await svc.restore("R1")
    assert status.unlocks is False
    assert svc.unlocked is False
    assert await storage.get("akili_license_token") == ""


@pytest.mark.asyncio
async def test_checkout_persists_recovery_id(keypair, restore_httpx):
    svc, storage, _ = _svc(
        keypair,
        {("POST", "/checkout"): (200, {"recovery_id": "K1", "checkout_url": "https://pay/x", "product": "monthly", "amount": 4.99, "currency": "USD"})},
    )
    order = await svc.checkout("monthly", "a@b.c")
    assert isinstance(order, Checkout)
    assert order.recovery_id == "K1"
    assert await storage.get("akili_license_recovery_id") == "K1"


@pytest.mark.asyncio
async def test_checkout_rejects_incomplete_order(keypair, restore_httpx):
    svc, _, _ = _svc(keypair, {("POST", "/checkout"): (200, {"recovery_id": "K1"})})
    with pytest.raises(LicenseUnavailable):
        await svc.checkout("monthly", "a@b.c")


@pytest.mark.asyncio
async def test_refresh_without_recovery_id_returns_none(keypair, restore_httpx):
    svc, _, _ = _svc(keypair, {})
    assert await svc.refresh() is None


@pytest.mark.asyncio
async def test_apply_cached_token_offline(keypair, restore_httpx):
    from tests.conftest import FakeStorage

    storage = FakeStorage({"akili_license_token": _token(keypair[0])})
    svc, _, _ = _svc(keypair, {}, storage=storage)
    assert await svc.apply_cached_token() is True
    assert svc.unlocked is True


@pytest.mark.asyncio
async def test_apply_cached_token_rejected_clears(keypair, restore_httpx):
    from tests.conftest import FakeStorage

    storage = FakeStorage({"akili_license_token": "garbage"})
    svc, _, _ = _svc(keypair, {}, storage=storage)
    assert await svc.apply_cached_token() is False
    assert svc.unlocked is False
