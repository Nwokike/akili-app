"""License token tests — the claim-check order of the KTV-ported verifier.

Test tokens are signed with a throwaway P-256 pair (cryptography is a
transitive dep via pyjwt/mcp) in the Worker's raw r||s format.
"""

import base64
import hashlib
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from services.license_token import ISSUER, LicenseClaims, TokenRejected, verify_token

APP_ID = "ng.kiri.akili-test"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _spki_b64url(public_key) -> str:
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    der = public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return _b64url(der)


@pytest.fixture()
def keypair():
    private = ec.generate_private_key(ec.SECP256R1())
    return private, _spki_b64url(private.public_key())


def _sign(private, payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    segment = _b64url(raw)
    der = private.sign(segment.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"v1.{segment}.{_b64url(sig)}"


def _claims(**over):
    now = int(time.time())
    base = {
        "ent": "e1",
        "app": APP_ID,
        "product": "monthly",
        "scope": "premium",
        "mode": "subscription",
        "status": "active",
        "paid_through": (now + 86400) * 1000,
        "iat": now - 60,
        "exp": now + 86400,
        "iss": ISSUER,
        "v": 1,
    }
    base.update(over)
    return base


def test_valid_token_returns_claims(keypair):
    private, pub = keypair
    claims = verify_token(_sign(private, _claims()), pub, APP_ID)
    assert isinstance(claims, LicenseClaims)
    assert claims.status == "active"
    assert claims.product == "monthly"
    assert claims.is_lifetime is False


def test_lifetime_token_has_no_expiry(keypair):
    private, pub = keypair
    payload = _claims()
    del payload["exp"]
    claims = verify_token(_sign(private, payload), pub, APP_ID)
    assert claims.expires_at is None
    assert claims.is_lifetime is True


def test_grace_unlocks(keypair):
    private, pub = keypair
    assert verify_token(_sign(private, _claims(status="grace")), pub, APP_ID).status == "grace"


def test_missing_token(keypair):
    _, pub = keypair
    with pytest.raises(TokenRejected) as exc:
        verify_token("", pub, APP_ID)
    assert exc.value.reason == "missing_token"


def test_malformed_shape(keypair):
    _, pub = keypair
    with pytest.raises(TokenRejected) as exc:
        verify_token("v1.only-two", pub, APP_ID)
    assert exc.value.reason == "malformed_token"


def test_tampered_payload_fails_signature(keypair):
    private, pub = keypair
    token = _sign(private, _claims())
    head, payload, sig = token.split(".")
    raw = base64.urlsafe_b64decode(payload + "==").decode()
    doc = json.loads(raw)
    doc["status"] = "active"
    doc["product"] = "lifetime"
    forged_payload = _b64url(json.dumps(doc, separators=(",", ":")).encode())
    with pytest.raises(TokenRejected) as exc:
        verify_token(f"{head}.{forged_payload}.{sig}", pub, APP_ID)
    assert exc.value.reason == "bad_signature"


def test_wrong_key_fails_signature(keypair):
    private, _ = keypair
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(TokenRejected) as exc:
        verify_token(_sign(private, _claims()), _spki_b64url(other.public_key()), APP_ID)
    assert exc.value.reason == "bad_signature"


def test_bad_issuer(keypair):
    private, pub = keypair
    with pytest.raises(TokenRejected) as exc:
        verify_token(_sign(private, _claims(iss="evil.example")), pub, APP_ID)
    assert exc.value.reason == "bad_issuer"


def test_wrong_app(keypair):
    private, pub = keypair
    with pytest.raises(TokenRejected) as exc:
        verify_token(_sign(private, _claims(app="ng.kiri.other")), pub, APP_ID)
    assert exc.value.reason == "wrong_app"


def test_unsupported_version(keypair):
    private, pub = keypair
    with pytest.raises(TokenRejected) as exc:
        verify_token(_sign(private, _claims(v=2)), pub, APP_ID)
    assert exc.value.reason == "unsupported_version"


def test_non_unlocking_status_rejected(keypair):
    private, pub = keypair
    for status in ("expired", "revoked", "pending", ""):
        with pytest.raises(TokenRejected):
            verify_token(_sign(private, _claims(status=status)), pub, APP_ID)


def test_expired_token(keypair):
    private, pub = keypair
    now = int(time.time())
    with pytest.raises(TokenRejected) as exc:
        verify_token(_sign(private, _claims(exp=now - 10)), pub, APP_ID)
    assert exc.value.reason == "expired"


def test_non_int_exp_is_malformed(keypair):
    private, pub = keypair
    with pytest.raises(TokenRejected) as exc:
        verify_token(_sign(private, _claims(exp="tomorrow")), pub, APP_ID)
    assert exc.value.reason == "malformed_claims"


def test_bad_public_key():
    with pytest.raises(TokenRejected) as exc:
        verify_token("v1.e30.e30", "not-a-key", APP_ID)
    assert exc.value.reason in ("bad_public_key", "malformed_token", "bad_signature")


def test_expiry_uses_injected_clock(keypair):
    """Deterministic expiry via the `now` parameter (no sleeping)."""
    private, pub = keypair
    token = _sign(private, _claims(iat=1_699_998_900, exp=1_700_000_000))
    assert verify_token(token, pub, APP_ID, now=1_699_999_000).status == "active"
    with pytest.raises(TokenRejected) as exc:
        verify_token(token, pub, APP_ID, now=1_700_000_001)
    assert exc.value.reason == "expired"


def test_sha256_known_vector():
    """Sanity: the stdlib SHA-256 the verifier relies on is intact."""
    assert hashlib.sha256(b"abc").hexdigest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
