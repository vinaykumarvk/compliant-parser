from __future__ import annotations

from typing import Any

from src.graph.query import graph_search
from src.state import STORE


def graph_fact_search(domain_id: str, knowledge_base_id: str, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    graph = graph_search(domain_id, knowledge_base_id, query)
    results: list[dict[str, Any]] = []
    node_labels = {node["id"]: node["label"] for node in STORE.graph_nodes.values()}
    for edge in graph["edges"]:
        results.append(
            {
                "id": edge["id"],
                "source": "graph",
                "score": round(float(edge.get("confidence", 0.5)), 6),
                "text": f"{node_labels.get(edge['source_node_id'], edge['source_node_id'])} {edge['predicate']} {node_labels.get(edge['target_node_id'], edge['target_node_id'])}",
                "citation": edge.get("citation", {}),
                "privacy_summary": {"raw_pii_sent_to_llm": False},
            }
        )
    for fact in STORE.facts.values():
        if fact["domain_id"] != domain_id or fact["knowledge_base_id"] != knowledge_base_id or fact["status"] != "approved":
            continue
        text = f"{fact['subject']} {fact['predicate']} {fact['object']}"
        if any(term.lower() in text.lower() for term in query.split()):
            results.append(
                {
                    "id": fact["id"],
                    "source": "fact",
                    "score": round(float(fact.get("confidence", 0.5)), 6),
                    "text": text,
                    "citation": fact.get("citation", {}),
                    "privacy_summary": {"raw_pii_sent_to_llm": False},
                }
            )
    return sorted(results, key=lambda row: row["score"], reverse=True)[:limit]
