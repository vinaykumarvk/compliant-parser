from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.core.errors import KISError
from src.llm.router import call_json_model
from src.main import create_app


def test_provider_governance_refuses_inactive_and_disallowed_models() -> None:
    settings = Settings(auth_disabled=True, api_keys={}, secret_key="test-secret")

    with pytest.raises(KISError) as inactive:
        call_json_model(
            domain_id="d1",
            provider="openai",
            model="gpt-5.2",
            system_prompt="sys",
            user_payload={"input": "hello"},
            settings=settings,
        )
    assert inactive.value.code == "PROVIDER_INACTIVE"

    client = TestClient(create_app(settings))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    client.post("/api/v1/domains/d1/providers", json={"provider": "openai", "allowed_models": ["gpt-5.2"]})

    with pytest.raises(KISError) as disallowed:
        call_json_model(
            domain_id="d1",
            provider="openai",
            model="gpt-4",
            system_prompt="sys",
            user_payload={"input": "hello"},
            settings=settings,
        )
    assert disallowed.value.code == "MODEL_NOT_ALLOWED"


def test_provider_governance_refuses_expired_credentials_and_over_budget() -> None:
    settings = Settings(auth_disabled=True, api_keys={}, secret_key="test-secret")
    client = TestClient(create_app(settings))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    provider = client.post("/api/v1/domains/d1/providers", json={"provider": "openai", "allowed_models": ["gpt-5.2"]}).json()
    client.post(
        f"/api/v1/domains/d1/providers/{provider['id']}/credentials",
        json={"api_key": "sk-secret", "expires_at": "2020-01-01T00:00:00Z"},
    )

    with pytest.raises(KISError) as expired:
        call_json_model(
            domain_id="d1",
            provider="openai",
            model="gpt-5.2",
            system_prompt="sys",
            user_payload={"input": "hello"},
            settings=settings,
        )
    assert expired.value.code == "CREDENTIAL_EXPIRED"

    client.post("/api/v1/domains/d1/providers", json={"provider": "self_hosted", "allowed_models": ["llama3"]})
    with pytest.raises(KISError) as budget:
        call_json_model(
            domain_id="d1",
            provider="self_hosted",
            model="llama3",
            system_prompt="sys",
            user_payload={"input": "too many words"},
            settings=settings,
            max_prompt_tokens=1,
        )
    assert budget.value.code == "LLM_BUDGET_EXCEEDED"
