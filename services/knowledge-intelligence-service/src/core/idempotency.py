from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from src.core.errors import KISError
from src.state import STORE, utcnow


def request_hash(body: Any) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def acquire_idempotency(key: str, *, body: Any, domain_id: Optional[str], actor_id: Optional[str]) -> dict[str, Any]:
    fingerprint = request_hash(body)
    existing = STORE.idempotency_records.get(key)
    if existing is None:
        record = {
            "key": key,
            "domain_id": domain_id,
            "actor_id": actor_id,
            "request_hash": fingerprint,
            "response": None,
            "created_at": utcnow(),
        }
        STORE.idempotency_records[key] = record
        return {"status": "new", "record": record}
    if existing["request_hash"] != fingerprint:
        raise KISError("IDEMPOTENCY_CONFLICT", "Idempotency key was already used with a different body.", status_code=409)
    return {"status": "replay", "record": existing}


def complete_idempotency(key: str, response: dict[str, Any]) -> dict[str, Any]:
    record = STORE.idempotency_records[key]
    record["response"] = response
    return record


def idempotent_response(key: str) -> Optional[dict[str, Any]]:
    record = STORE.idempotency_records.get(key)
    if not record:
        return None
    response = record.get("response")
    return dict(response) if isinstance(response, dict) else response
