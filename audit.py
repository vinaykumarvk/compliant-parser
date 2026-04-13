from __future__ import annotations

"""Audit logging and document integrity utilities for the IQW platform."""

import hashlib
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory audit store (replaced by DB in a later phase)
# ---------------------------------------------------------------------------
_audit_log_store: list[dict] = []


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------

def compute_sha256(file_bytes: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *file_bytes*."""
    return hashlib.sha256(file_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Core audit-logging function
# ---------------------------------------------------------------------------

def log_audit_event(
    user_id: Optional[str],
    action_type: str,
    entity_type: str,
    entity_id: Optional[str],
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Create an audit-log entry and persist it to the in-memory store.

    Returns the full entry dict so callers (or tests) can inspect it.
    """
    entry: dict = {
        "id": str(_uuid.uuid4()),
        "user_id": user_id,
        "action_type": action_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action_details": details,
        "ip_address": ip_address,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _audit_log_store.append(entry)
    logger.debug("audit: %s %s %s/%s by user=%s", action_type, entity_type, entity_type, entity_id, user_id)
    return entry


# ---------------------------------------------------------------------------
# Action-type inference from HTTP method + path
# ---------------------------------------------------------------------------

def infer_action_type(method: str, path: str) -> Optional[str]:
    """Map an HTTP method and URL path to a human-readable action type.

    Returns ``None`` for actions that should *not* be logged (e.g. plain GETs).
    """
    method = method.upper()

    if method == "POST":
        if "/auth/" in path:
            if "logout" in path:
                return "Logout"
            return "Login"
        if "/analysis/" in path:
            return "AI_Analysis"
        if "/documents/generate" in path:
            return "Document_Generation"
        return "Upload"

    if method in ("PUT", "PATCH"):
        return "Edit"

    if method == "DELETE":
        return "Delete"

    if method == "GET":
        if "/export" in path:
            return "Export"
        return None  # don't log ordinary reads

    return None


# ---------------------------------------------------------------------------
# Path parsing helpers
# ---------------------------------------------------------------------------

_PATH_SEGMENT_RE = re.compile(
    r"/api/v1/(?P<entity_type>[a-z_]+)(?:/(?P<entity_id>[^/]+))?",
)


def _extract_entity(path: str) -> tuple[str, Optional[str]]:
    """Pull the entity type and optional entity id from a ``/api/v1/`` path."""
    m = _PATH_SEGMENT_RE.search(path)
    if m:
        return m.group("entity_type"), m.group("entity_id")
    return "unknown", None


def _decode_user_id_from_jwt(auth_header: Optional[str]) -> Optional[str]:
    """Best-effort JWT decode — returns ``None`` on any failure."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        # Import project JWT settings so the middleware uses the same key.
        from auth import JWT_ALGORITHM, JWT_SECRET_KEY

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Starlette middleware
# ---------------------------------------------------------------------------

class AuditMiddleware(BaseHTTPMiddleware):
    """Log mutating API requests to the audit trail after the response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(_uuid.uuid4())

        # Only audit /api/v1/ routes
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id

        # Skip GET requests to avoid log bloat
        if request.method.upper() == "GET":
            return response

        action = infer_action_type(request.method, request.url.path)
        if action is None:
            return response

        user_id = _decode_user_id_from_jwt(request.headers.get("Authorization"))
        entity_type, entity_id = _extract_entity(request.url.path)
        ip_address = request.client.host if request.client else None

        log_audit_event(
            user_id=user_id,
            action_type=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details={"status_code": response.status_code, "request_id": request_id},
            ip_address=ip_address,
        )

        return response


# ---------------------------------------------------------------------------
# Search / retrieve helpers
# ---------------------------------------------------------------------------

def search_audit_logs(
    filters: Optional[dict] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Filter and paginate the in-memory audit store.

    Supported filter keys: ``date_from``, ``date_to``, ``user_id``,
    ``action_type``, ``entity_type``.
    """
    items = list(_audit_log_store)
    if filters:
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        f_user = filters.get("user_id")
        f_action = filters.get("action_type")
        f_entity = filters.get("entity_type")

        if date_from:
            items = [e for e in items if e["timestamp"] >= date_from]
        if date_to:
            items = [e for e in items if e["timestamp"] <= date_to]
        if f_user:
            items = [e for e in items if e["user_id"] == f_user]
        if f_action:
            items = [e for e in items if e["action_type"] == f_action]
        if f_entity:
            items = [e for e in items if e["entity_type"] == f_entity]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_audit_log(log_id: str) -> Optional[dict]:
    """Return a single audit entry by its id, or ``None``."""
    for entry in _audit_log_store:
        if entry["id"] == log_id:
            return entry
    return None
