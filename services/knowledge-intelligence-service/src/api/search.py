from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.retrieval.hybrid import hybrid_search
from src.retrieval.vector_search import vector_search
from src.state import STORE

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/search", tags=["search"])


class VectorSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    include_vector: bool = True
    include_graph: bool = True
    include_wiki: bool = True
    required_sources: list[str] = []


@router.post("/vector")
async def search_vector(domain_id: str, knowledge_base_id: str, body: VectorSearchRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return vector_search(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        query=body.query,
        top_k=body.top_k,
        settings=request.app.state.settings,
    )


@router.post("/hybrid")
async def search_hybrid(domain_id: str, knowledge_base_id: str, body: HybridSearchRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return hybrid_search(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        query=body.query,
        top_k=body.top_k,
        include_vector=body.include_vector,
        include_graph=body.include_graph,
        include_wiki=body.include_wiki,
        required_sources=set(body.required_sources),
        settings=request.app.state.settings,
    )


@router.get("/traces/{query_id}")
async def retrieval_trace(domain_id: str, knowledge_base_id: str, query_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    for row in STORE.retrieval_logs:
        if row.get("id") == query_id and row.get("domain_id") == domain_id and row.get("knowledge_base_id") == knowledge_base_id:
            return row
    return {"id": query_id, "found": False}
