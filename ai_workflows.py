from __future__ import annotations

"""Live LLM workflow services with explicit local/test stubs."""

import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit import compute_sha256
from external_interfaces import ExternalServiceError, ExternalServiceUnavailable, get_live_llm_client, get_object_bytes
from models import (
    AIAnalysisResult,
    Case,
    CaseDocument,
    CongruenceAlert,
    InvestigationPlan,
    JudgmentAnalysis,
    KnowledgeBaseEntry,
    Notification,
    SectionRecommendation,
    UsageEvent,
)


SECTION_DISCLAIMER = (
    "Final legal determination rests with the Investigating Officer and superior officers. "
    "These are AI-generated suggestions only."
)


def _allow_llm_stub() -> bool:
    """Permit local/test fallback only when no live LLM can be called."""
    import os

    return os.getenv("IQW_ALLOW_LLM_STUBS", "false").lower() in {"1", "true", "yes", "on"}


def _llm_json(system_prompt: str, payload: dict[str, Any], *, task: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        result = get_live_llm_client().generate_json(system_prompt, user_prompt)
        return result.data, {
            "provider": result.provider,
            "model": result.model,
            "mode": "live",
            "privacy": result.privacy,
        }
    except ExternalServiceUnavailable:
        if _allow_llm_stub():
            return None, {"provider": "stub", "model": "not_configured", "mode": "stub"}
        raise
    except ExternalServiceError:
        raise
    except Exception as exc:
        if _allow_llm_stub():
            return None, {"provider": "stub", "model": "error_fallback", "mode": f"stub_after_{task}_error"}
        raise ExternalServiceError(f"{task} LLM call failed: {exc}") from exc


async def _text_from_doc(doc: CaseDocument) -> str:
    if doc.ocr_extracted_text:
        return doc.ocr_extracted_text
    if getattr(doc, "file_storage_uri", None):
        content = await get_object_bytes(doc.file_storage_uri)
        return content.decode("utf-8", errors="replace")
    if doc.file_bytes:
        return doc.file_bytes.decode("utf-8", errors="replace")
    return ""


def _model_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _analysis_to_dict(row: AIAnalysisResult) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "document_id": row.document_id,
        "analysis_type": _model_value(row.analysis_type),
        "model_name": row.model_name,
        "model_version": row.model_version,
        "prompt_version": row.prompt_version,
        "result_json": row.result_json,
        "confidence_score": _model_value(row.confidence_score),
        "has_uncertainty_flag": row.has_uncertainty_flag,
        "uncertainty_tags": row.uncertainty_tags or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _stub_section_recommendations(_text: str, _show_all: bool = False) -> dict:
    return {
        "primary_sections": [],
        "alternative_sections": [],
        "all_sections": [],
        "hidden_below_threshold": 0,
        "disclaimer": SECTION_DISCLAIMER,
        "model_name": "external_interface_stub",
        "supported_model_family": "OpenAI/Gemini structured JSON adapter",
        "stub_reason": "Live LLM is not configured; no legal-section recommendation was generated.",
    }


def _normalize_enhanced_fields(data: dict) -> None:
    """Auto-assign applicability_rank and ensure enhanced field defaults."""
    for group_key in ("primary_sections", "alternative_sections"):
        items = data.get(group_key, [])
        if items and not any(item.get("applicability_rank") for item in items):
            ranked = sorted(items, key=lambda x: -(float(x.get("confidence_score") or 0)))
            for idx, item in enumerate(ranked):
                item["applicability_rank"] = idx + 1
        for item in items:
            item.setdefault("statutory_text", None)
            item.setdefault("ingredient_mapping", [])


def recommend_sections_from_text(text: str, show_all: bool = False) -> dict:
    try:
        from kis_client import KISClientError, KISUnavailable, recommend_sections_via_kis

        kis_result = recommend_sections_via_kis(text, show_all=show_all)
        if kis_result is not None:
            _normalize_enhanced_fields(kis_result)
            return kis_result
    except (KISClientError, KISUnavailable):
        import os

        if os.getenv("IQW_KIS_FALLBACK_ON_ERROR", "true").lower() not in {"1", "true", "yes", "on"}:
            raise

    system = (
        "You are a legal AI assistant for Indian police investigation support. "
        "Return JSON only. Recommend BNS/IPC sections from complaint text. "
        "Every recommendation must include confidence_score 0.0-1.0, legal_reasoning, "
        "supporting_ingredients, missing_ingredients, and alternatives. "
        "Additionally, for each section provide: "
        "applicability_rank (1 = most applicable, 2 = next, etc.), "
        "statutory_text (a brief extract of the BNS section definition text), and "
        "ingredient_mapping (array of objects with keys: ingredient, status "
        "(one of 'satisfied', 'uncertain', 'missing'), and complaint_fact). "
        "Do not fabricate facts; use only the supplied text."
    )
    schema_request = {
        "complaint_text": text,
        "show_all": show_all,
        "required_schema": {
            "primary_sections": [
                {
                    "section_code": "string",
                    "section_title": "string",
                    "act_name": "BNS or IPC",
                    "confidence_score": 0.0,
                    "legal_reasoning": "string",
                    "supporting_ingredients": ["string"],
                    "missing_ingredients": ["string"],
                    "applicability_rank": 1,
                    "statutory_text": "string (brief extract of BNS section definition)",
                    "ingredient_mapping": [
                        {"ingredient": "string", "status": "satisfied|uncertain|missing", "complaint_fact": "string"}
                    ],
                }
            ],
            "alternative_sections": [],
            "hidden_below_threshold": 0,
        },
    }
    data, meta = _llm_json(system, schema_request, task="section_recommendation")
    if data is None:
        data = _stub_section_recommendations(text, show_all)
    data.setdefault("primary_sections", [])
    data.setdefault("alternative_sections", [])
    if not show_all:
        data["primary_sections"] = [
            item for item in data.get("primary_sections", []) if float(item.get("confidence_score") or 0) >= 0.30
        ]
        data["alternative_sections"] = [
            item for item in data.get("alternative_sections", []) if float(item.get("confidence_score") or 0) >= 0.30
        ]
    _normalize_enhanced_fields(data)
    data["disclaimer"] = SECTION_DISCLAIMER
    data["model_name"] = f"{meta['provider']}:{meta['model']}"
    data["llm_provider"] = meta["provider"]
    data["llm_mode"] = meta["mode"]
    data["privacy_controls"] = meta.get("privacy", {})
    data["supported_model_family"] = "OpenAI/Gemini structured JSON adapter"
    return data


async def persist_section_recommendation(
    case_id: str,
    document_id: Optional[str],
    text: str,
    result: dict,
    user_id: str,
    db: AsyncSession,
) -> dict:
    analysis = AIAnalysisResult(
        case_id=case_id,
        document_id=document_id,
        analysis_type="Section_Recommendation",
        model_name=result["model_name"],
        model_version="1.0",
        prompt_version="section-v1",
        input_text_hash=compute_sha256(text.encode("utf-8")),
        result_json=result,
        confidence_score="Medium",
        has_uncertainty_flag=bool(result.get("hidden_below_threshold")),
        uncertainty_tags=["Possible_Legal_Mismatch"] if result.get("hidden_below_threshold") else [],
        created_by=user_id,
    )
    db.add(analysis)
    await db.flush()
    for group, is_primary, is_alt in (("primary_sections", True, False), ("alternative_sections", False, True)):
        for item in result.get(group, []):
            db.add(
                SectionRecommendation(
                    analysis_id=analysis.id,
                    section_code=item["section_code"],
                    section_title=item["section_title"],
                    act_name=item["act_name"],
                    confidence_score=item["confidence_score"],
                    legal_reasoning=item["legal_reasoning"],
                    supporting_ingredients=item["supporting_ingredients"],
                    missing_ingredients=item["missing_ingredients"],
                    is_primary=is_primary,
                    is_alternative=is_alt,
                    disclaimer_text=SECTION_DISCLAIMER,
                    applicability_rank=item.get("applicability_rank"),
                    statutory_text=item.get("statutory_text"),
                    ingredient_mapping=item.get("ingredient_mapping"),
                    created_by=user_id,
                )
            )
    await db.flush()
    result["persisted_analysis_id"] = analysis.id
    return result


def _score_to_confidence_label(score: float) -> str:
    if score >= 0.85:
        return "High"
    if score >= 0.55:
        return "Medium"
    return "Low"


def _kis_section_to_bns_payload(item: dict, *, fit: str = "primary") -> dict:
    """Transform a KIS/LLM section recommendation into the proposed_bns_sections format."""
    score = round(max(0.0, min(1.0, float(item.get("confidence_score") or 0))), 2)
    return {
        "section": item.get("section_code") or "-",
        "title": item.get("section_title") or "-",
        "offence_head": item.get("section_title") or "-",
        "fit": fit,
        "confidence": _score_to_confidence_label(score),
        "confidence_score": score,
        "evidence": (item.get("supporting_ingredients") or [])[:3],
        "rationale": item.get("legal_reasoning") or "-",
        "act": item.get("act_name") or "Bharatiya Nyaya Sanhita, 2023",
        "review_note": (
            ("Missing: " + ", ".join(item["missing_ingredients"]))
            if item.get("missing_ingredients")
            else None
        ),
        "applicability_rank": item.get("applicability_rank"),
        "statutory_text": item.get("statutory_text") or None,
        "ingredient_mapping": item.get("ingredient_mapping") or [],
        "source": "kis",
    }


async def auto_recommend_bns_sections(
    case_id: str,
    document_id: str,
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Automatically run BNS section recommendation on a newly uploaded document.

    Mirrors auto_run_congruence_for_document() — designed to be called right
    after document upload in api_v1.py.
    """
    if os.getenv("IQW_AUTO_BNS_RECOMMENDATION", "true").lower() not in {"1", "true", "yes", "on"}:
        return {"section_recommendation_status": "Disabled"}

    doc = await db.get(CaseDocument, document_id)
    if doc is None:
        return {"section_recommendation_status": "Skipped", "reason": "document_not_found"}

    text = await _text_from_doc(doc)
    if len(text.strip()) < 50:
        return {"section_recommendation_status": "Skipped", "reason": "insufficient_text"}

    # Idempotency — skip if already analysed
    existing = await db.execute(
        select(AIAnalysisResult).where(
            AIAnalysisResult.document_id == document_id,
            AIAnalysisResult.analysis_type == "Section_Recommendation",
        )
    )
    if existing.scalars().first() is not None:
        return {"section_recommendation_status": "Already_Exists"}

    result = await asyncio.to_thread(recommend_sections_from_text, text, False)

    persisted = await persist_section_recommendation(
        case_id=case_id,
        document_id=document_id,
        text=text,
        result=result,
        user_id=user_id,
        db=db,
    )

    # Merge KIS sections into proposed_bns_sections (same format the frontend renders)
    if doc.parsed_output is None:
        doc.parsed_output = {}
    if isinstance(doc.parsed_output, dict):
        fir_draft = doc.parsed_output.setdefault("fir_draft", {})

        # Build entries in the heuristic payload format
        kis_entries: list[dict] = []
        for item in result.get("primary_sections", []):
            kis_entries.append(_kis_section_to_bns_payload(item, fit="primary"))
        for item in result.get("alternative_sections", []):
            kis_entries.append(_kis_section_to_bns_payload(item, fit="alternative"))

        # Merge: KIS entries replace heuristic entries for the same section code
        existing = fir_draft.get("proposed_bns_sections") or []
        existing_codes = {e.get("section") for e in existing}
        merged = list(existing)
        for entry in kis_entries:
            if entry["section"] in existing_codes:
                merged = [e for e in merged if e.get("section") != entry["section"]]
            merged.append(entry)
        # Sort: primary first, then by confidence descending
        fit_order = {"primary": 0, "related": 1, "alternative": 2}
        merged.sort(key=lambda e: (fit_order.get(e.get("fit", "alternative"), 9), -(e.get("confidence_score") or 0)))
        fir_draft["proposed_bns_sections"] = merged

        # Also keep raw KIS output for traceability
        fir_draft["kis_bns_sections"] = {
            "primary": result.get("primary_sections", []),
            "alternative": result.get("alternative_sections", []),
            "model_name": result.get("model_name"),
        }

        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(doc, "parsed_output")
        await db.flush()

    return {
        "section_recommendation_status": "Completed",
        "primary_count": len(result.get("primary_sections", [])),
        "alternative_count": len(result.get("alternative_sections", [])),
        "analysis_id": persisted.get("persisted_analysis_id"),
    }


async def batch_recommend_sections(
    *,
    limit: int = 500,
    concurrency: int = 3,
    delay_ms: int = 200,
    dry_run: bool = False,
    user_id: str = "system:batch",
) -> dict:
    """Batch-reprocess existing documents that lack BNS section recommendations."""
    from database import get_session_factory

    factory = await get_session_factory()

    # Find candidate documents
    async with factory() as session:
        subq = (
            select(AIAnalysisResult.document_id)
            .where(AIAnalysisResult.analysis_type == "Section_Recommendation")
            .correlate(CaseDocument)
        )
        stmt = (
            select(CaseDocument.id, CaseDocument.case_id)
            .where(
                CaseDocument.ocr_extracted_text.isnot(None),
                CaseDocument.is_latest_version == True,  # noqa: E712
                ~CaseDocument.id.in_(subq),
            )
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

    candidates_found = len(rows)
    if dry_run:
        return {"candidates_found": candidates_found, "dry_run": True}

    semaphore = asyncio.Semaphore(concurrency)
    succeeded = 0
    skipped = 0
    failed = 0
    errors: list[dict] = []

    async def _process(doc_id: str, case_id: str) -> None:
        nonlocal succeeded, skipped, failed
        async with semaphore:
            async with factory() as session:
                try:
                    result = await auto_recommend_bns_sections(case_id, doc_id, user_id, session)
                    await session.commit()
                    status = result.get("section_recommendation_status", "")
                    if status == "Completed":
                        succeeded += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    await session.rollback()
                    failed += 1
                    errors.append({"document_id": doc_id, "error": str(exc)})
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)

    tasks = [_process(row.id, row.case_id) for row in rows]
    await asyncio.gather(*tasks, return_exceptions=True)

    return {
        "candidates_found": candidates_found,
        "processed": succeeded + skipped + failed,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "errors": errors[:50],
    }


def _supported_congruence_pair(a_type: str, b_type: str) -> bool:
    pair = {a_type, b_type}
    return (
        pair == {"Petition", "FIR"}
        or pair == {"FIR", "Witness_Statement"}
        or pair == {"FIR", "Charge_Sheet"}
        or "Medical_Report" in pair
    )


async def auto_run_congruence_for_document(
    case_id: str,
    new_document_id: str,
    user_id: str,
    db: AsyncSession,
) -> list[dict]:
    new_doc = await db.get(CaseDocument, new_document_id)
    if new_doc is None:
        return []
    result = await db.execute(select(CaseDocument).where(CaseDocument.case_id == case_id))
    docs = [doc for doc in result.scalars().all() if doc.id != new_document_id]
    created: list[dict] = []
    new_text = await _text_from_doc(new_doc)
    for other in docs:
        if not _supported_congruence_pair(str(_model_value(other.document_type)), str(_model_value(new_doc.document_type))):
            continue
        other_text = await _text_from_doc(other)
        data, meta = _llm_json(
            "Return JSON only. Compare two police case documents for contradictions, timeline inconsistencies, accused role mismatches, medical narrative discrepancies, and missing carry-forward facts. Use only supplied excerpts.",
            {
                "document_a_type": str(_model_value(other.document_type)),
                "document_a_text": other_text[:6000],
                "document_b_type": str(_model_value(new_doc.document_type)),
                "document_b_text": new_text[:6000],
                "required_schema": {
                    "alerts": [
                        {
                            "alert_type": "Contradiction|Timeline_Inconsistency|Role_Mismatch|Medical_Narrative_Discrepancy|Missing_Carry_Forward",
                            "severity": "High|Medium|Low",
                            "description": "string",
                            "excerpt_doc_a": "string",
                            "excerpt_doc_b": "string",
                        }
                    ]
                },
            },
            task="congruence_detection",
        )
        if data is None:
            data = {"alerts": [], "stub_reason": "Live LLM is not configured; congruence alerts were not generated."}
        for alert_payload in data.get("alerts", []) or []:
            alert_type = alert_payload.get("alert_type") or "Missing_Carry_Forward"
            severity = alert_payload.get("severity") or "Medium"
            description = alert_payload.get("description") or "Potential cross-document inconsistency."
            excerpt_a = alert_payload.get("excerpt_doc_a") or other_text[:240]
            excerpt_b = alert_payload.get("excerpt_doc_b") or new_text[:240]
            if alert_type not in {"Contradiction", "Timeline_Inconsistency", "Role_Mismatch", "Medical_Narrative_Discrepancy", "Missing_Carry_Forward"}:
                alert_type = "Contradiction"
            if severity not in {"High", "Medium", "Low"}:
                severity = "Medium"
            alert = CongruenceAlert(
                case_id=case_id,
                document_a_id=other.id,
                document_b_id=new_document_id,
                alert_type=alert_type,
                severity=severity,
                description=description,
                excerpt_doc_a=excerpt_a,
                excerpt_doc_b=excerpt_b,
                feeds_model_refinement=False,
                created_by=user_id,
            )
            db.add(alert)
            await db.flush()
            created.append(
                {
                    "id": alert.id,
                    "alert_type": alert_type,
                    "severity": severity,
                    "description": description,
                    "document_a_id": other.id,
                    "document_b_id": new_document_id,
                    "excerpt_doc_a": alert.excerpt_doc_a,
                    "excerpt_doc_b": alert.excerpt_doc_b,
                    "llm_provider": meta["provider"],
                    "llm_mode": meta["mode"],
                    "privacy_controls": meta.get("privacy", {}),
                }
            )
    if created:
        case = await db.get(Case, case_id)
        if case and case.io_id:
            db.add(
                Notification(
                    user_id=case.io_id,
                    type="congruence",
                    message=f"{len(created)} new congruence alert(s) generated.",
                    entity_type="case",
                    entity_id=case_id,
                    created_by=user_id,
                )
            )
            await db.flush()
    return created


async def dismiss_congruence_alert(
    alert_id: str,
    reason_code: str,
    notes: str,
    user_id: str,
    db: AsyncSession,
) -> dict:
    alert = await db.get(CongruenceAlert, alert_id)
    if alert is None:
        raise ValueError(f"Congruence alert '{alert_id}' not found.")
    alert.is_dismissed = True
    alert.dismiss_reason_code = reason_code
    alert.dismiss_notes = notes
    alert.dismissed_by = user_id
    alert.dismissed_at = datetime.now(timezone.utc)
    alert.feeds_model_refinement = True
    await db.flush()
    return {"id": alert.id, "is_dismissed": True, "feeds_model_refinement": True}


async def generate_investigation_plan(case_id: str, user_id: str, db: AsyncSession) -> dict:
    case = await db.get(Case, case_id)
    if case is None:
        raise ValueError(f"Case '{case_id}' not found.")
    offence = case.offence_type or case.primary_offence_type_id or "Generic"
    data, meta = _llm_json(
        "Return JSON only. Generate an editable investigation plan for an Indian police case. Include numbered steps with legal citations, evidence with forensic requirements, generated documents, and statutory deadline countdowns.",
        {
            "case": {
                "case_id": case.id,
                "case_type": _model_value(case.case_type),
                "crime_no": case.crime_no,
                "petition_no": case.petition_no,
                "brief_facts": case.brief_facts,
                "offence_type": offence,
            },
            "required_schema": {
                "investigation_steps": [{"number": 1, "step": "string", "legal_citation": "string", "completed": False}],
                "evidence_to_collect": [{"item": "string", "forensic_requirement": "string"}],
                "documents_to_generate": ["string"],
                "statutory_deadlines": [{"name": "string", "due_date": "YYYY-MM-DD", "countdown_days": 0}],
            },
        },
        task="investigation_plan",
    )
    deadlines = [
        {"name": "Progress review", "due_date": (date.today() + timedelta(days=30)).isoformat(), "countdown_days": 30},
        {"name": "Charge-sheet review", "due_date": (date.today() + timedelta(days=90)).isoformat(), "countdown_days": 90},
    ]
    if data is None:
        data = {
            "investigation_steps": [
                {"number": 1, "step": "Record detailed complainant statement", "legal_citation": "Section 183 BNSS", "completed": False},
                {"number": 2, "step": "Identify and examine material witnesses", "legal_citation": "BNSS investigation powers", "completed": False},
            ],
            "evidence_to_collect": [
                {"item": "CCTV/digital evidence", "forensic_requirement": "Preserve hash and chain of custody"},
                {"item": "Medical/FSL records", "forensic_requirement": "Certified report with lab reference"},
            ],
            "documents_to_generate": ["FSL forwarding letter", "Evidence certificate", "Case diary note"],
            "statutory_deadlines": deadlines,
        }
    plan = InvestigationPlan(
        case_id=case_id,
        offence_type_detected=offence,
        investigation_steps=data.get("investigation_steps") or [],
        evidence_to_collect=data.get("evidence_to_collect") or [],
        documents_to_generate=data.get("documents_to_generate") or [],
        statutory_deadlines=data.get("statutory_deadlines") or deadlines,
        is_editable=True,
        created_by=user_id,
    )
    db.add(plan)
    await db.flush()
    return {
        "id": plan.id,
        "case_id": case_id,
        "offence_type_detected": offence,
        "requires_io_confirmation": True,
        "investigation_steps": plan.investigation_steps,
        "evidence_to_collect": plan.evidence_to_collect,
        "documents_to_generate": plan.documents_to_generate,
        "statutory_deadlines": plan.statutory_deadlines,
        "is_editable": True,
        "llm_provider": meta["provider"],
        "llm_mode": meta["mode"],
        "privacy_controls": meta.get("privacy", {}),
    }


async def analyze_judgment_document(doc: CaseDocument, user_id: str, db: AsyncSession) -> dict:
    text = await _text_from_doc(doc)
    data, meta = _llm_json(
        "Return JSON only. Analyze a court judgment for police investigation lessons. Extract facts, issues, verdict, reasons, investigation lapses with court observations, evidence quality observations, lessons, avoidable errors, and proposed checklist updates requiring AI Admin approval.",
        {
            "judgment_text": text[:12000],
            "required_schema": {
                "case_facts": "string",
                "issues_raised": ["string"],
                "verdict": "string",
                "reasons_for_verdict": "string",
                "investigation_lapses": ["string"],
                "evidence_quality_observations": ["string"],
                "investigation_lessons": "string",
                "avoidable_errors": "string",
                "proposed_checklist_updates": [{"title": "string", "status": "Draft", "requires_ai_admin_approval": True}],
            },
        },
        task="judgment_analysis",
    )
    if data is None:
        data = {
            "case_facts": text[:500],
            "issues_raised": ["Whether investigation evidence proved the charged offence"],
            "verdict": "Extracted verdict requires AI Admin/legal review",
            "reasons_for_verdict": "Stub summary generated because live LLM is not configured.",
            "investigation_lapses": ["Check for missing witness linkage", "Check chain-of-custody observations"],
            "evidence_quality_observations": ["Review documentary and forensic evidence quality"],
            "investigation_lessons": "- Preserve source evidence early\n- Record specific witness facts\n- Keep hash and custody records",
            "avoidable_errors": "Avoid vague witness statements and incomplete digital evidence certification.",
            "proposed_checklist_updates": [
                {"title": "Judgment-derived evidence checklist", "status": "Draft", "requires_ai_admin_approval": True}
            ],
        }
    analysis = JudgmentAnalysis(
        uploaded_file_id=doc.id,
        case_facts=data.get("case_facts"),
        issues_raised=data.get("issues_raised") or [],
        verdict=data.get("verdict"),
        reasons_for_verdict=data.get("reasons_for_verdict"),
        investigation_lapses=data.get("investigation_lapses") or [],
        evidence_quality_observations=data.get("evidence_quality_observations") or [],
        investigation_lessons=data.get("investigation_lessons"),
        avoidable_errors=data.get("avoidable_errors"),
        proposed_checklist_updates=data.get("proposed_checklist_updates") or [],
        checklist_update_status="Pending_AI_Admin_Approval",
        created_by=user_id,
    )
    db.add(analysis)
    await db.flush()
    return {
        "id": analysis.id,
        "case_facts": analysis.case_facts,
        "issues_raised": analysis.issues_raised,
        "verdict": analysis.verdict,
        "investigation_lapses": analysis.investigation_lapses,
        "evidence_quality_observations": analysis.evidence_quality_observations,
        "investigation_lessons": analysis.investigation_lessons,
        "avoidable_errors": analysis.avoidable_errors,
        "proposed_checklist_updates": analysis.proposed_checklist_updates,
        "checklist_update_status": analysis.checklist_update_status,
        "llm_provider": meta["provider"],
        "llm_mode": meta["mode"],
        "privacy_controls": meta.get("privacy", {}),
    }


async def usage_analytics(filters: dict, user: dict, db: AsyncSession) -> dict:
    case_stmt = select(Case)
    if user.get("role") == "IO":
        case_stmt = case_stmt.where(Case.io_id == user.get("sub"))
    if filters.get("police_station_id"):
        case_stmt = case_stmt.where(Case.police_station_id == filters["police_station_id"])
    cases = (await db.execute(case_stmt)).scalars().all()
    case_ids = {case.id for case in cases}
    docs = (await db.execute(select(CaseDocument))).scalars().all()
    analyses = (await db.execute(select(AIAnalysisResult))).scalars().all()
    events = (await db.execute(select(UsageEvent))).scalars().all()
    return {
        "totals": {
            "cases_created": len(cases),
            "documents_uploaded": len([doc for doc in docs if doc.case_id in case_ids]),
            "ai_checks_performed": len([item for item in analyses if item.case_id in case_ids]),
            "documents_generated": 0,
        },
        "breakdowns": {
            "cases_by_io": {case.io_id or "unassigned": len([c for c in cases if c.io_id == case.io_id]) for case in cases},
            "cases_by_police_station": {case.police_station_id or "unassigned": len([c for c in cases if c.police_station_id == case.police_station_id]) for case in cases},
        },
        "time_spent": {
            "average_minutes_per_case": 0,
            "average_minutes_per_activity": 0,
        },
        "feature_usage_frequency": [
            {"module": event.module or event.event_type, "count": len([e for e in events if e.module == event.module])}
            for event in events
        ],
        "filters_applied": filters,
        "scope": "own" if user.get("role") == "IO" else "all",
    }
