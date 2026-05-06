from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.core.audit import record_audit, search_audit
from src.core.errors import KISError
from src.core.security import require_domain_access
from src.api.providers import public_credential
from src.graph.builder import promote_fact_to_graph
from src.pipeline.embeddings import embed_text
from src.quality.gates import run_quality_gates
from src.snapshots.service import create_snapshot, latest_published_snapshot, publish_snapshot
from src.state import STORE, utcnow
from src.wiki.compiler import compile_article

router = APIRouter(tags=["maintenance"])


class RebuildRequest(BaseModel):
    rebuild_vectors: bool = True
    recompile_wiki: bool = True
    promote_facts: bool = True
    create_snapshot: bool = False
    publish_snapshot: bool = False


def _kb_counts(domain_id: str, knowledge_base_id: str) -> dict[str, Any]:
    facts = [
        row
        for row in STORE.facts.values()
        if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
    ]
    fact_status_counts: dict[str, int] = {}
    for fact in facts:
        status = fact.get("status") or "unknown"
        fact_status_counts[status] = fact_status_counts.get(status, 0) + 1
    return {
        "source_count": len([
            row
            for row in STORE.sources.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]),
        "chunk_count": len([
            row
            for row in STORE.chunks.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]),
        "fact_count": len(facts),
        "fact_status_counts": fact_status_counts,
        "graph_node_count": len([
            row
            for row in STORE.graph_nodes.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]),
        "graph_edge_count": len([
            row
            for row in STORE.graph_edges.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]),
        "wiki_article_count": len([
            row
            for row in STORE.wiki_articles.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]),
        "snapshot_count": len([
            row
            for row in STORE.snapshots.values()
            if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
        ]),
        "latest_snapshot": latest_published_snapshot(domain_id, knowledge_base_id),
    }


def _credential_summary(domain_id: str, provider_config_id: str) -> dict[str, Any]:
    credentials = [
        row
        for row in STORE.credentials.values()
        if row["domain_id"] == domain_id and row["provider_config_id"] == provider_config_id
    ]
    active = [row for row in credentials if not row.get("revoked_at")]
    latest_active = sorted(active, key=lambda item: item["created_at"], reverse=True)[0] if active else None
    return {
        "credential_count": len(credentials),
        "active_credential_count": len(active),
        "latest_active_fingerprint": latest_active.get("fingerprint") if latest_active else None,
        "credentials": [public_credential(row) for row in sorted(credentials, key=lambda item: item["created_at"], reverse=True)],
    }


@router.get("/domains/{domain_id}/maintenance/dashboard")
async def maintenance_dashboard(domain_id: str, request: Request) -> dict[str, Any]:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:read"))
    domain = STORE.domains.get(domain_id)
    if not domain:
        raise KISError("DOMAIN_NOT_FOUND", "Domain not found.", status_code=404)
    knowledge_bases = []
    for kb in STORE.knowledge_bases.values():
        if kb["domain_id"] == domain_id and kb.get("deleted_at") is None:
            knowledge_bases.append({**kb, "counts": _kb_counts(domain_id, kb["id"])})
    providers = []
    for provider in STORE.providers.values():
        if provider["domain_id"] == domain_id:
            providers.append({**provider, **_credential_summary(domain_id, provider["id"])})
    return {
        "domain": domain,
        "knowledge_bases": knowledge_bases,
        "providers": providers,
        "recent_audit": list(reversed(search_audit(domain_id)))[:20],
    }


@router.post("/domains/{domain_id}/knowledge-bases/{knowledge_base_id}/maintenance:rebuild")
async def rebuild_knowledge_base(
    domain_id: str,
    knowledge_base_id: str,
    body: RebuildRequest,
    request: Request,
) -> dict[str, Any]:
    require_domain_access(request, domain_id, allowed_scopes=("domain:admin", "kb:write"))
    kb = STORE.knowledge_bases.get(knowledge_base_id)
    if not kb or kb["domain_id"] != domain_id:
        raise KISError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found.", status_code=404)

    report: dict[str, Any] = {
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "started_at": utcnow(),
        "vectors_rebuilt": 0,
        "wiki_recompiled": 0,
        "wiki_failures": [],
        "facts_promoted": 0,
        "quality_gates": None,
        "snapshot": None,
        "completed_at": None,
    }

    if body.rebuild_vectors:
        for chunk in STORE.chunks.values():
            if chunk["domain_id"] == domain_id and chunk["knowledge_base_id"] == knowledge_base_id:
                embedding = embed_text(domain_id, chunk["text"], settings=request.app.state.settings)
                chunk["masked_embedding_text"] = embedding.masked_text
                chunk["embedding"] = embedding.vector
                chunk["embedding_provider"] = embedding.provider
                chunk["embedding_model"] = embedding.model
                chunk["privacy_summary"] = embedding.privacy_summary
                report["vectors_rebuilt"] += 1

    if body.promote_facts:
        for fact in list(STORE.facts.values()):
            if (
                fact["domain_id"] == domain_id
                and fact["knowledge_base_id"] == knowledge_base_id
                and fact.get("status") == "approved"
            ):
                promote_fact_to_graph(fact["id"])
                report["facts_promoted"] += 1

    if body.recompile_wiki:
        for source in list(STORE.sources.values()):
            if source["domain_id"] == domain_id and source["knowledge_base_id"] == knowledge_base_id:
                try:
                    compile_article(domain_id, knowledge_base_id, source.get("title") or "Source", source_document_id=source["id"])
                    report["wiki_recompiled"] += 1
                except KISError as exc:
                    report["wiki_failures"].append({"source_id": source["id"], "error": exc.code})

    report["quality_gates"] = run_quality_gates(domain_id, knowledge_base_id)
    if body.create_snapshot or body.publish_snapshot:
        snapshot = create_snapshot(domain_id, knowledge_base_id)
        if body.publish_snapshot:
            snapshot = publish_snapshot(snapshot["id"])
        report["snapshot"] = snapshot
    report["completed_at"] = utcnow()
    record_audit(
        domain_id=domain_id,
        actor_id=getattr(request.state, "principal_id", None),
        action="knowledge_base.rebuild",
        resource_type="knowledge_base",
        resource_id=knowledge_base_id,
        metadata={
            "vectors_rebuilt": report["vectors_rebuilt"],
            "wiki_recompiled": report["wiki_recompiled"],
            "facts_promoted": report["facts_promoted"],
            "snapshot_id": report["snapshot"]["id"] if report.get("snapshot") else None,
        },
    )
    return report
