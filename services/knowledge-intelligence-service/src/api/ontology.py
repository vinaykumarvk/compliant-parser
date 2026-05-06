from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.ontology.service import create_ontology_type, list_ontology_types

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/ontology", tags=["ontology"])


class OntologyCreate(BaseModel):
    name: str
    description: str
    ontology_schema: dict[str, Any] = {}


@router.post("")
async def create_ontology(domain_id: str, knowledge_base_id: str, body: OntologyCreate, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return create_ontology_type(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        name=body.name,
        description=body.description,
        schema=body.ontology_schema,
    )


@router.get("")
async def list_ontology(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {"items": list_ontology_types(domain_id, knowledge_base_id)}
