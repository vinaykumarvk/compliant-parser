# -*- coding: utf-8 -*-
"""OCR enhancement utilities for the IQW platform.

Urdu language detection, per-segment confidence tagging, OCR noise
cleanup, and acknowledgement tracking for low-confidence segments.
"""

from __future__ import annotations

import re
import string
import unicodedata
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "acknowledge_ocr",
    "classify_confidence",
    "clean_urdu_noise",
    "detect_language_enhanced",
    "detect_urdu",
    "get_acknowledgement_status",
    "build_ocr_review_payload",
    "requires_acknowledgement",
    "tag_segment_confidence",
]

# ---------------------------------------------------------------------------
# Unicode ranges for script detection
# ---------------------------------------------------------------------------
_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_TELUGU_RE = re.compile(r"[\u0C00-\u0C7F]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# Threshold: fraction of alphabetic chars that must be Arabic-script
_URDU_THRESHOLD = 0.40

# Patterns that indicate OCR garbage
_GARBAGE_PATTERNS = re.compile(
    r"[^\x20-\x7E\u0600-\u06FF\u0900-\u097F\u0C00-\u0C7F\n\r\t]"
)
_REPEATED_PUNCT = re.compile(r"[!?.,:;]{4,}")
_BROKEN_LIGATURE_RE = re.compile(r"[\u0600-\u06FF]\s{2,}[\u0600-\u06FF]")

# Segment splitting: newline paragraphs or sentence boundaries
_SEGMENT_SPLIT = re.compile(r"\n{2,}|(?<=[.!?؟۔])\s+")

# Urdu diacritics (tashkeel) that OCR engines frequently misplace
_URDU_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670]")
# Zero-width joiners / non-joiners that break ligatures
_ZW_JOINERS = re.compile(r"[\u200C\u200D]")


# =========================================================================
# 1. Urdu language detection
# =========================================================================

def detect_urdu(text: str) -> bool:
    """Return *True* if *text* contains substantial Urdu/Arabic-script content."""
    if not text or not text.strip():
        return False
    alpha_chars = [ch for ch in text if unicodedata.category(ch).startswith("L")]
    if not alpha_chars:
        return False
    arabic_count = sum(1 for ch in alpha_chars if _ARABIC_SCRIPT_RE.match(ch))
    return (arabic_count / len(alpha_chars)) >= _URDU_THRESHOLD


def _script_ratio(text: str) -> Dict[str, float]:
    """Return fraction of letter characters belonging to each script."""
    alpha = [ch for ch in text if unicodedata.category(ch).startswith("L")]
    total = len(alpha) or 1
    return {
        "Arabic": sum(1 for c in alpha if _ARABIC_SCRIPT_RE.match(c)) / total,
        "Devanagari": sum(1 for c in alpha if _DEVANAGARI_RE.match(c)) / total,
        "Telugu": sum(1 for c in alpha if _TELUGU_RE.match(c)) / total,
        "Latin": sum(1 for c in alpha if _LATIN_RE.match(c)) / total,
    }


def detect_language_enhanced(text: str) -> dict:
    """Detect dominant language and script with a confidence score.

    Returns ``{"language": ..., "confidence": ..., "script": ...}``.
    """
    if not text or not text.strip():
        return {"language": "unknown", "confidence": 0.0, "script": "Unknown"}

    ratios = _script_ratio(text)
    best_script = max(ratios, key=ratios.get)  # type: ignore[arg-type]
    confidence = round(ratios[best_script], 3)

    script_to_lang = {
        "Arabic": "ur",
        "Devanagari": "hi",
        "Telugu": "te",
        "Latin": "en",
    }
    language = script_to_lang.get(best_script, "unknown")
    return {"language": language, "confidence": confidence, "script": best_script}


# =========================================================================
# 2 & 3. Confidence classification and per-segment tagging
# =========================================================================

def classify_confidence(segment_text: str) -> str:
    """Classify a text segment as ``High``, ``Medium``, or ``Low``.

    Low: >20% garbage chars, very short, or mostly punctuation.
    Medium: some suspicious patterns but mostly legible.
    High: clean text with good character distribution.
    """
    text = segment_text.strip()
    if not text:
        return "Low"

    length = len(text)
    if length < 5:
        return "Low"

    # Ratio of non-printable / garbage characters
    garbage_count = len(_GARBAGE_PATTERNS.findall(text))
    garbage_ratio = garbage_count / length

    # Punctuation-heavy check
    printable_non_space = [ch for ch in text if not ch.isspace()]
    if printable_non_space:
        punct_ratio = sum(
            1 for ch in printable_non_space if ch in string.punctuation or ch in "؟۔،"
        ) / len(printable_non_space)
    else:
        punct_ratio = 1.0

    # Repeated-punctuation noise
    has_repeated_punct = bool(_REPEATED_PUNCT.search(text))

    if garbage_ratio > 0.20 or punct_ratio > 0.60 or has_repeated_punct:
        return "Low"

    if garbage_ratio > 0.08 or punct_ratio > 0.35:
        return "Medium"

    return "High"


