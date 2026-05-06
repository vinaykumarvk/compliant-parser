# -*- coding: utf-8 -*-
"""Document quality evaluation engine for the IQW platform.

Provides checklist-based quality scoring, trial-risk classification,
and actionable suggestions for Investigating Officers (IOs).
"""

from __future__ import annotations

import re
import uuid
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_CHECKLISTS",
    "INVESTIGATION_QUESTIONS",
    "classify_trial_risk",
    "evaluate_checklist_item",
    "generate_suggestion",
    "run_quality_check",
    "run_llm_quality_check",
    "seed_checklists",
]

# ---------------------------------------------------------------------------
# Stop-words filtered out when building keyword sets from checklist items
# ---------------------------------------------------------------------------
_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "if", "in", "is", "it", "of", "on", "or", "the", "to", "was",
    "with", "not", "no", "any", "has", "had", "have", "that", "this",
    "their", "its", "such", "been", "were", "being",
})

# ---------------------------------------------------------------------------
# Default checklists — keyed by document_type
# ---------------------------------------------------------------------------
DEFAULT_CHECKLISTS: Dict[str, List[Dict[str, str]]] = {
    "Generic": [
        {"item": "Complainant full name and address", "severity": "High", "category": "Identity"},
        {"item": "Date and time of incident", "severity": "High", "category": "Timeline"},
        {"item": "Place of occurrence with landmark", "severity": "High", "category": "Location"},
        {"item": "Description of incident/offence", "severity": "High", "category": "Narrative"},
        {"item": "Property involved or loss amount", "severity": "Medium", "category": "Property"},
        {"item": "Name/description of accused", "severity": "High", "category": "Accused"},
        {"item": "Witness names and contact info", "severity": "Medium", "category": "Witnesses"},
        {"item": "Evidence description", "severity": "Medium", "category": "Evidence"},
        {"item": "Prior complaints or history", "severity": "Low", "category": "History"},
        {"item": "Motive or reason", "severity": "Medium", "category": "Motive"},
        {"item": "Injuries description", "severity": "Medium", "category": "Injuries"},
        {"item": "Vehicle details (if applicable)", "severity": "Low", "category": "Vehicle"},
        {"item": "Communication records referenced", "severity": "Low", "category": "Records"},
        {"item": "Signature or verification", "severity": "Medium", "category": "Verification"},
        {"item": "Investigating officer assignment", "severity": "High", "category": "Assignment"},
    ],
    "FIR": [
        {"item": "FIR number and police station", "severity": "High", "category": "Registration"},
        {"item": "Sections of law applied (BNS/IPC)", "severity": "High", "category": "Legal"},
        {"item": "Cognizable or non-cognizable classification", "severity": "High", "category": "Classification"},
        {"item": "Action taken by officer on duty", "severity": "Medium", "category": "Action"},
        {"item": "Time of registration vs time of occurrence", "severity": "Medium", "category": "Timeline"},
    ],
    "Witness_Statement": [
        {"item": "Witness relationship to complainant/accused", "severity": "Medium", "category": "Relationship"},
        {"item": "Statement recorded under oath", "severity": "High", "category": "Legal"},
        {"item": "Cross-examination readiness noted", "severity": "Low", "category": "Procedure"},
    ],
    "Charge_Sheet": [
        {"item": "List of accused with identification details", "severity": "High", "category": "Accused"},
        {"item": "Summary of evidence collected", "severity": "High", "category": "Evidence"},
        {"item": "Forensic or scientific reports attached", "severity": "Medium", "category": "Forensics"},
        {"item": "List of prosecution witnesses", "severity": "High", "category": "Witnesses"},
        {"item": "Court jurisdiction and filing deadline", "severity": "High", "category": "Jurisdiction"},
    ],
}

