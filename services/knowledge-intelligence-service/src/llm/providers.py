from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from src.config import Settings
from src.core.errors import KISError


class EmbeddingProvider(Protocol):
    provider: str
    model: str

    def embed(self, text: str, *, dimensions: int) -> list[float]:
        ...


class JSONProvider(Protocol):
    provider: str
    model: str
    mode: str

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        response_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DeterministicEmbeddingProvider:
    provider: str = "local"
    model: str = "deterministic-hash-embedding"

    def embed(self, text: str, *, dimensions: int) -> list[float]:
        from src.pipeline.embeddings import deterministic_embedding

        return deterministic_embedding(text, dimensions=dimensions)


@dataclass(frozen=True)
class LLMCallResult:
    data: dict[str, Any]
    provider: str
    model: str
    usage: dict[str, Any]


@dataclass(frozen=True)
class StubJSONProvider:
    provider: str
    model: str
    mode: str = "stub"

    def generate_json(
        self,
        _system_prompt: str,
        _user_prompt: str,
        *,
        response_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class OpenAIJSONProvider:
    model: str
    api_key: str
    base_url: str
    timeout_seconds: int
    provider: str = "openai"
    mode: str = "live"

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        response_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise KISError("LLM_PROVIDER_NOT_CONFIGURED", "OpenAI API key is not configured.", status_code=503)
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
            "text": {"format": _openai_response_format(response_schema)},
        }
        response = _json_request(
            f"{self.base_url.rstrip('/')}/responses",
            payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        return _json_from_text(_extract_openai_text(response))


@dataclass(frozen=True)
class GeminiJSONProvider:
    model: str
    api_key: str
    base_url: str
    timeout_seconds: int
    provider: str = "gemini"
    mode: str = "live"

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        response_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise KISError("LLM_PROVIDER_NOT_CONFIGURED", "Gemini API key is not configured.", status_code=503)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nReturn JSON only.\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        response = _json_request(
            f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent?key={self.api_key}",
            payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        return _json_from_text(_extract_gemini_text(response))


@dataclass(frozen=True)
class SelfHostedJSONProvider:
    model: str
    base_url: str
    api_key: Optional[str]
    timeout_seconds: int
    provider: str = "self_hosted"
    mode: str = "live"

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        response_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self.base_url:
            raise KISError("LLM_PROVIDER_NOT_CONFIGURED", "Self-hosted LLM URL is not configured.", status_code=503)
        endpoint = self.base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint + "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        response = _json_request(endpoint, payload, headers=headers, timeout=self.timeout_seconds)
        return _json_from_text(_extract_openai_chat_text(response))


def build_json_provider(
    provider: str,
    model: str,
    settings: Settings,
    *,
    api_key: Optional[str] = None,
) -> JSONProvider:
    normalized = provider.lower().replace("-", "_")
    if normalized in {"self_hosted", "vllm", "tgi", "internal"}:
        return SelfHostedJSONProvider(
            model=model,
            base_url=settings.self_hosted_llm_url or "",
            api_key=settings.self_hosted_llm_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if normalized == "openai":
        return OpenAIJSONProvider(
            model=model,
            api_key=api_key or settings.openai_api_key or "",
            base_url=settings.openai_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if normalized == "gemini":
        return GeminiJSONProvider(
            model=model,
            api_key=api_key or settings.gemini_api_key or "",
            base_url=settings.gemini_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if normalized == "local":
        return StubJSONProvider(provider="local", model=model)
    raise KISError("LLM_PROVIDER_UNSUPPORTED", f"Unsupported LLM provider: {provider}", status_code=422)


def _json_request(url: str, payload: dict[str, Any], *, headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise KISError("LLM_PROVIDER_ERROR", f"LLM provider request failed: {body[:500]}", status_code=502) from exc
    except Exception as exc:
        raise KISError("LLM_PROVIDER_ERROR", f"LLM provider request failed: {exc}", status_code=502) from exc


def _openai_response_format(response_schema: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not response_schema:
        return {"type": "json_object"}
    if response_schema.get("type") == "json_schema":
        return response_schema
    schema = response_schema.get("schema") if isinstance(response_schema.get("schema"), dict) else response_schema
    return {
        "type": "json_schema",
        "name": str(response_schema.get("name") or "kis_json_response")[:64],
        "description": response_schema.get("description") or "KIS structured JSON response",
        "strict": bool(response_schema.get("strict", True)),
        "schema": schema,
    }


def _extract_openai_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    fragments: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if isinstance(content, dict):
                text = content.get("text") or content.get("content")
                if text:
                    fragments.append(str(text))
    return "\n".join(fragments).strip()


def _extract_openai_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(item.get("text") or "") for item in content if isinstance(item, dict)).strip()
    return _extract_openai_text(payload)


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    fragments: list[str] = []
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if text:
                fragments.append(text)
    return "\n".join(fragments).strip()


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    if not cleaned:
        return {}
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(cleaned[start : end + 1])
        else:
            raise KISError("LLM_RESPONSE_INVALID", "LLM response was not valid JSON.", status_code=502)
    if not isinstance(parsed, dict):
        raise KISError("LLM_RESPONSE_INVALID", "LLM response JSON must be an object.", status_code=502)
    return parsed
