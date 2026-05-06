from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProtectedText:
    text: str
    summary: dict[str, Any]


def _fallback_mask(text: str) -> ProtectedText:
    patterns = {
        "phone": r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)",
        "email": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "aadhaar": r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)",
        "vehicle_number": r"\b[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,3}[-\s]?\d{4}\b",
    }
    masked = text
    counts: dict[str, int] = {}
    for pii_type, pattern in patterns.items():
        matches = list(re.finditer(pattern, masked, re.IGNORECASE))
        for index, match in enumerate(reversed(matches), start=1):
            token = f"[[PII_{pii_type.upper()}_{index:04d}]]"
            masked = masked[: match.start()] + token + masked[match.end() :]
        if matches:
            counts[pii_type] = len(matches)
    return ProtectedText(
        masked,
        {
            "pii_redacted_before_llm": bool(counts),
            "raw_pii_sent_to_llm": False,
            "redaction_count": sum(counts.values()),
            "redactions_by_type": counts,
        },
    )


def protect_text_for_provider(text: str, *, context: str = "embedding") -> ProtectedText:
    try:
        from privacy import protect_for_llm

        _, protected, pii_context = protect_for_llm("", text)
        summary = pii_context.metadata()
        summary["provider_context"] = context
        return ProtectedText(protected, summary)
    except Exception:
        protected = _fallback_mask(text)
        protected.summary["provider_context"] = context
        return protected


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
