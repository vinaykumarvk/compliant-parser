from __future__ import annotations

import re
from typing import Any


_BNS_CODE_RE = re.compile(r"^BNS-\d+[A-Z]?(?:\([0-9A-Za-z]+\))*$")


BNS_MAPPING_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "bns_mapping_result",
    "description": "Schema-valid BNS legal section mapping result with source citations.",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "primary_sections": {
                "type": "array",
                "items": {"$ref": "#/$defs/section_mapping"},
            },
            "alternative_sections": {
                "type": "array",
                "items": {"$ref": "#/$defs/section_mapping"},
            },
            "hidden_below_threshold": {"type": "integer"},
        },
        "required": ["primary_sections", "alternative_sections", "hidden_below_threshold"],
        "$defs": {
            "section_mapping": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section_code": {"type": "string", "pattern": _BNS_CODE_RE.pattern},
                    "section_title": {"type": "string"},
                    "act_name": {"type": "string"},
                    "confidence_score": {"type": "number"},
                    "legal_reasoning": {"type": "string"},
                    "supporting_ingredients": {"type": "array", "items": {"type": "string"}},
                    "missing_ingredients": {"type": "array", "items": {"type": "string"}},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "source": {"type": "string"},
                                "title": {"type": "string"},
                                "reference_id": {"type": "string"},
                            },
                            "required": ["source", "title", "reference_id"],
                        },
                    },
                },
                "required": [
                    "section_code",
                    "section_title",
                    "act_name",
                    "confidence_score",
                    "legal_reasoning",
                    "supporting_ingredients",
                    "missing_ingredients",
                    "citations",
                ],
            }
        },
    },
}


def bns_recommendations(complaint_text: str, context_results: list[dict[str, Any]]) -> dict[str, Any]:
    text = f"{complaint_text} " + " ".join(result.get("text", "") for result in context_results)
    lowered = text.lower()
    recommendations: list[dict[str, Any]] = []
    if any(term in lowered for term in ["theft", "stolen", "steal", "dishonest taking"]):
        citation = next((result.get("citation") for result in context_results if result.get("citation")), {})
        recommendations.append(
            {
                "section_code": "BNS-303",
                "section_title": "Theft",
                "act_name": "BNS",
                "confidence_score": 0.86,
                "legal_reasoning": "Complaint facts indicate dishonest taking or stolen movable property.",
                "supporting_ingredients": ["dishonest taking", "movable property"],
                "missing_ingredients": [],
                "citations": [citation] if citation else [],
            }
        )
    return {
        "primary_sections": recommendations,
        "alternative_sections": [],
        "hidden_below_threshold": 0,
    }


def validate_bns_mapping_result(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise ValueError("BNS mapping result must be an object.")
    required_root = {"primary_sections", "alternative_sections"}
    missing_root = required_root - set(result)
    if missing_root:
        raise ValueError(f"BNS mapping result is missing root fields: {sorted(missing_root)}")
    if not isinstance(result["primary_sections"], list):
        raise ValueError("BNS mapping primary_sections must be a list.")
    if not isinstance(result["alternative_sections"], list):
        raise ValueError("BNS mapping alternative_sections must be a list.")
    for item in result["primary_sections"]:
        if not isinstance(item, dict):
            raise ValueError("BNS mapping section entries must be objects.")
        required = {"section_code", "section_title", "act_name", "confidence_score", "legal_reasoning", "citations"}
        missing = required - set(item)
        if missing:
            raise ValueError(f"BNS mapping result is missing fields: {sorted(missing)}")
        if not _BNS_CODE_RE.match(str(item["section_code"])):
            raise ValueError("BNS mapping section_code must use a canonical code such as BNS-303.")
        if not isinstance(item["citations"], list):
            raise ValueError("BNS mapping citations must be a list.")


def is_schema_valid_bns_mapping(result: dict[str, Any]) -> bool:
    try:
        validate_bns_mapping_result(result)
        return True
    except (TypeError, ValueError):
        return False


def coerce_bns_mapping_result(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    if is_schema_valid_bns_mapping(result):
        return result

    if not any(key in result for key in ("primary_sections", "section_mappings", "sections")):
        return None
    raw_sections = result.get("primary_sections")
    if not isinstance(raw_sections, list):
        raw_sections = result.get("section_mappings") or result.get("sections") or []
    if not isinstance(raw_sections, list):
        return None

    primary_sections = [_coerce_section_mapping(item) for item in raw_sections]
    primary_sections = [item for item in primary_sections if item is not None]
    alternative_sections = result.get("alternative_sections")
    if not isinstance(alternative_sections, list):
        alternative_sections = []
    coerced = {
        "primary_sections": primary_sections,
        "alternative_sections": [
            item for item in (_coerce_section_mapping(item) for item in alternative_sections) if item is not None
        ],
        "hidden_below_threshold": int(result.get("hidden_below_threshold") or 0),
    }
    return coerced if is_schema_valid_bns_mapping(coerced) else None


def _coerce_section_mapping(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    section_code = item.get("section_code") or item.get("section") or item.get("section_number") or item.get("code")
    if section_code is None:
        return None
    section_code = _normalize_section_code(section_code)
    if section_code is None:
        return None
    if section_code.isdigit():
        section_code = f"BNS-{section_code}"
    confidence = item.get("confidence_score", item.get("confidence", 0.0))
    try:
        confidence_score = float(confidence)
    except (TypeError, ValueError):
        confidence_score = 0.0
    citations = item.get("citations") if isinstance(item.get("citations"), list) else []
    return {
        "section_code": section_code,
        "section_title": str(item.get("section_title") or item.get("title") or item.get("offence") or section_code),
        "act_name": str(item.get("act_name") or item.get("act") or "BNS"),
        "confidence_score": confidence_score,
        "legal_reasoning": str(item.get("legal_reasoning") or item.get("reasoning") or item.get("rationale") or ""),
        "supporting_ingredients": _string_list(item.get("supporting_ingredients") or item.get("ingredients")),
        "missing_ingredients": _string_list(item.get("missing_ingredients")),
        "citations": citations,
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_section_code(value: Any) -> str | None:
    raw = str(value).strip().upper()
    if not raw:
        return None
    if raw.isdigit():
        return f"BNS-{raw}"
    match = re.search(r"\bBNS\D{0,12}(\d+[A-Z]?(?:\([0-9A-Z]+\))*)", raw)
    if match:
        return f"BNS-{match.group(1)}"
    return raw
