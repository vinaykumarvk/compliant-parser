from __future__ import annotations

from fastapi import APIRouter, Request

from src.core.security import require_domain_access
from src.graph.builder import promote_fact_to_graph
from src.graph.query import graph_search, graph_stats

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/graph", tags=["graph"])


@router.post("/facts/{fact_id}:promote")
async def promote_fact(domain_id: str, knowledge_base_id: str, fact_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return promote_fact_to_graph(fact_id)


@router.get("/search")
async def search_graph(domain_id: str, knowledge_base_id: str, q: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return graph_search(domain_id, knowledge_base_id, q)


@router.get("/stats")
async def stats(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return graph_stats(domain_id, knowledge_base_id)
