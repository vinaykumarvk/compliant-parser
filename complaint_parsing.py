# -*- coding: utf-8 -*-
"""Utilities for multilingual police complaint parsing via Google Document AI."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

try:
    from google.api_core.client_options import ClientOptions
    from google.cloud import documentai
except ImportError:  # pragma: no cover - depends on local optional deps
    ClientOptions = None  # type: ignore[assignment]
    documentai = None  # type: ignore[assignment]

_FIELD_ORDER = ("who", "what", "when", "where", "why", "how")
_LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "unknown": "Unknown",
}
_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_MONTH_PATTERN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH_PATTERN}\s+\d{{2,4}}\b", re.IGNORECASE),
    re.compile(rf"\b{_MONTH_PATTERN}\s+\d{{1,2}},?\s+\d{{2,4}}\b", re.IGNORECASE),
]
_TIME_PATTERNS = [
    re.compile(r"\b\d{1,2}:\d{2}\s*(?:[AP]\.?M\.?)?\b", re.IGNORECASE),
    re.compile(
        r"\b(?:around|about|approx(?:\.|imately)?|at)\s+\d{1,2}(?::\d{2})?\s*(?:[AP]\.?M\.?)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}\s*(?:[AP]\.?M\.?)\b", re.IGNORECASE),
]
_ROLE_LABELS = {
    "complainant": [
        "complainant",
        "complainant name",
        "name of complainant",
        "informant",
        "applicant",
        "petitioner",
        "reporter",
    ],
    "victim": [
        "victim",
        "victim name",
        "name of victim",
        "aggrieved person",
        "injured person",
    ],
    "accused": [
        "accused",
        "accused name",
        "name of accused",
        "suspect",
        "suspects",
        "offender",
        "assailant",
    ],
    "witnesses": [
        "witness",
        "witnesses",
        "witness name",
        "name of witness",
        "eye witness",
    ],
}
_WHAT_LABELS = [
    "subject",
    "complaint",
    "incident",
    "nature of complaint",
    "nature of offence",
    "nature of offense",
    "offence",
    "offense",
    "allegation",
    "facts of complaint",
]
_WHEN_LABELS = [
    "date and time of incident",
    "date of incident",
    "time of incident",
    "when",
    "occurrence time",
    "incident time",
]
_WHERE_LABELS = [
    "place of occurrence",
    "place of incident",
    "place",
    "location",
    "address",
    "scene of offence",
    "scene of offense",
    "where",
]
_WHY_LABELS = [
    "reason",
    "motive",
    "cause",
    "why",
]
_HOW_LABELS = [
    "how",
    "manner",
    "modus operandi",
    "method",
]
_INCIDENT_KEYWORDS = {
    "theft": 3.2,
    "stolen": 3.0,
    "stole": 2.8,
    "snatched": 2.8,
    "assault": 3.1,
    "assaulted": 3.1,
    "fraud": 3.0,
    "cheating": 2.8,
    "cheated": 2.8,
    "harassment": 2.6,
    "threatened": 2.6,
    "threat": 2.2,
    "robbery": 3.1,
    "robbed": 3.1,
    "burglary": 3.0,
    "kidnapped": 3.2,
    "kidnapping": 3.2,
    "murder": 3.2,
    "forgery": 2.7,
    "forged": 2.7,
    "rape": 3.3,
    "molestation": 3.0,
    "trespass": 2.4,
    "attack": 2.6,
    "beaten": 2.4,
    "hit": 1.7,
    "missing": 1.7,
    "lost": 1.6,
    "incident": 1.2,
    "complaint": 0.9,
    "offence": 1.1,
    "offense": 1.1,
    "crime": 1.0,
}
_WHY_KEYWORDS = (
    "because",
    "due to",
    "owing to",
    "motive",
    "reason",
    "grudge",
    "revenge",
    "enmity",
    "for money",
    "to extort",
    "suspected",
    "appears to be",
    "seems to be",
)
_HOW_KEYWORDS = (
    "by ",
    "through",
    "using",
    "via ",
    "took ",
    "taken from",
    "removed from",
    "snatched from",
    "from pocket",
    "breaking",
    "entered",
    "posing as",
    "forged",
    "threatening",
)
_LOCATION_HINTS = (
    "road",
    "street",
    "lane",
    "market",
    "bus stand",
    "bus stop",
    "station",
    "village",
    "town",
    "district",
    "mandal",
    "area",
    "colony",
    "house",
    "home",
    "office",
    "shop",
    "bank",
    "school",
    "college",
    "junction",
    "circle",
    "cross",
    "layout",
    "apartment",
    "flat",
    "building",
    "temple",
    "mosque",
    "church",
)
_NON_LOCATION_HINTS = (
    "pocket",
    "bag",
    "wallet",
    "mobile",
    "phone",
    "neck",
    "hand",
    "finger",
    "vehicle",
)
_UNKNOWN_ACTOR_PATTERNS = (
    "unknown accused",
    "unknown person",
    "unknown persons",
    "unknown suspect",
    "unidentified person",
    "unidentified persons",
)
_COMPLAINT_INDICATORS = {
    "complaint": 1.1,
    "police": 1.1,
    "fir": 1.3,
    "accused": 1.0,
    "victim": 0.9,
    "complainant": 1.0,
    "incident": 0.8,
    "offence": 1.0,
    "offense": 1.0,
    "stolen": 1.1,
    "theft": 1.1,
    "assault": 1.1,
    "fraud": 1.1,
    "harassment": 1.0,
}


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into process environment."""
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def process_document_sample(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
    field_mask: Optional[str] = None,
    processor_version_id: Optional[str] = None,
) -> documentai.ProcessResponse:
    with open(file_path, "rb") as image:
        image_content = image.read()

    return process_document_bytes(
        project_id=project_id,
        location=location,
        processor_id=processor_id,
        content=image_content,
        mime_type=mime_type,
        field_mask=field_mask,
        processor_version_id=processor_version_id,
    )


