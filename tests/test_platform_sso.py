"""Platform SSO launch-token verification tests."""
import base64
import hashlib
import hmac
import json
import time

from app import _verify_platform_sso_token

SECRET = "sso-test-secret"


def _make_token(payload: dict, secret: str = SECRET) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signature = (
        base64.urlsafe_b64encode(hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest())
        .rstrip(b"=")
        .decode()
    )
    return f"{encoded}.{signature}"


def _payload(**overrides) -> dict:
    base = {
        "u": "user-1",
        "d": "Demo Administrator",
        "p": "platform_pilot_operator",
        "t": "kerala-police",
        "a": "iqw",
        "e": int(time.time() * 1000) + 60_000,
    }
    base.update(overrides)
    return base


def test_accepts_valid_token():
    payload = _verify_platform_sso_token(_make_token(_payload()), SECRET)
    assert payload is not None
    assert payload["t"] == "kerala-police"


def test_rejects_wrong_audience():
    assert _verify_platform_sso_token(_make_token(_payload(a="dopams")), SECRET) is None


def test_rejects_expired_token():
    assert _verify_platform_sso_token(_make_token(_payload(e=int(time.time() * 1000) - 1000)), SECRET) is None


def test_rejects_tampered_signature():
    token = _make_token(_payload())
    assert _verify_platform_sso_token(token[:-2] + "xx", SECRET) is None
    assert _verify_platform_sso_token(token, "other-secret") is None
