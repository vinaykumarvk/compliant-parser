from __future__ import annotations

"""Sync RAG-app policy documents into the KIS Policy knowledge base."""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from kis_client import KB_POLICY, KISClient, KISClientError, KISUnavailable, get_kis_client, is_kis_configured

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    total_documents: int = 0
    ingested: int = 0
    skipped_idempotent: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "ingested": self.ingested,
            "skipped_idempotent": self.skipped_idempotent,
            "error_count": len(self.errors),
            "errors": self.errors[:20],
            "dry_run": self.dry_run,
        }


def _ragapp_database_url() -> Optional[str]:
    url = os.getenv("IQW_RAGAPP_DATABASE_URL", "").strip()
    return url or None


async def sync_policy_kb(
    *,
    ragapp_database_url: Optional[str] = None,
    dry_run: bool = False,
    client: Optional[KISClient] = None,
) -> SyncResult:
    """Read RAG-app documents+chunks, push each document into KIS Policy KB.

    1. Connect to RAG-app DB (IQW_RAGAPP_DATABASE_URL)
    2. SELECT documents + chunks (ACTIVE only)
    3. Group chunks by document, concatenate in order
    4. Ingest each document via KISClient
    """
    result = SyncResult(dry_run=dry_run)

    db_url = ragapp_database_url or _ragapp_database_url()
    if not db_url:
        raise ValueError("IQW_RAGAPP_DATABASE_URL is not configured.")

    if not dry_run:
        if not is_kis_configured():
            raise KISUnavailable("KIS is not configured; cannot sync policy KB.")
        client = client or get_kis_client(KB_POLICY)

    engine = create_async_engine(db_url, echo=False)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                sa.text(
                    """
                    SELECT d.document_id, d.title, d.file_name, d.status,
                           c.content, c.chunk_index
                    FROM document d
                    JOIN chunk c ON c.document_id = d.document_id
                    WHERE d.status = 'ACTIVE'
                    ORDER BY d.document_id, c.chunk_index
                    """
                )
            )
            all_rows = rows.fetchall()
    finally:
        await engine.dispose()

    # Group chunks by document_id
    documents: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        doc_id = str(row.document_id)
        if doc_id not in documents:
            documents[doc_id] = {
                "document_id": doc_id,
                "title": row.title or row.file_name or f"document-{doc_id}",
                "file_name": row.file_name,
                "chunks": [],
            }
        documents[doc_id]["chunks"].append({
            "chunk_index": row.chunk_index,
            "content": row.content or "",
        })

    result.total_documents = len(documents)

    if dry_run:
        return result

    for doc_id, doc in documents.items():
        # Sort chunks by index and concatenate
        sorted_chunks = sorted(doc["chunks"], key=lambda c: c["chunk_index"])
        raw_text = "\n\n".join(chunk["content"] for chunk in sorted_chunks if chunk["content"])

        if not raw_text.strip():
            result.skipped_idempotent += 1
            continue

        try:
            ingested = client.ingest_source(  # type: ignore[union-attr]
                title=doc["title"],
                raw_text=raw_text,
                source_uri=f"ragapp://documents/{doc_id}",
                metadata={
                    "origin": "ragapp_policy_sync",
                    "ragapp_document_id": doc_id,
                    "file_name": doc["file_name"],
                    "chunk_count": len(sorted_chunks),
                },
            )
            if ingested.get("idempotent_replay"):
                result.skipped_idempotent += 1
            else:
                result.ingested += 1
        except (KISClientError, KISUnavailable) as exc:
            logger.warning("Policy sync failed for document %s: %s", doc_id, exc)
            result.errors.append({
                "document_id": doc_id,
                "title": doc["title"],
                "error": str(exc),
            })

    return result
