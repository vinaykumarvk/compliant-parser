from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_wiki_compile_preserves_citations_and_reports_links() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]
    client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Theft Source", "raw_text": "Theft under BNS-303 concerns dishonest taking of property."},
    )

    article = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile",
        json={"title": "Theft"},
    ).json()

    assert article["title"] == "Theft"
    assert article["citations"][0]["title"] == "Theft Source"
    assert article["broken_links"] == []


def test_wiki_compile_can_target_uploaded_source_document_id() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]
    source = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Uploaded complaint-1.pdf", "raw_text": "Motorcycle was stolen from the public parking area."},
    ).json()["source"]

    article = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile",
        json={"title": "Uploaded complaint-1.pdf", "source_document_id": source["id"]},
    ).json()

    assert article["title"] == "Uploaded complaint-1.pdf"
    assert article["citations"][0]["source_document_id"] == source["id"]


def test_wiki_compile_does_not_treat_pii_mask_tokens_as_broken_links() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]
    source = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Masked Source", "raw_text": "Theft note contains [[PII_PHONE_0001]] and BNS-303."},
    ).json()["source"]

    article = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/wiki/articles:compile",
        json={"title": "Masked uploaded source", "source_document_id": source["id"]},
    ).json()

    assert article["broken_links"] == []
