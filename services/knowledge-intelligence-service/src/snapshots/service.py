from __future__ import annotations

from typing import Any

from src.core.errors import KISError
from src.quality.gates import run_quality_gates
from src.state import STORE, new_id, utcnow


def _next_version(domain_id: str, knowledge_base_id: str) -> int:
    versions = [
        int(row["version"])
        for row in STORE.snapshots.values()
        if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
    ]
    return max(versions) + 1 if versions else 1


def create_snapshot(domain_id: str, knowledge_base_id: str) -> dict[str, Any]:
    manifest = {
        "source_count": len([row for row in STORE.sources.values() if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id]),
        "chunk_count": len([row for row in STORE.chunks.values() if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id]),
        "graph_node_count": len([row for row in STORE.graph_nodes.values() if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id]),
        "wiki_article_count": len([row for row in STORE.wiki_articles.values() if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id]),
    }
    snapshot = {
        "id": new_id("snap"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "version": _next_version(domain_id, knowledge_base_id),
        "status": "draft",
        "manifest": manifest,
        "quality_report": {},
        "created_at": utcnow(),
        "published_at": None,
        "retired": False,
    }
    STORE.snapshots[snapshot["id"]] = snapshot
    return snapshot


def publish_snapshot(snapshot_id: str) -> dict[str, Any]:
    snapshot = STORE.snapshots.get(snapshot_id)
    if not snapshot:
        raise KISError("SNAPSHOT_NOT_FOUND", "Snapshot not found.", status_code=404)
    report = run_quality_gates(snapshot["domain_id"], snapshot["knowledge_base_id"])
    snapshot["quality_report"] = report
    if not report["passed"]:
        raise KISError("QUALITY_GATES_FAILED", "Snapshot publication blocked by quality gates.", status_code=409)
    for row in STORE.snapshots.values():
        if (
            row["domain_id"] == snapshot["domain_id"]
            and row["knowledge_base_id"] == snapshot["knowledge_base_id"]
            and row["status"] == "published"
        ):
            row["status"] = "retired"
            row["retired"] = True
    snapshot["status"] = "published"
    snapshot["published_at"] = utcnow()
    return snapshot


def latest_published_snapshot(domain_id: str, knowledge_base_id: str) -> dict[str, Any] | None:
    snapshots = [
        row
        for row in STORE.snapshots.values()
        if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id and row["status"] == "published"
    ]
    return sorted(snapshots, key=lambda item: item["version"], reverse=True)[0] if snapshots else None


def rollback_snapshot(domain_id: str, knowledge_base_id: str, version: int) -> dict[str, Any]:
    target = next(
        (
            row
            for row in STORE.snapshots.values()
            if row["domain_id"] == domain_id
            and row["knowledge_base_id"] == knowledge_base_id
            and row["version"] == version
        ),
        None,
    )
    if not target:
        raise KISError("SNAPSHOT_NOT_FOUND", "Snapshot version not found.", status_code=404)
    for row in STORE.snapshots.values():
        if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id:
            row["status"] = "retired"
            row["retired"] = True
    target["status"] = "published"
    target["retired"] = False
    target["published_at"] = utcnow()
    return target
