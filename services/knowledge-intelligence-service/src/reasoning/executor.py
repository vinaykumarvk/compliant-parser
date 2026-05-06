from __future__ import annotations

import time
from typing import Any

from src.config import Settings
from src.core.errors import KISError
from src.llm.router import call_json_model
from src.prompts.registry import render_prompt, resolve_prompt
from src.reasoning.bns_mapping import (
    BNS_MAPPING_RESPONSE_SCHEMA,
    bns_recommendations,
    coerce_bns_mapping_result,
    validate_bns_mapping_result,
)
from src.reasoning.context import assemble_context
from src.state import STORE, new_id, utcnow


def create_reasoning_pattern(
    *,
    domain_id: str,
    knowledge_base_id: str,
    name: str,
    prompt_name: str,
    status: str = "active",
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pattern = {
        "id": new_id("pattern"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "name": name,
        "prompt_name": prompt_name,
        "status": status,
        "output_schema": output_schema or {},
        "created_at": utcnow(),
    }
    STORE.reasoning_patterns[pattern["id"]] = pattern
    return pattern


def resolve_pattern(domain_id: str, knowledge_base_id: str, name: str) -> dict[str, Any]:
    patterns = [
        row
        for row in STORE.reasoning_patterns.values()
        if row["domain_id"] == domain_id
        and row["knowledge_base_id"] == knowledge_base_id
        and row["name"] == name
        and row["status"] == "active"
    ]
    if not patterns:
        raise KISError("REASONING_PATTERN_NOT_ACTIVE", "No active reasoning pattern is available.", status_code=409)
    return patterns[-1]


def _pin_bns_reference_context(context: dict[str, Any], domain_id: str, knowledge_base_id: str) -> dict[str, Any]:
    existing_ids = {result.get("id") for result in context.get("results", [])}
    reference_results = []
    for chunk in STORE.chunks.values():
        if chunk["domain_id"] != domain_id or chunk["knowledge_base_id"] != knowledge_base_id:
            continue
        text = chunk.get("text", "")
        if chunk["id"] in existing_ids or ("bns-" not in text.lower() and "bharatiya nyaya sanhita" not in text.lower()):
            continue
        reference_results.append(
            {
                "id": chunk["id"],
                "source": "legal_reference",
                "score": 1.0,
                "text": text,
                "citation": chunk.get("citation", {}),
                "privacy_summary": chunk.get("privacy_summary", {}),
            }
        )
    if not reference_results:
        return context
    pinned = sorted(reference_results, key=lambda item: item["citation"].get("ordinal", 0))[:4]
    context["results"] = pinned + context.get("results", [])
    context.setdefault("source_counts", {})["legal_reference"] = len(pinned)
    return context


def execute_bns_mapping(
    *,
    domain_id: str,
    knowledge_base_id: str,
    complaint_text: str,
    provider: str,
    model: str,
    settings: Settings,
    max_prompt_tokens: int = 4000,
) -> dict[str, Any]:
    started = time.perf_counter()
    run = {
        "id": new_id("rrun"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "pattern_name": "fir_bns_mapping",
        "status": "running",
        "context_summary": {},
        "llm_usage": {},
        "privacy_summary": {},
        "result": {},
        "confidence": 0.0,
        "created_at": utcnow(),
    }
    STORE.reasoning_runs[run["id"]] = run
    try:
        pattern = resolve_pattern(domain_id, knowledge_base_id, "fir_bns_mapping")
        prompt = resolve_prompt(domain_id, knowledge_base_id, pattern["prompt_name"])
        context = assemble_context(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base_id,
            query=complaint_text,
            settings=settings,
        )
        context = _pin_bns_reference_context(context, domain_id, knowledge_base_id)
        context_results = [
            {
                "source": result.get("source"),
                "score": result.get("score"),
                "text": result["text"],
                "citation": result.get("citation", {}),
            }
            for result in context["results"]
        ]
        rendered = render_prompt(
            prompt["template"],
            {
                "complaint_text": complaint_text,
                "context": "\n".join(result["text"] for result in context_results),
            },
        )
        llm = call_json_model(
            domain_id=domain_id,
            provider=provider,
            model=model,
            system_prompt=(
                "Return JSON only. Map complaint facts to BNS sections using only the supplied KIS context. "
                "Every recommended section must cite at least one supplied context item. "
                "The section_code field must be an exact canonical code from context, such as BNS-303; "
                "do not put generic offence names or explanatory text in section_code."
            ),
            user_payload={
                "prompt": rendered,
                "complaint_text": complaint_text,
                "context_results": context_results,
                "required_output_schema": BNS_MAPPING_RESPONSE_SCHEMA["schema"],
                "pattern_output_schema": pattern.get("output_schema", {}),
            },
            settings=settings,
            response_schema=BNS_MAPPING_RESPONSE_SCHEMA,
            max_prompt_tokens=max_prompt_tokens,
        )
        coerced_llm_result = coerce_bns_mapping_result(llm.get("data"))
        if coerced_llm_result is not None:
            result = coerced_llm_result
            result_source = "llm"
        else:
            result = bns_recommendations(complaint_text, context["results"])
            result_source = "rules_fallback"
        validate_bns_mapping_result(result)
        run.update(
            {
                "status": "completed",
                "context_summary": {
                    "snapshot_id": context["snapshot"]["id"] if context.get("snapshot") else None,
                    "source_counts": context["source_counts"],
                    "context_result_count": len(context["results"]),
                },
                "llm_usage": {
                    "provider": llm["provider"],
                    "model": llm["model"],
                    "mode": llm["mode"],
                    "usage_event_id": llm["usage"]["id"],
                    "protected_user_prompt": llm["protected_user_prompt"],
                },
                "result_source": result_source,
                "privacy_summary": llm["privacy"],
                "result": result,
                "confidence": max([item["confidence_score"] for item in result["primary_sections"]] or [0.0]),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "completed_at": utcnow(),
            }
        )
        return run
    except Exception as exc:
        run.update(
            {
                "status": "failed",
                "error": str(exc),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "completed_at": utcnow(),
            }
        )
        raise
