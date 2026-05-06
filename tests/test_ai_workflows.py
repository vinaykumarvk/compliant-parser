from __future__ import annotations

from typing import Any

import kis_client
from ai_workflows import _kis_section_to_bns_payload, recommend_sections_from_text


def test_section_recommendation_prefers_kis_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("IQW_KIS_ENABLED", "true")
    monkeypatch.setenv("IQW_KIS_BASE_URL", "http://kis.local")
    monkeypatch.setenv("IQW_KIS_API_KEY", "secret-key")
    monkeypatch.setenv("IQW_KIS_DOMAIN", "police-iqw")
    monkeypatch.setenv("IQW_KIS_KB", "kb-1")

    def fake_bns_mapping(self: kis_client.KISClient, complaint_text: str) -> dict[str, Any]:
        return {
            "id": "rrun_1",
            "status": "completed",
            "context_summary": {"snapshot_id": "snap_1"},
            "llm_usage": {"provider": "self_hosted", "model": "llama3-legal-local"},
            "privacy_summary": {"raw_pii_sent_to_llm": False},
            "result": {
                "primary_sections": [
                    {
                        "section_code": "BNS-303",
                        "section_title": "Theft",
                        "act_name": "BNS",
                        "confidence_score": 0.9,
                        "legal_reasoning": "Theft facts present.",
                        "supporting_ingredients": ["dishonest taking"],
                        "missing_ingredients": [],
                        "citations": [{"title": "BNS"}],
                    }
                ],
                "alternative_sections": [],
                "hidden_below_threshold": 0,
            },
        }

    monkeypatch.setattr(kis_client.KISClient, "bns_mapping", fake_bns_mapping)

    result = recommend_sections_from_text("vehicle stolen")

    assert result["llm_provider"] == "kis"
    assert result["primary_sections"][0]["section_code"] == "BNS-303"
    # New enhanced fields should have defaults
    for item in result["primary_sections"]:
        assert "applicability_rank" in item
        assert "ingredient_mapping" in item


def test_section_recommendation_falls_back_when_kis_disabled(monkeypatch) -> None:
    monkeypatch.setenv("IQW_KIS_ENABLED", "false")
    monkeypatch.setenv("IQW_ALLOW_LLM_STUBS", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = recommend_sections_from_text("vehicle stolen")

    assert result["llm_provider"] == "stub"
    assert result["primary_sections"] == []


def test_kis_section_to_bns_payload_passes_through_enhanced_fields() -> None:
    item = {
        "section_code": "BNS-303",
        "section_title": "Theft",
        "act_name": "BNS",
        "confidence_score": 0.86,
        "legal_reasoning": "Dishonest taking of property.",
        "supporting_ingredients": ["dishonest taking", "movable property"],
        "missing_ingredients": ["intent to permanently deprive"],
        "applicability_rank": 1,
        "statutory_text": "Whoever intending to take dishonestly...",
        "ingredient_mapping": [
            {"ingredient": "dishonest taking", "status": "satisfied", "complaint_fact": "vehicle stolen"},
        ],
    }
    payload = _kis_section_to_bns_payload(item, fit="primary")
    assert payload["applicability_rank"] == 1
    assert payload["statutory_text"] == "Whoever intending to take dishonestly..."
    assert len(payload["ingredient_mapping"]) == 1
    assert payload["ingredient_mapping"][0]["status"] == "satisfied"
    assert payload["source"] == "kis"


def test_kis_section_to_bns_payload_defaults_when_fields_absent() -> None:
    item = {
        "section_code": "BNS-303",
        "section_title": "Theft",
        "act_name": "BNS",
        "confidence_score": 0.86,
        "legal_reasoning": "Theft.",
        "supporting_ingredients": [],
        "missing_ingredients": [],
    }
    payload = _kis_section_to_bns_payload(item, fit="primary")
    assert payload["applicability_rank"] is None
    assert payload["statutory_text"] is None
    assert payload["ingredient_mapping"] == []
