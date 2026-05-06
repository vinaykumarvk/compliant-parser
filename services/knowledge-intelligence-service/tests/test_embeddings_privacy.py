from __future__ import annotations

from src.config import Settings
from src.pipeline.embeddings import embed_text


def test_embedding_payload_is_masked_before_provider_call() -> None:
    text = "Complainant phone 9876543210 reported vehicle TS09AB1234 stolen."

    result = embed_text("d1", text, settings=Settings(embedding_dimensions=16))

    assert "9876543210" not in result.masked_text
    assert "TS09AB1234" not in result.masked_text
    assert "[[PII_" in result.masked_text
    assert result.privacy_summary["raw_pii_sent_to_llm"] is False
    assert len(result.vector) == 16
