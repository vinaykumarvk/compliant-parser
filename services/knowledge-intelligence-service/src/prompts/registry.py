from __future__ import annotations

import re
from typing import Any

from src.core.errors import KISError
from src.state import STORE, new_id, utcnow


def create_prompt(
    *,
    domain_id: str,
    knowledge_base_id: str,
    name: str,
    template: str,
    status: str = "draft",
) -> dict[str, Any]:
    versions = [
        prompt["version"]
        for prompt in STORE.prompts.values()
        if prompt["domain_id"] == domain_id and prompt.get("knowledge_base_id") == knowledge_base_id and prompt["name"] == name
    ]
    prompt = {
        "id": new_id("prompt"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "name": name,
        "version": max(versions) + 1 if versions else 1,
        "status": status,
        "template": template,
        "created_at": utcnow(),
    }
    STORE.prompts[prompt["id"]] = prompt
    return prompt


def set_prompt_status(prompt_id: str, status: str) -> dict[str, Any]:
    if status not in {"draft", "review", "approved", "active", "retired"}:
        raise KISError("PROMPT_STATUS_INVALID", "Invalid prompt status.", status_code=422)
    prompt = STORE.prompts.get(prompt_id)
    if not prompt:
        raise KISError("PROMPT_NOT_FOUND", "Prompt not found.", status_code=404)
    if status == "active" and prompt["status"] != "approved":
        raise KISError("PROMPT_NOT_APPROVED", "Only approved prompts can be activated.", status_code=409)
    if status == "active":
        for other in STORE.prompts.values():
            if (
                other["domain_id"] == prompt["domain_id"]
                and other.get("knowledge_base_id") == prompt.get("knowledge_base_id")
                and other["name"] == prompt["name"]
                and other["id"] != prompt_id
                and other["status"] == "active"
            ):
                other["status"] = "retired"
    prompt["status"] = status
    prompt["updated_at"] = utcnow()
    return prompt


def resolve_prompt(domain_id: str, knowledge_base_id: str, name: str) -> dict[str, Any]:
    prompts = [
        prompt
        for prompt in STORE.prompts.values()
        if prompt["domain_id"] == domain_id
        and prompt.get("knowledge_base_id") == knowledge_base_id
        and prompt["name"] == name
        and prompt["status"] == "active"
    ]
    if not prompts:
        raise KISError("PROMPT_NOT_ACTIVE", "No active prompt is available for this pattern.", status_code=409)
    return sorted(prompts, key=lambda item: item["version"], reverse=True)[0]


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = variables.get(key, "")
        return str(value)

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace, template)
