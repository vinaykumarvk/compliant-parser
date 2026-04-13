from __future__ import annotations

"""Audit logging and document integrity utilities for the IQW platform."""

import hashlib
import logging
import re
import uuid as _uuid
from typing import Optional

import jwt
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from models import AuditLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DEPRECATED: in-memory audit store — kept as an empty list for backward
# compatibility.  New code MUST use the async ORM functions below instead.
# This will be removed in a future release.
# ---------------------------------------------------------------------------
_audit_log_store: list[dict] = []


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------

def compute_sha256(file_bytes: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *file_bytes*."""
    return hashlib.sha256(file_bytes).hexdigest()


# ---------------------------------------------------------------------------
# ORM → dict helper
# ---------------------------------------------------------------------------

def _audit_to_dict(entry: AuditLog) -> dict:
    """Convert an ``AuditLog`` ORM instance to a plain dict whose keys match
    the legacy in-memory format."""
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "action_type": entry.action_type.value if hasattr(entry.action_type, "value") else entry.action_type,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "action_details": entry.action_details,
        "ip_address": entry.ip_address,
        "session_id": entry.session_id,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
    }


# ---------------------------------------------------------------------------
# Core audit-logging function
# ---------------------------------------------------------------------------

async def log_audit_event(
    user_id: Optional[str],
    action_type: str,
    entity_type: str,
    entity_id: Optional[str],
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    session_id: Optional[str] = None,
    *,
    db: AsyncSession,
) -> dict:
    """Create an audit-log entry and persist it via the ORM.

    Returns the full entry dict so callers (or tests) can inspect it.
    """
    entry = AuditLog(
        user_id=user_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action_details=details,
        ip_address=ip_address,
        session_id=session_id,
        created_by=user_id,
    )
    db.add(entry)
    await db.flush()
    logger.debug(
        "audit: %s %s %s/%s by user=%s",
        action_type, entity_type, entity_type, entity_id, user_id,
    )
    return _audit_to_dict(entry)


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

        try:
            from database import get_session_factory

            factory = await get_session_factory()
            async with factory() as session:
                await log_audit_event(
                    user_id=user_id,
                    action_type=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    details={"status_code": response.status_code, "request_id": request_id},
                    ip_address=ip_address,
                    db=session,
                )
                await session.commit()
        except Exception:
            logger.warning("Failed to persist audit log entry", exc_info=True)

        return response


# ---------------------------------------------------------------------------
# Search / retrieve helpers
# ---------------------------------------------------------------------------

async def search_audit_logs(
    filters: Optional[dict] = None,
    page: int = 1,
    page_size: int = 50,
    *,
    db: AsyncSession,
) -> dict:
    """Filter and paginate audit log entries from the database.

    Supported filter keys: ``date_from``, ``date_to``, ``user_id``,
    ``action_type``, ``entity_type``.
    """
    stmt = select(AuditLog)

    if filters:
        if filters.get("date_from"):
            stmt = stmt.where(AuditLog.timestamp >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(AuditLog.timestamp <= filters["date_to"])
        if filters.get("user_id"):
            stmt = stmt.where(AuditLog.user_id == filters["user_id"])
        if filters.get("action_type"):
            stmt = stmt.where(AuditLog.action_type == filters["action_type"])
        if filters.get("entity_type"):
            stmt = stmt.where(AuditLog.entity_type == filters["entity_type"])

    # Total count
    count_stmt = select(sa.func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    stmt = stmt.order_by(AuditLog.timestamp.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [_audit_to_dict(e) for e in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_audit_log(log_id: str, *, db: AsyncSession) -> Optional[dict]:
    """Return a single audit entry by its id, or ``None``."""
    entry = await db.get(AuditLog, log_id)
    return _audit_to_dict(entry) if entry else None
