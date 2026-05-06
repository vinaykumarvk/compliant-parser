from __future__ import annotations

from typing import Any, Optional


TEMPLATES: dict[str, dict[str, Any]] = {
    "police_iqw_bns": {
        "id": "police_iqw_bns",
        "name": "Police IQW BNS",
        "description": "Bharatiya Nyaya Sanhita knowledge base template for FIR drafting and BNS mapping.",
        "retrieval_profile": {
            "vector_weight": 0.45,
            "graph_weight": 0.25,
            "fact_weight": 0.20,
            "wiki_weight": 0.10,
            "required_sources": ["vector"],
        },
        "ontology_seeds": [
            {"name": "legal_section", "description": "BNS or IPC section"},
            {"name": "offence_ingredient", "description": "Required legal ingredient for an offence"},
        ],
        "prompt_seeds": [
            {
                "name": "fir_bns_mapping",
                "version": 1,
                "status": "active",
                "template": (
                    "Map complaint facts to BNS sections using only cited KIS context.\n\n"
                    "Complaint:\n{{ complaint_text }}\n\n"
                    "KIS context:\n{{ context }}"
                ),
            }
        ],
        "reasoning_seeds": [
            {
                "name": "fir_bns_mapping",
                "prompt_name": "fir_bns_mapping",
                "status": "active",
                "output_schema": {
                    "primary_sections": "list",
                    "alternative_sections": "list",
                    "hidden_below_threshold": "integer",
                },
            }
        ],
        "evaluation_seeds": [
            {
                "name": "bns_smoke",
                "cases": [
                    {
                        "query": "Motorcycle stolen from parking area",
                        "expected_sections": ["BNS-303"],
                    }
                ],
            }
        ],
    },
    "ps_wms_advisory": {
        "id": "ps_wms_advisory",
        "name": "PS-WMS Advisory",
        "description": "Migration-compatible advisory knowledge template from PS-WMS intelligence service.",
        "retrieval_profile": {
            "vector_weight": 0.40,
            "graph_weight": 0.30,
            "fact_weight": 0.20,
            "wiki_weight": 0.10,
            "required_sources": ["vector"],
        },
        "ontology_seeds": [
            {"name": "advisory_topic", "description": "PS-WMS advisory topic"},
            {"name": "policy_rule", "description": "Operational policy or rule"},
        ],
        "prompt_seeds": [],
        "evaluation_seeds": [],
    },
}


def list_templates() -> list[dict[str, Any]]:
    return [dict(template) for template in TEMPLATES.values()]


def get_template(template_id: str) -> Optional[dict[str, Any]]:
    template = TEMPLATES.get(template_id)
    return dict(template) if template else None
