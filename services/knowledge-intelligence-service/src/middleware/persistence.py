from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.db.state_persistence import persist_store


class StorePersistenceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and response.status_code < 400:
            settings = request.app.state.settings
            try:
                await persist_store(settings)
            except Exception as exc:
                request.app.state.persistence_error = exc.__class__.__name__
        return response
