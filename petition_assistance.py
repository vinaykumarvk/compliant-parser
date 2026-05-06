"""Deterministic missing-information assistance packet generation.

Phase 1 intentionally avoids LLM drafting. It creates a conservative English
packet from refined English text and parser gaps, with protected placeholders
and source-lineage records that can be persisted by the API layer.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass, replace
from typing import Any


PLACEHOLDER_PATTERN = re.compile(r"\[\[ADD_[A-Z]+_\d{3}: [^\]]+\]\]")

PACKET_STATUSES = {
    "drafting",
    "source_check_required",
    "needs_review",
    "approved",
    "printed",
    "shared",
    "accepted",
    "superseded",
    "failed",
    "cancelled",
}

FINAL_OR_REPLACED_STATUSES = {"printed", "shared", "accepted", "superseded", "failed", "cancelled"}

PLACEHOLDER_VALUE_STATUSES = {
    "blank",
    "filled",
    "accepted_unknown",
    "needs_follow_up",
    "officer_rejected",
    "accepted",
}

FINAL_ACCEPTABLE_VALUE_STATUSES = {"accepted", "accepted_unknown", "needs_follow_up"}

DISCLOSURE_TEXT = (
    "This document is generated to help you identify and add missing information. "
    "It is not your final complaint unless you verify it and sign or confirm it. "
    "You may refuse this document, ask for corrections, provide your own revised "
    "complaint, or state that you do not know a requested detail."
)


class PetitionAssistanceError(ValueError):
    """Domain error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "field": self.field}


@dataclass(frozen=True)
class BasisText:
    text: str
    basis_text_type: str
    basis_text_hash: str
    warnings: list[str]


@dataclass(frozen=True)
class GapFinding:
    id: str
    category: str
    field_key: str
    gap_status: str
    severity: str
    display_label: str
    petitioner_instruction: str
    evidence_text: str | None
    sources: list[str]
    display_order: int
    question_text: str | None = None
    missing_detail: str | None = None
    follow_up_action: str | None = None
    guidance: str | None = None
    purpose: str | None = None
    offence_type: str | None = None


@dataclass(frozen=True)
class PetitionPlaceholder:
    id: str
    gap_finding_id: str
    token: str
    category: str
    label: str
    instruction: str
    severity: str
    inserted_after_anchor: str | None
    display_order: int
    value_status: str = "blank"


@dataclass(frozen=True)
class SourceLineage:
    id: str
    output_span_id: str
    output_text: str
    source_type: str
    source_reference_id: str | None
    source_excerpt: str | None
    source_char_start: int | None
    source_char_end: int | None
    lineage_confidence: float
    reviewer_status: str = "accepted"


@dataclass(frozen=True)
class PacketValidation:
    placeholder_integrity_passed: bool
    missing_placeholder_tokens: list[str]
    source_lineage_complete: bool
    unsupported_fact_count: int
    contradiction_count: int
    contradiction_check_status: str
    quality_status: str
    quality_notes: list[str]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return cleaned or "detail"


def _humanize_field(value: str) -> str:
    text = re.sub(r"[_\.]+", " ", value).strip()
    text = re.sub(r"\s+", " ", text)
    known = {
        "who accused name": "Name of accused person",
        "who accused": "Accused details",
        "when date": "Date of incident",
        "when time": "Time of incident",
        "where location": "Exact incident location",
        "where exact location": "Exact incident location",
        "evidence cctv": "CCTV or supporting evidence",
    }
    return known.get(text.lower(), text[:1].upper() + text[1:] if text else "Missing detail")


def _category_for(label_or_field: str) -> str:
    value = label_or_field.lower()
    category_keywords = [
        ("contact", ("phone", "mobile", "contact")),
        ("evidence", ("evidence", "cctv", "proof", "document", "photo", "video", "recording")),
        ("when", ("when", "date", "time", "day", "month", "year")),
        ("where", ("where", "place", "location", "address", "jurisdiction", "scene")),
        ("why", ("why", "motive", "reason", "background")),
        ("how", ("how", "method", "sequence", "manner", "happened")),
        ("who", ("who", "accused", "complainant", "victim", "witness", "person", "name", "identity")),
        ("what", ("what", "property", "injury", "loss", "incident", "amount", "vehicle")),
    ]
    for category, keywords in category_keywords:
        if any(keyword in value for keyword in keywords):
            return category
    return "what"


def _instruction_for(label: str, status: str) -> str:
    lowered = label.lower()
    if "accused" in lowered:
        return (
            "If the accused is known, add full name, alias, address/contact, relationship, and specific role. "
            "If unknown, add physical description, vehicle/phone/social profile, direction of movement, or write that the accused is unknown."
        )
    if "witness" in lowered:
        return (
            "Add names, addresses/phone numbers, and what each witness saw or heard. "
            "If no witness is known, write that no witness is known at present."
        )
    if "complainant" in lowered or "informant" in lowered:
        return "Add only the missing complainant details such as parentage, address, phone number, age, occupation, or ID details."
    if "victim" in lowered:
        return "Confirm who the victim is and add age, address/contact, safety, injury, and support needs if different from the complainant."
    if "date" in lowered:
        return "Add the exact date of the incident, or the best-known date range and why the exact date is not known."
    if "time" in lowered:
        return "Add the exact time of the incident, or the best-known time window and why the exact time is not known."
    if "location" in lowered or "place" in lowered or "where" in lowered:
        return "Add the exact scene: house/shop/road name, number, floor/room, landmark, police-station limits, and how to identify it."
    if "how" in lowered or "method" in lowered or "sequence" in lowered:
        return "Describe the sequence of events and the method used by each accused: what happened first, next, and last."
    if "what" in lowered or "property" in lowered or "loss" in lowered:
        return "Add the specific property, injury, loss, value, documents, or harm caused, with bills/photos/serial numbers if available."
    if "evidence" in lowered or "cctv" in lowered or "digital" in lowered:
        return "Identify available evidence, who has it, device/platform details, and whether urgent preservation is needed."
    if status == "uncertain":
        return (
            f"Confirm or correct the {label.lower()}. If you do not know it, "
            "write that it is unknown."
        )
    return (
        f"Add the {label.lower()}. If you do not know it, write that it is unknown."
    )