def process_document_bytes(
    project_id: str,
    location: str,
    processor_id: str,
    content: bytes,
    mime_type: str,
    field_mask: Optional[str] = None,
    processor_version_id: Optional[str] = None,
) -> documentai.ProcessResponse:
    if ClientOptions is None or documentai is None:
        raise RuntimeError(
            "google-cloud-documentai is not installed. Install dependencies from requirements.txt."
        )
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    if processor_version_id:
        name = client.processor_version_path(
            project_id, location, processor_id, processor_version_id
        )
    else:
        name = client.processor_path(project_id, location, processor_id)

    raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
    request = documentai.ProcessRequest(
        name=name,
        raw_document=raw_document,
        field_mask=field_mask,
    )
    return client.process_document(request=request)


def get_translation_config() -> dict[str, Any]:
    return {
        "enabled": _is_env_true("TRANSLATION_ENABLED", True),
        "project_id": _clean_env_value(os.getenv("TRANSLATION_PROJECT_ID"))
        or _clean_env_value(os.getenv("DOC_AI_PROJECT_ID")),
        "location": _clean_env_value(os.getenv("TRANSLATION_LOCATION")) or "global",
        "target_language": _clean_env_value(os.getenv("TRANSLATION_TARGET_LANGUAGE"))
        or "en",
    }


def normalize_lines(raw: str) -> list[str]:
    normalized = _normalize_whitespace(raw)
    if not normalized:
        return []
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def _clean_env_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned or None


def _is_env_true(key: str, default: bool) -> bool:
    raw = _clean_env_value(os.getenv(key))
    if raw is None:
        return default
    return raw.lower() in _TRUE_VALUES


def _normalize_language_code(code: Optional[str]) -> str:
    normalized = (code or "").strip().lower()
    if "-" in normalized:
        normalized = normalized.split("-", 1)[0]
    return normalized if normalized in _LANGUAGE_NAMES else "unknown"


