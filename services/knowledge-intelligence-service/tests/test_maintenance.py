from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app
from src.state import STORE


def _client() -> TestClient:
    return TestClient(create_app(Settings(auth_disabled=True, api_keys={}, secret_key="test-secret", embedding_dimensions=16)))


def _ready_domain(client: TestClient) -> tuple[str, str]:
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()
    return "d1", kb["id"]


def test_maintenance_dashboard_is_non_secret_and_summarizes_domain() -> None:
    client = _client()
    domain_id, kb_id = _ready_domain(client)
    provider = client.post(
        f"/api/v1/domains/{domain_id}/providers",
        json={"provider": "openai", "allowed_models": ["gpt-5.2"]},
    ).json()
    client.post(
        f"/api/v1/domains/{domain_id}/providers/{provider['id']}/credentials",
        json={"api_key": "sk-secret"},
    )
    client.post(
        f"/api/v1/domains/{domain_id}/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of property."},
    )

    dashboard = client.get(f"/api/v1/domains/{domain_id}/maintenance/dashboard").json()

    assert dashboard["domain"]["id"] == domain_id
    assert dashboard["knowledge_bases"][0]["counts"]["source_count"] == 1
    assert dashboard["providers"][0]["active_credential_count"] == 1
    assert dashboard["providers"][0]["latest_active_fingerprint"].startswith("sha256:")
    assert dashboard["providers"][0]["credentials"][0]["active"] is True
    assert dashboard["providers"][0]["credentials"][0]["id"].startswith("cred_")
    assert "sk-secret" not in str(dashboard)
    assert "encrypted_secret" not in str(dashboard)


def test_provider_update_and_credential_revoke_are_audited() -> None:
    client = _client()
    domain_id, _kb_id = _ready_domain(client)
    provider = client.post(
        f"/api/v1/domains/{domain_id}/providers",
        json={"provider": "openai", "allowed_models": ["gpt-5.2"]},
    ).json()
    credential = client.post(
        f"/api/v1/domains/{domain_id}/providers/{provider['id']}/credentials",
        json={"api_key": "sk-secret"},
    ).json()

    updated = client.patch(
        f"/api/v1/domains/{domain_id}/providers/{provider['id']}",
        json={"allowed_models": ["gpt-5.2", "gpt-5.1"], "active": False},
    ).json()
    revoked = client.post(
        f"/api/v1/domains/{domain_id}/providers/{provider['id']}/credentials/{credential['id']}:revoke"
    ).json()

    assert updated["active"] is False
    assert updated["allowed_models"] == ["gpt-5.2", "gpt-5.1"]
    assert revoked["active"] is False
    audit_actions = {row["action"] for row in client.get(f"/api/v1/domains/{domain_id}/audit").json()["items"]}
    assert {"provider.update", "credential.revoke"}.issubset(audit_actions)


def test_maintenance_rebuild_vectors_wiki_graph_and_snapshot() -> None:
    client = _client()
    domain_id, kb_id = _ready_domain(client)
    source = client.post(
        f"/api/v1/domains/{domain_id}/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of property."},
    ).json()["source"]
    fact = client.post(
        f"/api/v1/domains/{domain_id}/knowledge-bases/{kb_id}/facts",
        json={
            "subject": "complaint:1",
            "predicate": "proposed_bns_section",
            "object_value": "BNS-303",
            "confidence": 0.9,
            "source_document_id": source["id"],
            "citation": {"source_document_id": source["id"], "title": source["title"]},
        },
    ).json()
    client.post(f"/api/v1/domains/{domain_id}/knowledge-bases/{kb_id}/facts/{fact['id']}:review", json={"status": "approved"})
    client.post(
        f"/api/v1/domains/{domain_id}/knowledge-bases/{kb_id}/evaluations",
        json={"name": "smoke", "cases": [{"query": "theft", "expected": "BNS-303"}]},
    )

    result = client.post(
        f"/api/v1/domains/{domain_id}/knowledge-bases/{kb_id}/maintenance:rebuild",
        json={"create_snapshot": True, "publish_snapshot": True},
    ).json()

    assert result["vectors_rebuilt"] > 0
    assert result["wiki_recompiled"] == 1
    assert result["facts_promoted"] == 1
    assert result["quality_gates"]["passed"] is True
    assert result["snapshot"]["status"] == "published"
    assert any(row["action"] == "knowledge_base.rebuild" for row in STORE.audit_events)