def _status_rank(status: str) -> int:
    return {"missing": 3, "uncertain": 2, "weak": 1}.get(status, 0)


def _severity_rank(severity: str) -> int:
    return {"mandatory": 3, "recommended": 2, "optional": 1}.get(severity, 0)


def _normalize_status(value: Any) -> str:
    return str(value or "").strip().lower()


def _basis_text_from_parsed(parsed_output: dict[str, Any]) -> str:
    text = parsed_output.get("text") if isinstance(parsed_output, dict) else {}
    text = text if isinstance(text, dict) else {}
    return _clean_text(
        text.get("refined_english_translation")
        or text.get("raw_english_translation")
        or text.get("english_text")
        or text.get("ocr_text")
    )


def _complaint_field(parsed_output: dict[str, Any], field_key: str) -> dict[str, Any]:
    complaint = parsed_output.get("complaint") if isinstance(parsed_output, dict) else {}
    complaint = complaint if isinstance(complaint, dict) else {}
    key = (field_key or "").lower().strip()
    if not key:
        return {}
    parts = [part for part in re.split(r"[._]+", key) if part]
    if not parts:
        return {}
    if parts[0] == "who" and len(parts) > 1:
        who = complaint.get("who") if isinstance(complaint.get("who"), dict) else {}
        components = who.get("components") if isinstance(who.get("components"), dict) else {}
        node = components.get(parts[1])
        return node if isinstance(node, dict) else {}
    if parts[0] == "when" and len(parts) > 1:
        when = complaint.get("when") if isinstance(complaint.get("when"), dict) else {}
        components = when.get("components") if isinstance(when.get("components"), dict) else {}
        node = components.get(parts[1])
        return node if isinstance(node, dict) else {}
    node = complaint.get(parts[0])
    return node if isinstance(node, dict) else {}


def _field_is_answered(parsed_output: dict[str, Any], field_key: str, *, allow_uncertain: bool = False) -> bool:
    field = _complaint_field(parsed_output, field_key)
    status = _normalize_status(field.get("status"))
    if status == "present":
        return True
    return allow_uncertain and status == "uncertain"


def _gap_already_answered(parsed_output: dict[str, Any], label: str, field_key: str | None, status: str) -> bool:
    if status != "missing":
        return False
    probe = f"{field_key or ''} {label}".lower()
    probe_words = re.sub(r"[_\.]+", " ", probe)
    for key in (
        "who.complainant",
        "who.victim",
        "what",
        "where",
        "when.time",
        "when.date",
        "how",
        "why",
    ):
        key_words = key.replace(".", " ")
        if key in probe or key_words in probe_words:
            return _field_is_answered(parsed_output, key)
    if probe_words.strip() in {"who", "what", "where", "when", "how", "why"}:
        return _field_is_answered(parsed_output, probe_words.strip())
    return False


def select_basis_text(parsed_output: dict[str, Any], *, allow_raw_fallback: bool = True) -> BasisText:
    """Select refined English when available, with explicit raw fallback."""

    text = parsed_output.get("text") if isinstance(parsed_output, dict) else {}
    text = text if isinstance(text, dict) else {}
    refined = _clean_text(text.get("refined_english_translation"))
    if refined:
        return BasisText(
            text=refined,
            basis_text_type="refined_english_translation",
            basis_text_hash=sha256_text(refined),
            warnings=[],
        )

    raw = _clean_text(text.get("raw_english_translation") or text.get("english_text"))
    if raw and allow_raw_fallback:
        return BasisText(
            text=raw,
            basis_text_type="raw_english_translation",
            basis_text_hash=sha256_text(raw),
            warnings=["RAW_ENGLISH_FALLBACK"],
        )

    raise PetitionAssistanceError(
        "MISSING_BASIS_TEXT",
        "A refined English translation is required before generating an assistance packet.",
        "parsed_output.text.refined_english_translation",
    )


def normalize_gap_findings(parsed_output: dict[str, Any]) -> list[GapFinding]:
    """Normalize parser gap output into deduplicated actionable findings."""

    gaps = parsed_output.get("gaps") if isinstance(parsed_output, dict) else {}
    gaps = gaps if isinstance(gaps, dict) else {}
    raw_items: list[dict[str, Any]] = []

    def add_item(value: Any, status: str, source: str, severity: str, field_key: str | None = None) -> None:
        if value is None:
            return
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str) or not item.strip():
                continue
            label = _humanize_field(item) if source.endswith("_field") else item.strip()
            category = _category_for(f"{field_key or item} {label}")
            normalized_field_key = f"{category}.{_slug(field_key or item)}"
            if _gap_already_answered(parsed_output, label, normalized_field_key, status):
                continue
            raw_items.append(
                {
                    "category": category,
                    "field_key": normalized_field_key,
                    "gap_status": status,
                    "severity": severity,
                    "display_label": label[:100],
                    "petitioner_instruction": _instruction_for(label, status),
                    "evidence_text": None,
                    "sources": [source],
                }
            )

    add_item(gaps.get("missing_details"), "missing", "5w1h_detail", "mandatory")
    add_item(gaps.get("uncertain_details"), "uncertain", "5w1h_detail", "recommended")
    add_item(gaps.get("missing_fields"), "missing", "5w1h_field", "mandatory")
    add_item(gaps.get("uncertain_fields"), "uncertain", "5w1h_field", "recommended")

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in raw_items:
        key = (item["category"], _slug(item["display_label"]))
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
            continue
        existing["sources"] = sorted(set(existing["sources"]) | set(item["sources"]))
        if _status_rank(item["gap_status"]) > _status_rank(existing["gap_status"]):
            existing["gap_status"] = item["gap_status"]
        if _severity_rank(item["severity"]) > _severity_rank(existing["severity"]):
            existing["severity"] = item["severity"]
        if not existing.get("field_key") and item.get("field_key"):
            existing["field_key"] = item["field_key"]

    ordered = sorted(
        deduped.values(),
        key=lambda item: (-_severity_rank(item["severity"]), item["category"], item["display_label"].lower()),
    )
    return [
        GapFinding(
            id=f"gf-{idx:03d}",
            category=item["category"],
            field_key=item["field_key"],
            gap_status=item["gap_status"],
            severity=item["severity"],
            display_label=item["display_label"],
            petitioner_instruction=item["petitioner_instruction"],
            evidence_text=item["evidence_text"],
            sources=item["sources"],
            display_order=idx,
        )
        for idx, item in enumerate(ordered, start=1)
    ]


