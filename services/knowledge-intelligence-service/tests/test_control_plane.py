from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def _client() -> TestClient:
    return TestClient(create_app(Settings(auth_disabled=True, api_keys={}, secret_key="test-secret")))


def test_control_plane_crud_template_provider_credential_and_audit() -> None:
    client = _client()

    domain = client.post("/api/v1/domains", json={"id": "police-iqw", "name": "Police IQW"}).json()
    assert domain["id"] == "police-iqw"

    kb = client.post(
        "/api/v1/domains/police-iqw/knowledge-bases",
        json={"name": "BNS Knowledge", "retrieval_profile": {"vector_weight": 0.5}},
    ).json()
    assert kb["domain_id"] == "police-iqw"

    templates = client.get("/api/v1/templates").json()["items"]
    assert {item["id"] for item in templates} >= {"police_iqw_bns", "ps_wms_advisory"}

    applied = client.post("/api/v1/domains/police-iqw/templates/police_iqw_bns:apply").json()
    assert applied["knowledge_base"]["template_id"] == "police_iqw_bns"

    provider = client.post(
        "/api/v1/domains/police-iqw/providers",
        json={"provider": "openai", "allowed_models": ["gpt-5.2"]},
    ).json()
    credential = client.post(
        f"/api/v1/domains/police-iqw/providers/{provider['id']}/credentials",
        json={"api_key": "sk-secret"},
    ).json()

    assert credential["fingerprint"].startswith("sha256:")
    assert "api_key" not in credential
    assert "secret" not in credential

    audit = client.get("/api/v1/domains/police-iqw/audit").json()["items"]
    assert {event["action"] for event in audit} >= {
        "domain.create",
        "knowledge_base.create",
        "template.apply",
        "provider.create",
        "credential.create",
    }


def test_membership_endpoint_creates_domain_scoped_membership() -> None:
    client = _client()
    client.post("/api/v1/domains", json={"id": "domain-a", "name": "Domain A"})

    membership = client.post(
        "/api/v1/domains/domain-a/memberships",
        json={"principal_id": "svc-a", "scopes": ["kb:read"]},
    ).json()

    assert membership["domain_id"] == "domain-a"
    assert membership["principal_id"] == "svc-a"
    assert membership["scopes"] == ["kb:read"]
