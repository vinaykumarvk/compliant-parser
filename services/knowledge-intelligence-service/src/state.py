from __future__ import annotations

import uuid
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@dataclass
class InMemoryKISStore:
    domains: dict[str, dict[str, Any]] = field(default_factory=dict)
    memberships: dict[str, dict[str, Any]] = field(default_factory=dict)
    knowledge_bases: dict[str, dict[str, Any]] = field(default_factory=dict)
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    credentials: dict[str, dict[str, Any]] = field(default_factory=dict)
    prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    legal_holds: dict[str, dict[str, Any]] = field(default_factory=dict)
    deletion_requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    idempotency_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    retrieval_logs: list[dict[str, Any]] = field(default_factory=list)
    ontology_types: dict[str, dict[str, Any]] = field(default_factory=dict)
    facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    graph_nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    graph_edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    wiki_articles: dict[str, dict[str, Any]] = field(default_factory=dict)
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    evaluation_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    evaluation_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    feedback_items: dict[str, dict[str, Any]] = field(default_factory=dict)
    reasoning_patterns: dict[str, dict[str, Any]] = field(default_factory=dict)
    reasoning_runs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def reset(self) -> None:
        for value in self.__dict__.values():
            value.clear()

    def export_payload(self) -> dict[str, Any]:
        return copy.deepcopy({
            key: value
            for key, value in self.__dict__.items()
            if isinstance(value, (dict, list))
        })

    def import_payload(self, payload: dict[str, Any]) -> None:
        self.reset()
        for key, current in self.__dict__.items():
            value = payload.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                current.update(value)
            elif isinstance(current, list) and isinstance(value, list):
                current.extend(value)


STORE = InMemoryKISStore()
