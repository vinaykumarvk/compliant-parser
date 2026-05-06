from __future__ import annotations

from fastapi import APIRouter, Request

from src.db.session import database_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
    }


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    db = await database_status(settings)
    return {
        "status": "ok" if db["status"] in {"ok", "not_configured"} else "degraded",
        "service": settings.service_name,
        "database": db,
        "providers_configured": {
            "openai": settings.openai_api_key_configured,
            "gemini": settings.gemini_api_key_configured,
        },
    }
