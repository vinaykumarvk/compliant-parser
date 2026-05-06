from __future__ import annotations

from typing import Any, Optional

from src.state import STORE, new_id, utcnow


def submit_feedback(
    *,
    domain_id: str,
    knowledge_base_id: str,
    target_type: str,
    target_id: str,
    rating: str,
    comment: Optional[str] = None,
) -> dict[str, Any]:
    item = {
        "id": new_id("feedback"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "target_type": target_type,
        "target_id": target_id,
        "rating": rating,
        "comment": comment,
        "created_at": utcnow(),
    }
    STORE.feedback_items[item["id"]] = item
    if rating.lower() in {"bad", "incorrect", "unsafe"}:
        STORE.audit_events.append(
            {
                "id": new_id("audit"),
                "domain_id": domain_id,
                "actor_id": "feedback",
                "action": "review_task.create",
                "resource_type": target_type,
                "resource_id": target_id,
                "metadata": {"feedback_id": item["id"], "comment": comment},
                "created_at": utcnow(),
            }
        )
    return item
