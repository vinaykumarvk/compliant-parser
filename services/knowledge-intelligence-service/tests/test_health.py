from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_health_and_readiness_start_without_database_or_provider() -> None:
    app = create_app(Settings(auth_disabled=True, api_keys={}))
    client = TestClient(app)

    health = client.get("/api/v1/health")
    ready = client.get("/api/v1/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["database"]["configured"] is False
    assert ready.json()["database"]["status"] == "not_configured"
    assert "secret" not in str(ready.json()).lower()