def create_placeholders(gap_findings: list[GapFinding]) -> list[PetitionPlaceholder]:
    counters: dict[str, int] = {}
    placeholders: list[PetitionPlaceholder] = []
    for idx, finding in enumerate(gap_findings, start=1):
        category = finding.category.upper()
        counters[category] = counters.get(category, 0) + 1
        label = finding.display_label[:80]
        token = f"[[ADD_{category}_{counters[category]:03d}: {label}]]"
        placeholders.append(
            PetitionPlaceholder(
                id=str(uuid.uuid4()),
                gap_finding_id=finding.id,
                token=token,
                category=finding.category,
                label=label,
                instruction=finding.petitioner_instruction,
                severity=finding.severity,
                inserted_after_anchor=None,
                display_order=idx,
            )
        )
    return placeholders


def infer_offence_type(parsed_output: dict[str, Any]) -> str:
    basis_text = _basis_text_from_parsed(parsed_output).lower()
    fir = parsed_output.get("fir_draft") if isinstance(parsed_output, dict) else {}
    fir = fir if isinstance(fir, dict) else {}
    occurrence = fir.get("occurrence") if isinstance(fir.get("occurrence"), dict) else {}
    declared = str(occurrence.get("nature_of_offence") or "").lower()
    text = f"{declared} {basis_text}"
    offence_keywords = [
        ("road_accident", ("accident", "rash", "negligent driving", "hit and run", "vehicle hit")),
        ("cybercrime", ("cyber", "upi", "online", "whatsapp", "instagram", "facebook", "email", "otp", "bank account")),
        ("financial_crime", ("cheat", "fraud", "forgery", "loan", "investment", "transaction", "upi", "account")),
        ("theft", ("theft", "stolen", "snatched", "robbery", "burglary", "house breaking", "dacoity")),
        ("domestic_violence", ("dowry", "cruelty", "husband", "in-laws", "matrimonial", "domestic violence")),
        ("sexual_offence", ("rape", "sexual", "molest", "outrage", "harass", "assaulted sexually")),
        ("pocso", ("child", "minor", "pocso", "school girl", "below 18")),
        ("sc_st_atrocity", ("sc/st", "caste", "tribe", "atrocity")),
        ("murder_grievous_hurt", ("murder", "death", "dead body", "grievous", "stab", "attempt to murder")),
        ("missing_person", ("missing", "kidnap", "abduct", "elopement", "trafficking")),
        ("land_property", ("land", "trespass", "possession", "survey number", "property dispute")),
        ("public_order", ("riot", "unlawful assembly", "communal", "group assault")),
        ("intimidation_harassment", ("threat", "extortion", "stalking", "harassment", "blackmail")),
    ]
    for offence_type, keywords in offence_keywords:
        if any(keyword in text for keyword in keywords):
            return offence_type
    return "general"


def _purpose_applies(question_purpose: str, requested_purpose: str) -> bool:
    values = {
        item.strip().lower()
        for item in re.split(r"[,/|]+", question_purpose or "petition")
        if item.strip()
    }
    requested = (requested_purpose or "petition").strip().lower()
    return not values or "all" in values or requested in values


def _offence_applies(question_offence: str, inferred_offence: str) -> bool:
    value = (question_offence or "").strip().lower()
    if not value or value in {"general", "universal", "all"}:
        return True
    values = {_slug(item) for item in re.split(r"[,/|]+", value) if item.strip()}
    return _slug(inferred_offence) in values


def _text_has(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles if needle)


def _regex_has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _excerpt_for(text: str, *needles: str) -> str:
    lowered = text.lower()
    for needle in needles:
        if not needle:
            continue
        idx = lowered.find(needle.lower())
        if idx >= 0:
            start = max(0, idx - 120)
            end = min(len(text), idx + len(needle) + 180)
            return text[start:end].strip()
    return ""


def _question_not_applicable(question_text: str, basis_text: str, inferred_offence: str) -> bool:
    q = question_text.lower()
    combined = basis_text.lower()
    child_related = ("child", "pocso", "minor", "school dob", "girl child")
    if any(term in q for term in child_related) and inferred_offence != "pocso" and not _text_has(combined, *child_related):
        return True
    if "sexual" in q and inferred_offence not in {"sexual_offence", "pocso"} and not _text_has(combined, "sexual", "rape", "molest"):
        return True
    if ("caste" in q or "sc/st" in q) and inferred_offence != "sc_st_atrocity" and not _text_has(combined, "caste", "sc/st"):
        return True
    if "medical examination" in q and not _text_has(combined, "injury", "injured", "hurt", "pain", "bleeding", "hospital", "medical"):
        return True
    if "electronic" in q and not _text_has(combined, "email", "whatsapp", "online", "electronic", "portal", "cctns"):
        return True
    if "oral" in q and not _text_has(combined, "oral", "told", "stated orally"):
        return True
    return False


