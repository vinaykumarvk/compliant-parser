from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Iterable

from cryptography.fernet import Fernet
from fastapi import Request

from src.core.errors import KISError


def _derive_fernet_key(secret_key: str) -> bytes:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str, secret_key: str) -> str:
    return Fernet(_derive_fernet_key(secret_key)).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str, secret_key: str) -> str:
    return Fernet(_derive_fernet_key(secret_key)).decrypt(token.encode("utf-8")).decode("utf-8")


def secret_fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:24]}"


def hash_value(value: str, *, salt: str = "kis") -> str:
    return hmac.new(salt.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def require_scope(request: Request, required: str) -> None:
    scopes = set(getattr(request.state, "scopes", set()) or set())
    if "system:admin" not in scopes and required not in scopes:
        raise KISError("SCOPE_DENIED", f"Required scope missing: {required}", status_code=403)


def require_domain_access(request: Request, domain_id: str, *, allowed_scopes: Iterable[str] = ("domain:admin",)) -> None:
    settings = request.app.state.settings
    if settings.auth_disabled:
        return
    scopes = set(getattr(request.state, "scopes", set()) or set())
    state_domain = getattr(request.state, "domain_id", None)
    if "system:admin" in scopes:
        return
    if state_domain == domain_id and (not allowed_scopes or scopes.intersection(set(allowed_scopes))):
        return
    raise KISError("DOMAIN_ACCESS_DENIED", "Principal is not permitted for this domain.", status_code=403)
