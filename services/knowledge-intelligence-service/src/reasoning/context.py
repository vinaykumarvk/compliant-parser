from __future__ import annotations

from typing import Any

from src.config import Settings
from src.retrieval.hybrid import hybrid_search
from src.snapshots.service import latest_published_snapshot


def assemble_context(
    *,
    domain_id: str,
    knowledge_base_id: str,
    query: str,
    settings: Settings,
    token_budget: int = 1200,
) -> dict[str, Any]:
    snapshot = latest_published_snapshot(domain_id, knowledge_base_id)
    retrieval = hybrid_search(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        query=query,
        settings=settings,
        top_k=6,
    )
    budget_remaining = token_budget
    selected = []
    for result in retrieval["results"]:
        words = result["text"].split()
        if budget_remaining <= 0:
            break
        trimmed = " ".join(words[:budget_remaining])
        selected.append({**result, "text": trimmed})
        budget_remaining -= len(trimmed.split())
    return {
        "snapshot": snapshot,
        "results": selected,
        "source_counts": retrieval["source_counts"],
        "degraded": retrieval["degraded"],
    }
