from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app
from src.state import STORE


def test_negative_feedback_creates_review_audit_task() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={})))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]

    feedback = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/feedback",
        json={
            "target_type": "retrieval_result",
            "target_id": "result-1",
            "rating": "incorrect",
            "comment": "Wrong section",
        },
    ).json()

    assert feedback["rating"] == "incorrect"
    assert any(event["action"] == "review_task.create" for event in STORE.audit_events)
