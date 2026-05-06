from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app
from src.state import STORE, utcnow


def test_cross_domain_read_is_denied_for_domain_principal() -> None:
    STORE.domains["domain-b"] = {
        "id": "domain-b",
        "name": "Domain B",
        "metadata": {},
        "status": "active",
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "deleted_at": None,
    }
    client = TestClient(
        create_app(
            Settings(
                auth_disabled=False,
                api_keys={
                    "domain-a-key": {
                        "principal_id": "svc-a",
                        "domain_id": "domain-a",
                        "scopes": ["domain:admin", "kb:read"],
                    }
                },
            )
        )
    )

    response = client.get("/api/v1/domains/domain-b", headers={"X-API-Key": "domain-a-key"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DOMAIN_ACCESS_DENIED"
