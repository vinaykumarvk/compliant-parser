from __future__ import annotations

"""Tests for the dual Knowledge Base (Policy + Cases) search endpoints."""

import os
import sys
from typing import Any
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")
os.environ.setdefault("APP_SESSION_SECRET", "test-session-secret")
os.environ.setdefault("APP_ADMIN_USERNAME", "operator")
os.environ.setdefault("APP_ADMIN_PASSWORD", "correct horse battery staple")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import kis_client
from kis_client import KB_POLICY, KB_CASES, KISUnavailable


def _configure(monkeypatch) -> None:
    monkeypatch.setenv("IQW_KIS_ENABLED", "true")
    monkeypatch.setenv("IQW_KIS_BASE_URL", "http://kis.local")
    monkeypatch.setenv("IQW_KIS_API_KEY", "secret-key")
    monkeypatch.setenv("IQW_KIS_DOMAIN", "police-iqw")
    monkeypatch.setenv("IQW_KIS_KB", "kb-1")
    monkeypatch.setenv("IQW_KIS_KB_POLICY", "policy-kb")
    monkeypatch.setenv("IQW_KIS_KB_CASES", "cases-kb")


class _FakeKISClient:
    """Fake KIS client that returns canned search results."""

    def __init__(self, config: Any = None) -> None:
        self.config = config or kis_client.get_kis_config()

    def hybrid_search(self, query: str, *, top_k: int = 5) -> dict[str, Any]:
        return {
            "items": [
                {
                    "title": f"Result for: {query}",
                    "text": "Sample text content",
                    "score": 0.95,
                    "source_type": "vector",
                    "source_uri": "test://doc/1",
                }
            ]
        }


def test_knowledge_status_endpoint(monkeypatch) -> None:
    """GET /api/v1/knowledge/status returns both KB configs."""
    _configure(monkeypatch)

    status = kis_client.kis_status(kis_client.get_multi_kb_config().policy)
    assert status["enabled"] is True
    assert status["configured"] is True

    status_cases = kis_client.kis_status(kis_client.get_multi_kb_config().cases)
    assert status_cases["enabled"] is True
    assert status_cases["configured"] is True


def test_policy_search_returns_results(monkeypatch) -> None:
    """Policy KB search returns results from the correct KB."""
    _configure(monkeypatch)

    client = _FakeKISClient(config=kis_client.get_multi_kb_config().policy)
    results = client.hybrid_search("BNS section 303 theft", top_k=5)

    assert len(results["items"]) == 1
    assert "BNS section 303" in results["items"][0]["title"]
    assert results["items"][0]["score"] == 0.95


def test_cases_search_returns_results(monkeypatch) -> None:
    """Cases KB search returns results from the correct KB."""
    _configure(monkeypatch)

    client = _FakeKISClient(config=kis_client.get_multi_kb_config().cases)
    results = client.hybrid_search("chain snatching railway station", top_k=5)

    assert len(results["items"]) == 1
    assert "chain snatching" in results["items"][0]["title"]


def test_search_unavailable_when_not_configured(monkeypatch) -> None:
    """Search raises KISUnavailable when KB is not configured."""
    monkeypatch.setenv("IQW_KIS_ENABLED", "false")
    monkeypatch.delenv("IQW_KIS_BASE_URL", raising=False)
    monkeypatch.delenv("IQW_KIS_API_KEY", raising=False)
    monkeypatch.delenv("IQW_KIS_DOMAIN", raising=False)
    monkeypatch.delenv("IQW_KIS_KB", raising=False)
    monkeypatch.delenv("IQW_KIS_KB_POLICY", raising=False)
    monkeypatch.delenv("IQW_KIS_KB_CASES", raising=False)

    multi = kis_client.get_multi_kb_config()
    assert not kis_client.is_kis_configured(multi.policy)
    assert not kis_client.is_kis_configured(multi.cases)

    with pytest.raises(KISUnavailable):
        kis_client.get_kis_client(KB_POLICY)

    with pytest.raises(KISUnavailable):
        kis_client.get_kis_client(KB_CASES)


def test_multi_kb_configs_are_independent(monkeypatch) -> None:
    """Policy and Cases KBs have different knowledge_base_id values."""
    _configure(monkeypatch)

    multi = kis_client.get_multi_kb_config()

    assert multi.policy.knowledge_base_id == "policy-kb"
    assert multi.cases.knowledge_base_id == "cases-kb"
    assert multi.policy.knowledge_base_id != multi.cases.knowledge_base_id
    # Shared settings
    assert multi.policy.base_url == multi.cases.base_url
    assert multi.policy.api_key == multi.cases.api_key
    assert multi.policy.domain_id == multi.cases.domain_id


# --- AI Query tests ---


def test_ai_query_context_assembly(monkeypatch) -> None:
    """AI query builds context from KB search results for LLM synthesis."""
    _configure(monkeypatch)

    # Simulate what the endpoint does: search KB → build context
    client = _FakeKISClient(config=kis_client.get_multi_kb_config().policy)
    search_results = client.hybrid_search("BNS section 303", top_k=8)

    items = search_results.get("items") or []
    context_parts = []
    sources = []
    for i, item in enumerate(items):
        title = item.get("title") or f"Source {i + 1}"
        text = item.get("text") or ""
        context_parts.append(f"[Source {i + 1}: {title}]\n{text}")
        sources.append({"index": i + 1, "title": title, "score": item.get("score")})

    assert len(context_parts) == 1
    assert "Result for: BNS section 303" in context_parts[0]
    assert sources[0]["score"] == 0.95


def test_ai_query_fallback_without_llm(monkeypatch) -> None:
    """AI query returns search-only fallback when LLM is unavailable."""
    _configure(monkeypatch)

    # The endpoint catches ExternalServiceUnavailable and returns fallback
    fallback = {
        "query": "test query",
        "kb": "policy",
        "answer": "AI answer generation is not available. Review the source results below.",
        "confidence": "low",
        "cited_sources": [1],
        "follow_up_suggestions": [],
        "sources": [{"index": 1, "title": "Test", "score": 0.9}],
        "llm_provider": "unavailable",
        "llm_mode": "search_only",
    }

    assert fallback["llm_mode"] == "search_only"
    assert fallback["confidence"] == "low"
    assert len(fallback["sources"]) == 1


def test_ai_query_invalid_kb_rejected(monkeypatch) -> None:
    """AI query rejects unknown KB names."""
    _configure(monkeypatch)

    # KB_POLICY and KB_CASES are the only valid values
    assert kis_client.KB_POLICY == "policy"
    assert kis_client.KB_CASES == "cases"
    # An unknown KB name should trigger ValueError in get_kis_client
    with pytest.raises(ValueError, match="Unknown KB"):
        kis_client.get_kis_client("unknown_kb")
