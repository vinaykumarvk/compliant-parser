from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_mvp_smoke_flow_publishes_snapshot_and_runs_cited_bns_mapping() -> None:
    client = TestClient(
        create_app(
            Settings(
                auth_disabled=True,
                api_keys={},
                embedding_dimensions=16,
                secret_key="test-secret",
                allow_llm_stubs=True,
            )
        )
    )

    client.post("/api/v1/domains", json={"id": "police-iqw", "name": "Police IQW"})
    applied = client.post("/api/v1/domains/police-iqw/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    client.post(
        "/api/v1/domains/police-iqw/providers",
        json={"provider": "self_hosted", "allowed_models": ["llama3-legal-local"]},
    )
    source = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/sources",
        json={
            "title": "BNS Theft Source",
            "raw_text": "Theft under BNS-303 concerns dishonest taking of movable property.",
        },
    ).json()["source"]
    article = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/wiki/articles:compile",
        json={"title": "Theft"},
    ).json()
    snapshot = client.post(f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/snapshots").json()
    published = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/snapshots/{snapshot['id']}:publish"
    ).json()
    hybrid = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/search/hybrid",
        json={"query": "vehicle theft BNS-303", "top_k": 5},
    ).json()
    reasoning = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/reasoning/bns-mapping",
        json={
            "complaint_text": "My motorcycle was stolen from parking.",
            "provider": "self_hosted",
            "model": "llama3-legal-local",
        },
    ).json()

    assert source["status"] == "indexed"
    assert article["citations"]
    assert published["status"] == "published"
    assert hybrid["source_counts"]["vector"] >= 1
    assert reasoning["result"]["primary_sections"][0]["section_code"] == "BNS-303"
    assert reasoning["result"]["primary_sections"][0]["citations"]
    assert reasoning["privacy_summary"]["raw_pii_sent_to_llm"] is False
