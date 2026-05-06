from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

from src.config import Settings
from src.llm.router import embedding_provider_for_settings, record_usage
from src.privacy.pii import protect_text_for_provider, text_hash


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    masked_text: str
    privacy_summary: dict[str, Any]
    provider: str
    model: str


def deterministic_embedding(text: str, *, dimensions: int = 32) -> list[float]:
    vector = [0.0] * dimensions
    tokens = re.findall(r"[\w\[\]_]+", text.lower())
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def embed_text(domain_id: str, text: str, *, settings: Settings) -> EmbeddingResult:
    protected = protect_text_for_provider(text, context="embedding")
    provider = embedding_provider_for_settings(settings)
    vector = provider.embed(protected.text, dimensions=settings.embedding_dimensions)
    record_usage(
        domain_id=domain_id,
        provider=provider.provider,
        model=provider.model,
        purpose="embedding",
        input_hash=text_hash(protected.text),
        metadata={"privacy": protected.summary, "raw_payload_stored": False},
    )
    return EmbeddingResult(
        vector=vector,
        masked_text=protected.text,
        privacy_summary=protected.summary,
        provider=provider.provider,
        model=provider.model,
    )
