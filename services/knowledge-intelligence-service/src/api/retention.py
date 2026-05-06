from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

from src.core.audit import record_audit
from src.core.legal_hold import create_legal_hold, ensure_not_on_legal_hold
from src.core.security import require_domain_access
from src.state import STORE, new_id, utcnow

router = APIRouter(prefix="/domains/{domain_id}", tags=["retention"])


class LegalHoldCreate(BaseModel):
    resource_type: str
    resource_id: str
    reason: str


class DeletionRequestCreate(BaseModel):
    resource_type: str
    resource_id: str
    reason: Optional[str] = None


@router.post("/legal-holds")
async def add_legal_hold(domain_id: str, body: LegalHoldCreate, request: Request) -> dict:
    require_domain_access(request, domain_id)
    hold = create_legal_hold(domain_id, body.resource_type, body.resource_id, body.reason)
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="legal_hold.create",
        resource_type=body.resource_type,
        resource_id=body.resource_id,
    )
    return hold


@router.post("/deletion-requests")
async def request_deletion(domain_id: str, body: DeletionRequestCreate, request: Request) -> dict:
    require_domain_access(request, domain_id)
    ensure_not_on_legal_hold(domain_id, body.resource_type, body.resource_id)
    deletion = {
        "id": new_id("delete"),
        "domain_id": domain_id,
        "resource_type": body.resource_type,
        "resource_id": body.resource_id,
        "reason": body.reason,
        "status": "requested",
        "created_at": utcnow(),
    }
    STORE.deletion_requests[deletion["id"]] = deletion
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="deletion.request",
        resource_type=body.resource_type,
        resource_id=body.resource_id,
    )
    return deletion
