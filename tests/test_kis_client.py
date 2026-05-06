from __future__ import annotations

from typing import Any

import pytest

import kis_client


def _configure(monkeypatch) -> None:
    monkeypatch.setenv("IQW_KIS_ENABLED", "true")
    monkeypatch.setenv("IQW_KIS_BASE_URL", "http://kis.local")
    monkeypatch.setenv("IQW_KIS_API_KEY", "secret-key")
    monkeypatch.setenv("IQW_KIS_DOMAIN", "police-iqw")
    monkeypatch.setenv("IQW_KIS_KB", "kb-1")


def test_kis_status_is_non_secret(monkeypatch) -> None:
    _configure(monkeypatch)

    status = kis_client.kis_status()

    assert status["configured"] is True
    assert status["credential_configured"] is True
    assert "secret-key" not in str(status)


def test_recommend_sections_via_kis_maps_reasoning_run(monkeypatch) -> None:
    _configure(monkeypatch)

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

    result = kis_client.recommend_sections_via_kis("vehicle stolen")

    assert result is not None
    assert result["primary_sections"][0]["section_code"] == "BNS-303"
    assert result["model_name"] == "kis:self_hosted:llama3-legal-local"
    assert result["kis_reasoning_run_id"] == "rrun_1"
    assert result["privacy_controls"]["raw_pii_sent_to_llm"] is False


class _RecordingKISClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def ingest_source(self, **payload: Any) -> dict[str, Any]:
        self.calls.append(("ingest_source", payload))
        return {"source": {"id": "src_1"}, "chunks": [{"id": "chunk_1"}]}

    def create_fact(self, **payload: Any) -> dict[str, Any]:
        self.calls.append(("create_fact", payload))
        return {"id": f"fact_{len([call for call in self.calls if call[0] == 'create_fact'])}", **payload}

    def review_fact(self, fact_id: str, *, status: str = "approved") -> dict[str, Any]:
        self.calls.append(("review_fact", {"fact_id": fact_id, "status": status}))
        return {"id": fact_id, "status": status}

    def promote_fact(self, fact_id: str) -> dict[str, Any]:
        self.calls.append(("promote_fact", {"fact_id": fact_id}))
        return {"edge": {"id": f"edge_{fact_id}"}}

    def compile_wiki_article(self, **payload: Any) -> dict[str, Any]:
        self.calls.append(("compile_wiki_article", payload))
        return {"id": "wiki_1", **payload}

    def run_quality_gates(self) -> dict[str, Any]:
        self.calls.append(("run_quality_gates", {}))
        return {"passed": True}


def test_index_uploaded_document_masks_pii_and_creates_enrichment(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("APP_SESSION_SECRET", "test-session-secret")
    client = _RecordingKISClient()

    result = kis_client.index_uploaded_document_via_kis(
        record_id="record-1",
        file_name="complaint.pdf",
        document_format="POLICE_COMPLAINT",
        parsed_output={
            "summary": "Phone 9876543210 and vehicle KA01AB1234 were reported stolen.",
            "language": {"detected_name": "English"},
            "fir_draft": {
                "jurisdiction": {"police_station": "Panjagutta"},
                "occurrence": {"nature_of_offence": "theft"},
                "proposed_bns_sections": [{"section_code": "BNS-303"}],
            },
        },
        client=client,  # type: ignore[arg-type]
    )

    ingest = next(payload for name, payload in client.calls if name == "ingest_source")
    raw_text = ingest["raw_text"]
    assert result["indexed"] is True
    assert "9876543210" not in raw_text
    assert "KA01AB1234" not in raw_text
    assert "[[PII_PHONE_" in raw_text
    assert ingest["metadata"]["complaint_parser_record_id"] == "record-1"
    assert ingest["metadata"]["masked_before_kis_ingest"] is True
    fact_payloads = [payload for name, payload in client.calls if name == "create_fact"]
    assert ("proposed_bns_section", "BNS-303") in {
        (payload["predicate"], payload["object_value"]) for payload in fact_payloads
    }
    assert any(name == "compile_wiki_article" for name, _payload in client.calls)


def test_index_uploaded_document_can_publish_snapshot(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("APP_SESSION_SECRET", "test-session-secret")

    class PublishingClient(_RecordingKISClient):
        def create_snapshot(self) -> dict[str, Any]:
            self.calls.append(("create_snapshot", {}))
            return {"id": "snap_1"}

        def publish_snapshot(self, snapshot_id: str) -> dict[str, Any]:
            self.calls.append(("publish_snapshot", {"snapshot_id": snapshot_id}))
            return {"id": snapshot_id, "status": "published"}

    client = PublishingClient()
    result = kis_client.index_uploaded_document_via_kis(
        record_id="record-1",
        file_name="complaint.pdf",
        document_format="POLICE_COMPLAINT",
        parsed_output={"summary": "General complaint", "fir_draft": {}},
        publish_snapshot=True,
        client=client,  # type: ignore[arg-type]
    )

    assert result["published_snapshot_id"] == "snap_1"
    assert any(name == "publish_snapshot" for name, _payload in client.calls)


# --- Multi-KB tests ---


def test_get_multi_kb_config_defaults(monkeypatch) -> None:
    """When only IQW_KIS_KB is set, both policy and cases use the same KB."""
    _configure(monkeypatch)

    multi = kis_client.get_multi_kb_config()

    assert multi.policy.knowledge_base_id == "kb-1"
    assert multi.cases.knowledge_base_id == "kb-1"
    assert multi.policy.base_url == "http://kis.local"
    assert multi.cases.api_key == "secret-key"


def test_get_multi_kb_config_separate(monkeypatch) -> None:
    """When separate KB env vars are set, each KB gets its own ID."""
    _configure(monkeypatch)
    monkeypatch.setenv("IQW_KIS_KB_POLICY", "policy-bns-bnss")
    monkeypatch.setenv("IQW_KIS_KB_CASES", "case-docs")

    multi = kis_client.get_multi_kb_config()

    assert multi.policy.knowledge_base_id == "policy-bns-bnss"
    assert multi.cases.knowledge_base_id == "case-docs"
    # Shared fields
    assert multi.policy.domain_id == multi.cases.domain_id == "police-iqw"
    assert multi.policy.base_url == multi.cases.base_url == "http://kis.local"


def test_get_kis_client_factory(monkeypatch) -> None:
    """get_kis_client returns a KISClient with the correct KB config."""
    _configure(monkeypatch)
    monkeypatch.setenv("IQW_KIS_KB_POLICY", "pol-kb")
    monkeypatch.setenv("IQW_KIS_KB_CASES", "cas-kb")

    policy_client = kis_client.get_kis_client(kis_client.KB_POLICY)
    cases_client = kis_client.get_kis_client(kis_client.KB_CASES)
    default_client = kis_client.get_kis_client()

    assert policy_client.config.knowledge_base_id == "pol-kb"
    assert cases_client.config.knowledge_base_id == "cas-kb"
    # Default is cases
    assert default_client.config.knowledge_base_id == "cas-kb"


def test_get_kis_client_invalid_name(monkeypatch) -> None:
    """get_kis_client raises ValueError for unknown KB name."""
    _configure(monkeypatch)

    with pytest.raises(ValueError, match="Unknown KB"):
        kis_client.get_kis_client("nonexistent")
