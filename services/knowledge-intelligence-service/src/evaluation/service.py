from __future__ import annotations

from typing import Any

from src.config import Settings
from src.retrieval.hybrid import hybrid_search
from src.retrieval.vector_search import vector_search
from src.state import STORE, new_id, utcnow


def create_evaluation_set(domain_id: str, knowledge_base_id: str, name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    row = {
        "id": new_id("evalset"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "name": name,
        "cases": cases,
        "created_at": utcnow(),
    }
    STORE.evaluation_sets[row["id"]] = row
    return row


def _hit(results: list[dict[str, Any]], expected: list[str]) -> bool:
    haystack = " ".join(str(row.get("text", "")) for row in results).lower()
    return any(item.lower() in haystack for item in expected)


def run_evaluation(domain_id: str, knowledge_base_id: str, evaluation_set_id: str, *, settings: Settings) -> dict[str, Any]:
    evaluation_set = STORE.evaluation_sets[evaluation_set_id]
    total = max(len(evaluation_set["cases"]), 1)
    vector_hits = 0
    hybrid_hits = 0
    citation_hits = 0
    failures = 0
    for case in evaluation_set["cases"]:
        expected = case.get("expected_sections") or case.get("expected_terms") or []
        vector = vector_search(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base_id,
            query=case["query"],
            settings=settings,
            top_k=5,
        )
        hybrid = hybrid_search(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base_id,
            query=case["query"],
            settings=settings,
            top_k=5,
        )
        vector_hits += int(_hit(vector["results"], expected))
        hybrid_hits += int(_hit(hybrid["results"], expected))
        citation_hits += int(all(row.get("citation") for row in hybrid["results"])) if hybrid["results"] else 0
        failures += len(hybrid["failures"])
    metrics = {
        "recall_vector": round(vector_hits / total, 4),
        "recall_hybrid": round(hybrid_hits / total, 4),
        "recall_lift": round((hybrid_hits - vector_hits) / total, 4),
        "mrr": round(hybrid_hits / total, 4),
        "citation_coverage": round(citation_hits / total, 4),
        "source_failure_count": failures,
    }
    run = {
        "id": new_id("evalrun"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "evaluation_set_id": evaluation_set_id,
        "metrics": metrics,
        "created_at": utcnow(),
    }
    STORE.evaluation_runs[run["id"]] = run
    return run
