from __future__ import annotations

from typing import Any

from src.state import STORE


def graph_search(domain_id: str, knowledge_base_id: str, query: str) -> dict[str, Any]:
    needle = query.lower()
    nodes = [
        node
        for node in STORE.graph_nodes.values()
        if node["domain_id"] == domain_id
        and node["knowledge_base_id"] == knowledge_base_id
        and needle in node["label"].lower()
    ]
    node_ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in STORE.graph_edges.values()
        if edge["domain_id"] == domain_id
        and edge["knowledge_base_id"] == knowledge_base_id
        and (edge["source_node_id"] in node_ids or edge["target_node_id"] in node_ids or needle in edge["predicate"].lower())
    ]
    return {"nodes": nodes, "edges": edges}


def graph_stats(domain_id: str, knowledge_base_id: str) -> dict[str, int]:
    nodes = [
        node
        for node in STORE.graph_nodes.values()
        if node["domain_id"] == domain_id and node["knowledge_base_id"] == knowledge_base_id
    ]
    edges = [
        edge
        for edge in STORE.graph_edges.values()
        if edge["domain_id"] == domain_id and edge["knowledge_base_id"] == knowledge_base_id
    ]
    return {"node_count": len(nodes), "edge_count": len(edges)}
