from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.audit import record_audit
from src.core.errors import KISError
from src.core.security import require_domain_access
from src.state import STORE, new_id, utcnow

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainCreate(BaseModel):
    id: Optional[str] = None
    name: str
    metadata: dict[str, Any] = {}


class MembershipCreate(BaseModel):
    principal_id: str
    scopes: list[str]


@router.post("")
async def create_domain(body: DomainCreate, request: Request) -> dict[str, Any]:
    domain_id = body.id or new_id("domain")
    if domain_id in STORE.domains:
        raise KISError("DOMAIN_EXISTS", "Domain already exists.", status_code=409)
    domain = {
        "id": domain_id,
        "name": body.name,
        "metadata": body.metadata,
        "status": "active",
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "deleted_at": None,
    }
    STORE.domains[domain_id] = domain
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="domain.create",
        resource_type="domain",
        resource_id=domain_id,
    )
    return domain


@router.get("/{domain_id}")
async def get_domain(domain_id: str, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id)
    domain = STORE.domains.get(domain_id)
    if not domain:
        raise KISError("DOMAIN_NOT_FOUND", "Domain not found.", status_code=404)
    return domain


@router.post("/{domain_id}/memberships")
async def create_membership(domain_id: str, body: MembershipCreate, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id)
    if domain_id not in STORE.domains:
        raise KISError("DOMAIN_NOT_FOUND", "Domain not found.", status_code=404)
    membership = {
        "id": new_id("membership"),
        "domain_id": domain_id,
        "principal_id": body.principal_id,
        "scopes": body.scopes,
        "created_at": utcnow(),
    }
    STORE.memberships[membership["id"]] = membership
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="membership.create",
        resource_type="membership",
        resource_id=membership["id"],
    )
    return membership
