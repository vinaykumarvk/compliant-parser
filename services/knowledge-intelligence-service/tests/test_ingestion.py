from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def _client() -> TestClient:
    return TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))


def _kb(client: TestClient) -> str:
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()
    return kb["id"]


def test_ingestion_lifecycle_creates_source_chunks_and_embeddings() -> None:
    client = _client()
    kb_id = _kb(client)

    response = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={
            "title": "BNS theft note",
            "raw_text": "BNS section 303 covers theft. Theft requires dishonest taking of movable property.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["status"] == "indexed"
    assert payload["source"]["chunk_count"] >= 1
    assert payload["chunks"][0]["embedding"]
    assert payload["chunks"][0]["citation"]["title"] == "BNS theft note"


def test_duplicate_content_increments_version() -> None:
    client = _client()
    kb_id = _kb(client)
    body = {"title": "BNS theft note", "raw_text": "BNS section 303 covers theft."}

    first = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources", json=body).json()
    second = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources", json=body).json()

    assert first["source"]["version"] == 1
    assert second["source"]["version"] == 2


def test_complaint_parser_record_ingest_is_idempotent() -> None:
    client = _client()
    kb_id = _kb(client)
    body = {
        "title": "Uploaded complaint",
        "raw_text": "Masked uploaded complaint text.",
        "metadata": {"origin": "complaint_parser_history", "complaint_parser_record_id": "record-1"},
    }

    first = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources", json=body).json()
    second = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources", json=body).json()

    assert first["source"]["id"] == second["source"]["id"]
    assert second["idempotent_replay"] is True
