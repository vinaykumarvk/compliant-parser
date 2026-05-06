from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock

os.environ.setdefault("APP_SESSION_SECRET", "test-session-secret")

import kis_client
import kis_indexing_status
from api_v1 import (
    KISCredentialCreateRequest,
    KISProviderCreateRequest,
    KISProviderUpdateRequest,
    KISRebuildRequest,
    KISRollbackRequest,
    approve_kis_fact_endpoint,
    create_kis_credential_endpoint,
    create_kis_provider_endpoint,
    kis_facts_endpoint,
    kis_indexing_records_endpoint,
    kis_maintenance_dashboard_endpoint,
    kis_status_endpoint,
    publish_kis_snapshot_endpoint,
    rebuild_kis_knowledge_base_endpoint,
    retry_failed_kis_indexing_endpoint,
    reject_kis_fact_endpoint,
    revoke_kis_credential_endpoint,
    rollback_kis_snapshot_endpoint,
    update_kis_provider_endpoint,
)


def _configure(monkeypatch) -> None:
    monkeypatch.setenv("IQW_KIS_ENABLED", "true")
    monkeypatch.setenv("IQW_KIS_BASE_URL", "http://kis.local")
    monkeypatch.setenv("IQW_KIS_API_KEY", "secret-key")
    monkeypatch.setenv("IQW_KIS_DOMAIN", "police-iqw")
    monkeypatch.setenv("IQW_KIS_KB", "kb-1")


class _FakeAdminKISClient:
    def latest_snapshot(self) -> dict[str, Any]:
        return {"snapshot": {"id": "snap_1", "status": "published", "manifest": {"source_count": 2}}}

    def run_quality_gates(self) -> dict[str, Any]:
        return {"passed": True, "checks": [{"name": "citation_coverage", "passed": True}]}

    def graph_stats(self) -> dict[str, Any]:
        return {"node_count": 2, "edge_count": 1}

    def list_wiki_articles(self) -> dict[str, Any]:
        return {"items": [{"id": "wiki_1"}]}

    def list_facts(self) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": "fact_1",
                    "subject": "record-1",
                    "predicate": "incident_category",
                    "object": "theft",
                    "status": "candidate",
                    "confidence": 0.8,
                },
                {"id": "fact_2", "subject": "record-2", "predicate": "source_system", "object": "parser", "status": "approved"},
            ]
        }

    def review_fact(self, fact_id: str, *, status: str = "approved") -> dict[str, Any]:
        return {"id": fact_id, "status": status}

    def promote_fact(self, fact_id: str) -> dict[str, Any]:
        return {"id": "edge_1", "fact_id": fact_id}

    def create_snapshot(self) -> dict[str, Any]:
        return {"id": "snap_2"}

    def publish_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        return {"id": snapshot_id, "status": "published"}

    def maintenance_dashboard(self) -> dict[str, Any]:
        return {
            "domain": {"id": "police-iqw", "name": "Police IQW"},
            "knowledge_bases": [{"id": "kb-1", "counts": {"source_count": 2}}],
            "providers": [
                {
                    "id": "provider_1",
                    "provider": "openai",
                    "latest_active_fingerprint": "sha256:abc",
                    "credentials": [{"id": "cred_1", "fingerprint": "sha256:abc", "active": True}],
                }
            ],
            "recent_audit": [{"action": "provider.update"}],
        }

    def create_provider(self, *, provider: str, allowed_models: list[str], active: bool = True, budget: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"id": "provider_1", "provider": provider, "allowed_models": allowed_models, "active": active, "budget": budget or {}}

    def update_provider(self, provider_config_id: str, *, allowed_models=None, active=None, budget=None) -> dict[str, Any]:
        return {"id": provider_config_id, "allowed_models": allowed_models or [], "active": active, "budget": budget or {}}

    def create_credential(self, provider_config_id: str, *, api_key: str, expires_at: str | None = None) -> dict[str, Any]:
        return {"id": "cred_1", "provider_config_id": provider_config_id, "fingerprint": "sha256:abc", "expires_at": expires_at, "active": True}

    def revoke_credential(self, provider_config_id: str, credential_id: str) -> dict[str, Any]:
        return {"id": credential_id, "provider_config_id": provider_config_id, "fingerprint": "sha256:abc", "active": False}

    def rebuild_knowledge_base(self, **kwargs) -> dict[str, Any]:
        return {"vectors_rebuilt": 2, "wiki_recompiled": 1, "facts_promoted": 1, "quality_gates": {"passed": True}, "snapshot": {"id": "snap_3", "status": "published"}}

    def rollback_snapshot(self, version: int) -> dict[str, Any]:
        return {"id": "snap_1", "version": version, "status": "published"}


