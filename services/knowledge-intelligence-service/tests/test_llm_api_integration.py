from __future__ import annotations

import json
import urllib.request
from typing import Any

from src.config import Settings
from src.llm.router import call_json_model
from src.state import STORE


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_json_call_uses_real_api_shape_and_masked_prompt(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    STORE.providers["provider_1"] = {
        "id": "provider_1",
        "domain_id": "d1",
        "provider": "openai",
        "allowed_models": ["gpt-5.2"],
        "active": True,
    }

    def fake_urlopen(request: urllib.request.Request, *, timeout: int, context: Any) -> _FakeHTTPResponse:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))  # type: ignore[union-attr]
        captured["timeout"] = timeout
        return _FakeHTTPResponse({"output_text": "{\"primary_sections\": []}"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = call_json_model(
        domain_id="d1",
        provider="openai",
        model="gpt-5.2",
        system_prompt="Return JSON.",
        user_payload={"complaint": "Phone 9876543210 and vehicle KA01AB1234 were reported stolen."},
        settings=Settings(openai_api_key="sk-test", llm_timeout_seconds=7),
    )

    sent = json.dumps(captured["payload"])
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["timeout"] == 7
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert "9876543210" not in sent
    assert "KA01AB1234" not in sent
    assert "[[PII_" in sent
    assert result["provider"] == "openai"
    assert result["mode"] == "live"
    assert result["data"] == {"primary_sections": []}


def test_self_hosted_json_call_uses_chat_completions_shape(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    STORE.providers["provider_1"] = {
        "id": "provider_1",
        "domain_id": "d1",
        "provider": "self_hosted",
        "allowed_models": ["llama3-legal-local"],
        "active": True,
    }

    def fake_urlopen(request: urllib.request.Request, *, timeout: int, context: Any) -> _FakeHTTPResponse:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))  # type: ignore[union-attr]
        return _FakeHTTPResponse({"choices": [{"message": {"content": "{\"ok\": true}"}}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = call_json_model(
        domain_id="d1",
        provider="self_hosted",
        model="llama3-legal-local",
        system_prompt="Return JSON.",
        user_payload={"complaint": "Vehicle KA01AB1234 was stolen."},
        settings=Settings(
            self_hosted_llm_url="http://llm.internal",
            self_hosted_llm_api_key="local-key",
            llm_timeout_seconds=5,
        ),
    )

    sent = json.dumps(captured["payload"])
    assert captured["url"] == "http://llm.internal/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer local-key"
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["messages"][1]["role"] == "user"
    assert "KA01AB1234" not in sent
    assert result["provider"] == "self_hosted"
    assert result["data"] == {"ok": True}


def test_openai_json_call_can_request_structured_output_schema(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    STORE.providers["provider_1"] = {
        "id": "provider_1",
        "domain_id": "d1",
        "provider": "openai",
        "allowed_models": ["gpt-5.2"],
        "active": True,
    }

    def fake_urlopen(request: urllib.request.Request, *, timeout: int, context: Any) -> _FakeHTTPResponse:
        captured["payload"] = json.loads(request.data.decode("utf-8"))  # type: ignore[union-attr]
        return _FakeHTTPResponse({"output_text": "{\"ok\": true}"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = call_json_model(
        domain_id="d1",
        provider="openai",
        model="gpt-5.2",
        system_prompt="Return JSON.",
        user_payload={"task": "structured"},
        settings=Settings(openai_api_key="sk-test"),
        response_schema={
            "name": "test_schema",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
        },
    )

    response_format = captured["payload"]["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["name"] == "test_schema"
    assert response_format["strict"] is True
    assert response_format["schema"]["required"] == ["ok"]
    assert result["data"] == {"ok": True}
