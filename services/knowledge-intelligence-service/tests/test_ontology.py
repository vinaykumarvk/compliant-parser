from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_template_application_seeds_ontology_types() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})

    applied = client.post("/api/v1/domains/d1/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    ontology = client.get(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/ontology").json()["items"]

    assert {row["name"] for row in ontology} >= {"legal_section", "offence_ingredient"}


def test_ontology_create_endpoint_validates_name() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]

    response = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/ontology",
        json={"name": "incident_type", "description": "Incident type"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "incident_type"
