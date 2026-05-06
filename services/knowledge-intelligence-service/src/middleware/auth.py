from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.config import Settings
from src.core.errors import error_response


@dataclass(frozen=True)
class Principal:
    api_key_id: str
    principal_id: str
    domain_id: Optional[str]
    scopes: frozenset[str]


PUBLIC_PATH_SUFFIXES = ("/health", "/ready", "/openapi.json", "/docs", "/redoc")


def _is_public_path(path: str) -> bool:
    if path in {"/", "/favicon.ico"}:
        return True
    return any(path.endswith(suffix) for suffix in PUBLIC_PATH_SUFFIXES)


def parse_principal(api_key: str, settings: Settings) -> Optional[Principal]:
    entry: Any = settings.api_keys.get(api_key)
    if not isinstance(entry, dict):
        return None
    return Principal(
        api_key_id=secrets.token_hex(8),
        principal_id=str(entry.get("principal_id") or "service-principal"),
        domain_id=str(entry["domain_id"]) if entry.get("domain_id") else None,
        scopes=frozenset(str(scope) for scope in entry.get("scopes", [])),
    )


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        if _is_public_path(request.url.path):
            return await call_next(request)

        if self.settings.auth_disabled:
            request.state.principal_id = "anonymous-dev"
            request.state.domain_id = request.headers.get("X-Domain-ID")
            request.state.scopes = {"domain:admin", "kb:read", "kb:write", "llm:execute"}
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return error_response("AUTH_REQUIRED", "Missing X-API-Key header.", status_code=401)

        principal = parse_principal(api_key, self.settings)
        if principal is None:
            return error_response("AUTH_INVALID", "Invalid API key.", status_code=401)

        request.state.principal_id = principal.principal_id
        request.state.domain_id = request.headers.get("X-Domain-ID") or principal.domain_id
        request.state.scopes = set(principal.scopes)
        return await call_next(request)
