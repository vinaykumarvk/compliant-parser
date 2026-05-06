from __future__ import annotations

from src.core.errors import KISError
from src.state import STORE, new_id, utcnow


def create_legal_hold(domain_id: str, resource_type: str, resource_id: str, reason: str) -> dict[str, str]:
    hold = {
        "id": new_id("hold"),
        "domain_id": domain_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "reason": reason,
        "active": True,
        "created_at": utcnow(),
    }
    STORE.legal_holds[hold["id"]] = hold
    return hold


def active_holds(domain_id: str, resource_type: str, resource_id: str) -> list[dict[str, str]]:
    return [
        hold
        for hold in STORE.legal_holds.values()
        if hold["domain_id"] == domain_id
        and hold["resource_type"] == resource_type
        and hold["resource_id"] == resource_id
        and hold.get("active") is True
    ]


def ensure_not_on_legal_hold(domain_id: str, resource_type: str, resource_id: str) -> None:
    if active_holds(domain_id, resource_type, resource_id):
        raise KISError("LEGAL_HOLD_ACTIVE", "Resource is under legal hold and cannot be deleted.", status_code=409)
