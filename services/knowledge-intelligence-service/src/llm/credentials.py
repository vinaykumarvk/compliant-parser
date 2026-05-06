from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from src.core.errors import KISError
from src.core.security import decrypt_secret
from src.state import STORE


def _parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def resolve_credential(domain_id: str, provider_config_id: str, *, secret_key: str) -> dict[str, Any]:
    credentials = [
        row
        for row in STORE.credentials.values()
        if row["domain_id"] == domain_id and row["provider_config_id"] == provider_config_id
        and not row.get("revoked_at")
    ]
    if not credentials:
        raise KISError("CREDENTIAL_MISSING", "No active credential is configured for provider.", status_code=403)
    latest = sorted(credentials, key=lambda item: item["created_at"], reverse=True)[0]
    expires_at = _parse_expiry(latest.get("expires_at"))
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise KISError("CREDENTIAL_EXPIRED", "Provider credential is expired.", status_code=403)
    return {
        "credential_id": latest["id"],
        "fingerprint": latest["fingerprint"],
        "secret": decrypt_secret(latest["encrypted_secret"], secret_key),
    }
