from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def _client_and_kb(domain_id: str = "d1") -> tuple[TestClient, str]:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": domain_id, "name": domain_id})
    kb_id = client.post(f"/api/v1/domains/{domain_id}/knowledge-bases", json={"name": "KB"}).json()["id"]
    return client, kb_id


def test_approved_fact_promotes_to_graph_with_provenance() -> None:
    client, kb_id = _client_and_kb()
    fact = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts",
        json={
            "subject": "BNS-303",
            "predicate": "requires",
            "object_value": "dishonest taking",
            "confidence": 0.9,
            "citation": {"title": "BNS"},
        },
    ).json()
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts/{fact['id']}:review", json={"status": "approved"})

    promoted = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/graph/facts/{fact['id']}:promote").json()
    stats = client.get(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/graph/stats").json()
    search = client.get(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/graph/search", params={"q": "BNS-303"}).json()

    assert promoted["edge"]["citation"] == {"title": "BNS"}
    assert stats == {"node_count": 2, "edge_count": 1}
    assert search["nodes"][0]["label"] == "BNS-303"


def test_graph_search_is_domain_scoped() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "a", "name": "A"})
    client.post("/api/v1/domains", json={"id": "b", "name": "B"})
    kb_a = client.post("/api/v1/domains/a/knowledge-bases", json={"name": "A"}).json()["id"]
    kb_b = client.post("/api/v1/domains/b/knowledge-bases", json={"name": "B"}).json()["id"]
    fact = client.post(
        f"/api/v1/domains/a/knowledge-bases/{kb_a}/facts",
        json={"subject": "BNS-303", "predicate": "covers", "object_value": "theft", "confidence": 0.8},
    ).json()
    client.post(f"/api/v1/domains/a/knowledge-bases/{kb_a}/facts/{fact['id']}:review", json={"status": "approved"})
    client.post(f"/api/v1/domains/a/knowledge-bases/{kb_a}/graph/facts/{fact['id']}:promote")

    search_b = client.get(f"/api/v1/domains/b/knowledge-bases/{kb_b}/graph/search", params={"q": "BNS-303"}).json()

    assert search_b == {"nodes": [], "edges": []}


def test_duplicate_source_fact_returns_existing_fact() -> None:
    client, kb_id = _client_and_kb()
    body = {
        "subject": "complaint_parser_record:1",
        "predicate": "document_format",
        "object_value": "POLICE_COMPLAINT",
        "confidence": 0.9,
        "source_document_id": "src_1",
    }

    first = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts", json=body).json()
    second = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts", json=body).json()

    assert first["id"] == second["id"]
