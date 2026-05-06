from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_legal_hold_blocks_deletion_request() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})

    hold = client.post(
        "/api/v1/domains/d1/legal-holds",
        json={"resource_type": "knowledge_base", "resource_id": "kb-1", "reason": "active case"},
    )
    blocked = client.post(
        "/api/v1/domains/d1/deletion-requests",
        json={"resource_type": "knowledge_base", "resource_id": "kb-1"},
    )

    assert hold.status_code == 200
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "LEGAL_HOLD_ACTIVE"


def test_deletion_request_allowed_without_legal_hold() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})

    response = client.post(
        "/api/v1/domains/d1/deletion-requests",
        json={"resource_type": "knowledge_base", "resource_id": "kb-1"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "requested"
