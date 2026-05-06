from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.reasoning.fact_extraction import execute_fact_extraction
from src.reasoning.executor import create_reasoning_pattern, execute_bns_mapping
from src.state import STORE

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/reasoning", tags=["reasoning"])


class PatternCreate(BaseModel):
    name: str
    prompt_name: str
    status: str = "active"
    output_schema: dict[str, Any] = {}


class BNSMappingRequest(BaseModel):
    complaint_text: str
    provider: str = "self_hosted"
    model: str = "llama3-legal-local"
    max_prompt_tokens: int = 4000


class FactExtractionRequest(BaseModel):
    source_text: str
    provider: str = "self_hosted"
    model: str = "llama3-legal-local"
    source_document_id: Optional[str] = None
    citation: dict[str, Any] = {}


@router.post("/patterns")
async def create_pattern(domain_id: str, knowledge_base_id: str, body: PatternCreate, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return create_reasoning_pattern(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        name=body.name,
        prompt_name=body.prompt_name,
        status=body.status,
        output_schema=body.output_schema,
    )


@router.get("/patterns")
async def list_patterns(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {
        "items": [
            row
            for row in STORE.reasoning_patterns.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]
    }


@router.post("/bns-mapping")
async def bns_mapping(domain_id: str, knowledge_base_id: str, body: BNSMappingRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "llm:execute", "kb:read"))
    return execute_bns_mapping(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        complaint_text=body.complaint_text,
        provider=body.provider,
        model=body.model,
        settings=request.app.state.settings,
        max_prompt_tokens=body.max_prompt_tokens,
    )


@router.post("/fact-extraction")
async def fact_extraction(domain_id: str, knowledge_base_id: str, body: FactExtractionRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "llm:execute", "kb:write"))
    return execute_fact_extraction(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        source_text=body.source_text,
        provider=body.provider,
        model=body.model,
        settings=request.app.state.settings,
        source_document_id=body.source_document_id,
        citation=body.citation,
    )
