from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.evaluation.service import create_evaluation_set, run_evaluation
from src.state import STORE

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/evaluations", tags=["evaluations"])


class EvaluationSetCreate(BaseModel):
    name: str
    cases: list[dict[str, Any]]


@router.post("")
async def create_set(domain_id: str, knowledge_base_id: str, body: EvaluationSetCreate, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return create_evaluation_set(domain_id, knowledge_base_id, body.name, body.cases)


@router.get("")
async def list_sets(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {
        "items": [
            row
            for row in STORE.evaluation_sets.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]
    }


@router.post("/{evaluation_set_id}:run")
async def run_set(domain_id: str, knowledge_base_id: str, evaluation_set_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return run_evaluation(domain_id, knowledge_base_id, evaluation_set_id, settings=request.app.state.settings)
