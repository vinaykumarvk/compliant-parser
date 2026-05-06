from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def _client() -> TestClient:
    app = create_app(
        Settings(
            auth_disabled=False,
            api_keys={
                "valid-key": {
                    "principal_id": "svc-test",
                    "domain_id": "domain-a",
                    "scopes": ["kb:read"],
                }
            },
        )
    )
    router = APIRouter()

    @router.get("/probe")
    async def probe(request: Request) -> dict[str, object]:
        return {
            "principal_id": request.state.principal_id,
            "domain_id": request.state.domain_id,
            "scopes": sorted(request.state.scopes),
        }

    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_auth_rejects_missing_or_invalid_key() -> None:
    client = _client()
    assert client.get("/api/v1/probe").status_code == 401
    assert client.get("/api/v1/probe", headers={"X-API-Key": "bad"}).status_code == 401


def test_auth_sets_principal_domain_and_scopes() -> None:
    response = _client().get("/api/v1/probe", headers={"X-API-Key": "valid-key"})

    assert response.status_code == 200
    assert response.json() == {
        "principal_id": "svc-test",
        "domain_id": "domain-a",
        "scopes": ["kb:read"],
    }


def test_header_domain_overrides_key_default_domain() -> None:
    response = _client().get(
        "/api/v1/probe",
        headers={"X-API-Key": "valid-key", "X-Domain-ID": "domain-b"},
    )

    assert response.status_code == 200
    assert response.json()["domain_id"] == "domain-b"
