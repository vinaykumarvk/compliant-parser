from __future__ import annotations

import math
from typing import Any

from src.config import Settings
from src.pipeline.embeddings import embed_text
from src.privacy.pii import protect_text_for_provider, text_hash
from src.state import STORE, new_id, utcnow


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)


def vector_search(
    *,
    domain_id: str,
    knowledge_base_id: str,
    query: str,
    settings: Settings,
    top_k: int = 5,
) -> dict[str, Any]:
    protected_query = protect_text_for_provider(query, context="retrieval_query")
    query_embedding = embed_text(domain_id, query, settings=settings)
    candidates = [
        chunk
        for chunk in STORE.chunks.values()
        if chunk["domain_id"] == domain_id and chunk["knowledge_base_id"] == knowledge_base_id
    ]
    ranked = sorted(
        (
            {
                "id": chunk["id"],
                "source": "vector",
                "score": round(cosine_similarity(query_embedding.vector, chunk["embedding"]), 6),
                "text": chunk["text"],
                "citation": chunk["citation"],
                "privacy_summary": chunk["privacy_summary"],
            }
            for chunk in candidates
        ),
        key=lambda row: row["score"],
        reverse=True,
    )[: max(1, min(top_k, 50))]
    log = {
        "id": new_id("rq"),
        "type": "retrieval_query",
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "mode": "vector",
        "query_hash": text_hash(query),
        "redacted_query": protected_query.text,
        "privacy_summary": protected_query.summary,
        "result_count": len(ranked),
        "created_at": utcnow(),
    }
    STORE.retrieval_logs.append(log)
    return {
        "mode": "vector",
        "query_id": log["id"],
        "results": ranked,
        "source_counts": {"vector": len(ranked)},
        "privacy_summary": protected_query.summary,
    }