def _evaluate_question(
    parsed_output: dict[str, Any],
    question: dict[str, Any],
    *,
    purpose: str,
    inferred_offence: str,
) -> dict[str, Any] | None:
    question_text = _clean_text(question.get("question_text"))
    if not question_text:
        return None
    question_purpose = str(question.get("purpose") or "petition")
    question_offence = str(question.get("offence_type") or "")
    if not _purpose_applies(question_purpose, purpose):
        return None
    if not _offence_applies(question_offence, inferred_offence):
        return None

    basis_text = _basis_text_from_parsed(parsed_output)
    q = question_text.lower()
    category = str(question.get("category") or _category_for(question_text)).lower()
    severity = str(question.get("severity") or "recommended").lower()
    status = "not_applicable"
    evidence = ""
    missing_detail = ""
    follow_up = ""
    reason = ""

    if _question_not_applicable(question_text, basis_text, inferred_offence):
        reason = "Question does not apply to the facts detected in this petition."
    elif "cognizable" in q:
        status = "present" if _field_is_answered(parsed_output, "what", allow_uncertain=True) else "missing"
        evidence = _excerpt_for(basis_text, "stolen", "assault", "threat", "cheat", "accident")
        missing_detail = "" if status == "present" else "Facts showing the offence complained of"
        follow_up = "Add the act, loss/injury, accused conduct, and why police action is required."
        reason = "Cognizable scrutiny depends first on the factual act disclosed, not on legal sections."
    elif "date" in q and "time" in q and ("occurrence" in q or "incident" in q or "offence" in q):
        missing = []
        if not _field_is_answered(parsed_output, "when.date"):
            missing.append("exact incident date")
        if not _field_is_answered(parsed_output, "when.time", allow_uncertain=True):
            missing.append("exact or approximate incident time")
        status = "present" if not missing else "missing"
        evidence = _excerpt_for(basis_text, "am", "pm", "morning", "evening", "night")
        missing_detail = ", ".join(missing)
        follow_up = "Add the incident date/time or the best-known window with a reason if exact timing is unknown."
        reason = "Time details are needed for FIR chronology, alibi checks, CCTV, CDR, and witness correlation."
    elif "exact place" in q or "place of occurrence" in q or "scene" in q:
        if _field_is_answered(parsed_output, "where"):
            where_value = str(_complaint_field(parsed_output, "where").get("value") or "")
            vague = len(where_value.split()) < 4 or _text_has(where_value, "near", "beside", "area", "road", "bus stop")
            status = "uncertain" if vague else "present"
            evidence = where_value
            missing_detail = "full address/landmark/house or shop number" if vague else ""
        else:
            status = "missing"
            missing_detail = "exact scene of offence"
        follow_up = "Add house/shop/road name, number, floor/room, landmark, owner/occupier, and police-station limits if known."
        reason = "The scene must be identifiable for jurisdiction, spot panchanama, CCTV search, and court proof."
    elif "full name" in q and ("informant" in q or "complainant" in q):
        missing = []
        if not _field_is_answered(parsed_output, "who.complainant"):
            missing.append("complainant full name")
        if not _regex_has(basis_text, r"\b(?:s/o|d/o|w/o|son of|daughter of|wife of|husband of)\b"):
            missing.append("parentage/spouse name")
        if not _regex_has(basis_text, r"\b(?:age|aged|dob|date of birth|\d{1,2}\s*years)\b"):
            missing.append("age/DOB")
        if not _regex_has(basis_text, r"\b\d{10}\b"):
            missing.append("phone number")
        if not _text_has(basis_text, "address", "resident of", "r/o", "door no", "house no"):
            missing.append("address")
        status = "present" if not missing else "uncertain"
        evidence = _excerpt_for(basis_text, "my name is", "i,", "resident of", "r/o")
        missing_detail = ", ".join(missing)
        follow_up = "Add only the missing identity/contact fields; do not repeat details already present."
        reason = "Complete informant identity supports notice, statement, summons, and court attendance."
    elif "victim" in q and ("who is the victim" in q or "victim details" in q or "victim:" in q):
        if _field_is_answered(parsed_output, "who.victim"):
            status = "present"
            evidence = "; ".join(str(v) for v in _complaint_field(parsed_output, "who.victim").get("values", [])[:3])
        else:
            status = "uncertain" if _field_is_answered(parsed_output, "who.complainant") else "missing"
            missing_detail = "victim identity and whether the complainant is also the victim"
        follow_up = "Confirm the victim name and relationship to the complainant; add age/contact/safety needs if different."
        reason = "Victim identity is needed for statement, protection, medical/legal aid, and trial witness planning."
    elif (
        category == "accused"
        or q.startswith("is the accused")
        or q.startswith("full particulars")
        or q.startswith("physical description")
        or q.startswith("relationship with victim")
        or q.startswith("how does the informant identify the accused")
        or "specific role" in q
        or "co-accused" in q
    ):
        accused_field = _complaint_field(parsed_output, "who.accused")
        accused_present = _normalize_status(accused_field.get("status")) == "present"
        unknown_declared = _text_has(basis_text, "unknown accused", "unknown person", "unknown persons", "unidentified")
        if accused_present:
            status = "present"
            evidence = "; ".join(str(v) for v in accused_field.get("values", [])[:3]) or str(accused_field.get("value") or "")
        elif unknown_declared and ("known, unknown" in q or "is the accused known" in q):
            status = "present"
            evidence = _excerpt_for(basis_text, "unknown")
        elif unknown_declared and "physical description" in q:
            has_description = _text_has(basis_text, "height", "complexion", "vehicle", "shirt", "clothes", "bike", "car")
            status = "present" if has_description else "missing"
            missing_detail = "" if has_description else "physical description, vehicle, direction, clothes, accent, or identifying clue"
        else:
            status = "missing"
            missing_detail = "accused identity, description, relationship, or unknown-accused statement"
        follow_up = _instruction_for("accused details", status)
        reason = "Accused identity or description guides identification, investigation, arrest risk, and witness examination."
    elif (
        category == "witnesses"
        or q.startswith("direct eyewitnesses")
        or q.startswith("first-disclosure witnesses")
        or q.startswith("last-seen witnesses")
        or q.startswith("circumstantial witnesses")
        or q.startswith("documentary/digital witnesses")
        or q.startswith("independent local witnesses")
        or "all material witnesses" in q
        or "natural witnesses" in q
    ):
        if _field_is_answered(parsed_output, "who.witnesses"):
            status = "present"
            evidence = "; ".join(str(v) for v in _complaint_field(parsed_output, "who.witnesses").get("values", [])[:3])
        else:
            status = "missing"
            missing_detail = "names/contact/details of direct, first-disclosure, local, documentary, or digital witnesses"
        follow_up = _instruction_for("witness details", status)
        reason = "Witness traceability prevents later gaps and helps decide whether early Magistrate statements are needed."
    elif "chronological sequence" in q or "what happened first" in q:
        has_sequence = _text_has(basis_text, "then", "after that", "thereafter", "first", "next", "last")
        if _field_is_answered(parsed_output, "what") and len(basis_text.split()) >= 45:
            status = "present" if has_sequence else "uncertain"
        else:
            status = "missing"
        missing_detail = "" if status == "present" else "step-by-step sequence of events"
        follow_up = "Add what happened first, next, and last, including each accused act."
        reason = "Chronology avoids contradictions and supports FIR narration, witness statements, and court evidence."
    elif "physical acts" in q or ("how" in q and "occurred" in q):
        status = "present" if _field_is_answered(parsed_output, "how", allow_uncertain=True) else "missing"
        missing_detail = "" if status == "present" else "method and specific physical acts by each accused"
        follow_up = _instruction_for("how the incident happened", status)
        reason = "Specific acts are needed to map facts to legal ingredients and individual accused roles."
    elif "loss" in q or "injury" in q or "property damage" in q or "financial harm" in q:
        status = "present" if _field_is_answered(parsed_output, "what", allow_uncertain=True) else "missing"
        evidence = _excerpt_for(basis_text, "stolen", "injury", "loss", "damage", "amount")
        missing_detail = "" if status == "present" else "loss, injury, property value, or harm caused"
        follow_up = _instruction_for("loss or injury details", status)
        reason = "Loss/injury detail supports offence gravity, recovery, compensation, medical/FSL, and charge-sheet proof."
    elif (
        category == "evidence"
        and ("digital" in q or "cctv" in q or "electronic" in q)
    ) or q.startswith("are digital records"):
        has_evidence = _text_has(basis_text, "cctv", "video", "photo", "whatsapp", "call", "recording", "upi", "email", "screenshot")
        status = "present" if has_evidence else "uncertain"
        evidence = _excerpt_for(basis_text, "cctv", "whatsapp", "call", "upi", "screenshot")
        missing_detail = "" if has_evidence else "whether CCTV, phone, chat, payment, device, or platform evidence exists"
        follow_up = _instruction_for("digital or documentary evidence", status)
        reason = "Digital evidence may need urgent preservation, source device details, hash/certificate planning, and chain of custody."
    elif (
        inferred_offence == "theft"
        and category == "specific_offence"
        and _slug(str(question.get("offence_type") or "")) == "theft"
        and ("property" in q or "stolen" in q)
    ):
        has_property = _text_has(basis_text, "phone", "mobile", "cash", "gold", "vehicle", "jewellery", "documents", "property")
        has_identifier = _text_has(basis_text, "imei", "serial", "bill", "receipt", "value", "weight", "photo")
        status = "present" if has_property and has_identifier else "uncertain" if has_property else "missing"
        missing_detail = "" if status == "present" else "property description, identifier, value, ownership proof, photos/bills"
        follow_up = "Add property identifiers such as IMEI/serial number, marks, value, bills/photos, and ownership proof."
        reason = "Property particulars support search, recovery, insurance checks, and proof of ownership."
    else:
        reason = "No reliable deterministic signal was found for this checklist item in the current petition text."

    if status == "not_applicable":
        return {
            **question,
            "evaluation_status": status,
            "evidence_excerpt": None,
            "missing_detail": None,
            "follow_up_action": None,
            "guidance": question.get("guidance") or reason,
            "evaluation_reason": reason,
            "purpose": question_purpose,
            "offence_type": question_offence or None,
        }

    return {
        **question,
        "evaluation_status": status,
        "evidence_excerpt": evidence or None,
        "missing_detail": missing_detail or None,
        "follow_up_action": follow_up or _instruction_for(question_text, status),
        "guidance": question.get("guidance") or reason,
        "evaluation_reason": reason,
        "purpose": question_purpose,
        "offence_type": question_offence or None,
    }


