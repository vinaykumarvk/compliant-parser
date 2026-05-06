from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_snapshot_publish_blocked_when_quality_gates_fail() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]
    snapshot = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots").json()

    response = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots/{snapshot['id']}:publish")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "QUALITY_GATES_FAILED"


def test_quality_gates_pass_with_template_evaluation_and_cited_wiki() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    applied = client.post("/api/v1/domains/d1/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of property."},
    )
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile", json={"title": "Theft"})

    report = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/quality-gates:run").json()

    assert report["passed"] is True
