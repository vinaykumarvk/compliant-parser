from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.quality.gates import run_quality_gates
from src.snapshots.service import create_snapshot, latest_published_snapshot, publish_snapshot, rollback_snapshot

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}", tags=["snapshots"])


class RollbackRequest(BaseModel):
    version: int


@router.post("/snapshots")
async def create_snapshot_endpoint(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return create_snapshot(domain_id, knowledge_base_id)


@router.post("/snapshots/{snapshot_id}:publish")
async def publish_snapshot_endpoint(domain_id: str, knowledge_base_id: str, snapshot_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return publish_snapshot(snapshot_id)


@router.post("/snapshots:rollback")
async def rollback_snapshot_endpoint(domain_id: str, knowledge_base_id: str, body: RollbackRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return rollback_snapshot(domain_id, knowledge_base_id, body.version)


@router.get("/snapshots/latest")
async def latest_snapshot(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    snapshot = latest_published_snapshot(domain_id, knowledge_base_id)
    return {"snapshot": snapshot}


@router.post("/quality-gates:run")
async def quality_gates(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return run_quality_gates(domain_id, knowledge_base_id)
