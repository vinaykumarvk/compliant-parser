from __future__ import annotations

import pytest

from src.core.errors import KISError
from src.prompts.registry import create_prompt, render_prompt, resolve_prompt, set_prompt_status


def test_prompt_version_lifecycle_and_rendering() -> None:
    prompt = create_prompt(
        domain_id="d1",
        knowledge_base_id="kb1",
        name="fir_bns_mapping",
        template="Map {{ complaint_text }} with {{ context }}",
    )

    with pytest.raises(KISError):
        set_prompt_status(prompt["id"], "active")

    approved = set_prompt_status(prompt["id"], "approved")
    active = set_prompt_status(prompt["id"], "active")
    resolved = resolve_prompt("d1", "kb1", "fir_bns_mapping")

    assert approved["status"] == "active"
    assert active["id"] == prompt["id"]
    assert resolved["version"] == 1
    assert render_prompt(active["template"], {"complaint_text": "theft", "context": "BNS-303"}) == "Map theft with BNS-303"
