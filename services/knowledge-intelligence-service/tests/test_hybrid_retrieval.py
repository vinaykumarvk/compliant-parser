from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.core.errors import KISError
from src.main import create_app
from src.retrieval.hybrid import hybrid_search


def _ready_client() -> tuple[TestClient, str]:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    applied = client.post("/api/v1/domains/d1/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    source = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of property."},
    ).json()["source"]
    fact = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts",
        json={
            "subject": "BNS-303",
            "predicate": "covers",
            "object_value": "theft",
            "confidence": 0.9,
            "source_document_id": source["id"],
            "citation": {"title": "Theft Source"},
        },
    ).json()
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts/{fact['id']}:review", json={"status": "approved"})
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/graph/facts/{fact['id']}:promote")
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile", json={"title": "Theft"})
    return client, kb_id


def test_hybrid_search_returns_source_counts_and_cited_results() -> None:
    client, kb_id = _ready_client()

    response = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/search/hybrid",
        json={"query": "theft BNS-303", "top_k": 5},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["source_counts"]["vector"] >= 1
    assert payload["source_counts"]["fact"] >= 1
    assert payload["source_counts"]["wiki"] >= 1
    assert all(result["citation"] for result in payload["results"])


def test_hybrid_non_required_source_failure_is_degraded_and_required_failure_errors() -> None:
    _client, kb_id = _ready_client()
    settings = Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)

    degraded = hybrid_search(
        domain_id="d1",
        knowledge_base_id=kb_id,
        query="theft",
        settings=settings,
        fail_sources={"wiki"},
    )
    assert degraded["degraded"] is True
    assert degraded["failures"][0]["source"] == "wiki"

    with pytest.raises(KISError) as error:
        hybrid_search(
            domain_id="d1",
            knowledge_base_id=kb_id,
            query="theft",
            settings=settings,
            fail_sources={"wiki"},
            required_sources={"wiki"},
        )
    assert error.value.code == "REQUIRED_SOURCE_FAILED"
