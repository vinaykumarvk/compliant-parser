from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.audit import record_audit
from src.core.errors import KISError
from src.core.security import require_domain_access
from src.state import STORE, new_id, utcnow

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases", tags=["knowledge-bases"])


class KnowledgeBaseCreate(BaseModel):
    name: str
    retrieval_profile: dict[str, Any] = {}


@router.post("")
async def create_knowledge_base(domain_id: str, body: KnowledgeBaseCreate, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    if domain_id not in STORE.domains:
        raise KISError("DOMAIN_NOT_FOUND", "Domain not found.", status_code=404)
    kb = {
        "id": new_id("kb"),
        "domain_id": domain_id,
        "name": body.name,
        "retrieval_profile": body.retrieval_profile,
        "status": "active",
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "deleted_at": None,
    }
    STORE.knowledge_bases[kb["id"]] = kb
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="knowledge_base.create",
        resource_type="knowledge_base",
        resource_id=kb["id"],
    )
    return kb


@router.get("")
async def list_knowledge_bases(domain_id: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {
        "items": [
            kb
            for kb in STORE.knowledge_bases.values()
            if kb["domain_id"] == domain_id and kb.get("deleted_at") is None
        ]
    }


@router.get("/{knowledge_base_id}")
async def get_knowledge_base(domain_id: str, knowledge_base_id: str, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    kb = STORE.knowledge_bases.get(knowledge_base_id)
    if not kb or kb["domain_id"] != domain_id:
        raise KISError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found.", status_code=404)
    return kb
