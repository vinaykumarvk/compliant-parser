from __future__ import annotations

from typing import Any, Optional

from src.config import Settings
from src.core.errors import KISError
from src.pipeline.chunker import chunk_text
from src.pipeline.embeddings import embed_text
from src.privacy.pii import text_hash
from src.state import STORE, new_id, utcnow


def _next_version(domain_id: str, knowledge_base_id: str, content_hash: str) -> int:
    versions = [
        int(row.get("version", 1))
        for row in STORE.sources.values()
        if row["domain_id"] == domain_id
        and row["knowledge_base_id"] == knowledge_base_id
        and row["content_hash"] == content_hash
    ]
    return (max(versions) + 1) if versions else 1


def _existing_idempotent_source(
    domain_id: str,
    knowledge_base_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    record_id = metadata.get("complaint_parser_record_id")
    origin = metadata.get("origin")
    if not record_id or not origin:
        return None
    for source in STORE.sources.values():
        source_metadata = source.get("metadata") or {}
        if (
            source["domain_id"] == domain_id
            and source["knowledge_base_id"] == knowledge_base_id
            and source_metadata.get("origin") == origin
            and source_metadata.get("complaint_parser_record_id") == record_id
        ):
            return source
    return None


def ingest_source_text(
    *,
    domain_id: str,
    knowledge_base_id: str,
    title: str,
    raw_text: str,
    settings: Settings,
    source_uri: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    kb = STORE.knowledge_bases.get(knowledge_base_id)
    if not kb or kb["domain_id"] != domain_id or kb.get("deleted_at") is not None:
        raise KISError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found.", status_code=404)
    if not raw_text.strip():
        raise KISError("SOURCE_EMPTY", "Source text is required.", status_code=422)

    metadata = metadata or {}
    existing = _existing_idempotent_source(domain_id, knowledge_base_id, metadata)
    if existing is not None:
        chunks = [
            chunk
            for chunk in STORE.chunks.values()
            if chunk["domain_id"] == domain_id
            and chunk["knowledge_base_id"] == knowledge_base_id
            and chunk["source_document_id"] == existing["id"]
        ]
        return {"source": existing, "chunks": chunks, "idempotent_replay": True}

    content_hash = text_hash(raw_text)
    source = {
        "id": new_id("src"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "title": title,
        "source_uri": source_uri,
        "content_hash": content_hash,
        "version": _next_version(domain_id, knowledge_base_id, content_hash),
        "status": "indexing",
        "metadata": metadata,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    STORE.sources[source["id"]] = source

    chunks = []
    for chunk in chunk_text(raw_text, chunk_size=80, overlap=10):
        embedding = embed_text(domain_id, chunk.text, settings=settings)
        chunk_row = {
            "id": new_id("chunk"),
            "domain_id": domain_id,
            "knowledge_base_id": knowledge_base_id,
            "source_document_id": source["id"],
            "ordinal": chunk.ordinal,
            "text": chunk.text,
            "masked_embedding_text": embedding.masked_text,
            "text_hash": text_hash(chunk.text),
            "embedding": embedding.vector,
            "embedding_provider": embedding.provider,
            "embedding_model": embedding.model,
            "privacy_summary": embedding.privacy_summary,
            "citation": {
                "source_document_id": source["id"],
                "title": title,
                "ordinal": chunk.ordinal,
                "source_uri": source_uri,
            },
            "created_at": utcnow(),
        }
        STORE.chunks[chunk_row["id"]] = chunk_row
        chunks.append(chunk_row)

    source["status"] = "indexed"
    source["chunk_count"] = len(chunks)
    source["updated_at"] = utcnow()
    return {"source": source, "chunks": chunks}
