from __future__ import annotations

import time
from typing import Any, Optional

from src.config import Settings
from src.core.errors import KISError
from src.facts.service import create_fact
from src.llm.router import call_json_model
from src.state import STORE, new_id, utcnow


FACT_EXTRACTION_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "kis_fact_extraction_result",
    "description": "Candidate graph facts extracted from masked source text.",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "subject": {"type": "string"},
                        "predicate": {"type": "string"},
                        "object_value": {"type": "string"},
                        "confidence": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["subject", "predicate", "object_value", "confidence", "rationale"],
                },
            }
        },
        "required": ["facts"],
    },
}


def validate_fact_extraction_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise KISError("LLM_RESPONSE_INVALID", "Fact extraction response must be an object.", status_code=502)
    facts = result.get("facts")
    if not isinstance(facts, list):
        raise KISError("LLM_RESPONSE_INVALID", "Fact extraction response must contain facts list.", status_code=502)
    normalized = []
    for item in facts:
        if not isinstance(item, dict):
            raise KISError("LLM_RESPONSE_INVALID", "Fact entries must be objects.", status_code=502)
        missing = {"subject", "predicate", "object_value", "confidence", "rationale"} - set(item)
        if missing:
            raise KISError("LLM_RESPONSE_INVALID", f"Fact entry missing fields: {sorted(missing)}", status_code=502)
        try:
            confidence = float(item["confidence"])
        except (TypeError, ValueError) as exc:
            raise KISError("LLM_RESPONSE_INVALID", "Fact confidence must be numeric.", status_code=502) from exc
        normalized.append(
            {
                "subject": str(item["subject"]).strip(),
                "predicate": str(item["predicate"]).strip(),
                "object_value": str(item["object_value"]).strip(),
                "confidence": max(0.0, min(confidence, 1.0)),
                "rationale": str(item["rationale"]).strip(),
            }
        )
    return {"facts": [item for item in normalized if item["subject"] and item["predicate"] and item["object_value"]]}


def execute_fact_extraction(
    *,
    domain_id: str,
    knowledge_base_id: str,
    source_text: str,
    provider: str,
    model: str,
    settings: Settings,
    source_document_id: Optional[str] = None,
    citation: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    run = {
        "id": new_id("rrun"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "pattern_name": "candidate_fact_extraction",
        "status": "running",
        "llm_usage": {},
        "privacy_summary": {},
        "candidate_facts": [],
        "created_at": utcnow(),
    }
    STORE.reasoning_runs[run["id"]] = run
    llm = call_json_model(
        domain_id=domain_id,
        provider=provider,
        model=model,
        system_prompt=(
            "Extract candidate non-PII graph facts from masked source text. "
            "Facts must remain candidates until a reviewer approves them."
        ),
        user_payload={"source_text": source_text, "schema": FACT_EXTRACTION_RESPONSE_SCHEMA["schema"]},
        settings=settings,
        response_schema=FACT_EXTRACTION_RESPONSE_SCHEMA,
    )
    result = validate_fact_extraction_result(llm.get("data"))
    facts = [
        create_fact(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base_id,
            subject=item["subject"],
            predicate=item["predicate"],
            object_value=item["object_value"],
            confidence=item["confidence"],
            source_document_id=source_document_id,
            citation={**(citation or {}), "rationale": item["rationale"]},
        )
        for item in result["facts"]
    ]
    run.update(
        {
            "status": "completed",
            "llm_usage": {
                "provider": llm["provider"],
                "model": llm["model"],
                "mode": llm["mode"],
                "usage_event_id": llm["usage"]["id"],
                "protected_user_prompt": llm["protected_user_prompt"],
            },
            "privacy_summary": llm["privacy"],
            "candidate_facts": facts,
            "candidate_fact_count": len(facts),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "completed_at": utcnow(),
        }
    )
    return run