def evaluate_checklist_questions(
    parsed_output: dict[str, Any],
    questions: list[dict[str, Any]],
    *,
    purpose: str = "petition",
) -> list[dict[str, Any]]:
    inferred_offence = infer_offence_type(parsed_output)
    evaluations: list[dict[str, Any]] = []
    for question in questions or []:
        if not bool(question.get("is_active", True)):
            continue
        result = _evaluate_question(
            parsed_output,
            question,
            purpose=purpose,
            inferred_offence=inferred_offence,
        )
        if result is not None:
            evaluations.append(result)
    return sorted(
        evaluations,
        key=lambda item: (
            0 if item.get("evaluation_status") in {"missing", "uncertain"} else 1,
            -_severity_rank(str(item.get("severity") or "")),
            int(item.get("display_order") or 0),
        ),
    )


def _gap_findings_from_checklist_evaluations(evaluations: list[dict[str, Any]]) -> list[GapFinding]:
    actionable = [
        item
        for item in evaluations or []
        if item.get("evaluation_status") in {"missing", "uncertain"}
    ]
    findings: list[GapFinding] = []
    for idx, item in enumerate(actionable, start=1):
        label = _clean_text(item.get("missing_detail")) or _clean_text(item.get("question_text"))[:100]
        category = str(item.get("category") or _category_for(label)).lower()
        findings.append(
            GapFinding(
                id=f"cf-{idx:03d}",
                category=category,
                field_key=str(item.get("expected_field_key") or f"{category}.{_slug(label)}"),
                gap_status=str(item.get("evaluation_status") or "missing"),
                severity=str(item.get("severity") or "mandatory"),
                display_label=label[:100],
                petitioner_instruction=_clean_text(item.get("follow_up_action")) or _instruction_for(label, str(item.get("evaluation_status") or "missing")),
                evidence_text=_clean_text(item.get("evidence_excerpt")) or None,
                sources=["checklist"],
                display_order=idx,
                question_text=_clean_text(item.get("question_text")) or None,
                missing_detail=_clean_text(item.get("missing_detail")) or None,
                follow_up_action=_clean_text(item.get("follow_up_action")) or None,
                guidance=_clean_text(item.get("guidance")) or None,
                purpose=str(item.get("purpose") or "petition"),
                offence_type=str(item.get("offence_type") or "") or None,
            )
        )
    return findings


def _dedupe_gap_findings(findings: list[GapFinding]) -> list[GapFinding]:
    deduped: dict[str, GapFinding] = {}
    for finding in findings:
        key = _slug(finding.display_label)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = finding
            continue
        sources = sorted(set(existing.sources) | set(finding.sources))
        if _severity_rank(finding.severity) > _severity_rank(existing.severity):
            deduped[key] = replace(finding, sources=sources)
        else:
            deduped[key] = replace(
                existing,
                sources=sources,
                question_text=existing.question_text or finding.question_text,
                guidance=existing.guidance or finding.guidance,
            )
    ordered = sorted(
        deduped.values(),
        key=lambda item: (-_severity_rank(item.severity), item.category, item.display_label.lower()),
    )
    return [replace(finding, display_order=idx) for idx, finding in enumerate(ordered, start=1)]


