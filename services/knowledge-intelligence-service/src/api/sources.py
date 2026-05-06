from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.audit import record_audit
from src.core.errors import KISError
from src.core.security import require_domain_access
from src.pipeline.ingestion import ingest_source_text
from src.state import STORE

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/sources", tags=["sources"])


class SourceIngestRequest(BaseModel):
    title: str
    raw_text: str
    source_uri: Optional[str] = None
    metadata: dict[str, Any] = {}


@router.post("")
async def ingest_source(domain_id: str, knowledge_base_id: str, body: SourceIngestRequest, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    result = ingest_source_text(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        title=body.title,
        raw_text=body.raw_text,
        source_uri=body.source_uri,
        metadata=body.metadata,
        settings=request.app.state.settings,
    )
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="source.ingest",
        resource_type="source_document",
        resource_id=result["source"]["id"],
        metadata={"chunk_count": len(result["chunks"])},
    )
    return result


@router.get("/{source_id}")
async def get_source(domain_id: str, knowledge_base_id: str, source_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    source = STORE.sources.get(source_id)
    if not source or source["domain_id"] != domain_id or source["knowledge_base_id"] != knowledge_base_id:
        raise KISError("SOURCE_NOT_FOUND", "Source not found.", status_code=404)
    chunks = [
        chunk
        for chunk in STORE.chunks.values()
        if chunk["source_document_id"] == source_id and chunk["domain_id"] == domain_id
    ]
    return {"source": source, "chunks": chunks}
