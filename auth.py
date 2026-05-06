from __future__ import annotations

"""JWT authentication and role-based access control for the IQW platform."""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Set

import jwt
from fastapi import Depends, Request
from passlib.context import CryptContext


# ---------------------------------------------------------------------------
# Lazy import helpers (break circular dep with api_v1)
# ---------------------------------------------------------------------------

def _raise_api_error(code_name: str, message: str, field: Optional[str] = None) -> None:
    """Deferred import wrapper for api_v1.raise_api_error."""
    from api_v1 import ErrorCode, raise_api_error
    raise_api_error(ErrorCode[code_name], message, field)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_jwt_secret_env = os.getenv("JWT_SECRET_KEY") or os.getenv("APP_SESSION_SECRET")
if not _jwt_secret_env:
    if os.getenv("IQW_ALLOW_INSECURE_DEV_SECRET", "").lower() in {"1", "true", "yes", "on"}:
        import warnings
        warnings.warn(
            "JWT_SECRET_KEY not set - using explicitly enabled insecure development secret.",
            stacklevel=1,
        )
        _jwt_secret_env = "dev-insecure-secret-change-me"
    else:
        raise RuntimeError(
            "JWT_SECRET_KEY or APP_SESSION_SECRET must be set. "
            "Set IQW_ALLOW_INSECURE_DEV_SECRET=true only for local throwaway development."
        )
JWT_SECRET_KEY: str = _jwt_secret_env
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

MAX_FAILED_ATTEMPTS: int = 5
LOCKOUT_DURATION_MINUTES: int = 30


# ---------------------------------------------------------------------------
# Password hashing (bcrypt via passlib)
# ---------------------------------------------------------------------------

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT token creation / validation
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    role: str,
    expires_delta: timedelta = timedelta(hours=8),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    role: str = "",
    expires_delta: timedelta = timedelta(hours=24),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises on expiry or bad signature."""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        _raise_api_error("AUTHENTICATION_ERROR", "Token has expired")
    except jwt.InvalidTokenError as exc:
        _raise_api_error("AUTHENTICATION_ERROR", f"Invalid token: {exc}")
    return {}  # pragma: no cover — raise_api_error always raises


# ---------------------------------------------------------------------------
# Token blacklist (in-memory, for logout)
# ---------------------------------------------------------------------------

blacklisted_tokens: Set[str] = set()


def blacklist_token(token: str) -> None:
    blacklisted_tokens.add(token)


def is_blacklisted(token: str) -> bool:
    return token in blacklisted_tokens


# ---------------------------------------------------------------------------
# Account lockout tracking (in-memory)
# ---------------------------------------------------------------------------

_failed_attempts: Dict[str, Dict[str, Any]] = {}


def check_lockout(employee_id: str) -> None:
    """Raise 423 if the account is currently locked."""
    record = _failed_attempts.get(employee_id)
    if record is None:
        return
    locked_until = record.get("locked_until")
    if locked_until is not None:
        if time.time() < locked_until:
            _raise_api_error(
                "ACCOUNT_LOCKED",
                "Account locked due to multiple failed attempts. "
                "Try again after 30 minutes or contact your System Administrator.",
            )
        # Lock period has expired — reset
        clear_failed_attempts(employee_id)


def record_failed_attempt(employee_id: str) -> None:
    record = _failed_attempts.setdefault(employee_id, {"count": 0, "locked_until": None})
    record["count"] += 1
    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = time.time() + LOCKOUT_DURATION_MINUTES * 60


def clear_failed_attempts(employee_id: str) -> None:
    _failed_attempts.pop(employee_id, None)


# ---------------------------------------------------------------------------
# Permissions matrix
# ---------------------------------------------------------------------------

PERMISSIONS: Dict[str, list] = {
    "create_case": ["IO", "Clerk", "SHO", "System_Admin"],
    "transition_case_status": ["IO", "SHO", "System_Admin"],
    "upload_document": ["IO", "Clerk", "SHO", "System_Admin"],
    "run_quality_check": ["IO", "AI_Admin"],
    "run_section_recommendation": ["IO", "AI_Admin"],
    "run_congruence": ["IO", "AI_Admin"],
    "generate_document": ["IO"],
    "sign_document": ["IO"],
    "dismiss_alert": ["IO", "AI_Admin"],
    "view_own_analytics": ["IO"],
    "view_all_analytics": ["AI_Admin", "System_Admin"],
    "manage_kb": ["AI_Admin"],
    "manage_users": ["System_Admin"],
    "manage_config": ["System_Admin"],
    "upload_judgment": ["IO", "AI_Admin"],
    "access_ocr": ["IO", "Clerk", "AI_Admin"],
}


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _extract_bearer_token(request: Request) -> str:
    """Pull the raw JWT string from the Authorization header."""
    auth_header: Optional[str] = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        _raise_api_error(
            "AUTHENTICATION_ERROR",
            "Missing or malformed Authorization header",
        )
    return auth_header[7:]


async def require_auth(request: Request) -> dict:
    """FastAPI dependency — validates JWT and returns payload dict."""
    token = _extract_bearer_token(request)
    if is_blacklisted(token):
        _raise_api_error("AUTHENTICATION_ERROR", "Token has been revoked")
    payload = decode_token(token)
    if payload.get("type") != "access":
        _raise_api_error("AUTHENTICATION_ERROR", "Expected an access token")
    return payload


def require_role(*roles: str) -> Callable:
    """Return a dependency that enforces the user has one of the listed roles."""

    async def _check(payload: dict = Depends(require_auth)) -> dict:
        if payload.get("role") not in roles:
            _raise_api_error(
                "AUTHORIZATION_ERROR",
                f"Role '{payload.get('role')}' is not authorized. "
                f"Required: {', '.join(roles)}",
            )
        return payload

    return _check


def require_permission(permission: str) -> Callable:
    """Return a dependency that checks the user's role against PERMISSIONS."""

    allowed_roles = PERMISSIONS.get(permission)
    if allowed_roles is None:
        raise ValueError(f"Unknown permission: {permission}")

    async def _check(payload: dict = Depends(require_auth)) -> dict:
        if payload.get("role") not in allowed_roles:
            _raise_api_error(
                "AUTHORIZATION_ERROR",
                f"Permission '{permission}' denied for role '{payload.get('role')}'",
            )
        return payload

    return _check