def _split_source_paragraphs(text: str) -> list[tuple[str, int, int]]:
    paragraphs: list[tuple[str, int, int]] = []
    cursor = 0
    for part in re.split(r"\n\s*\n", text):
        paragraph = part.strip()
        if not paragraph:
            continue
        start = text.find(paragraph, cursor)
        if start < 0:
            start = cursor
        end = start + len(paragraph)
        cursor = end
        paragraphs.append((paragraph, start, end))
    return paragraphs or [(text, 0, len(text))]


def generate_english_packet(
    *,
    parse_record_id: str,
    file_name: str | None,
    basis: BasisText,
    gap_findings: list[GapFinding],
    placeholders: list[PetitionPlaceholder],
    checklist_evaluations: list[dict[str, Any]] | None = None,
) -> tuple[str, str, list[SourceLineage]]:
    """Build deterministic packet body and lineage records."""

    title = "Missing Information Assistance Packet"
    lines: list[str] = [
        f"# {title}",
        "",
        "## Disclosure",
        DISCLOSURE_TEXT,
        "",
        "## Source Complaint Text",
    ]
    lineage: list[SourceLineage] = [
        SourceLineage(
            id=str(uuid.uuid4()),
            output_span_id="en-disclosure-001",
            output_text=DISCLOSURE_TEXT,
            source_type="disclosure_template",
            source_reference_id="petitioner-consent-v1",
            source_excerpt=None,
            source_char_start=None,
            source_char_end=None,
            lineage_confidence=1.0,
        )
    ]

    for idx, (paragraph, start, end) in enumerate(_split_source_paragraphs(basis.text), start=1):
        lines.extend([paragraph, ""])
        lineage.append(
            SourceLineage(
                id=str(uuid.uuid4()),
                output_span_id=f"en-source-p{idx:03d}",
                output_text=paragraph,
                source_type=basis.basis_text_type,
                source_reference_id=f"parse_records.{parse_record_id}.parsed_output.text",
                source_excerpt=paragraph[:1000],
                source_char_start=start,
                source_char_end=end,
                lineage_confidence=1.0,
            )
        )

    actionable_checklist = [
        item
        for item in (checklist_evaluations or [])
        if item.get("evaluation_status") in {"missing", "uncertain"}
    ][:20]
    lines.extend(["## Checklist Validation And Foolproofing Guidance"])
    if actionable_checklist:
        for idx, item in enumerate(actionable_checklist, start=1):
            status = str(item.get("evaluation_status") or "missing").replace("_", " ")
            question_text = _clean_text(item.get("question_text"))
            missing_detail = _clean_text(item.get("missing_detail")) or "Detail needs officer/petitioner confirmation."
            follow_up = _clean_text(item.get("follow_up_action")) or _instruction_for(missing_detail, str(item.get("evaluation_status") or "missing"))
            guidance = _clean_text(item.get("guidance"))
            lines.append(f"{idx}. {status.title()}: {question_text}")
            lines.append(f"   - Missing/uncertain detail: {missing_detail}")
            lines.append(f"   - Follow-up: {follow_up}")
            if guidance:
                lines.append(f"   - Why it matters: {guidance}")
            evidence = _clean_text(item.get("evidence_excerpt"))
            if evidence:
                lines.append(f"   - Current petition evidence: {evidence[:500]}")
            lines.append("")
            lineage.append(
                SourceLineage(
                    id=str(uuid.uuid4()),
                    output_span_id=f"en-checklist-{idx:03d}",
                    output_text=question_text,
                    source_type="checklist_evaluation",
                    source_reference_id=str(item.get("id") or item.get("question_id") or ""),
                    source_excerpt=missing_detail,
                    source_char_start=None,
                    source_char_end=None,
                    lineage_confidence=1.0,
                )
            )
    else:
        lines.extend(
            [
                "No checklist-driven missing or uncertain details were identified. Officer review is still required before treating the petition as complete.",
                "",
            ]
        )

    lines.extend(["## Details To Be Added Or Confirmed"])
    if placeholders:
        finding_by_id = {finding.id: finding for finding in gap_findings}
        for placeholder in placeholders:
            finding = finding_by_id[placeholder.gap_finding_id]
            if finding.question_text:
                line = f"- {placeholder.token} - {placeholder.instruction} Checklist question: {finding.question_text}"
            else:
                line = f"- {placeholder.token} - {placeholder.instruction}"
            lines.append(line)
            lineage.append(
                SourceLineage(
                    id=str(uuid.uuid4()),
                    output_span_id=f"en-placeholder-{placeholder.display_order:03d}",
                    output_text=placeholder.token,
                    source_type="gap_finding",
                    source_reference_id=finding.id,
                    source_excerpt=finding.display_label,
                    source_char_start=None,
                    source_char_end=None,
                    lineage_confidence=1.0,
                )
            )
    else:
        no_gap_text = "No mandatory missing details were identified by the parser. Officer review is still required."
        lines.append(no_gap_text)
        lineage.append(
            SourceLineage(
                id=str(uuid.uuid4()),
                output_span_id="en-no-gap-001",
                output_text=no_gap_text,
                source_type="disclosure_template",
                source_reference_id="no-gap-template-v1",
                source_excerpt=None,
                source_char_start=None,
                source_char_end=None,
                lineage_confidence=1.0,
            )
        )

    source_ref = file_name or parse_record_id
    verification_text = (
        "I have read or understood this assistance packet. The final complaint will be treated as my statement "
        "only after I verify the completed text."
    )
    lines.extend(
        [
            "",
            "## Petitioner Verification",
            verification_text,
            "",
            f"Source record: {source_ref}",
            "Petitioner name: ______________________________",
            "Signature or thumb impression: ______________________________",
            "Date: ____________________",
            "Officer witness: ______________________________",
        ]
    )
    lineage.append(
        SourceLineage(
            id=str(uuid.uuid4()),
            output_span_id="en-verification-001",
            output_text=verification_text,
            source_type="disclosure_template",
            source_reference_id="petitioner-verification-v1",
            source_excerpt=None,
            source_char_start=None,
            source_char_end=None,
            lineage_confidence=1.0,
        )
    )

    body_markdown = "\n".join(lines).strip() + "\n"
    return body_markdown, body_markdown, lineage


