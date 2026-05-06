from __future__ import annotations

from typing import Any

from src.state import STORE, new_id, utcnow


def _actionable_broken_links(article: dict[str, Any]) -> list[str]:
    return [link for link in article.get("broken_links", []) if not str(link).startswith("PII_")]


def run_quality_gates(domain_id: str, knowledge_base_id: str) -> dict[str, Any]:
    wiki_articles = [
        article
        for article in STORE.wiki_articles.values()
        if article["domain_id"] == domain_id and article["knowledge_base_id"] == knowledge_base_id
    ]
    facts = [
        fact
        for fact in STORE.facts.values()
        if fact["domain_id"] == domain_id and fact["knowledge_base_id"] == knowledge_base_id
    ]
    eval_sets = [
        item
        for item in STORE.evaluation_sets.values()
        if item["domain_id"] == domain_id and item["knowledge_base_id"] == knowledge_base_id
    ]
    checks = [
        {
            "name": "citation_coverage",
            "passed": all(article.get("citations") for article in wiki_articles) if wiki_articles else False,
        },
        {
            "name": "broken_wiki_links",
            "passed": all(not _actionable_broken_links(article) for article in wiki_articles),
        },
        {
            "name": "low_confidence_graph_edges",
            "passed": all(edge.get("confidence", 0.0) >= 0.5 for edge in STORE.graph_edges.values() if edge["domain_id"] == domain_id),
        },
        {
            "name": "active_fact_contradictions",
            "passed": len({(fact["subject"], fact["predicate"], fact["object"]) for fact in facts}) == len(facts),
        },
        {
            "name": "required_evaluation_set",
            "passed": bool(eval_sets),
        },
    ]
    passed = all(check["passed"] for check in checks)
    report = {"passed": passed, "checks": checks, "created_at": utcnow()}
    if not passed:
        STORE.audit_events.append(
            {
                "id": new_id("audit"),
                "domain_id": domain_id,
                "actor_id": "quality-gates",
                "action": "quality_gates.fail",
                "resource_type": "knowledge_base",
                "resource_id": knowledge_base_id,
                "metadata": report,
                "created_at": utcnow(),
            }
        )
    return report
