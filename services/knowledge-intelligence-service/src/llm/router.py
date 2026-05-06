from __future__ import annotations

import json
from typing import Any, Optional

from src.config import Settings
from src.core.errors import KISError
from src.llm.credentials import resolve_credential
from src.llm.providers import DeterministicEmbeddingProvider, EmbeddingProvider, StubJSONProvider, build_json_provider
from src.privacy.pii import protect_text_for_provider, text_hash
from src.state import STORE, new_id, utcnow


def embedding_provider_for_settings(_settings: Settings) -> EmbeddingProvider:
    return DeterministicEmbeddingProvider()


def record_usage(
    *,
    domain_id: str,
    provider: str,
    model: str,
    purpose: str,
    input_hash: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    event = {
        "id": new_id("usage"),
        "domain_id": domain_id,
        "provider": provider,
        "model": model,
        "purpose": purpose,
        "input_hash": input_hash,
        "metadata": metadata,
        "created_at": utcnow(),
    }
    STORE.retrieval_logs.append({"type": "usage", **event})
    return event


def ensure_model_allowed(domain_id: str, provider: str, model: str) -> dict[str, Any]:
    configs = [
        row
        for row in STORE.providers.values()
        if row["domain_id"] == domain_id and row["provider"] == provider and row.get("active") is True
    ]
    if not configs:
        raise KISError("PROVIDER_INACTIVE", "Provider is not active for this domain.", status_code=403)
    for config in configs:
        if model in config.get("allowed_models", []):
            return config
    raise KISError("MODEL_NOT_ALLOWED", "Model is not allowed for this domain.", status_code=403)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def call_json_model(
    *,
    domain_id: str,
    provider: str,
    model: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    settings: Settings,
    response_schema: Optional[dict[str, Any]] = None,
    max_prompt_tokens: int = 4000,
) -> dict[str, Any]:
    provider_config = ensure_model_allowed(domain_id, provider, model)
    raw_user_prompt = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
    prompt_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(raw_user_prompt)
    if prompt_tokens > max_prompt_tokens:
        raise KISError("LLM_BUDGET_EXCEEDED", "Prompt exceeds configured token budget.", status_code=429)

    protected_system = protect_text_for_provider(system_prompt, context="llm_system_prompt")
    protected_user = protect_text_for_provider(raw_user_prompt, context="llm_user_prompt")

    credential_metadata: Optional[dict[str, Any]] = None
    credential_secret: Optional[str] = None
    if provider not in {"local", "self_hosted"}:
        try:
            credential = resolve_credential(domain_id, provider_config["id"], secret_key=settings.secret_key)
            credential_secret = credential["secret"]
            credential_metadata = {"credential_id": credential["credential_id"], "fingerprint": credential["fingerprint"]}
        except KISError as exc:
            if exc.code != "CREDENTIAL_MISSING":
                raise
            if provider == "openai" and settings.openai_api_key:
                credential_metadata = {"source": "environment", "configured": True}
            elif provider == "gemini" and settings.gemini_api_key:
                credential_metadata = {"source": "environment", "configured": True}
            else:
                raise

    json_provider = build_json_provider(provider, model, settings, api_key=credential_secret)
    try:
        response_data = json_provider.generate_json(
            protected_system.text,
            protected_user.text,
            response_schema=response_schema,
        )
        mode = json_provider.mode
    except KISError as exc:
        if not settings.allow_llm_stubs:
            raise
        response_data = StubJSONProvider(provider=provider, model=model).generate_json(
            protected_system.text,
            protected_user.text,
            response_schema=response_schema,
        )
        mode = f"stub_after_{exc.code.lower()}"

    usage = record_usage(
        domain_id=domain_id,
        provider=json_provider.provider,
        model=json_provider.model,
        purpose="reasoning",
        input_hash=text_hash(protected_user.text),
        metadata={
            "prompt_tokens_estimate": prompt_tokens,
            "privacy": protected_user.summary,
            "credential": credential_metadata,
            "raw_payload_stored": False,
            "mode": mode,
        },
    )
    return {
        "provider": json_provider.provider,
        "model": json_provider.model,
        "mode": mode,
        "data": response_data,
        "usage": usage,
        "privacy": protected_user.summary,
        "protected_system_prompt": protected_system.text,
        "protected_user_prompt": protected_user.text,
    }
