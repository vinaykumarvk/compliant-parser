from __future__ import annotations

"""Governance helpers for AI prompt/knowledge-base promotion workflows."""

from typing import Any


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def validate_kb_entry(entry_type: Any, title: str | None, content: dict | None) -> dict[str, Any]:
    """Run deterministic validation checks before Production promotion."""
    entry_type_value = _value(entry_type)
    content = content or {}
    tests = [
        {"name": "title_present", "passed": bool((title or "").strip())},
        {"name": "content_present", "passed": bool(content)},
        {
            "name": "change_description_present",
            "passed": bool(content.get("change_description") or content.get("rationale")),
        },
    ]
    if entry_type_value == "Checklist":
        items = content.get("items") or content.get("checklist")
        tests.append({"name": "checklist_items_present", "passed": isinstance(items, list) and bool(items)})
    if entry_type_value == "SOP":
        tests.append({"name": "sop_steps_present", "passed": bool(content.get("steps") or content.get("procedure"))})
    if entry_type_value == "Template":
        tests.append({"name": "template_body_present", "passed": bool(content.get("template_body") or content.get("body"))})

    passed = all(test["passed"] for test in tests)
    return {
        "passed": passed,
        "tests": tests,
        "validation_status": "Passed" if passed else "Failed",
    }


def validate_kb_promotion(current_status: Any, target_status: str, validation_status: str | None) -> None:
    """Raise ValueError when a KB entry promotion violates governance flow."""
    status = _value(current_status)
    if target_status not in {"Staging", "Production"}:
        raise ValueError("target_status must be Staging or Production.")
    if target_status == "Staging":
        if status not in {"Draft", "Staging"}:
            raise ValueError("Only Draft or Staging entries can be promoted to Staging.")
        return
    if status != "Staging":
        raise ValueError("Production promotion requires the entry to be in Staging status.")
    if validation_status != "Passed":
        raise ValueError("Production promotion requires a passed validation report.")