def _normalize_whitespace(text: str) -> str:
    value = (text or "").replace("\r", "\n")
    value = value.replace("\u00a0", " ").replace("\u200c", " ").replace("\u200d", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _split_sentences(text: str) -> list[str]:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return []
    parts = re.split(r"(?:\n+|(?<=[.!?])\s+)", normalized)
    sentences = []
    for part in parts:
        candidate = _clean_extracted_value(part)
        if candidate:
            sentences.append(candidate)
    return sentences


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _clean_extracted_value(value: Any) -> Optional[str]:
    cleaned = _normalize_whitespace(str(value or ""))
    if not cleaned:
        return None
    cleaned = cleaned.strip(" \t-:;,.|•")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None
    if not re.search(r"[A-Za-z\u0900-\u097F\u0C00-\u0C7F0-9]", cleaned):
        return None
    return cleaned


def _clean_name_fragment(value: Any) -> Optional[str]:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return None
    cleaned = re.sub(
        r"\b(?:resident|residing|address|aged|age|years|year|s/o|d/o|w/o|r/o|occupation)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" ,;:-")
    if not cleaned:
        return None
    if _is_unknown_actor(cleaned):
        return _standardize_unknown_actor(cleaned)
    words = cleaned.split()
    if len(words) > 8:
        return None
    if not re.search(r"[A-Za-z]", cleaned):
        return None
    return cleaned


def _standardize_unknown_actor(value: str) -> str:
    lowered = value.lower()
    if "accused" in lowered:
        return "Unknown accused"
    if "suspect" in lowered:
        return "Unknown suspect"
    return "Unknown person"


def _is_unknown_actor(value: str) -> bool:
    lowered = value.lower()
    return any(pattern in lowered for pattern in _UNKNOWN_ACTOR_PATTERNS)


def _split_people_value(value: str) -> list[str]:
    if _is_unknown_actor(value):
        return [_standardize_unknown_actor(value)]
    parts = re.split(r"\s*(?:,|/|\band\b)\s*", value, flags=re.IGNORECASE)
    names = []
    for part in parts:
        cleaned = _clean_name_fragment(part)
        if cleaned:
            names.append(cleaned)
    return _dedupe_keep_order(names)


def _extract_labeled_values(lines: list[str], labels: list[str], max_matches: int = 5) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    if not lines:
        return matches

    label_patterns = [
        re.escape(label).replace(r"\ ", r"\s+")
        for label in labels
    ]
    for index, raw_line in enumerate(lines):
        line = _normalize_whitespace(raw_line)
        if not line:
            continue
        for label_pattern in label_patterns:
            exact_match = re.fullmatch(label_pattern, line, re.IGNORECASE)
            if exact_match:
                if index + 1 < len(lines):
                    value = _clean_extracted_value(lines[index + 1])
                    if value:
                        matches.append((value, line))
                continue

            inline_match = re.match(
                rf"^\s*{label_pattern}\s*(?:[:\-]\s*|\s+)(?P<value>.+)$",
                line,
                re.IGNORECASE,
            )
            if inline_match:
                value = _clean_extracted_value(inline_match.group("value"))
                if value:
                    matches.append((value, line))

        if len(matches) >= max_matches:
            break

    deduped = []
    seen = set()
    for value, evidence in matches:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((value, evidence))
    return deduped


def _collect_pattern_matches(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    matches = []
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            value = _clean_extracted_value(match.group(0))
            if value:
                matches.append(value)
    return _dedupe_keep_order(matches)


def _score_sentence(sentence: str, weighted_keywords: dict[str, float]) -> float:
    lowered = sentence.lower()
    score = 0.0
    for keyword, weight in weighted_keywords.items():
        if keyword in lowered:
            score += weight
    return score


def _pick_best_sentence(
    sentences: list[str],
    weighted_keywords: dict[str, float],
    *,
    extra_score: Optional[callable] = None,
) -> tuple[Optional[str], float]:
    best_sentence = None
    best_score = 0.0
    for sentence in sentences:
        score = _score_sentence(sentence, weighted_keywords)
        if extra_score is not None:
            score += extra_score(sentence)
        if score > best_score:
            best_sentence = sentence
            best_score = score
    return best_sentence, best_score


def _strip_reporting_prefix(value: str) -> str:
    cleaned = value
    cleaned = re.sub(
        r"^(?:i(?:\s+would)?(?:\s+like)?\s+to\s+(?:report|inform|state)|"
        r"this is to\s+(?:report|inform|state)|it is submitted that)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def _detect_language(text: str) -> dict[str, Any]:
    counts = {"en": 0, "hi": 0, "te": 0}
    for char in text or "":
        codepoint = ord(char)
        if 0x0900 <= codepoint <= 0x097F:
            counts["hi"] += 1
        elif 0x0C00 <= codepoint <= 0x0C7F:
            counts["te"] += 1
        elif char.isascii() and char.isalpha():
            counts["en"] += 1

    total = sum(counts.values())
    if total == 0:
        return {
            "language_code": "unknown",
            "confidence_score": 0.0,
            "method": "script_heuristic",
            "counts": counts,
        }

    dominant = max(counts, key=counts.get)
    dominant_share = counts[dominant] / total
    language_code = dominant if dominant_share >= 0.45 else "unknown"
    if dominant in {"hi", "te"} and counts[dominant] >= 6:
        language_code = dominant
    elif dominant == "en" and counts["en"] >= max(counts["hi"], counts["te"]) * 2:
        language_code = "en"

    return {
        "language_code": language_code,
        "confidence_score": round(dominant_share, 2),
        "method": "script_heuristic",
        "counts": counts,
    }


def _chunk_text_for_translation(text: str, max_chars: int = 24000) -> list[str]:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalized) if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            sentence_parts = _split_sentences(paragraph)
            if not sentence_parts:
                sentence_parts = [paragraph]
        else:
            sentence_parts = [paragraph]

        for part in sentence_parts:
            if len(part) > max_chars:
                for index in range(0, len(part), max_chars):
                    chunks.append(part[index : index + max_chars])
                continue

            candidate = part if not current else f"{current}\n\n{part}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = part

    if current:
        chunks.append(current)
    return chunks


def _translate_to_english(text: str, detected_language: str) -> dict[str, Any]:
    normalized_text = _normalize_whitespace(text)
    config = get_translation_config()
    result = {
        "english_text": normalized_text,
        "source_language": detected_language,
        "target_language": config["target_language"],
        "status": "not_needed",
        "provider": "identity",
        "error": None,
    }
    if not normalized_text:
        return result

    if detected_language == "en":
        return result

    if not config["enabled"]:
        result.update({"status": "disabled", "provider": "none"})
        return result

    if not config["project_id"]:
        result.update(
            {
                "status": "unavailable",
                "provider": "google_cloud_translate",
                "error": "Set TRANSLATION_PROJECT_ID or DOC_AI_PROJECT_ID to enable translation.",
            }
        )
        return result

    try:
        from google.cloud import translate
    except ImportError:
        result.update(
            {
                "status": "unavailable",
                "provider": "google_cloud_translate",
                "error": "google-cloud-translate is not installed.",
            }
        )
        return result

    try:
        client = translate.TranslationServiceClient()
        parent = f"projects/{config['project_id']}/locations/{config['location']}"
        chunks = _chunk_text_for_translation(normalized_text)
        translated_chunks = []
        source_language = detected_language if detected_language != "unknown" else None

        for chunk in chunks:
            request: dict[str, Any] = {
                "parent": parent,
                "contents": [chunk],
                "mime_type": "text/plain",
                "target_language_code": config["target_language"],
            }
            if source_language:
                request["source_language_code"] = source_language
            response = client.translate_text(request=request)
            for item in response.translations:
                translated = _normalize_whitespace(getattr(item, "translated_text", ""))
                if translated:
                    translated_chunks.append(translated)
                detected_code = _normalize_language_code(
                    getattr(item, "detected_language_code", None)
                )
                if detected_code != "unknown":
                    source_language = detected_code

        translated_text = "\n\n".join(translated_chunks).strip()
        if translated_text:
            result.update(
                {
                    "english_text": translated_text,
                    "source_language": source_language or detected_language,
                    "status": "translated",
                    "provider": "google_cloud_translate",
                }
            )
            return result

        result.update(
            {
                "status": "failed",
                "provider": "google_cloud_translate",
                "error": "Translation completed but returned no translated text.",
            }
        )
        return result
    except Exception as exc:  # pragma: no cover - depends on live cloud config
        result.update(
            {
                "status": "failed",
                "provider": "google_cloud_translate",
                "error": str(exc),
            }
        )
        return result


def _build_component_payload(
    values: list[str],
    *,
    inferred: bool = False,
) -> dict[str, Any]:
    deduped_values = _dedupe_keep_order(values)
    if not deduped_values:
        return {
            "status": "missing",
            "values": [],
            "confidence_score": 0.0,
            "inferred": inferred,
        }

    generic_only = all(_is_unknown_actor(value) for value in deduped_values)
    if inferred or generic_only:
        status = "uncertain"
        confidence_score = 0.55 if inferred else 0.6
    else:
        status = "present"
        confidence_score = 0.86

    return {
        "status": status,
        "values": deduped_values,
        "confidence_score": confidence_score,
        "inferred": inferred,
    }


def _extract_role_values(
    role: str,
    lines: list[str],
    sentences: list[str],
    english_text: str,
) -> tuple[list[str], list[str], bool]:
    values: list[str] = []
    evidence: list[str] = []
    inferred = False

    for value, line in _extract_labeled_values(lines, _ROLE_LABELS.get(role, []), max_matches=3):
        extracted_people = _split_people_value(value)
        if extracted_people:
            values.extend(extracted_people)
            evidence.append(line)

    if role == "complainant":
        patterns = [
            r"\bmy name is\s+(?P<value>[^,.;\n]+)",
            r"\bi am\s+(?P<value>[^,.;\n]+)",
            r"\bi,\s*(?P<value>[^,.;\n]+?)\s+(?:resident|residing|would like|want to report|am writing)\b",
        ]
    elif role == "victim":
        patterns = [
            r"\bvictim(?: name)?\s*(?:is|was|are|were)?\s*[:\-]?\s*(?P<value>[^,.;\n]+)",
            r"\binjured person\s*(?:is|was)?\s*[:\-]?\s*(?P<value>[^,.;\n]+)",
        ]
    elif role == "accused":
        patterns = [
            r"\baccused(?: person| persons)?\s*(?:is|was|are|were|named|name)?\s*[:\-]?\s*(?P<value>[^.;\n]+)",
            r"\bsuspect(?:s)?\s*(?:is|was|are|were|named|name)?\s*[:\-]?\s*(?P<value>[^.;\n]+)",
            r"\bagainst\s+(?P<value>[^.;\n]+)",
        ]
    else:
        patterns = [
            r"\bwitness(?:es)?\s*(?:is|was|are|were|named|name)?\s*[:\-]?\s*(?P<value>[^.;\n]+)",
            r"\beye witness(?:es)?\s*(?:is|was|are|were)?\s*[:\-]?\s*(?P<value>[^.;\n]+)",
        ]

    for sentence in sentences:
        for pattern in patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if not match:
                continue
            extracted_people = _split_people_value(match.group("value"))
            if extracted_people:
                values.extend(extracted_people)
                evidence.append(sentence)

    if role == "accused":
        for pattern in _UNKNOWN_ACTOR_PATTERNS:
            match = re.search(rf"\b{re.escape(pattern)}\b", english_text, re.IGNORECASE)
            if match:
                values.append(_standardize_unknown_actor(pattern))
                evidence.append(match.group(0))

    if role == "victim" and not values:
        complainant_values, _, _ = _extract_role_values("complainant", lines, sentences[:5], english_text)
        if complainant_values and re.search(r"\bmy\b", english_text, re.IGNORECASE):
            values.extend(complainant_values)
            evidence.append("Victim inferred from first-person complaint narration.")
            inferred = True

    return _dedupe_keep_order(values), _dedupe_keep_order(evidence), inferred


def _make_field_payload(
    value: Optional[str],
    evidence: list[str],
    confidence_score: float,
    *,
    status: Optional[str] = None,
    **extra: Any,
) -> dict[str, Any]:
    cleaned_value = _clean_extracted_value(value) if value else None
    cleaned_evidence = _dedupe_keep_order(
        [item for item in (_clean_extracted_value(entry) for entry in evidence) if item]
    )

    if status is None:
        if not cleaned_value:
            status = "missing"
            confidence_score = 0.0
        elif confidence_score >= 0.72:
            status = "present"
        else:
            status = "uncertain"

    payload: dict[str, Any] = {
        "status": status,
        "value": cleaned_value,
        "confidence_score": round(max(0.0, min(1.0, confidence_score)), 2),
        "evidence": cleaned_evidence,
    }
    payload.update(extra)
    return payload


def _extract_who(lines: list[str], sentences: list[str], english_text: str) -> dict[str, Any]:
    components = {}
    evidence = []
    role_order = ("complainant", "victim", "accused", "witnesses")
    present_components = 0
    uncertain_components = 0

    for role in role_order:
        role_values, role_evidence, inferred = _extract_role_values(
            role, lines, sentences, english_text
        )
        component = _build_component_payload(role_values, inferred=inferred)
        components[role] = component
        evidence.extend(role_evidence)
        if component["status"] == "present":
            present_components += 1
        elif component["status"] == "uncertain":
            uncertain_components += 1

    role_fragments = []
    for role in role_order:
        values = components[role]["values"]
        if values:
            role_fragments.append(f"{role}: {', '.join(values)}")

    if present_components:
        status = "present"
        confidence_score = min(0.95, 0.7 + (present_components * 0.1))
    elif uncertain_components:
        status = "uncertain"
        confidence_score = 0.58
    else:
        status = "missing"
        confidence_score = 0.0

    return _make_field_payload(
        "; ".join(role_fragments) if role_fragments else None,
        evidence,
        confidence_score,
        status=status,
        components=components,
    )


def _extract_what(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _WHAT_LABELS, max_matches=2)
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(
            _strip_reporting_prefix(value),
            [evidence],
            0.9,
            status="present",
        )

    best_sentence, score = _pick_best_sentence(sentences, _INCIDENT_KEYWORDS)
    if not best_sentence:
        return _make_field_payload(None, [], 0.0, status="missing")

    cleaned_sentence = _strip_reporting_prefix(best_sentence)
    if score >= 3.0:
        return _make_field_payload(cleaned_sentence, [best_sentence], 0.84, status="present")
    return _make_field_payload(cleaned_sentence, [best_sentence], 0.58, status="uncertain")


def _extract_when(lines: list[str], sentences: list[str], english_text: str) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _WHEN_LABELS, max_matches=2)
    date_candidates = _collect_pattern_matches(english_text, _DATE_PATTERNS)
    time_candidates = _collect_pattern_matches(english_text, _TIME_PATTERNS)

    evidence = [item[1] for item in labeled_matches]
    best_sentence = next(
        (
            sentence
            for sentence in sentences
            if _collect_pattern_matches(sentence, _DATE_PATTERNS)
            or _collect_pattern_matches(sentence, _TIME_PATTERNS)
        ),
        None,
    )
    if best_sentence:
        evidence.append(best_sentence)

    if labeled_matches:
        value = labeled_matches[0][0]
    elif date_candidates and time_candidates:
        value = f"{date_candidates[0]}; {time_candidates[0]}"
    elif date_candidates:
        value = date_candidates[0]
    elif time_candidates:
        value = time_candidates[0]
    else:
        value = None

    if date_candidates and time_candidates:
        status = "present"
        confidence_score = 0.9
    elif date_candidates or time_candidates:
        status = "uncertain"
        confidence_score = 0.62
    else:
        status = "missing"
        confidence_score = 0.0

    return _make_field_payload(
        value,
        evidence,
        confidence_score,
        status=status,
        components={
            "date": {
                "status": "present" if date_candidates else "missing",
                "value": date_candidates[0] if date_candidates else None,
            },
            "time": {
                "status": "present" if time_candidates else "missing",
                "value": time_candidates[0] if time_candidates else None,
            },
        },
    )


def _trim_temporal_suffix(value: str) -> Optional[str]:
    cleaned = value
    cleaned = re.sub(
        r"\b(?:on|around|about|at about|at approximately|at approx\.?)\b\s+.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    for pattern in _DATE_PATTERNS + _TIME_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return _clean_extracted_value(cleaned)


def _extract_location_fragment(sentence: str) -> Optional[str]:
    patterns = [
        r"\b(?:near|in front of|inside|outside|beside|between)\s+(?P<value>[^.;]+)",
        r"\b(?:at)\s+(?P<value>[^.;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if not match:
            continue
        value = _trim_temporal_suffix(match.group("value"))
        if not value:
            continue
        lowered = value.lower()
        if any(noise in lowered for noise in _NON_LOCATION_HINTS) and not any(
            hint in lowered for hint in _LOCATION_HINTS
        ):
            continue
        return value
    return None


def _where_extra_score(sentence: str) -> float:
    lowered = sentence.lower()
    score = 0.0
    if any(hint in lowered for hint in _LOCATION_HINTS):
        score += 1.4
    if re.search(r"\b(?:at|near|inside|outside|between|beside)\b", lowered):
        score += 0.9
    if _collect_pattern_matches(sentence, _DATE_PATTERNS) or _collect_pattern_matches(sentence, _TIME_PATTERNS):
        score += 0.2
    return score


def _extract_where(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _WHERE_LABELS, max_matches=2)
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(value, [evidence], 0.88, status="present")

    best_sentence, score = _pick_best_sentence(
        sentences,
        {"location": 1.2, "place": 1.0, "scene": 0.9},
        extra_score=_where_extra_score,
    )
    if not best_sentence:
        return _make_field_payload(None, [], 0.0, status="missing")

    fragment = _extract_location_fragment(best_sentence)
    if fragment:
        return _make_field_payload(fragment, [best_sentence], 0.76, status="present")
    if score > 1.2:
        return _make_field_payload(best_sentence, [best_sentence], 0.55, status="uncertain")
    return _make_field_payload(None, [], 0.0, status="missing")


def _extract_reason_fragment(sentence: str) -> Optional[str]:
    patterns = [
        r"\bbecause\s+(?P<value>[^.;]+)",
        r"\bdue to\s+(?P<value>[^.;]+)",
        r"\b(?:motive|reason)\s*(?:is|was|appears to be|seems to be)?\s*(?P<value>[^.;]+)",
        r"\bsuspected\s+(?P<value>[^.;]+)",
        r"\b(?:appears|seems)\s+to\s+be\s+(?P<value>[^.;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return _clean_extracted_value(match.group("value"))
    return None


def _extract_why(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _WHY_LABELS, max_matches=2)
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(value, [evidence], 0.82, status="present")

    candidate_sentences = [
        sentence
        for sentence in sentences
        if any(keyword in sentence.lower() for keyword in _WHY_KEYWORDS)
    ]
    if not candidate_sentences:
        return _make_field_payload(None, [], 0.0, status="missing")

    best_sentence = candidate_sentences[0]
    fragment = _extract_reason_fragment(best_sentence)
    if fragment:
        lowered = best_sentence.lower()
        if "suspected" in lowered:
            return _make_field_payload(fragment, [best_sentence], 0.56, status="uncertain")
        return _make_field_payload(fragment, [best_sentence], 0.78, status="present")
    return _make_field_payload(best_sentence, [best_sentence], 0.48, status="uncertain")


def _extract_method_fragment(sentence: str) -> Optional[str]:
    patterns = [
        r"\b(?:by|through|using|via)\s+(?P<value>[^.;]+)",
        r"\b(?:taken|removed|stolen|snatched)\s+from\s+(?P<value>[^.;]+)",
        r"\btook\s+(?P<value>[^.;]+)",
        r"\b(?:after|while)\s+(?P<value>[^.;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return _clean_extracted_value(match.group("value"))
    return None


def _extract_how(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _HOW_LABELS, max_matches=2)
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(value, [evidence], 0.82, status="present")

    candidate_sentences = [
        sentence
        for sentence in sentences
        if any(keyword in sentence.lower() for keyword in _HOW_KEYWORDS)
    ]
    if not candidate_sentences:
        return _make_field_payload(None, [], 0.0, status="missing")

    best_sentence = candidate_sentences[0]
    fragment = _extract_method_fragment(best_sentence)
    if fragment:
        return _make_field_payload(fragment, [best_sentence], 0.78, status="present")
    return _make_field_payload(best_sentence, [best_sentence], 0.54, status="uncertain")


def _assess_police_complaint_relevance(english_text: str) -> dict[str, Any]:
    lowered = english_text.lower()
    indicators = []
    raw_score = 0.0
    for keyword, weight in _COMPLAINT_INDICATORS.items():
        if keyword in lowered:
            raw_score += weight
            indicators.append(keyword)
    normalized_score = round(min(1.0, raw_score / 4.5), 2)
    return {
        "score": normalized_score,
        "likely_police_complaint": normalized_score >= 0.35,
        "indicators": indicators[:10],
    }


def _build_gap_summary(
    complaint_fields: dict[str, dict[str, Any]],
    language_info: dict[str, Any],
    complaint_assessment: dict[str, Any],
) -> dict[str, Any]:
    present_fields = []
    missing_fields = []
    uncertain_fields = []

    for field_name in _FIELD_ORDER:
        status = complaint_fields.get(field_name, {}).get("status", "missing")
        if status == "present":
            present_fields.append(field_name)
        elif status == "uncertain":
            uncertain_fields.append(field_name)
        else:
            missing_fields.append(field_name)

    completeness_score = round(
        (len(present_fields) + (0.5 * len(uncertain_fields))) / len(_FIELD_ORDER),
        2,
    )

    pipeline_flags = []
    if language_info.get("detected") == "unknown":
        pipeline_flags.append("language_detection_uncertain")
    if language_info.get("translation_status") in {"failed", "unavailable", "disabled"} and language_info.get("detected") != "en":
        pipeline_flags.append("translation_to_english_unavailable")
    if not complaint_assessment.get("likely_police_complaint", False):
        pipeline_flags.append("low_police_complaint_signal")

    if missing_fields:
        summary = f"Missing fields: {', '.join(missing_fields)}."
    elif uncertain_fields:
        summary = f"Fields requiring confirmation: {', '.join(uncertain_fields)}."
    else:
        summary = "All 5W + 1H fields were detected."

    requires_review = bool(missing_fields or uncertain_fields or pipeline_flags)
    return {
        "available_fields": present_fields,
        "missing_fields": missing_fields,
        "uncertain_fields": uncertain_fields,
        "completeness_score": completeness_score,
        "requires_review": requires_review,
        "pipeline_flags": pipeline_flags,
        "summary": summary,
    }


def _build_confidence_summary(
    complaint_fields: dict[str, dict[str, Any]],
    gaps: dict[str, Any],
) -> dict[str, Any]:
    field_scores = {
        field_name: round(
            float(complaint_fields.get(field_name, {}).get("confidence_score") or 0.0),
            2,
        )
        for field_name in _FIELD_ORDER
    }
    score_values = list(field_scores.values())
    average_score = round(sum(score_values) / len(score_values), 2) if score_values else 0.0
    return {
        "average_score": average_score,
        "min_score": min(score_values) if score_values else 0.0,
        "max_score": max(score_values) if score_values else 0.0,
        "field_scores": field_scores,
        "review_required": bool(gaps.get("requires_review")),
    }


def _build_incident_overview(complaint_fields: dict[str, dict[str, Any]]) -> Optional[str]:
    parts = []
    what_value = complaint_fields.get("what", {}).get("value")
    where_value = complaint_fields.get("where", {}).get("value")
    when_value = complaint_fields.get("when", {}).get("value")

    if what_value:
        parts.append(str(what_value))
    if where_value:
        parts.append(f"Location: {where_value}")
    if when_value:
        parts.append(f"When: {when_value}")

    if not parts:
        return None
    return " | ".join(parts)


def parse_document(raw: str) -> dict[str, Any]:
    raw_text = _normalize_whitespace(raw)
    raw_lines = normalize_lines(raw_text)

    language_detection = _detect_language(raw_text)
    translation_result = _translate_to_english(
        raw_text,
        language_detection["language_code"],
    )
    detected_language = _normalize_language_code(
        translation_result.get("source_language") or language_detection["language_code"]
    )
    english_text = _normalize_whitespace(
        translation_result.get("english_text") or raw_text
    )
    english_lines = normalize_lines(english_text)
    english_sentences = _split_sentences(english_text)

    language_info = {
        "detected": detected_language,
        "detected_name": _LANGUAGE_NAMES.get(detected_language, "Unknown"),
        "detection_method": language_detection["method"],
        "detection_confidence_score": language_detection["confidence_score"],
        "translation_target": "en",
        "translation_status": translation_result["status"],
        "translation_provider": translation_result["provider"],
        "translation_error": translation_result["error"],
    }

    complaint_fields = {
        "who": _extract_who(english_lines, english_sentences, english_text),
        "what": _extract_what(english_lines, english_sentences),
        "when": _extract_when(english_lines, english_sentences, english_text),
        "where": _extract_where(english_lines, english_sentences),
        "why": _extract_why(english_lines, english_sentences),
        "how": _extract_how(english_lines, english_sentences),
    }
    complaint_assessment = _assess_police_complaint_relevance(english_text)
    gaps = _build_gap_summary(complaint_fields, language_info, complaint_assessment)
    confidence = _build_confidence_summary(complaint_fields, gaps)

    return {
        "schema_version": "3.0",
        "document_type": "police_complaint",
        "language": language_info,
        "text": {
            "ocr_text": raw_text,
            "english_text": english_text,
        },
        "complaint": complaint_fields,
        "gaps": gaps,
        "confidence": confidence,
        "summary": {
            "incident_overview": _build_incident_overview(complaint_fields),
            "gap_statement": gaps["summary"],
        },
        "meta": {
            "detected_format": "POLICE_COMPLAINT",
            "parser_used": "police_complaint",
            "line_count": len(raw_lines),
            "english_line_count": len(english_lines),
            "sentence_count": len(english_sentences),
            "complaint_assessment": complaint_assessment,
            "source_language_counts": language_detection["counts"],
        },
    }


if __name__ == "__main__":
    load_dotenv()
    project_id = os.getenv("DOC_AI_PROJECT_ID")
    location = os.getenv("DOC_AI_LOCATION", "eu")
    processor_id = os.getenv("DOC_AI_PROCESSOR_ID")
    mime_type = os.getenv("DOC_AI_MIME_TYPE", "application/pdf")
    field_mask = os.getenv("DOC_AI_FIELD_MASK", "text")
    folder_path = os.getenv("DOC_INPUT_FOLDER")
    if not folder_path:
        raise ValueError("Set DOC_INPUT_FOLDER in .env to run batch parsing.")
    if not project_id or not processor_id:
        raise ValueError(
            "Set DOC_AI_PROJECT_ID and DOC_AI_PROCESSOR_ID in .env to run batch parsing."
        )

    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        result = process_document_sample(
            project_id, location, processor_id, file_path, mime_type, field_mask
        )
        parsed_result = parse_document(result.document.text or "")
        print(json.dumps(parsed_result, ensure_ascii=False, indent=2))
