from __future__ import annotations

from typing import Any

import kis_client
from ai_workflows import recommend_sections_from_text


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


def test_section_recommendation_falls_back_when_kis_disabled(monkeypatch) -> None:
    monkeypatch.setenv("IQW_KIS_ENABLED", "false")
    monkeypatch.setenv("IQW_ALLOW_LLM_STUBS", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = recommend_sections_from_text("vehicle stolen")

    assert result["llm_provider"] == "stub"
    assert result["primary_sections"] == []
