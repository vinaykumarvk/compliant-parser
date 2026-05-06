from __future__ import annotations

from fastapi import APIRouter, Request

from src.core.audit import record_audit
from src.core.errors import KISError
from src.core.security import require_domain_access
from src.state import STORE, new_id, utcnow
from src.templates.seeds import get_template, list_templates

router = APIRouter(tags=["templates"])


@router.get("/templates")
async def templates() -> dict[str, list[dict]]:
    return {"items": list_templates()}


@router.post("/domains/{domain_id}/templates/{template_id}:apply")
async def apply_template(domain_id: str, template_id: str, request: Request) -> dict:
    require_domain_access(request, domain_id)
    if domain_id not in STORE.domains:
        raise KISError("DOMAIN_NOT_FOUND", "Domain not found.", status_code=404)
    template = get_template(template_id)
    if not template:
        raise KISError("TEMPLATE_NOT_FOUND", "Template not found.", status_code=404)
    kb = {
        "id": new_id("kb"),
        "domain_id": domain_id,
        "name": template["name"],
        "retrieval_profile": template.get("retrieval_profile", {}),
        "status": "active",
        "template_id": template_id,
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "deleted_at": None,
    }
    STORE.knowledge_bases[kb["id"]] = kb
    for seed in template.get("prompt_seeds", []):
        prompt = dict(seed)
        prompt.update({"id": new_id("prompt"), "domain_id": domain_id, "knowledge_base_id": kb["id"]})
        STORE.prompts[prompt["id"]] = prompt
    for seed in template.get("ontology_seeds", []):
        ontology = dict(seed)
        ontology.update({"id": new_id("ont"), "domain_id": domain_id, "knowledge_base_id": kb["id"]})
        STORE.ontology_types[ontology["id"]] = ontology
    for seed in template.get("evaluation_seeds", []):
        evaluation_set = dict(seed)
        evaluation_set.update({"id": new_id("evalset"), "domain_id": domain_id, "knowledge_base_id": kb["id"]})
        STORE.evaluation_sets[evaluation_set["id"]] = evaluation_set
    for seed in template.get("reasoning_seeds", []):
        pattern = dict(seed)
        pattern.update({"id": new_id("pattern"), "domain_id": domain_id, "knowledge_base_id": kb["id"]})
        STORE.reasoning_patterns[pattern["id"]] = pattern
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="template.apply",
        resource_type="domain_template",
        resource_id=template_id,
        metadata={"knowledge_base_id": kb["id"]},
    )
    return {"template": template, "knowledge_base": kb}
