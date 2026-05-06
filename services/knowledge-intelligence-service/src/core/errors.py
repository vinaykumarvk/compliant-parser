from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse


class KISError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400, field: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field


def error_payload(code: str, message: str, *, field: Optional[str] = None, request_id: Optional[str] = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "request_id": request_id,
        }
    }


def error_response(
    code: str,
    message: str,
    *,
    status_code: int = 400,
    field: Optional[str] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    return JSONResponse(error_payload(code, message, field=field, request_id=request_id), status_code=status_code)


async def kis_error_handler(request: Request, exc: KISError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return error_response(
        exc.code,
        exc.message,
        status_code=exc.status_code,
        field=exc.field,
        request_id=request_id,
    )
