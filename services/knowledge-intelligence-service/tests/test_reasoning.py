from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def _ready_kb() -> tuple[TestClient, str]:
    settings = Settings(
        auth_disabled=True,
        api_keys={},
        embedding_dimensions=16,
        secret_key="test-secret",
        allow_llm_stubs=True,
    )
    client = TestClient(create_app(settings))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    applied = client.post("/api/v1/domains/d1/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    client.post("/api/v1/domains/d1/providers", json={"provider": "self_hosted", "allowed_models": ["llama3-legal-local"]})
    client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of movable property."},
    )
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile", json={"title": "Theft"})
    snapshot = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots").json()
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots/{snapshot['id']}:publish")
    return client, kb_id


def test_reasoning_run_records_context_usage_privacy_and_result() -> None:
    client, kb_id = _ready_kb()

    response = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/reasoning/bns-mapping",
        json={
            "complaint_text": "My phone 9876543210 was with me when my vehicle KA01AB1234 was stolen.",
            "provider": "self_hosted",
            "model": "llama3-legal-local",
        },
    )

    run = response.json()
    assert response.status_code == 200
    assert run["status"] == "completed"
    assert run["context_summary"]["snapshot_id"].startswith("snap_")
    assert run["llm_usage"]["provider"] == "self_hosted"
    assert run["result_source"] == "rules_fallback"
    assert run["privacy_summary"]["raw_pii_sent_to_llm"] is False
    assert "9876543210" not in run["llm_usage"]["protected_user_prompt"]
    assert "KA01AB1234" not in run["llm_usage"]["protected_user_prompt"]
    assert run["result"]["primary_sections"][0]["section_code"] == "BNS-303"
