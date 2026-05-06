from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def test_evaluation_run_reports_hybrid_recall_lift() -> None:
    client = TestClient(create_app(Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16)))
    client.post("/api/v1/domains", json={"id": "d1", "name": "Domain"})
    kb_id = client.post("/api/v1/domains/d1/knowledge-bases", json={"name": "KB"}).json()["id"]
    client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/sources",
        json={"title": "Ingredient Source", "raw_text": "Dishonest taking of movable property indicates theft."},
    )
    fact = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts",
        json={"subject": "BNS-303", "predicate": "covers", "object_value": "theft", "confidence": 0.9},
    ).json()
    client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/facts/{fact['id']}:review", json={"status": "approved"})
    eval_set = client.post(
        f"/api/v1/domains/d1/knowledge-bases/{kb_id}/evaluations",
        json={"name": "BNS smoke", "cases": [{"query": "vehicle theft", "expected_sections": ["BNS-303"]}]},
    ).json()

    run = client.post(f"/api/v1/domains/d1/knowledge-bases/{kb_id}/evaluations/{eval_set['id']}:run").json()

    assert run["metrics"]["recall_hybrid"] == 1.0
    assert run["metrics"]["recall_vector"] == 0.0
    assert run["metrics"]["recall_lift"] == 1.0
    assert run["metrics"]["source_failure_count"] == 0


def test_bns_reference_remains_available_after_uploaded_document_ingestion() -> None:
    settings = Settings(auth_disabled=True, api_keys={}, embedding_dimensions=16, allow_llm_stubs=True)
    client = TestClient(create_app(settings))
    client.post("/api/v1/domains", json={"id": "police-iqw", "name": "Police IQW"})
    applied = client.post("/api/v1/domains/police-iqw/templates/police_iqw_bns:apply").json()
    kb_id = applied["knowledge_base"]["id"]
    client.post(
        "/api/v1/domains/police-iqw/providers",
        json={"provider": "self_hosted", "allowed_models": ["llama3-legal-local"]},
    )
    client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/sources",
        json={
            "title": "BNS Theft Source",
            "raw_text": "Bharatiya Nyaya Sanhita BNS-303 covers theft and dishonest taking of movable property.",
        },
    )
    for index in range(8):
        source = client.post(
            f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/sources",
            json={
                "title": f"Uploaded complaint {index}",
                "raw_text": f"Uploaded complaint {index} reports a road accident, injury, public nuisance, and vehicle damage.",
                "metadata": {
                    "origin": "complaint_parser_history",
                    "complaint_parser_record_id": f"record-{index}",
                },
            },
        ).json()["source"]
        fact = client.post(
            f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/facts",
            json={
                "subject": f"complaint_parser_record:{index}",
                "predicate": "incident_category",
                "object_value": "road_accident_or_injury",
                "source_document_id": source["id"],
                "confidence": 0.8,
            },
        ).json()
        client.post(f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/facts/{fact['id']}:review", json={"status": "approved"})
        client.post(f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/graph/facts/{fact['id']}:promote")
        client.post(
            f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/wiki/articles:compile",
            json={"title": f"Uploaded complaint {index}", "source_document_id": source["id"]},
        )

    vector = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/search/vector",
        json={"query": "theft BNS-303 dishonest taking movable property", "top_k": 5},
    ).json()
    reasoning = client.post(
        f"/api/v1/domains/police-iqw/knowledge-bases/{kb_id}/reasoning/bns-mapping",
        json={
            "complaint_text": "A motorcycle was stolen from public parking without consent.",
            "provider": "self_hosted",
            "model": "llama3-legal-local",
        },
    ).json()

    assert any("BNS Theft Source" == row["citation"]["title"] for row in vector["results"])
    assert reasoning["context_summary"]["source_counts"]["legal_reference"] >= 1
    assert reasoning["result"]["primary_sections"][0]["section_code"] == "BNS-303"