# ---------------------------------------------------------------------------
# Investigation questions — structured per-category for LLM semantic analysis
# ---------------------------------------------------------------------------
INVESTIGATION_QUESTIONS: Dict[str, List[Dict[str, Any]]] = {
    "Generic": [
        {
            "id": "identity",
            "label": "Complainant / Victim Identity",
            "trial_impact": "Failure to establish victim identity can lead to case dismissal.",
            "questions": [
                {"q": "Is the complainant's full name recorded (including father's/spouse's name)?", "severity": "High"},
                {"q": "Is the complainant's complete residential address provided?", "severity": "High"},
                {"q": "Are contact details (phone/mobile) mentioned?", "severity": "Medium"},
                {"q": "Is age, gender, or occupation stated?", "severity": "Low"},
            ],
        },
        {
            "id": "location",
            "label": "Place of Occurrence",
            "trial_impact": "Imprecise location weakens scene-of-crime evidence and jurisdiction.",
            "questions": [
                {"q": "Is the place of occurrence described with enough detail to identify it?", "severity": "High"},
                {"q": "Are nearby landmarks, road names, or shop names mentioned?", "severity": "Medium"},
                {"q": "Is there a GPS coordinate, survey number, or pin code?", "severity": "Low"},
            ],
        },
        {
            "id": "timeline",
            "label": "Date & Time of Incident",
            "trial_impact": "Missing timeline undermines alibis and corroboration.",
            "questions": [
                {"q": "Is the date of the incident recorded?", "severity": "High"},
                {"q": "Is the approximate or exact time stated?", "severity": "High"},
                {"q": "Is there a delay between occurrence and reporting — if so, is it explained?", "severity": "Medium"},
            ],
        },
        {
            "id": "accused",
            "label": "Accused / Suspect Details",
            "trial_impact": "Unidentified accused makes arrest and charge-sheet difficult.",
            "questions": [
                {"q": "Is the accused named, or is a physical description provided?", "severity": "High"},
                {"q": "Are identification marks, aliases, or known associates mentioned?", "severity": "Medium"},
                {"q": "Is the accused's last known address or workplace noted?", "severity": "Medium"},
            ],
        },
        {
            "id": "narrative",
            "label": "Incident Narrative",
            "trial_impact": "Vague narrative fails to establish actus reus and mens rea.",
            "questions": [
                {"q": "Is the sequence of events described in the complainant's own words?", "severity": "High"},
                {"q": "Are specific criminal acts (assault, theft, threat, etc.) described?", "severity": "High"},
                {"q": "Are dialogues, threats, or demands quoted?", "severity": "Medium"},
            ],
        },
        {
            "id": "property",
            "label": "Property / Loss",
            "trial_impact": "Unspecified property weakens theft/robbery charges.",
            "questions": [
                {"q": "Is stolen/damaged property listed with descriptions?", "severity": "Medium"},
                {"q": "Are estimated values or serial numbers/IMEI provided?", "severity": "Medium"},
            ],
        },
        {
            "id": "witnesses",
            "label": "Witnesses",
            "trial_impact": "No witnesses weakens prosecution's corroboration.",
            "questions": [
                {"q": "Are any witnesses named?", "severity": "Medium"},
                {"q": "Are witness contact details or addresses provided?", "severity": "Medium"},
            ],
        },
        {
            "id": "evidence",
            "label": "Evidence",
            "trial_impact": "Undocumented evidence may be inadmissible.",
            "questions": [
                {"q": "Is physical or digital evidence mentioned (CCTV, photos, documents)?", "severity": "Medium"},
                {"q": "Is there mention of evidence collection or preservation?", "severity": "Low"},
            ],
        },
        {
            "id": "injuries",
            "label": "Injuries / Medical",
            "trial_impact": "Missing injury details weaken assault/hurt charges.",
            "questions": [
                {"q": "Are injuries described or a medical report referenced?", "severity": "Medium"},
                {"q": "Is the nature and severity of injuries stated?", "severity": "Medium"},
            ],
        },
        {
            "id": "verification",
            "label": "Verification & Signature",
            "trial_impact": "Unsigned documents may be challenged for authenticity.",
            "questions": [
                {"q": "Is a signature, thumb impression, or attestation present?", "severity": "Medium"},
                {"q": "Is the investigating officer's name and designation recorded?", "severity": "High"},
            ],
        },
    ],
    "FIR": [
        {
            "id": "registration",
            "label": "FIR Registration Details",
            "trial_impact": "Missing registration data invalidates the FIR as a legal document.",
            "questions": [
                {"q": "Is the FIR number recorded?", "severity": "High"},
                {"q": "Is the police station name mentioned?", "severity": "High"},
                {"q": "Are applicable sections of law (BNS/IPC) cited?", "severity": "High"},
                {"q": "Is the cognizable/non-cognizable classification stated?", "severity": "High"},
                {"q": "Is the time of registration vs time of occurrence noted?", "severity": "Medium"},
            ],
        },
    ],
    "Witness_Statement": [
        {
            "id": "witness_identity",
            "label": "Witness Identity & Relationship",
            "trial_impact": "Unverified witness identity undermines testimony credibility.",
            "questions": [
                {"q": "Is the witness's full name and address recorded?", "severity": "High"},
                {"q": "Is the witness's relationship to complainant/accused stated?", "severity": "Medium"},
            ],
        },
        {
            "id": "witness_account",
            "label": "Witness Account",
            "trial_impact": "Vague witness account cannot corroborate prosecution's version.",
            "questions": [
                {"q": "Does the witness describe what they personally saw or heard?", "severity": "High"},
                {"q": "Are specific details (time, place, persons) mentioned in the account?", "severity": "High"},
            ],
        },
        {
            "id": "witness_procedure",
            "label": "Statement Procedure",
            "trial_impact": "Procedural lapses make the statement vulnerable to defence objections.",
            "questions": [
                {"q": "Is it stated that the statement was recorded under oath?", "severity": "High"},
                {"q": "Is cross-examination readiness noted?", "severity": "Low"},
            ],
        },
    ],
    "Charge_Sheet": [
        {
            "id": "cs_accused",
            "label": "Accused Identification (Charge Sheet)",
            "trial_impact": "Incomplete accused details may cause court to reject the charge sheet.",
            "questions": [
                {"q": "Is each accused listed with full identification details?", "severity": "High"},
                {"q": "Are arrest/bail details mentioned for each accused?", "severity": "High"},
            ],
        },
        {
            "id": "cs_evidence",
            "label": "Evidence Summary (Charge Sheet)",
            "trial_impact": "Missing evidence summary weakens prosecution's case.",
            "questions": [
                {"q": "Is a summary of collected evidence provided?", "severity": "High"},
                {"q": "Are forensic/scientific reports attached or referenced?", "severity": "Medium"},
            ],
        },
        {
            "id": "cs_witnesses",
            "label": "Prosecution Witnesses (Charge Sheet)",
            "trial_impact": "Unlisted witnesses cannot be examined during trial.",
            "questions": [
                {"q": "Is a list of prosecution witnesses provided?", "severity": "High"},
            ],
        },
        {
            "id": "cs_jurisdiction",
            "label": "Jurisdiction & Filing",
            "trial_impact": "Wrong jurisdiction leads to case transfer or dismissal.",
            "questions": [
                {"q": "Is the court of jurisdiction specified?", "severity": "High"},
                {"q": "Is the filing deadline or submission date mentioned?", "severity": "High"},
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# LLM system prompt for semantic quality analysis
# ---------------------------------------------------------------------------
_QUALITY_SYSTEM_PROMPT = """\
You are a senior Indian police investigation quality analyst. Your task is to \
evaluate an investigation document against a set of structured quality questions.

CRITICAL INSTRUCTIONS:
- Look for SEMANTIC meaning, not keywords. A shop address IS a place of \
occurrence. A person's name with "S/o" IS an identity. A date mentioned in \
the narrative IS a timeline.
- Quote EXACT text from the document as excerpts — do not paraphrase.
- Do NOT fabricate findings. If information is genuinely absent, say so.
- Assess trial impact from the prosecution's perspective.
- For each question, determine: "complete" (clearly present), "partial" \
(some info but incomplete), or "not_found" (absent).
- For each category, give an overall status: "complete" if all questions are \
complete, "partial" if any are partial or some not_found, "not_found" if all \
are not_found.

Respond with ONLY valid JSON matching the required schema.\
"""

_QUALITY_USER_TEMPLATE = """\
Document type: {document_type}
Document text (first 8000 chars):
---
{document_text}
---

Investigation questions by category:
{questions_json}

Required JSON response schema:
{{
  "categories": [
    {{
      "id": "<category id>",
      "label": "<category label>",
      "status": "complete | partial | not_found",
      "summary": "<1-2 sentence summary of what was found or missing>",
      "findings": [
        {{
          "question": "<the question text>",
          "answer": "<brief answer based on document>",
          "excerpt": "<exact quote from document or null>",
          "status": "complete | partial | not_found"
        }}
      ],
      "gaps": ["<specific missing information>"],
      "io_actions": ["<specific action the IO should take>"],
      "trial_impact": "<how gaps affect trial prospects>"
    }}
  ],
  "overall_readiness": "Ready | Needs_Work | Incomplete",
  "investigation_readiness_score": 0.0 to 1.0,
  "priority_actions": ["<most urgent IO actions>"],
  "strengths": ["<well-documented aspects>"]
}}\
"""


_CASE_CONTEXT_SECTION = """\
CASE CONTEXT (from petition intake):
The following facts were extracted from the source petition. Use this context to
INFORM your evaluation. If a checklist item is answered by the petition context,
mark it "complete" and cite the petition context as the source. Do NOT mark items
as "not_found" when the petition context clearly provides the information.

Petition-extracted metadata:
{context_json}
"""

OFFENCE_SPECIFIC_QUESTIONS: Dict[str, List[Dict[str, Any]]] = {
    "Theft": [
        {
            "id": "theft_specifics",
            "label": "Theft-Specific Investigation Points",
            "trial_impact": "Missing property details or entry method weakens theft prosecution under IPC 379/380.",
            "questions": [
                {"q": "Is the stolen property described with specifics (make, model, serial number, value)?", "severity": "High"},
                {"q": "Is the mode of entry or method of theft described?", "severity": "High"},
                {"q": "Has a property list or seizure memo been prepared?", "severity": "Medium"},
            ],
        },
    ],
    "Robbery": [
        {
            "id": "robbery_specifics",
            "label": "Robbery-Specific Investigation Points",
            "trial_impact": "Missing evidence of force or threat weakens robbery charge under IPC 392.",
            "questions": [
                {"q": "Is there evidence of force, threat, or intimidation described?", "severity": "High"},
                {"q": "Are weapons or instruments used in the robbery described?", "severity": "High"},
                {"q": "Are injuries to the victim documented with medical evidence?", "severity": "Medium"},
            ],
        },
    ],
    "Cheating": [
        {
            "id": "cheating_specifics",
            "label": "Cheating-Specific Investigation Points",
            "trial_impact": "Missing evidence of dishonest inducement weakens cheating charge under IPC 420.",
            "questions": [
                {"q": "Is the false representation or promise described with specifics?", "severity": "High"},
                {"q": "Is the financial loss or property delivered quantified?", "severity": "High"},
                {"q": "Are documentary evidences (receipts, agreements, messages) collected or referenced?", "severity": "Medium"},
            ],
        },
    ],
}


def _get_investigation_questions(document_type: str, offence_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return merged investigation questions for *document_type*.

    Type-specific categories are listed first, followed by Generic categories
    whose ``id`` is not already covered.
    """
    generic = INVESTIGATION_QUESTIONS.get("Generic", [])
    type_specific = INVESTIGATION_QUESTIONS.get(document_type)
    if not type_specific:
        base = list(generic)
    else:
        seen_ids = {cat["id"] for cat in type_specific}
        base = list(type_specific)
        for cat in generic:
            if cat["id"] not in seen_ids:
                base.append(cat)
                seen_ids.add(cat["id"])

    # Merge offence-specific questions if available
    if offence_type:
        offence_cats = OFFENCE_SPECIFIC_QUESTIONS.get(offence_type, [])
        existing_ids = {cat["id"] for cat in base}
        for cat in offence_cats:
            if cat["id"] not in existing_ids:
                base.append(cat)
                existing_ids.add(cat["id"])
    return base


def _normalize_llm_quality_result(
    data: Dict[str, Any],
    document_type: str,
    questions: List[Dict[str, Any]],
    latency_ms: int,
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and normalize LLM output into canonical quality result.

    Builds backward-compatible flat ``findings`` alongside the richer
    ``categories`` structure.
    """
    categories = data.get("categories", [])
    overall_readiness = data.get("overall_readiness", "Needs_Work")
    readiness_score = data.get("investigation_readiness_score", 0.5)
    priority_actions = data.get("priority_actions", [])
    strengths = data.get("strengths", [])

    # Build flat findings for backward compatibility
    flat_findings: List[Dict[str, Any]] = []
    present_count = 0
    weak_count = 0
    missing_count = 0

    _status_map = {"complete": "present", "partial": "weak", "not_found": "missing"}

    for cat in categories:
        cat_id = cat.get("id", "")
        cat_label = cat.get("label", "")
        for finding in cat.get("findings", []):
            raw_status = finding.get("status", "not_found")
            mapped_status = _status_map.get(raw_status, "missing")
            # Determine severity from question definitions
            severity = "Medium"
            for q_cat in questions:
                if q_cat["id"] == cat_id:
                    for q in q_cat.get("questions", []):
                        if q["q"] == finding.get("question"):
                            severity = q.get("severity", "Medium")
                            break
                    break

            flat_finding = {
                "item": finding.get("question", ""),
                "severity": severity,
                "category": cat_label,
                "status": mapped_status,
                "excerpt": finding.get("excerpt"),
                "char_start": None,
                "char_end": None,
                "citation": {
                    "citation_id": str(uuid.uuid4()),
                    "excerpt": finding.get("excerpt"),
                    "char_start": None,
                    "char_end": None,
                    "purpose": "supporting_excerpt" if mapped_status != "missing" else "absence_check",
                    "click_target": None,
                },
                "suggestion": finding.get("answer", ""),
            }
            flat_findings.append(flat_finding)

            if mapped_status == "present":
                present_count += 1
            elif mapped_status == "weak":
                weak_count += 1
            else:
                missing_count += 1

    total_items = len(flat_findings)
    completeness_score = round(present_count / total_items, 2) if total_items else 0.0

    trial_risk_indicators = _derive_trial_risks_from_categories(categories)

    analysis_id = str(uuid.uuid4())

    return {
        "analysis_id": analysis_id,
        "document_type": document_type,
        "checklist_used": "semantic_llm",
        "checklist_note": None,
        "analysis_mode": "semantic",
        # New rich structure
        "categories": categories,
        "overall_readiness": overall_readiness,
        "investigation_readiness_score": readiness_score,
        "priority_actions": priority_actions,
        "strengths": strengths,
        # Backward-compatible flat structure
        "findings": flat_findings,
        "suppressed_uncited_findings": [],
        "trial_risk_indicators": trial_risk_indicators,
        "completeness_score": completeness_score,
        "confidence_score": readiness_score,
        "latency_ms": latency_ms,
        "latency_target_ms": QUALITY_LATENCY_TARGET_MS,
        "latency_within_target": latency_ms < QUALITY_LATENCY_TARGET_MS,
        "total_items": total_items,
        "present_count": present_count,
        "weak_count": weak_count,
        "missing_count": missing_count,
        "llm_meta": meta,
    }


def _derive_trial_risks_from_categories(categories: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Build trial risk indicators from category gaps."""
    risks: List[Dict[str, str]] = []
    for cat in categories:
        status = cat.get("status", "complete")
        if status == "complete":
            continue
        gaps = cat.get("gaps", [])
        trial_impact = cat.get("trial_impact", "")
        label = cat.get("label", "Unknown")
        severity = "High" if status == "not_found" else "Medium"

        if gaps:
            for gap in gaps:
                risks.append({
                    "risk": f"{label}: {gap}",
                    "severity": severity,
                })
        elif trial_impact:
            risks.append({
                "risk": f"{label}: {trial_impact}",
                "severity": severity,
            })
    return risks


def run_llm_quality_check(
    document_text: str,
    document_type: str,
    offence_type: Optional[str] = None,
    case_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run LLM-powered semantic quality check with keyword fallback.

    On LLM unavailability or error, silently falls back to the keyword-based
    :func:`run_quality_check`.
    """
    import json as _json

    started = time.perf_counter()
    questions = _get_investigation_questions(document_type, offence_type=offence_type)

    # Truncate document for LLM context
    truncated_text = document_text[:8000] if document_text else ""
    if not truncated_text.strip():
        return run_quality_check(document_text, document_type, offence_type)

    # Build questions payload (strip to essentials)
    q_payload = []
    for cat in questions:
        q_payload.append({
            "id": cat["id"],
            "label": cat["label"],
            "trial_impact": cat["trial_impact"],
            "questions": [{"q": q["q"], "severity": q["severity"]} for q in cat["questions"]],
        })

    user_prompt_text = _QUALITY_USER_TEMPLATE.format(
        document_type=document_type,
        document_text=truncated_text,
        questions_json=_json.dumps(q_payload, indent=2, ensure_ascii=False),
    )

    if case_context:
        context_section = _CASE_CONTEXT_SECTION.format(
            context_json=_json.dumps(case_context, indent=2, ensure_ascii=False, default=str)
        )
        user_prompt_text = context_section + "\n" + user_prompt_text

    try:
        from ai_workflows import _llm_json
        llm_data, meta = _llm_json(
            _QUALITY_SYSTEM_PROMPT,
            {"system": _QUALITY_SYSTEM_PROMPT, "user": user_prompt_text},
            task="quality_check",
        )
    except Exception:
        logger.info("LLM unavailable for quality check — falling back to keyword engine.")
        return run_quality_check(document_text, document_type, offence_type)

    if llm_data is None:
        # Stub mode — fall back to keyword engine
        logger.info("LLM returned stub — falling back to keyword engine.")
        return run_quality_check(document_text, document_type, offence_type)

    latency_ms = int((time.perf_counter() - started) * 1000)

    try:
        result = _normalize_llm_quality_result(llm_data, document_type, questions, latency_ms, meta)
    except Exception:
        logger.exception("Failed to normalize LLM quality result — falling back.")
        return run_quality_check(document_text, document_type, offence_type)

    logger.info(
        "Semantic quality check: type=%s, readiness=%s, score=%.2f, categories=%d",
        document_type, result.get("overall_readiness"), result.get("completeness_score", 0), len(result.get("categories", [])),
    )
    return result


# In-memory store used at runtime (populated by seed_checklists)
_checklist_store: Dict[str, List[Dict[str, str]]] = {}
GENERIC_CHECKLIST_NOTE = "Generic checklist applied. Contact AI Admin for offence-specific checklists."
QUALITY_LATENCY_TARGET_MS = 10_000

# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_checklists() -> None:
    """Populate the in-memory checklist store from *DEFAULT_CHECKLISTS*.

    Safe to call multiple times; each call resets the store to the
    built-in defaults.
    """
    _checklist_store.clear()
    for doc_type, items in DEFAULT_CHECKLISTS.items():
        _checklist_store[doc_type] = [entry.copy() for entry in items]
    logger.info("Seeded %d checklist types into in-memory store.", len(_checklist_store))


def _get_checklist(document_type: str) -> List[Dict[str, str]]:
    """Return the checklist for *document_type*, falling back to Generic."""
    if not _checklist_store:
        seed_checklists()
    checklist = _checklist_store.get(document_type)
    if checklist is not None:
        return checklist
    return _checklist_store.get("Generic", [])


# ---------------------------------------------------------------------------
# Keyword extraction helpers
# ---------------------------------------------------------------------------

def _extract_keywords(text: str) -> List[str]:
    """Split *text* into lowercase tokens, discarding stop-words and
    tokens shorter than 3 characters."""
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


def _find_best_match(keywords: List[str], document_text: str) -> tuple:
    """Search *document_text* for *keywords* and return (hit_count,
    excerpt, char_start, char_end).

    The excerpt is the first sentence-like window surrounding the best
    keyword match.
    """
    doc_lower = document_text.lower()
    hit_count = 0
    best_start: Optional[int] = None
    best_end: Optional[int] = None

    for kw in keywords:
        pos = doc_lower.find(kw)
        if pos != -1:
            hit_count += 1
            if best_start is None:
                # Capture a context window around the first hit
                window_start = max(0, pos - 40)
                window_end = min(len(document_text), pos + len(kw) + 80)
                best_start = window_start
                best_end = window_end

    excerpt: Optional[str] = None
    if best_start is not None and best_end is not None:
        excerpt = document_text[best_start:best_end].strip()

    return hit_count, excerpt, best_start, best_end


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate_checklist_item(item_text: str, document_text: str) -> Dict[str, Any]:
    """Evaluate a single checklist item against *document_text*.

    Returns a dict with keys ``status``, ``excerpt``, ``char_start``,
    ``char_end``.  Status is one of ``"present"``, ``"weak"``, or
    ``"missing"``.
    """
    keywords = _extract_keywords(item_text)
    if not keywords:
        return {"status": "missing", "excerpt": None, "char_start": None, "char_end": None}

    hit_count, excerpt, char_start, char_end = _find_best_match(keywords, document_text)
    ratio = hit_count / len(keywords)

    if ratio >= 0.5:
        status = "present"
    elif ratio >= 0.2:
        status = "weak"
    else:
        status = "missing"

    return {
        "status": status,
        "excerpt": excerpt if status != "missing" else None,
        "char_start": char_start if status != "missing" else None,
        "char_end": char_end if status != "missing" else None,
    }


# ---------------------------------------------------------------------------
# Trial-risk classification
# ---------------------------------------------------------------------------

_RISK_TEMPLATES = {
    "High": "Missing critical element ({item}) — likely acquittal risk",
    "Medium": "Missing supporting element ({item}) — may be challenged during trial",
    "Low": "Minor deficiency ({item}) — may weaken prosecution narrative",
}


def classify_trial_risk(findings: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Derive trial-risk indicators from checklist *findings*.

    Each finding is expected to contain ``item``, ``severity``, and
    ``status`` keys.  Only items whose status is ``"missing"`` or
    ``"weak"`` generate a risk indicator.
    """
    risks: List[Dict[str, str]] = []
    for finding in findings:
        status = finding.get("status", "present")
        if status == "present":
            continue
        severity = finding.get("severity", "Low")
        item = finding.get("item", "Unknown item")
        template = _RISK_TEMPLATES.get(severity, _RISK_TEMPLATES["Low"])
        qualifier = "Partially addressed" if status == "weak" else "Missing"
        risk_text = f"{qualifier}: {template.format(item=item)}"
        risks.append({"risk": risk_text, "severity": severity})
    return risks


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------

_SUGGESTION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "Identity": {
        "missing": "Record the complainant's full name, father's/spouse's name, and residential address with pin code.",
        "weak": "Verify and complete the complainant's identity details — ensure address includes pin code.",
    },
    "Timeline": {
        "missing": "Document the exact date, time, and day of the incident as reported by the complainant.",
        "weak": "Clarify the timeline — confirm whether date/time is approximate or exact.",
    },
    "Location": {
        "missing": "Record the precise place of occurrence including nearby landmarks, GPS coordinates if available.",
        "weak": "Add a recognisable landmark or survey number to strengthen location details.",
    },
    "Narrative": {
        "missing": "Obtain a detailed description of the incident in the complainant's own words.",
        "weak": "Expand the incident description with specific actions, sequence of events, and dialogues.",
    },
    "Property": {
        "missing": "List all property involved with estimated values and identifying marks.",
        "weak": "Add serial numbers, make/model, or photographs of the property for identification.",
    },
    "Accused": {
        "missing": "Record the name, alias, physical description, and last known address of the accused.",
        "weak": "Supplement accused details with photographs, identification marks, or known associates.",
    },
    "Witnesses": {
        "missing": "Identify and record at least two independent witnesses with contact information.",
        "weak": "Verify witness contact details and note their relationship to the parties involved.",
    },
    "Evidence": {
        "missing": "Collect and document all available evidence — physical, digital, and documentary.",
        "weak": "Ensure chain-of-custody documentation is complete for all evidence items.",
    },
    "History": {
        "missing": "Check for and note any prior complaints or criminal history related to the parties.",
        "weak": "Cross-reference prior complaint numbers and outcomes for completeness.",
    },
    "Motive": {
        "missing": "Investigate and record the apparent motive or reason behind the offence.",
        "weak": "Strengthen motive narrative with supporting evidence or witness statements.",
    },
    "Injuries": {
        "missing": "Obtain and attach a medical examination report detailing all injuries sustained.",
        "weak": "Ensure injury description includes nature, severity, and medical prognosis.",
    },
    "Vehicle": {
        "missing": "Record vehicle registration number, make, model, colour, and chassis number.",
        "weak": "Verify vehicle details against RTO records and add ownership information.",
    },
    "Records": {
        "missing": "Collect relevant communication records — call logs, messages, emails, or CCTV footage.",
        "weak": "Obtain certified copies of communication records with timestamps.",
    },
    "Verification": {
        "missing": "Ensure the document carries the complainant's signature or thumb impression with attestation.",
        "weak": "Add attestation from a gazetted officer or magistrate if required.",
    },
    "Assignment": {
        "missing": "Assign an Investigating Officer and record their name, rank, and badge number.",
        "weak": "Confirm IO assignment details and ensure jurisdictional authority is documented.",
    },
    "Registration": {
        "missing": "Record the FIR number, date of registration, and police station details.",
        "weak": "Verify FIR number sequence and ensure registration timestamp is accurate.",
    },
    "Legal": {
        "missing": "Cite the applicable sections of law (BNS/IPC/Special Acts) with brief descriptions.",
        "weak": "Review cited sections for accuracy and add any additional applicable provisions.",
    },
    "Classification": {
        "missing": "Classify the offence as cognizable or non-cognizable with legal basis.",
        "weak": "Re-examine classification and document the reasoning for the determination.",
    },
    "Action": {
        "missing": "Document the immediate action taken by the officer upon receiving the complaint.",
        "weak": "Expand the action-taken section with timelines and specific steps performed.",
    },
    "Procedure": {
        "missing": "Note whether cross-examination readiness has been assessed for the witness.",
        "weak": "Prepare the witness for potential cross-examination and document readiness status.",
    },
    "Relationship": {
        "missing": "Record the witness's relationship to both the complainant and the accused.",
        "weak": "Clarify the nature and duration of the witness's relationship to involved parties.",
    },
    "Forensics": {
        "missing": "Attach all forensic and scientific examination reports with lab reference numbers.",
        "weak": "Ensure forensic reports are signed, dated, and reference the correct case number.",
    },
    "Jurisdiction": {
        "missing": "Specify the court of jurisdiction and confirm the charge-sheet filing deadline.",
        "weak": "Verify jurisdictional competence and confirm remaining days for filing.",
    },
}

_FALLBACK_SUGGESTIONS = {
    "missing": "Obtain and document the required information: {item}.",
    "weak": "Strengthen the existing documentation for: {item}.",
}


def generate_suggestion(item_text: str, status: str, category: Optional[str] = None) -> str:
    """Return an actionable suggestion for an IO based on the checklist
    item's *status* (``"missing"`` or ``"weak"``).

    Uses category-specific templates when *category* is provided;
    otherwise falls back to a generic template.
    """
    if status == "present":
        return "No action needed — item is adequately documented."

    if category and category in _SUGGESTION_TEMPLATES:
        templates = _SUGGESTION_TEMPLATES[category]
        return templates.get(status, templates.get("missing", ""))

    fallback = _FALLBACK_SUGGESTIONS.get(status, _FALLBACK_SUGGESTIONS["missing"])
    return fallback.format(item=item_text)


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_confidence(completeness: float, weak_count: int, total: int) -> str:
    """Map completeness score and weak-item ratio to a confidence label."""
    if total == 0:
        return "Low"
    weak_ratio = weak_count / total
    if completeness >= 0.80 and weak_ratio <= 0.10:
        return "High"
    if completeness >= 0.50:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_quality_check(
    document_text: str,
    document_type: str,
    offence_type: Optional[str] = None,
    checklist_override: Optional[List[Dict[str, str]]] = None,
    checklist_note: Optional[str] = None,
    case_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a full quality check on *document_text*.

    Parameters
    ----------
    document_text:
        The plain-text content of the document to evaluate.
    document_type:
        One of the known document types (``"FIR"``, ``"Charge_Sheet"``,
        ``"Witness_Statement"``, or ``"Generic"``).
    offence_type:
        Optional offence classification (reserved for future
        offence-specific checklists).

    Returns
    -------
    dict
        A results dict containing findings, scores, and risk indicators.
    """
    started = time.perf_counter()
    base_checklist = checklist_override or _get_checklist(document_type)
    checklist_name = "KnowledgeBaseEntry" if checklist_override else (document_type if document_type in _checklist_store else "Generic")

    # For typed documents, merge the Generic checklist with the
    # type-specific one so the IO gets comprehensive coverage.
    if checklist_override:
        checklist = list(base_checklist)
    elif checklist_name != "Generic":
        generic = _get_checklist("Generic")
        seen_categories = {entry["category"] for entry in base_checklist}
        merged = list(base_checklist)
        for entry in generic:
            if entry["category"] not in seen_categories:
                merged.append(entry)
                seen_categories.add(entry["category"])
        checklist = merged
    else:
        checklist = list(base_checklist)

    findings: List[Dict[str, Any]] = []
    present_count = 0
    weak_count = 0
    missing_count = 0

    for entry in checklist:
        item_text = entry["item"]
        severity = entry["severity"]
        category = entry["category"]

        result = evaluate_checklist_item(item_text, document_text)
        suggestion = generate_suggestion(item_text, result["status"], category)

        excerpt = result["excerpt"]
        char_start = result["char_start"]
        char_end = result["char_end"]
        if not excerpt:
            excerpt = document_text[:240].strip() or "[empty document]"
            char_start = 0
            char_end = min(len(document_text), 240)

        citation = {
            "citation_id": str(uuid.uuid4()),
            "excerpt": excerpt,
            "char_start": char_start,
            "char_end": char_end,
            "purpose": "supporting_excerpt" if result["status"] != "missing" else "absence_check",
            "click_target": f"excerpt:{char_start or 0}-{char_end or 0}",
        }

        finding = {
            "item": item_text,
            "severity": severity,
            "category": category,
            "status": result["status"],
            "excerpt": excerpt,
            "char_start": char_start,
            "char_end": char_end,
            "citation": citation,
            "suggestion": suggestion,
        }
        findings.append(finding)

        if result["status"] == "present":
            present_count += 1
        elif result["status"] == "weak":
            weak_count += 1
        else:
            missing_count += 1

    total_items = len(findings)
    completeness_score = round(present_count / total_items, 2) if total_items else 0.0
    confidence_score = _compute_confidence(completeness_score, weak_count, total_items)
    trial_risk_indicators = classify_trial_risk(findings)

    analysis_id = str(uuid.uuid4())
    latency_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "Quality check %s: type=%s, score=%.2f, present=%d, weak=%d, missing=%d",
        analysis_id, document_type, completeness_score,
        present_count, weak_count, missing_count,
    )

    return {
        "analysis_id": analysis_id,
        "document_type": document_type,
        "checklist_used": checklist_name,
        "checklist_note": checklist_note or (GENERIC_CHECKLIST_NOTE if checklist_name == "Generic" else None),
        "findings": findings,
        "suppressed_uncited_findings": [],
        "trial_risk_indicators": trial_risk_indicators,
        "completeness_score": completeness_score,
        "confidence_score": confidence_score,
        "latency_ms": latency_ms,
        "latency_target_ms": QUALITY_LATENCY_TARGET_MS,
        "latency_within_target": latency_ms < QUALITY_LATENCY_TARGET_MS,
        "total_items": total_items,
        "present_count": present_count,
        "weak_count": weak_count,
        "missing_count": missing_count,
    }
