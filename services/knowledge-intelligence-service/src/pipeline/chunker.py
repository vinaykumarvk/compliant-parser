from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    text: str
    start_token: int
    end_token: int


def chunk_text(text: str, *, chunk_size: int = 160, overlap: int = 30) -> list[TextChunk]:
    words = [word for word in text.split() if word]
    if not words:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    chunks: list[TextChunk] = []
    start = 0
    ordinal = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(TextChunk(ordinal=ordinal, text=" ".join(words[start:end]), start_token=start, end_token=end))
        ordinal += 1
        if end == len(words):
            break
        start = end - overlap
    return chunks
