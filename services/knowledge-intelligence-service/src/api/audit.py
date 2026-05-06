from __future__ import annotations

from fastapi import APIRouter, Request

from src.core.audit import search_audit
from src.core.security import require_domain_access

router = APIRouter(prefix="/domains/{domain_id}/audit", tags=["audit"])


@router.get("")
async def audit_events(domain_id: str, request: Request) -> dict[str, list[dict]]:
    require_domain_access(request, domain_id)
    return {"items": search_audit(domain_id)}
