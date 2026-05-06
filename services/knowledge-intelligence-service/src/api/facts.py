from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.facts.service import create_fact, review_fact
from src.state import STORE

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/facts", tags=["facts"])


class FactCreate(BaseModel):
    subject: str
    predicate: str
    object_value: str
    confidence: float = 0.5
    source_document_id: Optional[str] = None
    citation: dict[str, Any] = {}


class FactReview(BaseModel):
    status: str


@router.post("")
async def create_fact_endpoint(domain_id: str, knowledge_base_id: str, body: FactCreate, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return create_fact(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        subject=body.subject,
        predicate=body.predicate,
        object_value=body.object_value,
        confidence=body.confidence,
        source_document_id=body.source_document_id,
        citation=body.citation,
    )


@router.post("/{fact_id}:review")
async def review_fact_endpoint(domain_id: str, knowledge_base_id: str, fact_id: str, body: FactReview, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    fact = review_fact(fact_id, status=body.status)
    return fact


@router.get("")
async def list_facts(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {
        "items": [
            row
            for row in STORE.facts.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]
    }