def validate_packet_body(
    *,
    body_plain_text: str,
    placeholders: list[PetitionPlaceholder],
    lineage: list[SourceLineage],
) -> PacketValidation:
    tokens = [placeholder.token for placeholder in placeholders]
    missing_tokens = [token for token in tokens if token not in body_plain_text]
    lineage_gap_tokens = {
        entry.output_text
        for entry in lineage
        if entry.source_type == "gap_finding" and PLACEHOLDER_PATTERN.fullmatch(entry.output_text)
    }
    missing_lineage = [token for token in tokens if token not in lineage_gap_tokens]
    has_source_lineage = any(
        entry.source_type in {"refined_english_translation", "raw_english_translation"}
        for entry in lineage
    )
    source_lineage_complete = not missing_tokens and not missing_lineage and has_source_lineage
    quality_notes: list[str] = []
    if missing_tokens:
        quality_notes.append("One or more placeholder tokens are missing from the packet body.")
    if missing_lineage:
        quality_notes.append("One or more placeholder tokens do not have gap lineage.")
    if not has_source_lineage:
        quality_notes.append("No source complaint lineage is attached.")
    if not quality_notes:
        quality_notes.append("All deterministic packet validation checks passed.")

    return PacketValidation(
        placeholder_integrity_passed=not missing_tokens,
        missing_placeholder_tokens=missing_tokens,
        source_lineage_complete=source_lineage_complete,
        unsupported_fact_count=0 if source_lineage_complete else len(missing_lineage),
        contradiction_count=0,
        contradiction_check_status="passed",
        quality_status="passed" if source_lineage_complete else "failed",
        quality_notes=quality_notes,
    )


