from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.core.errors import KISError
from src.core.idempotency import acquire_idempotency, complete_idempotency, idempotent_response
from src.llm.router import call_json_model
from src.main import create_app
from src.pipeline.embeddings import embed_text


def test_release_gate_secrets_privacy_idempotency_and_retention() -> None:
    settings = Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16, secret_key="test-secret")
    client = TestClient(create_app(settings))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    provider = client.post(
        "/api/v1/domains/d1/providers",
        json={"provider": "openai", "allowed_models": ["gpt-5.2"]},
    ).json()
    credential = client.post(
        f"/api/v1/domains/d1/providers/{provider['id']}/credentials",
        json={"api_key": "sk-live-secret"},
    ).json()

    assert "sk-live-secret" not in str(credential)

    embedding = embed_text("d1", "Victim phone 9876543210 and vehicle KA01AB1234 were in the report.", settings=settings)
    assert "9876543210" not in embedding.masked_text
    assert "KA01AB1234" not in embedding.masked_text

    first = acquire_idempotency("idem-release", body={"x": 1}, domain_id="d1", actor_id="svc")
    complete_idempotency("idem-release", {"ok": True})
    replay = acquire_idempotency("idem-release", body={"x": 1}, domain_id="d1", actor_id="svc")
    assert first["status"] == "new"
    assert replay["status"] == "replay"
    assert idempotent_response("idem-release") == {"ok": True}
    with pytest.raises(KISError):
        acquire_idempotency("idem-release", body={"x": 2}, domain_id="d1", actor_id="svc")

    client.post(
        "/api/v1/domains/d1/legal-holds",
        json={"resource_type": "knowledge_base", "resource_id": "kb-1", "reason": "case hold"},
    )
    deletion = client.post(
        "/api/v1/domains/d1/deletion-requests",
        json={"resource_type": "knowledge_base", "resource_id": "kb-1"},
    )
    assert deletion.status_code == 409


def test_release_gate_llm_prompt_is_masked() -> None:
    settings = Settings(auth_disabled=True, api_keys={}, secret_key="test-secret", allow_llm_stubs=True)
    client = TestClient(create_app(settings))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    client.post("/api/v1/domains/d1/providers", json={"provider": "self_hosted", "allowed_models": ["llama3"]})

    result = call_json_model(
        domain_id="d1",
        provider="self_hosted",
        model="llama3",
        system_prompt="Return JSON",
        user_payload={"complainant": "Phone 9876543210 vehicle KA01AB1234"},
        settings=settings,
    )

    assert "9876543210" not in result["protected_user_prompt"]
    assert "KA01AB1234" not in result["protected_user_prompt"]
    assert result["privacy"]["raw_pii_sent_to_llm"] is False
    assert result["mode"].startswith("stub_after_")
