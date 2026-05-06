from __future__ import annotations

from typing import Any

from src.core.errors import KISError
from src.state import STORE, new_id, utcnow


def create_ontology_type(
    *,
    domain_id: str,
    knowledge_base_id: str,
    name: str,
    description: str,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise KISError("ONTOLOGY_NAME_REQUIRED", "Ontology type name is required.", status_code=422)
    row = {
        "id": new_id("ont"),
        "domain_id": domain_id,
        "knowledge_base_id": knowledge_base_id,
        "name": name,
        "description": description,
        "schema": schema or {},
        "created_at": utcnow(),
    }
    STORE.ontology_types[row["id"]] = row
    return row


def list_ontology_types(domain_id: str, knowledge_base_id: str) -> list[dict[str, Any]]:
    return [
        row
        for row in STORE.ontology_types.values()
        if row["domain_id"] == domain_id and row["knowledge_base_id"] == knowledge_base_id
    ]


def validate_type(domain_id: str, knowledge_base_id: str, type_name: str) -> None:
    if not any(
        row
        for row in STORE.ontology_types.values()
        if row["domain_id"] == domain_id
        and row["knowledge_base_id"] == knowledge_base_id
        and row["name"] == type_name
    ):
        raise KISError("ONTOLOGY_TYPE_UNKNOWN", f"Unknown ontology type: {type_name}", status_code=422)
