from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.wiki.compiler import compile_article, list_articles

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/wiki", tags=["wiki"])


class WikiCompileRequest(BaseModel):
    title: str
    source_document_id: Optional[str] = None


@router.post("/articles:compile")
async def compile_article_endpoint(domain_id: str, knowledge_base_id: str, body: WikiCompileRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return compile_article(domain_id, knowledge_base_id, body.title, source_document_id=body.source_document_id)


@router.get("/articles")
async def articles(domain_id: str, knowledge_base_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {"items": list_articles(domain_id, knowledge_base_id)}
