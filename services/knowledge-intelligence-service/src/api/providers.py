from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.audit import record_audit
from src.core.security import encrypt_secret, require_domain_access, secret_fingerprint
from src.state import STORE, new_id, utcnow

router = APIRouter(prefix="/domains/{domain_id}/providers", tags=["providers"])


class ProviderCreate(BaseModel):
    provider: str
    allowed_models: list[str]
    active: bool = True
    budget: dict[str, Any] = {}


class ProviderUpdate(BaseModel):
    allowed_models: Optional[list[str]] = None
    active: Optional[bool] = None
    budget: Optional[dict[str, Any]] = None


class CredentialCreate(BaseModel):
    api_key: str
    expires_at: Optional[str] = None


def public_credential(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "domain_id": row["domain_id"],
        "provider_config_id": row["provider_config_id"],
        "fingerprint": row["fingerprint"],
        "expires_at": row.get("expires_at"),
        "revoked_at": row.get("revoked_at"),
        "active": not bool(row.get("revoked_at")),
        "created_at": row["created_at"],
    }


@router.post("")
async def create_provider(domain_id: str, body: ProviderCreate, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id)
    provider = {
        "id": new_id("provider"),
        "domain_id": domain_id,
        "provider": body.provider,
        "allowed_models": body.allowed_models,
        "active": body.active,
        "budget": body.budget,
        "created_at": utcnow(),
    }
    STORE.providers[provider["id"]] = provider
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="provider.create",
        resource_type="provider",
        resource_id=provider["id"],
    )
    return provider


@router.get("")
async def list_providers(domain_id: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    require_domain_access(request, domain_id)
    return {"items": [row for row in STORE.providers.values() if row["domain_id"] == domain_id]}


@router.post("/{provider_config_id}/credentials")
async def create_credential(
    domain_id: str,
    provider_config_id: str,
    body: CredentialCreate,
    request: Request,
) -> dict[str, Any]:
    require_domain_access(request, domain_id)
    credential = {
        "id": new_id("cred"),
        "domain_id": domain_id,
        "provider_config_id": provider_config_id,
        "fingerprint": secret_fingerprint(body.api_key),
        "encrypted_secret": encrypt_secret(body.api_key, request.app.state.settings.secret_key),
        "expires_at": body.expires_at,
        "revoked_at": None,
        "created_at": utcnow(),
    }
    STORE.credentials[credential["id"]] = credential
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="credential.create",
        resource_type="llm_credential",
        resource_id=credential["id"],
        metadata={"fingerprint": credential["fingerprint"]},
    )
    return public_credential(credential)


@router.get("/{provider_config_id}/credentials")
async def list_credentials(domain_id: str, provider_config_id: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    require_domain_access(request, domain_id)
    return {
        "items": [
            public_credential(row)
            for row in STORE.credentials.values()
            if row["domain_id"] == domain_id and row["provider_config_id"] == provider_config_id
        ]
    }


@router.patch("/{provider_config_id}")
async def update_provider(domain_id: str, provider_config_id: str, body: ProviderUpdate, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id)
    provider = STORE.providers.get(provider_config_id)
    if not provider or provider["domain_id"] != domain_id:
        from src.core.errors import KISError

        raise KISError("PROVIDER_NOT_FOUND", "Provider configuration not found.", status_code=404)
    if body.allowed_models is not None:
        provider["allowed_models"] = body.allowed_models
    if body.active is not None:
        provider["active"] = body.active
    if body.budget is not None:
        provider["budget"] = body.budget
    provider["updated_at"] = utcnow()
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="provider.update",
        resource_type="provider",
        resource_id=provider["id"],
        metadata={"active": provider.get("active"), "allowed_model_count": len(provider.get("allowed_models") or [])},
    )
    return provider


@router.post("/{provider_config_id}/credentials/{credential_id}:revoke")
async def revoke_credential(domain_id: str, provider_config_id: str, credential_id: str, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id)
    credential = STORE.credentials.get(credential_id)
    if (
        not credential
        or credential["domain_id"] != domain_id
        or credential["provider_config_id"] != provider_config_id
    ):
        from src.core.errors import KISError

        raise KISError("CREDENTIAL_NOT_FOUND", "Credential not found.", status_code=404)
    credential["revoked_at"] = datetime.now(timezone.utc).isoformat()
    credential["revoked_by"] = getattr(request.state, "principal_id", None)
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="credential.revoke",
        resource_type="llm_credential",
        resource_id=credential["id"],
        metadata={"fingerprint": credential["fingerprint"]},
    )
    return public_credential(credential)
