from __future__ import annotations

import time
from typing import Any, Optional, Set

from src.config import Settings
from src.core.errors import KISError
from src.retrieval.graph_query import graph_fact_search
from src.retrieval.ranking import rerank_and_dedupe
from src.retrieval.vector_search import vector_search
from src.retrieval.wiki_query import wiki_search


def hybrid_search(
    *,
    domain_id: str,
    knowledge_base_id: str,
    query: str,
    settings: Settings,
    top_k: int = 5,
    include_vector: bool = True,
    include_graph: bool = True,
    include_wiki: bool = True,
    required_sources: Optional[Set[str]] = None,
    fail_sources: Optional[Set[str]] = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    required_sources = required_sources or set()
    fail_sources = fail_sources or set()
    results: list[dict[str, Any]] = []
    source_counts = {"vector": 0, "graph": 0, "fact": 0, "wiki": 0}
    failures: list[dict[str, str]] = []

    def record_failure(source: str, message: str) -> None:
        if source in required_sources:
            raise KISError("REQUIRED_SOURCE_FAILED", f"Required retrieval source failed: {source}", status_code=503)
        failures.append({"source": source, "message": message})

    if include_vector:
        try:
            if "vector" in fail_sources:
                raise RuntimeError("simulated vector failure")
            vector = vector_search(
                domain_id=domain_id,
                knowledge_base_id=knowledge_base_id,
                query=query,
                settings=settings,
                top_k=top_k,
            )
            source_counts["vector"] = len(vector["results"])
            results.extend(vector["results"])
        except Exception as exc:
            record_failure("vector", exc.__class__.__name__)

    if include_graph:
        try:
            if "graph" in fail_sources:
                raise RuntimeError("simulated graph failure")
            graph_results = graph_fact_search(domain_id, knowledge_base_id, query, limit=top_k)
            source_counts["graph"] = len([row for row in graph_results if row["source"] == "graph"])
            source_counts["fact"] = len([row for row in graph_results if row["source"] == "fact"])
            results.extend(graph_results)
        except Exception as exc:
            record_failure("graph", exc.__class__.__name__)

    if include_wiki:
        try:
            if "wiki" in fail_sources:
                raise RuntimeError("simulated wiki failure")
            wiki_results = wiki_search(domain_id, knowledge_base_id, query, limit=top_k)
            source_counts["wiki"] = len(wiki_results)
            results.extend(wiki_results)
        except Exception as exc:
            record_failure("wiki", exc.__class__.__name__)

    ranked = rerank_and_dedupe(results)[: max(1, min(top_k, 50))]
    return {
        "mode": "hybrid",
        "results": ranked,
        "source_counts": source_counts,
        "degraded": bool(failures),
        "failures": failures,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
