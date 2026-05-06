from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app
from src.reasoning.fact_extraction import validate_fact_extraction_result


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_fact_extraction_creates_candidate_facts_only_and_masks_pii(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: urllib.request.Request, *, timeout: int, context: Any) -> _FakeHTTPResponse:
        captured["payload"] = json.loads(request.data.decode("utf-8"))  # type: ignore[union-attr]
        return _FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "facts": [
                                        {
                                            "subject": "complaint_parser_record:1",
                                            "predicate": "incident_category",
                                            "object_value": "theft_or_property_loss",
                                            "confidence": 0.82,
                                            "rationale": "The masked text describes a stolen vehicle.",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = TestClient(
        create_app(
            Settings(
                auth_disabled=True,
                api_keys={},
                self_hosted_llm_url="http://llm.internal",
                embedding_dimensions=16,
            )
        )
    )
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]
    client.post("/api/v1/domains/d1/providers", json={"provider": "self_hosted", "allowed_models": ["llama3-legal-local"]})

    run = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/reasoning/fact-extraction",
        json={
            "source_text": "Phone 9876543210 reported that vehicle KA01AB1234 was stolen.",
            "provider": "self_hosted",
            "model": "llama3-legal-local",
            "source_document_id": "src_1",
            "citation": {"title": "Uploaded complaint"},
        },
    ).json()

    sent = json.dumps(captured["payload"])
    assert "9876543210" not in sent
    assert "KA01AB1234" not in sent
    assert run["status"] == "completed"
    assert run["candidate_fact_count"] == 1
    assert run["candidate_facts"][0]["status"] == "candidate"
    assert run["candidate_facts"][0]["predicate"] == "incident_category"
    assert run["privacy_summary"]["raw_pii_sent_to_llm"] is False


def test_invalid_fact_extraction_schema_is_rejected() -> None:
    with pytest.raises(Exception):
        validate_fact_extraction_result({"items": []})
