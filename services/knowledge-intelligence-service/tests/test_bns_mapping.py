from __future__ import annotations

from src.reasoning.bns_mapping import (
    BNS_MAPPING_RESPONSE_SCHEMA,
    bns_recommendations,
    coerce_bns_mapping_result,
    is_schema_valid_bns_mapping,
    validate_bns_mapping_result,
)


def test_bns_mapping_returns_cited_section_recommendation() -> None:
    result = bns_recommendations(
        "Vehicle was stolen from the parking area.",
        [{"text": "BNS-303 covers theft.", "citation": {"title": "BNS"}}],
    )

    validate_bns_mapping_result(result)
    assert result["primary_sections"][0]["section_code"] == "BNS-303"
    assert result["primary_sections"][0]["citations"] == [{"title": "BNS"}]


def test_invalid_llm_bns_mapping_shape_is_rejected_without_type_error() -> None:
    result = {"primary_sections": [303], "alternative_sections": []}

    assert is_schema_valid_bns_mapping(result) is False


def test_incomplete_llm_bns_mapping_shape_is_rejected() -> None:
    result = {"section_mappings": []}

    assert is_schema_valid_bns_mapping(result) is False


def test_legacy_llm_section_mappings_are_coerced_to_bns_schema() -> None:
    result = coerce_bns_mapping_result(
        {
            "section_mappings": [
                {
                    "section_number": 303,
                    "title": "Theft",
                    "confidence": "0.7",
                    "reasoning": "Dishonest taking is present.",
                    "citations": [{"title": "BNS"}],
                }
            ]
        }
    )

    assert result is not None
    assert result["primary_sections"][0]["section_code"] == "BNS-303"
    assert result["primary_sections"][0]["confidence_score"] == 0.7


def test_bns_mapping_response_schema_is_strict_json_schema() -> None:
    schema = BNS_MAPPING_RESPONSE_SCHEMA["schema"]

    assert BNS_MAPPING_RESPONSE_SCHEMA["name"] == "bns_mapping_result"
    assert BNS_MAPPING_RESPONSE_SCHEMA["strict"] is True
    assert schema["additionalProperties"] is False
    assert "primary_sections" in schema["required"]


def test_generic_llm_section_code_is_rejected() -> None:
    result = {
        "primary_sections": [
            {
                "section_code": "BNS Section - Theft (Generic)",
                "section_title": "Theft",
                "act_name": "BNS",
                "confidence_score": 0.8,
                "legal_reasoning": "The facts indicate theft.",
                "citations": [],
            }
        ],
        "alternative_sections": [],
        "hidden_below_threshold": 0,
    }

    assert is_schema_valid_bns_mapping(result) is False