def tag_segment_confidence(
    text: str,
    source: str = "ocr",
) -> List[dict]:
    """Split *text* into segments and tag each with a confidence level.

    Each segment dict: text, confidence, source, char_start, char_end.
    """
    if not text:
        return []

    parts = _SEGMENT_SPLIT.split(text)
    segments: List[dict] = []
    cursor = 0

    for part in parts:
        part_stripped = part.strip()
        if not part_stripped:
            cursor += len(part)
            continue

        start = text.index(part_stripped, cursor)
        end = start + len(part_stripped)

        segments.append({
            "text": part_stripped,
            "confidence": classify_confidence(part_stripped),
            "source": source,
            "char_start": start,
            "char_end": end,
        })
        cursor = end

    return segments


# =========================================================================
# 4. Acknowledgement tracking (in-memory)
# =========================================================================

_acknowledgements: Dict[str, dict] = {}


def acknowledge_ocr(
    document_id: str,
    user_id: str,
    segments: Optional[List[int]] = None,
) -> dict:
    """Mark OCR segments as human-reviewed.

    *segments*: zero-based indices to acknowledge (``None`` = all).
    Returns the updated acknowledgement record.
    """
    now = datetime.now(timezone.utc).isoformat()
    record = _acknowledgements.get(document_id, {
        "document_id": document_id,
        "acknowledged_segments": [],
        "history": [],
    })

    entry = {"user_id": user_id, "timestamp": now, "segments": segments}
    record["history"].append(entry)

    if segments is not None:
        existing = set(record["acknowledged_segments"])
        existing.update(segments)
        record["acknowledged_segments"] = sorted(existing)
    else:
        record["acknowledged_segments"] = "all"

    record["last_updated"] = now
    _acknowledgements[document_id] = record
    return record


def get_acknowledgement_status(document_id: str) -> Optional[dict]:
    """Return the acknowledgement record for *document_id*, or ``None``."""
    return _acknowledgements.get(document_id)


def requires_acknowledgement(segments: List[dict]) -> bool:
    """Return ``True`` if any segment has ``Low`` confidence."""
    return any(seg.get("confidence") == "Low" for seg in segments)


def build_ocr_review_payload(document_id: str, extracted_text: str, original_label: str = "") -> dict:
    """Build the three-pane OCR review payload expected by the UI."""
    language = detect_language_enhanced(extracted_text)
    segments = tag_segment_confidence(extracted_text, source="ocr")
    return {
        "document_id": document_id,
        "language": language,
        "panes": {
            "original": {"label": original_label or document_id},
            "extracted_text": extracted_text,
            "english_translation": extracted_text if language["language"] == "en" else "[translation pending review]",
        },
        "segments": segments,
        "requires_acknowledgement": requires_acknowledgement(segments),
        "latency_target_ms_per_page": 5000,
    }


# =========================================================================
# 5. Urdu OCR noise cleanup
# =========================================================================

def clean_urdu_noise(text: str) -> str:
    """Remove common Urdu OCR artifacts (diacritics, broken ligatures, stray Latin chars)."""
    if not text:
        return text

    # Strip stray diacritics
    cleaned = _URDU_DIACRITICS.sub("", text)

    # Remove zero-width joiners that disrupt ligatures
    cleaned = _ZW_JOINERS.sub("", cleaned)

    # Collapse extraneous spaces between Arabic-script characters
    cleaned = _BROKEN_LIGATURE_RE.sub(
        lambda m: m.group(0).replace(" ", ""), cleaned
    )

    # Remove isolated single Latin characters surrounded by Urdu text
    cleaned = re.sub(
        r"(?<=[\u0600-\u06FF])\s*[A-Za-z]\s*(?=[\u0600-\u06FF])",
        " ",
        cleaned,
    )

    # Normalise multiple spaces to one
    cleaned = re.sub(r" {2,}", " ", cleaned)

    return cleaned.strip()
