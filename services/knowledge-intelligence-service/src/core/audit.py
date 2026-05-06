from __future__ import annotations

from typing import Any, Optional

from src.state import STORE, new_id, utcnow


def record_audit(
    *,
    domain_id: Optional[str],
    actor_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event = {
        "id": new_id("audit"),
        "domain_id": domain_id,
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "metadata": metadata or {},
        "created_at": utcnow(),
    }
    STORE.audit_events.append(event)
    return event


def search_audit(domain_id: Optional[str] = None) -> list[dict[str, Any]]:
    if domain_id is None:
        return list(STORE.audit_events)
    return [event for event in STORE.audit_events if event.get("domain_id") == domain_id]
