from __future__ import annotations

from typing import Any

from src.core.errors import KISError
from src.state import STORE, new_id, utcnow


def _node_key(domain_id: str, knowledge_base_id: str, label: str) -> tuple[str, str, str]:
    return (domain_id, knowledge_base_id, label.lower().strip())


def _upsert_node(domain_id: str, knowledge_base_id: str, label: str, type_name: str = "concept") -> dict[str, Any]:
    for node in STORE.graph_nodes.values():
        if _node_key(domain_id, knowledge_base_id, label) == _node_key(node["domain_id"], node["knowledge_base_id"], node["label"]):
            return node
    node = {
        "id": new_id("node"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "label": label,
        "type_name": type_name,
        "created_at": utcnow(),
    }
    STORE.graph_nodes[node["id"]] = node
    return node


def promote_fact_to_graph(fact_id: str) -> dict[str, Any]:
    fact = STORE.facts.get(fact_id)
    if not fact:
        raise KISError("FACT_NOT_FOUND", "Fact not found.", status_code=404)
    if fact["status"] != "approved":
        raise KISError("FACT_NOT_APPROVED", "Only approved facts can be promoted.", status_code=409)
    source = _upsert_node(fact["domain_id"], fact["knowledge_base_id"], fact["subject"])
    target = _upsert_node(fact["domain_id"], fact["knowledge_base_id"], fact["object"])
    for edge in STORE.graph_edges.values():
        if (
            edge["source_node_id"] == source["id"]
            and edge["target_node_id"] == target["id"]
            and edge["predicate"] == fact["predicate"]
        ):
            return {"source_node": source, "target_node": target, "edge": edge}
    edge = {
        "id": new_id("edge"),
        "domain_id": fact["domain_id"],
        "knowledge_base_id": fact["knowledge_base_id"],
        "source_node_id": source["id"],
        "target_node_id": target["id"],
        "predicate": fact["predicate"],
        "confidence": fact["confidence"],
        "citation": fact.get("citation", {}),
        "source_fact_id": fact["id"],
        "created_at": utcnow(),
    }
    STORE.graph_edges[edge["id"]] = edge
    return {"source_node": source, "target_node": target, "edge": edge}
