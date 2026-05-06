from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {"vector": 0.45, "graph": 0.25, "fact": 0.20, "wiki": 0.10}


def rerank_and_dedupe(results: list[dict[str, Any]], weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    weights = weights or DEFAULT_WEIGHTS
    by_key: dict[str, dict[str, Any]] = {}
    for result in results:
        key = f"{result.get('source')}:{result.get('text')[:160]}:{result.get('citation')}"
        weighted = dict(result)
        weighted["base_score"] = result.get("score", 0.0)
        weighted["score"] = round(float(result.get("score", 0.0)) * weights.get(result.get("source"), 0.1), 6)
        if key not in by_key or weighted["score"] > by_key[key]["score"]:
            by_key[key] = weighted
    return sorted(by_key.values(), key=lambda row: row["score"], reverse=True)
