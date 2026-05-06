from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app
from src.state import STORE


def _client() -> TestClient:
    return TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))


def _domain_kb(client: TestClient, domain_id: str) -> str:
    client.post("/api/v1/domains", json={"id": domain_id, "name": domain_id})
    return client.post(f"/api/v1/domains/{domain_id}/knowledge-bases", json={"name": "KB"}).json()["id"]


def test_vector_search_returns_citations_and_filters_domain() -> None:
    client = _client()
    kb_a = _domain_kb(client, "a")
    kb_b = _domain_kb(client, "b")
    client.post(
        f"/api/v1/domains/a/knowledge-bases/{kb_a}/sources",
        json={"title": "Theft", "raw_text": "BNS section 303 covers theft of movable property."},
    )
    client.post(
        f"/api/v1/domains/b/knowledge-bases/{kb_b}/sources",
        json={"title": "Forgery", "raw_text": "Forgery provisions are separate and unrelated."},
    )

    response = client.post(
        f"/api/v1/domains/a/knowledge-bases/{kb_a}/search/vector",
        json={"query": "Which section applies to theft of vehicle KA01AB1234?", "top_k": 3},
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    assert all(result["citation"]["title"] == "Theft" for result in results)
    assert all(result["citation"]["source_document_id"].startswith("src_") for result in results)

    trace = STORE.retrieval_logs[-1]
    assert trace["type"] == "retrieval_query"
    assert "KA01AB1234" not in trace["redacted_query"]
    assert trace["privacy_summary"]["raw_pii_sent_to_llm"] is False
