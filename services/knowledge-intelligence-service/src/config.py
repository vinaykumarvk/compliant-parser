from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _list_env(name: str, default: Optional[list[str]] = None) -> list[str]:
    value = _env(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def _json_env(name: str, default: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    value = _env(name)
    if not value:
        return dict(default or {})
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return dict(default or {})
    return parsed if isinstance(parsed, dict) else dict(default or {})


@dataclass(frozen=True)
class Settings:
    service_name: str = "knowledge-intelligence-service"
    service_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: Optional[str] = None
    cloud_sql_connection_name: Optional[str] = None
    db_user: str = "postgres"
    db_name: str = "police_kb"
    db_password: Optional[str] = None
    db_iam_auth: bool = False
    auto_migrate: bool = True
    require_database: bool = False
    redis_url: Optional[str] = None
    auth_disabled: bool = False
    api_keys: dict[str, Any] = field(default_factory=dict)
    cors_origins: list[str] = field(default_factory=list)
    secret_key: str = "local-dev-only"
    pii_strict: bool = True
    embedding_dimensions: int = 32
    default_provider: str = "self_hosted"
    allowed_models: list[str] = field(default_factory=lambda: ["self_hosted:llama3-legal-local"])
    self_hosted_llm_url: Optional[str] = None
    self_hosted_llm_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: Optional[str] = None
    openai_api_key_configured: bool = False
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_api_key: Optional[str] = None
    gemini_api_key_configured: bool = False
    llm_timeout_seconds: int = 120
    allow_llm_stubs: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        db_password = _env("KIS_DB_PASSWORD") or _env("DB_PASSWORD")
        openai_api_key = _env("KIS_OPENAI_API_KEY") or _env("OPENAI_API_KEY")
        gemini_api_key = _env("KIS_GEMINI_API_KEY") or _env("GEMINI_API_KEY")
        return cls(
            service_name=_env("KIS_SERVICE_NAME", cls.service_name) or cls.service_name,
            service_version=_env("KIS_SERVICE_VERSION", cls.service_version) or cls.service_version,
            api_prefix=_env("KIS_API_PREFIX", cls.api_prefix) or cls.api_prefix,
            database_url=_env("KIS_DATABASE_URL") or _env("DATABASE_URL"),
            cloud_sql_connection_name=_env("KIS_CLOUD_SQL_CONNECTION_NAME") or _env("CLOUD_SQL_CONNECTION_NAME"),
            db_user=_env("KIS_DB_USER") or _env("DB_USER", cls.db_user) or cls.db_user,
            db_name=_env("KIS_DB_NAME") or _env("DB_NAME", cls.db_name) or cls.db_name,
            db_password=db_password,
            db_iam_auth=_bool_env("KIS_DB_IAM_AUTH", not bool(db_password)),
            auto_migrate=_bool_env("KIS_AUTO_MIGRATE", True),
            require_database=_bool_env("KIS_REQUIRE_DATABASE", False),
            redis_url=_env("KIS_REDIS_URL"),
            auth_disabled=_bool_env("KIS_AUTH_DISABLED", False),
            api_keys=_json_env("KIS_API_KEYS"),
            cors_origins=_list_env("KIS_CORS_ORIGINS"),
            secret_key=_env("KIS_SECRET_KEY", "local-dev-only") or "local-dev-only",
            pii_strict=_bool_env("KIS_PII_STRICT", True),
            embedding_dimensions=int(_env("KIS_EMBEDDING_DIMENSIONS", "32") or "32"),
            default_provider=_env("KIS_DEFAULT_PROVIDER", "self_hosted") or "self_hosted",
            allowed_models=_list_env("KIS_ALLOWED_MODELS", ["self_hosted:llama3-legal-local"]),
            self_hosted_llm_url=(_env("KIS_SELF_HOSTED_LLM_URL") or _env("IQW_SELF_HOSTED_LLM_URL") or None),
            self_hosted_llm_api_key=(_env("KIS_SELF_HOSTED_LLM_API_KEY") or _env("IQW_SELF_HOSTED_LLM_API_KEY") or None),
            openai_base_url=(_env("KIS_OPENAI_BASE_URL") or _env("OPENAI_BASE_URL", cls.openai_base_url) or cls.openai_base_url).rstrip("/"),
            openai_api_key=openai_api_key,
            openai_api_key_configured=bool(openai_api_key),
            gemini_base_url=(_env("KIS_GEMINI_BASE_URL") or _env("GEMINI_BASE_URL", cls.gemini_base_url) or cls.gemini_base_url).rstrip("/"),
            gemini_api_key=gemini_api_key,
            gemini_api_key_configured=bool(gemini_api_key),
            llm_timeout_seconds=int(_env("KIS_LLM_TIMEOUT_SECONDS", "120") or "120"),
            allow_llm_stubs=_bool_env("KIS_ALLOW_LLM_STUBS", False),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
