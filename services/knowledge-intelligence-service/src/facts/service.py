from __future__ import annotations

from typing import Any, Optional

from src.core.errors import KISError
from src.state import STORE, new_id, utcnow


def create_fact(
    *,
    domain_id: str,
    knowledge_base_id: str,
    subject: str,
    predicate: str,
    object_value: str,
    confidence: float,
    source_document_id: Optional[str] = None,
    citation: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    for existing in STORE.facts.values():
        if (
            existing["domain_id"] == domain_id
            and existing["knowledge_base_id"] == knowledge_base_id
            and existing.get("source_document_id") == source_document_id
            and existing["subject"] == subject
            and existing["predicate"] == predicate
            and existing["object"] == object_value
        ):
            return existing
    fact = {
        "id": new_id("fact"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "subject": subject,
        "predicate": predicate,
        "object": object_value,
        "confidence": confidence,
        "status": "candidate",
        "source_document_id": source_document_id,
        "citation": citation or {},
        "created_at": utcnow(),
    }
    STORE.facts[fact["id"]] = fact
    return fact


def review_fact(fact_id: str, *, status: str) -> dict[str, Any]:
    fact = STORE.facts.get(fact_id)
    if not fact:
        raise KISError("FACT_NOT_FOUND", "Fact not found.", status_code=404)
    if status not in {"approved", "rejected", "candidate"}:
        raise KISError("FACT_STATUS_INVALID", "Invalid fact review status.", status_code=422)
    fact["status"] = status
    fact["reviewed_at"] = utcnow()
    return fact


def approved_facts(domain_id: str, knowledge_base_id: str) -> list[dict[str, Any]]:
    return [
        fact
        for fact in STORE.facts.values()
        if fact["domain_id"] == domain_id and fact["knowledge_base_id"] == knowledge_base_id and fact["status"] == "approved"
    ]
