from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.security import require_domain_access
from src.prompts.registry import create_prompt, render_prompt, set_prompt_status

router = APIRouter(prefix="/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/prompts", tags=["prompts"])


class PromptCreate(BaseModel):
    name: str
    template: str
    status: str = "draft"


class PromptRender(BaseModel):
    template: str
    variables: dict


@router.post("")
async def create_prompt_endpoint(domain_id: str, knowledge_base_id: str, body: PromptCreate, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return create_prompt(
        domain_id=domain_id,
        knowledge_base_id=knowledge_base_id,
        name=body.name,
        template=body.template,
        status=body.status,
    )


@router.post("/{prompt_id}:approve")
async def approve_prompt(domain_id: str, knowledge_base_id: str, prompt_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return set_prompt_status(prompt_id, "approved")


@router.post("/{prompt_id}:activate")
async def activate_prompt(domain_id: str, knowledge_base_id: str, prompt_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    return set_prompt_status(prompt_id, "active")


@router.post(":render")
async def render_prompt_endpoint(domain_id: str, knowledge_base_id: str, body: PromptRender, request: Request) -> dict:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    return {"text": render_prompt(body.template, body.variables)}
