from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def _ready_kb(client: TestClient) -> str:
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    applied = client.post("/api/v1/domains/d1/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of property."},
    )
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile", json={"title": "Theft"})
    return kb_id


def test_snapshot_publish_and_rollback() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    kb_id = _ready_kb(client)

    snap1 = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots").json()
    published1 = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots/{snap1['id']}:publish").json()
    snap2 = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots").json()
    published2 = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots/{snap2['id']}:publish").json()
    rolled = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/snapshots:rollback", json={"version": 1}).json()

    assert published1["status"] == "published"
    assert published2["version"] == 2
    assert rolled["version"] == 1
    assert rolled["status"] == "published"