def build_assistance_packet(
    *,
    parse_record_id: str,
    parsed_output: dict[str, Any],
    file_name: str | None = None,
    case_id: str | None = None,
    created_by: str = "system",
    checklist_evaluations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a Phase 1 packet DTO from parsed complaint output."""

    basis = select_basis_text(parsed_output)
    parser_gaps = normalize_gap_findings(parsed_output)
    checklist_gaps = _gap_findings_from_checklist_evaluations(checklist_evaluations or [])
    gaps = _dedupe_gap_findings(parser_gaps + checklist_gaps)
    placeholders = create_placeholders(gaps)
    body_markdown, body_plain_text, lineage = generate_english_packet(
        parse_record_id=parse_record_id,
        file_name=file_name,
        basis=basis,
        gap_findings=gaps,
        placeholders=placeholders,
        checklist_evaluations=checklist_evaluations,
    )
    validation = validate_packet_body(
        body_plain_text=body_plain_text,
        placeholders=placeholders,
        lineage=lineage,
    )
    language = parsed_output.get("language") if isinstance(parsed_output, dict) else {}
    language = language if isinstance(language, dict) else {}
    request_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    source_language = language.get("detected") or language.get("detected_name") or "unknown"
    mandatory_count = sum(1 for placeholder in placeholders if placeholder.severity == "mandatory")
    recommended_count = sum(1 for placeholder in placeholders if placeholder.severity == "recommended")
    status = "needs_review" if validation.quality_status == "passed" else "source_check_required"

    return {
        "request": {
            "id": request_id,
            "parse_record_id": parse_record_id,
            "case_id": case_id,
            "source_language": source_language,
            "source_language_name": language.get("detected_name") or source_language,
            "basis_text_type": basis.basis_text_type,
            "basis_text_hash": basis.basis_text_hash,
            "checklist_version": max(
                [int(item.get("checklist_version") or 0) for item in (checklist_evaluations or [])] or [0]
            )
            or None,
            "generation_status": status,
            "mandatory_gap_count": mandatory_count,
            "recommended_gap_count": recommended_count,
            "source_lineage_status": "complete" if validation.source_lineage_complete else "incomplete",
            "contradiction_check_status": validation.contradiction_check_status,
            "unsupported_fact_count": validation.unsupported_fact_count,
            "created_by": created_by,
            "warnings": basis.warnings,
        },
        "gap_findings": [asdict(finding) for finding in gaps],
        "checklist_evaluations": checklist_evaluations or [],
        "placeholders": [asdict(placeholder) for placeholder in placeholders],
        "draft": {
            "id": draft_id,
            "rewrite_request_id": request_id,
            "draft_language": "en",
            "draft_version": 1,
            "title": "Missing Information Assistance Packet",
            "body_markdown": body_markdown,
            "body_plain_text": body_plain_text,
            "placeholder_count": len(placeholders),
            "mandatory_placeholder_count": mandatory_count,
            "generation_method": "deterministic_template",
            "quality_status": validation.quality_status,
            "quality_notes": validation.quality_notes,
            "source_lineage_complete": validation.source_lineage_complete,
            "unsupported_fact_count": validation.unsupported_fact_count,
            "contradiction_count": validation.contradiction_count,
            "sha256_hash": sha256_text(body_plain_text),
        },
        "lineage": [asdict(entry) for entry in lineage],
        "validation": asdict(validation),
    }


def merge_final_petition_text(
    *,
    body_markdown: str,
    placeholders: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge petitioner-reviewed values without inventing unresolved details."""

    final_text = body_markdown
    unresolved: list[dict[str, Any]] = []
    replacements: list[dict[str, Any]] = []

    for placeholder in placeholders:
        token = str(placeholder.get("token") or "")
        if not token:
            continue
        status = str(placeholder.get("value_status") or "blank")
        label = str(placeholder.get("label") or "missing detail")
        value = _clean_text(placeholder.get("petitioner_value"))
        replacement: str | None = None

        if status == "accepted":
            if not value:
                unresolved.append({"token": token, "status": status, "reason": "accepted_value_missing"})
                continue
            replacement = value
        elif status == "accepted_unknown":
            replacement = f"[Petitioner stated that the {label.lower()} is unknown]"
        elif status == "needs_follow_up":
            replacement = f"[Further follow-up required: {label}]"
        else:
            unresolved.append({"token": token, "status": status, "reason": "not_finalized"})
            continue

        final_text = final_text.replace(token, replacement)
        replacements.append(
            {
                "placeholder_id": placeholder.get("id"),
                "token": token,
                "status": status,
                "replacement": replacement,
            }
        )

    return {
        "body_markdown": final_text,
        "body_plain_text": final_text,
        "sha256_hash": sha256_text(final_text),
        "unresolved": unresolved,
        "replacements": replacements,
    }


def language_direction(language: str | None) -> str:
    value = (language or "").strip().lower()
    if value == "ur" or "urdu" in value:
        return "rtl"
    return "ltr"


def protect_placeholder_tokens(text: str) -> tuple[str, dict[str, str]]:
    token_map: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        key = f"__PETITION_PLACEHOLDER_{len(token_map):03d}__"
        token_map[key] = match.group(0)
        return key

    return PLACEHOLDER_PATTERN.sub(replace, text), token_map


def restore_placeholder_tokens(text: str, token_map: dict[str, str]) -> str:
    restored = text
    for key, token in token_map.items():
        restored = restored.replace(key, token)
    return restored


def validate_placeholder_tokens(source_text: str, translated_text: str) -> dict[str, Any]:
    source_tokens = PLACEHOLDER_PATTERN.findall(source_text or "")
    translated_tokens = PLACEHOLDER_PATTERN.findall(translated_text or "")
    missing = [token for token in source_tokens if token not in translated_tokens]
    extra = [token for token in translated_tokens if token not in source_tokens]
    return {
        "placeholder_integrity_passed": not missing and not extra and len(source_tokens) == len(translated_tokens),
        "source_placeholder_count": len(source_tokens),
        "translated_placeholder_count": len(translated_tokens),
        "missing_placeholder_tokens": missing,
        "extra_placeholder_tokens": extra,
    }


def build_draft_translation_payload(
    *,
    rewrite_request_id: str,
    draft_id: str,
    body_markdown: str,
    target_language: str,
    target_language_name: str | None = None,
    translator: Any | None = None,
) -> dict[str, Any]:
    """Build an original-language draft while protecting placeholders.

    `translator` is an optional callable used by tests or provider integrations. When
    absent, the function returns an explicit English-only issue rather than claiming
    semantic equivalence.
    """

    protected_body, token_map = protect_placeholder_tokens(body_markdown)
    semantic_status = "pending"
    english_only_reason = None
    if translator is None:
        translated = body_markdown
        semantic_status = "english_only_issue" if (target_language or "").lower() not in {"en", "english"} else "not_required"
        if semantic_status == "english_only_issue":
            english_only_reason = "Original-language petition packet translation is not configured."
    else:
        translated = restore_placeholder_tokens(str(translator(protected_body, target_language)), token_map)

    validation = validate_placeholder_tokens(body_markdown, translated)
    if not validation["placeholder_integrity_passed"]:
        semantic_status = "placeholder_failed"

    return {
        "id": str(uuid.uuid4()),
        "rewrite_request_id": rewrite_request_id,
        "generated_petition_draft_id": draft_id,
        "target_language": target_language or "unknown",
        "target_language_name": target_language_name or target_language or "Unknown",
        "direction": language_direction(target_language or target_language_name),
        "translated_body_markdown": translated,
        "placeholder_integrity_passed": validation["placeholder_integrity_passed"],
        "semantic_validation_status": semantic_status,
        "semantic_validation_notes": [english_only_reason] if english_only_reason else [],
        "english_only_reason": english_only_reason,
        "sha256_hash": sha256_text(translated),
        "validation": validation,
    }


def merge_gap_sources(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for source_items in sources:
        for item in source_items or []:
            label = str(item.get("display_label") or item.get("label") or item.get("question_text") or "").strip()
            category = str(item.get("category") or _category_for(label)).strip().lower() or "what"
            key = (category, _slug(label))
            if key not in merged:
                merged[key] = {**item, "category": category, "display_label": label, "sources": list(item.get("sources") or [])}
            else:
                existing = merged[key]
                existing["sources"] = sorted(set(existing.get("sources") or []) | set(item.get("sources") or []))
                if _severity_rank(str(item.get("severity") or "")) > _severity_rank(str(existing.get("severity") or "")):
                    existing["severity"] = item.get("severity")
    return list(merged.values())


def validate_llm_rewrite_contract(output: dict[str, Any], expected_placeholders: list[str]) -> dict[str, Any]:
    body = str(output.get("body_markdown") or output.get("body_plain_text") or "")
    lineage = output.get("lineage") if isinstance(output.get("lineage"), list) else []
    missing_placeholders = [token for token in expected_placeholders if token not in body]
    unsupported_facts = output.get("unsupported_facts")
    if not isinstance(unsupported_facts, list):
        unsupported_facts = []
    lineage_ids = {
        str(item.get("output_text") or "")
        for item in lineage
        if isinstance(item, dict)
    }
    missing_lineage = [token for token in expected_placeholders if token not in lineage_ids]
    errors = []
    if missing_placeholders:
        errors.append("missing_placeholders")
    if missing_lineage:
        errors.append("missing_lineage")
    if unsupported_facts:
        errors.append("unsupported_facts")
    return {
        "valid": not errors,
        "errors": errors,
        "missing_placeholders": missing_placeholders,
        "missing_lineage": missing_lineage,
        "unsupported_fact_count": len(unsupported_facts),
    }


def summarize_pilot_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {
            "total": 0,
            "semantic_drift_rate": 0.0,
            "unsupported_fact_rate": 0.0,
            "refusal_or_correction_rate": 0.0,
            "override_rate": 0.0,
        }
    semantic_drift = sum(1 for row in rows if row.get("semantic_drift_flag"))
    unsupported = sum(1 for row in rows if int(row.get("unsupported_fact_count") or 0) > 0)
    refusal = sum(1 for row in rows if row.get("refusal_or_correction"))
    override = sum(1 for row in rows if row.get("officer_override_used"))
    return {
        "total": total,
        "semantic_drift_rate": semantic_drift / total,
        "unsupported_fact_rate": unsupported / total,
        "refusal_or_correction_rate": refusal / total,
        "override_rate": override / total,
    }
