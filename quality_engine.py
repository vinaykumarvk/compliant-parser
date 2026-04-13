# -*- coding: utf-8 -*-
"""Document quality evaluation engine for the IQW platform.

Provides checklist-based quality scoring, trial-risk classification,
and actionable suggestions for Investigating Officers (IOs).
"""

from __future__ import annotations

import re
import uuid
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_CHECKLISTS",
    "classify_trial_risk",
    "evaluate_checklist_item",
    "generate_suggestion",
    "run_quality_check",
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

# In-memory store used at runtime (populated by seed_checklists)
_checklist_store: Dict[str, List[Dict[str, str]]] = {}

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
    base_checklist = _get_checklist(document_type)
    checklist_name = document_type if document_type in _checklist_store else "Generic"

    # For typed documents, merge the Generic checklist with the
    # type-specific one so the IO gets comprehensive coverage.
    if checklist_name != "Generic":
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

        finding = {
            "item": item_text,
            "severity": severity,
            "category": category,
            "status": result["status"],
            "excerpt": result["excerpt"],
            "char_start": result["char_start"],
            "char_end": result["char_end"],
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

    logger.info(
        "Quality check %s: type=%s, score=%.2f, present=%d, weak=%d, missing=%d",
        analysis_id, document_type, completeness_score,
        present_count, weak_count, missing_count,
    )

    return {
        "analysis_id": analysis_id,
        "document_type": document_type,
        "checklist_used": checklist_name,
        "findings": findings,
        "trial_risk_indicators": trial_risk_indicators,
        "completeness_score": completeness_score,
        "confidence_score": confidence_score,
        "total_items": total_items,
        "present_count": present_count,
        "weak_count": weak_count,
        "missing_count": missing_count,
    }
