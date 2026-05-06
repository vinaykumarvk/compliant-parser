from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.feedback.service import submit_feedback

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    target_type: str
    target_id: str
    rating: str
    comment: Optional[str] = None


@router.post("")
async def feedback(domain_id: str, knowledge_base_id: str, body: FeedbackCreate, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write", "kb:read"))
    return submit_feedback(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        target_type=body.target_type,
        target_id=body.target_id,
        rating=body.rating,
        comment=body.comment,
    )