def test_kis_admin_status_is_non_secret(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis_client, "KISClient", _FakeAdminKISClient)

    result = asyncio.run(kis_status_endpoint(current_user={"role": "System_Admin"}))

    assert result["available"] is True
    assert result["latest_snapshot"]["id"] == "snap_1"
    assert result["quality_gates"]["passed"] is True
    assert result["graph"]["edge_count"] == 1
    assert result["wiki_article_count"] == 1
    assert result["fact_count"] == 2
    assert "secret-key" not in str(result)


def test_kis_admin_snapshot_publish_uses_quality_gate(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis_client, "KISClient", _FakeAdminKISClient)

    result = asyncio.run(publish_kis_snapshot_endpoint(current_user={"role": "System_Admin"}))

    assert result["published"] is True
    assert result["snapshot"]["id"] == "snap_2"


def test_kis_admin_indexing_records_endpoint(monkeypatch) -> None:
    records = [
        {
            "id": "record-1",
            "file_name": "complaint.pdf",
            "kis_index_status": "indexed",
            "kis_source_id": "src_1",
        }
    ]
    list_mock = AsyncMock(return_value=records)
    counts_mock = AsyncMock(return_value={"indexed": 1, "failed": 0})
    monkeypatch.setattr(kis_indexing_status, "list_kis_indexing_records", list_mock)
    monkeypatch.setattr(kis_indexing_status, "kis_index_status_counts", counts_mock)

    result = asyncio.run(kis_indexing_records_endpoint(limit=10, current_user={"role": "System_Admin"}))

    assert result["items"][0]["kis_index_status"] == "indexed"
    assert result["counts"]["indexed"] == 1
    list_mock.assert_awaited_once_with(limit=10)


def test_kis_admin_retry_failed_endpoint(monkeypatch) -> None:
    retry_mock = AsyncMock(return_value=3)
    monkeypatch.setattr(kis_indexing_status, "requeue_failed_kis_indexing", retry_mock)

    result = asyncio.run(retry_failed_kis_indexing_endpoint(limit=25, current_user={"role": "System_Admin"}))

    assert result["requeued"] == 3
    retry_mock.assert_awaited_once_with(limit=25)


def test_kis_maintenance_dashboard_and_provider_endpoints_are_non_secret(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis_client, "KISClient", _FakeAdminKISClient)

    dashboard = asyncio.run(kis_maintenance_dashboard_endpoint(current_user={"role": "System_Admin"}))
    created_provider = asyncio.run(
        create_kis_provider_endpoint(
            KISProviderCreateRequest(provider="openai", allowed_models=["gpt-5.2"]),
            current_user={"role": "System_Admin"},
        )
    )
    updated_provider = asyncio.run(
        update_kis_provider_endpoint(
            "provider_1",
            KISProviderUpdateRequest(allowed_models=["gpt-5.2", "gpt-5.1"], active=False),
            current_user={"role": "System_Admin"},
        )
    )
    credential = asyncio.run(
        create_kis_credential_endpoint(
            "provider_1",
            KISCredentialCreateRequest(api_key="sk-secret"),
            current_user={"role": "System_Admin"},
        )
    )
    revoked = asyncio.run(
        revoke_kis_credential_endpoint("provider_1", "cred_1", current_user={"role": "System_Admin"})
    )

    assert dashboard["domain"]["id"] == "police-iqw"
    assert created_provider["provider"] == "openai"
    assert updated_provider["active"] is False
    assert credential["fingerprint"].startswith("sha256:")
    assert revoked["active"] is False
    assert "sk-secret" not in str(credential)
    assert "sk-secret" not in str(dashboard)


def test_kis_rebuild_and_snapshot_rollback_endpoints(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis_client, "KISClient", _FakeAdminKISClient)

    rebuild = asyncio.run(
        rebuild_kis_knowledge_base_endpoint(
            KISRebuildRequest(create_snapshot=True, publish_snapshot=True),
            current_user={"role": "System_Admin"},
        )
    )
    rollback = asyncio.run(
        rollback_kis_snapshot_endpoint(KISRollbackRequest(version=1), current_user={"role": "System_Admin"})
    )

    assert rebuild["quality_gates"]["passed"] is True
    assert rebuild["snapshot"]["status"] == "published"
    assert rollback["version"] == 1
    assert rollback["status"] == "published"


def test_kis_fact_review_endpoints(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setattr(kis_client, "KISClient", _FakeAdminKISClient)

    candidates = asyncio.run(kis_facts_endpoint(status="candidate", current_user={"role": "System_Admin"}))
    approved = asyncio.run(approve_kis_fact_endpoint("fact_1", current_user={"role": "System_Admin"}))
    rejected = asyncio.run(reject_kis_fact_endpoint("fact_1", current_user={"role": "System_Admin"}))

    assert candidates["total"] == 1
    assert candidates["items"][0]["id"] == "fact_1"
    assert approved["approved"] is True
    assert approved["promoted"]["fact_id"] == "fact_1"
    assert rejected["rejected"] is True
    assert rejected["fact"]["status"] == "rejected"
