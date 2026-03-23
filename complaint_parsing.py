# -*- coding: utf-8 -*-
"""Utilities for multilingual police complaint parsing via Google Document AI."""

from __future__ import annotations

import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "get_translation_config",
    "load_dotenv",
    "normalize_lines",
    "parse_document",
    "process_document_bytes",
    "process_document_sample",
]

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
_BNS_REFERENCE_URL = "https://www.indiacode.nic.in/handle/123456789/20062?view_type=browse"
_BNSS_REFERENCE_URL = "https://www.indiacode.nic.in/bitstream/123456789/20340/1/bnss%2C_2023.pdf"
_TELANGANA_FIR_FAQ_URL = "https://mgov.telangana.gov.in/faqnew.html"
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
    "accident": 2.8,
    "collision": 2.8,
    "collided": 2.8,
    "crash": 2.6,
    "overtaking": 2.4,
    "run over": 2.8,
    "knocked down": 2.8,
    "rash driving": 2.6,
    "head-on": 2.8,
    "skidded": 2.4,
    "rammed": 2.6,
    "cyber": 2.4,
    "hacked": 2.6,
    "arson": 3.0,
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
    "unknown rider",
    "unknown driver",
    "unknown bike rider",
    "unknown vehicle",
    "unidentified rider",
    "unknown caller",
    "unknown men",
    "unknown man",
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
    "accident": 1.0,
    "collision": 1.0,
    "injured": 0.9,
    "hospital": 0.8,
    "ambulance": 0.9,
    "fracture": 0.9,
    "arson": 1.1,
    "cyber": 1.0,
}
_HEADER_LABELS = {"date", "from", "subject"}
_SALUTATION_PREFIXES = ("respected", "sir", "madam", "dear")
_SIGNATURE_PREFIXES = ("sd/-", "sd /-", "sd/", "signature")
_MOTIVE_KEYWORDS = (
    "because",
    "motive",
    "reason",
    "grudge",
    "revenge",
    "enmity",
    "dispute",
    "threat",
    "threatened",
    "opportunistic",
    "foul play",
    "stock shortage",
    "negligence",
    "reckless",
    "rash driving",
    "careless",
    "speeding",
    "wrong side driving",
    "drunk driving",
    "intoxicated",
    "property dispute",
    "land dispute",
    "overtaking",
    "opposite direction",
    "oncoming",
    "dangerous driving",
)
_ADMIN_CONTEXT_MARKERS = (
    "received on",
    "registered",
    "enquiry",
    "petition",
    "entrusted to",
    "investigation",
    "case in",
)
_REASON_NOISE_PREFIXES = (
    "the force",
    "force",
    "a small scratch",
    "small scratch",
    "injury",
    "pain",
    "fear",
)
_METHOD_HINTS = (
    "front door latch",
    "cupboard open",
    "handbag zip",
    "crowded bus",
    "from my pocket",
    "from the pocket",
    "from my neck",
    "from the parking area",
    "pulled",
    "snatched",
    "sped away",
    "fire set",
    "deliberate fire setting",
    "storage room",
    "forced open",
    "damaged",
    "while overtaking",
    "coming from opposite direction",
    "hit me",
    "collided with",
    "crashed into",
    "knocked me down",
    "head-on collision",
    "hit with a rod",
    "shared the otp",
    "impersonating",
)
_NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}$")
_REVIEW_QUESTION_MAP = {
    "who": "Who are the complainant, victim, accused, and witnesses in this complaint?",
    "who.complainant": "Who submitted or signed the complaint?",
    "who.victim": "Who was affected or injured in the incident?",
    "who.accused": "Who caused the incident or is being accused?",
    "who.witnesses": "Who saw the incident or can confirm what happened?",
    "what": "What exactly happened in the incident?",
    "when": "When did the incident occur?",
    "when.date": "On what date did the incident occur?",
    "when.time": "At what time did the incident occur?",
    "where": "Where did the incident occur?",
    "why": "Why does the complaint say the incident happened?",
    "how": "How did the incident happen?",
}
_LLM_VALIDATION_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "from",
    "by",
    "with",
    "my",
    "our",
    "their",
    "his",
    "her",
    "this",
    "that",
    "these",
    "those",
    "it",
    "is",
    "was",
    "were",
    "be",
    "been",
    "being",
    "am",
    "are",
    "as",
    "after",
    "before",
    "during",
    "while",
    "into",
    "near",
    "along",
    "about",
    "around",
    "against",
    "through",
    "another",
    "same",
    "incident",
    "complaint",
}
_UNKNOWN_FIELD_MARKERS = (
    "unknown",
    "not stated",
    "not mentioned",
    "not provided",
    "not specified",
    "unclear",
    "cannot determine",
    "unable to determine",
    "none",
    "n/a",
)
_EXTRACTION_SYSTEM_PROMPT = """\
You are an expert Indian police complaint analyst. Extract structured 5W+1H information from police complaints covering ALL crime types: road accidents, theft, robbery, snatching, assault, arson, fraud, cyber crime, and others.

Return ONLY a JSON object with this exact shape:
{
  "complaint_summary": string,
  "review_questions": [string],
  "answers": {
    "who": {"complainant": [string], "victim": [string], "accused": [string], "witnesses": [string], "confidence": string, "evidence": [string]},
    "what": {"answer": string, "confidence": string, "evidence": [string]},
    "when": {"answer": string, "date": string, "time": string, "confidence": string, "evidence": [string]},
    "where": {"answer": string, "confidence": string, "evidence": [string]},
    "why": {"answer": string, "confidence": string, "evidence": [string]},
    "how": {"answer": string, "confidence": string, "evidence": [string]}
  }
}

Field definitions:
- WHO: complainant (person filing), victim (person harmed), accused (offender). Only use generic labels like "Unknown person" or "Unknown caller" when the complaint itself explicitly says unknown/unidentified or directly describes that role. Do not invent a new accused role from thin air.
- WHAT: A concise 1-2 sentence summary of the incident. Do NOT copy the entire narrative paragraph.
- WHEN: Date and time of the incident (not the date of filing or hospital visit).
- WHERE: The physical location where the incident occurred (e.g. road name, junction, market). Do NOT use the hospital, police station, or place where the complainant is currently located.
- WHY: The cause or motive. For accidents: reckless driving, wrong-side driving, speeding, drunk driving, negligence. For crimes: grudge, revenge, money dispute, opportunistic. Use empty string only if genuinely not mentioned.
- HOW: The specific physical mechanism of the incident. For accidents: "bike overtook from opposite side and collided head-on". For theft: "broke front door latch and opened cupboard". Be specific, not vague.

Confidence must be one of: high, medium, low.
Every evidence item must be a direct snippet copied from the complaint text, not a paraphrase.
If a field is unknown or weakly supported, use empty strings or empty arrays and add a useful follow-up question to review_questions.

IMPORTANT — Language quality:
All answer values and complaint_summary MUST be in clear, grammatically correct English. The complaint text may be a machine translation from Hindi, Telugu, or another Indian language and will often contain broken grammar, garbled fragments, or literal word-for-word translations. You MUST rewrite every answer into proper English while preserving the factual meaning. Do not copy translation artefacts. Write as a professional police report would read."""
_EXTRACTION_FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": (
            "Complaint text:\nI, Hemanth Choudhary, age 22, was returning from office on 06-02-2026 around 11:00 PM. "
            "On the route from Moram X Road to Parsigutta, a bike coming from the opposite direction, while overtaking another vehicle, "
            "hit me. I fell down and lost consciousness. A nearby person called my mother. An ambulance came and brought me to Srikara Hospital, "
            "RTC X Road. The doctors said bones in my right leg below the knee are broken in two places and surgery is needed."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "complaint_summary": "Road accident where a bike hit the complainant while overtaking, causing leg fractures",
            "review_questions": ["Who was riding the bike that hit the complainant?", "Exact location on the route where the collision occurred?"],
            "answers": {
                "who": {"complainant": ["Hemanth Choudhary"], "victim": ["Hemanth Choudhary"], "accused": [], "witnesses": ["Nearby person who called my mother"], "confidence": "medium", "evidence": ["A nearby person called my mother"]},
                "what": {"answer": "Road accident where an oncoming bike hit the complainant while overtaking another vehicle, causing leg fractures", "confidence": "high", "evidence": ["a bike coming from the opposite direction, while overtaking another vehicle, hit me"]},
                "when": {"answer": "06-02-2026 around 11:00 PM", "date": "06-02-2026", "time": "11:00 PM", "confidence": "high", "evidence": ["on 06-02-2026 around 11:00 PM"]},
                "where": {"answer": "On the route from Moram X Road to Parsigutta", "confidence": "medium", "evidence": ["On the route from Moram X Road to Parsigutta"]},
                "why": {"answer": "Reckless driving — bike rider overtook from the opposite direction into oncoming traffic", "confidence": "high", "evidence": ["a bike coming from the opposite direction, while overtaking another vehicle, hit me"]},
                "how": {"answer": "A bike coming from the opposite direction overtook another vehicle and collided head-on with the complainant", "confidence": "high", "evidence": ["a bike coming from the opposite direction, while overtaking another vehicle, hit me. I fell down"]},
            },
        }),
    },
    {
        "role": "user",
        "content": (
            "Complaint text:\nI, Sunita Reddy, received a phone call on 10-03-2026 from someone claiming to be an SBI bank officer. "
            "He said my account would be blocked unless I verified my details. He asked me to share the OTP sent to my phone. "
            "After I shared the OTP, Rs. 1,50,000 was debited from my savings account. I realized I was cheated and went to the bank."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "complaint_summary": "Cyber fraud where caller impersonated a bank officer and stole Rs. 1,50,000 via OTP phishing",
            "review_questions": ["What was the phone number of the fraudulent caller?", "Which SBI branch does the complainant's account belong to?"],
            "answers": {
                "who": {"complainant": ["Sunita Reddy"], "victim": ["Sunita Reddy"], "accused": ["Unknown caller impersonating SBI officer"], "witnesses": [], "confidence": "high", "evidence": ["someone claiming to be an SBI bank officer"]},
                "what": {"answer": "Cyber fraud where a caller impersonated a bank officer and stole Rs. 1,50,000 through OTP phishing", "confidence": "high", "evidence": ["After I shared the OTP, Rs. 1,50,000 was debited from my savings account"]},
                "when": {"answer": "10-03-2026", "date": "10-03-2026", "time": "", "confidence": "high", "evidence": ["on 10-03-2026"]},
                "where": {"answer": "", "confidence": "low", "evidence": []},
                "why": {"answer": "Financial fraud to steal money from the victim's bank account", "confidence": "high", "evidence": ["Rs. 1,50,000 was debited from my savings account"]},
                "how": {"answer": "Caller impersonated an SBI bank officer, claimed the account would be blocked, and tricked the victim into sharing OTP to authorize a fraudulent debit", "confidence": "high", "evidence": ["He said my account would be blocked unless I verified my details. He asked me to share the OTP"]},
            },
        }),
    },
    {
        "role": "user",
        "content": (
            "Complaint text:\nI, Raju Yadav, was walking near the railway crossing on 15-01-2026 at about 9:30 PM. "
            "Three unknown men came from behind, hit me on the head with a rod, and snatched my wallet containing Rs. 12,000, "
            "my Aadhaar card, and a gold ring from my finger. They fled towards the old bridge. I was bleeding and a passerby helped me to the hospital."
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "complaint_summary": "Armed robbery near railway crossing where three unknown men hit the complainant with a rod and snatched wallet and gold ring",
            "review_questions": ["Can the complainant describe the appearance of any of the three men?", "Which hospital was the complainant taken to?"],
            "answers": {
                "who": {"complainant": ["Raju Yadav"], "victim": ["Raju Yadav"], "accused": ["Unknown men (3)"], "witnesses": ["Passerby who helped to hospital"], "confidence": "medium", "evidence": ["Three unknown men came from behind", "a passerby helped me to the hospital"]},
                "what": {"answer": "Armed robbery where three unknown men assaulted the complainant with a rod and snatched his wallet and gold ring", "confidence": "high", "evidence": ["hit me on the head with a rod, and snatched my wallet"]},
                "when": {"answer": "15-01-2026 at about 9:30 PM", "date": "15-01-2026", "time": "9:30 PM", "confidence": "high", "evidence": ["on 15-01-2026 at about 9:30 PM"]},
                "where": {"answer": "Near the railway crossing", "confidence": "high", "evidence": ["near the railway crossing"]},
                "why": {"answer": "Robbery motivated by intent to steal money and valuables", "confidence": "high", "evidence": ["snatched my wallet containing Rs. 12,000"]},
                "how": {"answer": "Three men approached from behind, struck the complainant on the head with a rod, then snatched his wallet and gold ring before fleeing towards the old bridge", "confidence": "high", "evidence": ["hit me on the head with a rod, and snatched my wallet containing Rs. 12,000, my Aadhaar card, and a gold ring"]},
            },
        }),
    },
]


def load_dotenv(dotenv_path: str = ".env", override: bool = False) -> None:
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
            if override or key not in os.environ:
                os.environ[key] = value


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
    credentials=None,
) -> documentai.ProcessResponse:
    if ClientOptions is None or documentai is None:
        raise RuntimeError(
            "google-cloud-documentai is not installed. Install dependencies from requirements.txt."
        )
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    kwargs: dict = {"client_options": opts}
    if credentials is not None:
        kwargs["credentials"] = credentials
    client = documentai.DocumentProcessorServiceClient(**kwargs)

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
    provider = (_clean_env_value(os.getenv("TRANSLATION_PROVIDER")) or "auto").lower()
    if provider not in {"auto", "google", "openai", "none"}:
        provider = "auto"

    fallback_provider = (
        _clean_env_value(os.getenv("TRANSLATION_FALLBACK_PROVIDER")) or "openai"
    ).lower()
    if fallback_provider not in {"google", "openai", "none"}:
        fallback_provider = "openai"

    openai_api_key = _clean_env_value(os.getenv("OPENAI_TRANSLATION_API_KEY")) or _clean_env_value(
        os.getenv("OPENAI_API_KEY")
    )

    return {
        "enabled": _is_env_true("TRANSLATION_ENABLED", True),
        "provider": provider,
        "fallback_provider": fallback_provider,
        "project_id": _clean_env_value(os.getenv("TRANSLATION_PROJECT_ID"))
        or _clean_env_value(os.getenv("DOC_AI_PROJECT_ID")),
        "location": _clean_env_value(os.getenv("TRANSLATION_LOCATION")) or "global",
        "target_language": _clean_env_value(os.getenv("TRANSLATION_TARGET_LANGUAGE"))
        or "en",
        "openai_enabled": _is_env_true("OPENAI_TRANSLATION_ENABLED", True),
        "openai_api_key": openai_api_key,
        "openai_api_key_configured": bool(openai_api_key),
        "openai_base_url": (
            _clean_env_value(os.getenv("OPENAI_TRANSLATION_BASE_URL"))
            or _clean_env_value(os.getenv("OPENAI_BASE_URL"))
            or "https://api.openai.com/v1"
        ).rstrip("/"),
        "openai_model": _clean_env_value(os.getenv("OPENAI_TRANSLATION_MODEL")) or "gpt-5.2",
        "openai_reasoning_effort": (
            _clean_env_value(os.getenv("OPENAI_TRANSLATION_REASONING_EFFORT")) or "none"
        ).lower(),
    }


def get_question_guided_extraction_config() -> dict[str, Any]:
    translation_config = get_translation_config()
    reasoning_effort = (
        _clean_env_value(os.getenv("OPENAI_EXTRACTION_REASONING_EFFORT")) or "medium"
    ).lower()
    if reasoning_effort not in {"none", "low", "medium", "high", "xhigh"}:
        reasoning_effort = "medium"
    min_confidence_label = (
        _clean_env_value(os.getenv("OPENAI_EXTRACTION_MIN_CONFIDENCE")) or "medium"
    ).lower()
    if min_confidence_label not in {"low", "medium", "high"}:
        min_confidence_label = "medium"
    min_confidence_score = _confidence_label_to_score(min_confidence_label, 0.68)

    return {
        "enabled": _is_env_true("OPENAI_EXTRACTION_ENABLED", True),
        "api_key": translation_config["openai_api_key"],
        "api_key_configured": translation_config["openai_api_key_configured"],
        "base_url": translation_config["openai_base_url"],
        "model": _clean_env_value(os.getenv("OPENAI_EXTRACTION_MODEL"))
        or translation_config["openai_model"],
        "reasoning_effort": reasoning_effort,
        "min_confidence_label": min_confidence_label,
        "min_confidence_score": min_confidence_score,
        "require_evidence": _is_env_true("OPENAI_EXTRACTION_REQUIRE_EVIDENCE", True),
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
    return lowered.startswith(("unknown ", "unidentified ")) or any(
        pattern in lowered for pattern in _UNKNOWN_ACTOR_PATTERNS
    )


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


def _is_header_label(line: str) -> bool:
    cleaned = _clean_extracted_value(line)
    if not cleaned:
        return False
    return cleaned.rstrip(":").strip().lower() in _HEADER_LABELS


def _is_salutation_line(line: str) -> bool:
    cleaned = _clean_extracted_value(line)
    if not cleaned:
        return False
    lowered = cleaned.lower().rstrip(",")
    return any(lowered.startswith(prefix) for prefix in _SALUTATION_PREFIXES)


def _is_signature_line(line: str) -> bool:
    cleaned = _clean_extracted_value(line)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    return any(lowered.startswith(prefix) for prefix in _SIGNATURE_PREFIXES)


def _join_continued_lines(lines: list[str], start_index: int, max_lines: int = 3) -> Optional[str]:
    parts: list[str] = []
    for index in range(start_index, min(len(lines), start_index + max_lines)):
        raw_line = _normalize_whitespace(lines[index]).strip()
        line = _clean_extracted_value(raw_line)
        if not line:
            break
        if index != start_index and (
            _is_header_label(line) or _is_salutation_line(line) or _is_signature_line(line)
        ):
            break
        parts.append(line)
        if raw_line.endswith((".", "!", "?", ";", ":")):
            break
        if index + 1 >= len(lines):
            break
        next_line = _clean_extracted_value(lines[index + 1]) or ""
        if _is_header_label(next_line) or _is_salutation_line(next_line) or _is_signature_line(next_line):
            break
    return _clean_extracted_value(" ".join(parts))


def _looks_like_person_name(value: str) -> bool:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return False
    cleaned = re.sub(
        r"^(?:from|sd/?-?|statement(?:\s+recorded)?\s+of|complaint\s+of|deposition\s+of)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:i\s*,\s*|i\s+am\s+)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.split(
        r",\s*(?:aged?|residing|resident|address|occupation|s/o|d/o|w/o|r/o)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-")
    return bool(cleaned and _NAME_PATTERN.fullmatch(cleaned))


def _extract_name_from_identity_line(value: str) -> Optional[str]:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return None
    cleaned = re.sub(
        r"^(?:from|sd/?-?|statement(?:\s+recorded)?\s+of|complaint\s+of|deposition\s+of)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:i\s*,\s*|i\s+am\s+)", "", cleaned, flags=re.IGNORECASE)
    direct_patterns = [
        r"\bmy name is\s+(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,5})",
        (
            r"^(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,5})"
            r"(?=(?:\s*,)?\s*(?:aged?|age|residing|resident|address|occupation|occ|s/o|d/o|w/o|r/o|"
            r"have\b|had\b|am\b|was\b|is\b|private\b)|$)"
        ),
    ]
    for pattern in direct_patterns:
        direct_match = re.search(pattern, cleaned, re.IGNORECASE)
        if direct_match:
            extracted_name = _clean_name_fragment(direct_match.group("value"))
            if extracted_name:
                return extracted_name
    candidate = re.split(
        r",\s*(?:aged?|residing|resident|address|occupation|s/o|d/o|w/o|r/o)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-")
    if _looks_like_person_name(candidate):
        return _clean_name_fragment(candidate)
    return None


def _extract_address_from_identity_line(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return None
    match = re.search(
        r"\b(?:residing at|resident of|r/o|address(?: is)?)\s+(?P<value>.+)",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        return _clean_extracted_value(match.group("value"))

    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if parts and _looks_like_person_name(parts[0]) and len(parts) > 1:
        candidate = ", ".join(parts[1:])
        if any(hint in candidate.lower() for hint in _LOCATION_HINTS):
            return _clean_extracted_value(candidate)
    return None


def _score_date_candidate(value: str) -> float:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return 0.0
    date_matches = _collect_pattern_matches(cleaned, _DATE_PATTERNS)
    if not date_matches:
        return 0.0
    if len(cleaned.split()) <= 6:
        return 1.0
    return 0.55


def _score_identity_candidate(value: str) -> float:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return 0.0
    score = 0.0
    if _extract_name_from_identity_line(cleaned):
        score += 0.7
    if _extract_address_from_identity_line(cleaned):
        score += 0.5
    return score


def _score_subject_candidate(value: str) -> float:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return 0.0
    lowered = cleaned.lower()
    if _score_date_candidate(cleaned) >= 1.0 or _score_identity_candidate(cleaned) >= 0.7:
        return 0.0
    score = _score_sentence(cleaned, _INCIDENT_KEYWORDS)
    if "complaint" in lowered or "subject" in lowered:
        score += 0.8
    if "regarding" in lowered:
        score += 0.4
    return score


def _extract_header_value(
    lines: list[str],
    label: str,
    scorer: Callable[[str], float],
    *,
    max_ahead: int = 6,
    max_join_lines: int = 3,
) -> Optional[str]:
    label_pattern = re.escape(label).replace(r"\ ", r"\s+")
    best_value = None
    best_score = 0.0

    for index, raw_line in enumerate(lines):
        line = _normalize_whitespace(raw_line)
        if not line:
            continue

        inline_match = re.match(
            rf"^\s*{label_pattern}\s*(?:[:\-]\s*|\s+)(?P<value>.+)$",
            line,
            re.IGNORECASE,
        )
        if inline_match:
            candidate = _clean_extracted_value(inline_match.group("value"))
            if candidate:
                score = scorer(candidate)
                if score > best_score:
                    best_value = candidate
                    best_score = score

        if not re.fullmatch(label_pattern, line, re.IGNORECASE):
            continue

        for offset in range(1, max_ahead + 1):
            candidate_index = index + offset
            if candidate_index >= len(lines):
                break
            candidate = _join_continued_lines(lines, candidate_index, max_lines=max_join_lines)
            if not candidate or _is_header_label(candidate):
                continue
            score = scorer(candidate)
            if score > best_score:
                best_value = candidate
                best_score = score

    return best_value if best_score > 0 else None


def _extract_header_date(lines: list[str]) -> Optional[str]:
    return _extract_header_value(lines, "date", _score_date_candidate, max_join_lines=1)


def _extract_from_value(lines: list[str]) -> Optional[str]:
    return _extract_header_value(lines, "from", _score_identity_candidate, max_join_lines=3)


def _extract_subject_value(lines: list[str]) -> Optional[str]:
    label_pattern = r"subject"
    for index, raw_line in enumerate(lines):
        line = _normalize_whitespace(raw_line)
        if not line:
            continue
        inline_match = re.match(
            rf"^\s*{label_pattern}\s*(?:[:\-]\s*|\s+)(?P<value>.+)$",
            line,
            re.IGNORECASE,
        )
        if inline_match:
            candidate = _clean_extracted_value(inline_match.group("value"))
            if candidate and _score_subject_candidate(candidate) > 0:
                return candidate
        if not re.fullmatch(label_pattern, line, re.IGNORECASE):
            continue
        for offset in range(1, 7):
            candidate_index = index + offset
            if candidate_index >= len(lines):
                break
            candidate = _join_continued_lines(lines, candidate_index, max_lines=3)
            if candidate and _score_subject_candidate(candidate) > 0:
                return candidate
    return None


def _extract_signature_name(lines: list[str]) -> Optional[str]:
    for line in reversed(lines):
        if not _is_signature_line(line):
            continue
        name = _extract_name_from_identity_line(line)
        if name:
            return name

    footer_metadata_patterns = (
        r"^received on\b",
        r"^made petition\b",
        r"^after enquiry\b",
        r"^statement recorded\b",
        r"^registered\b",
        r"^case in\b",
        r"^mlc no\b",
        r"^ip no\b",
    )
    for index, line in enumerate(lines):
        if not any(re.search(pattern, line, re.IGNORECASE) for pattern in footer_metadata_patterns):
            continue
        for candidate_line in reversed(lines[max(0, index - 3) : index]):
            name = _extract_name_from_identity_line(candidate_line)
            if name:
                return name
    return None


def _extract_body_lines(lines: list[str]) -> list[str]:
    start_index = 0
    for index, line in enumerate(lines):
        if _is_salutation_line(line):
            start_index = index + 1
            break
    body_lines = [
        line
        for line in lines[start_index:]
        if not _is_header_label(line) and not _is_signature_line(line)
    ]
    return body_lines or [line for line in lines if not _is_header_label(line) and not _is_signature_line(line)]


def _merge_wrapped_lines(lines: list[str]) -> str:
    merged_lines: list[str] = []
    buffer = ""
    buffer_closed = False
    for raw_line in lines:
        normalized_line = _normalize_whitespace(raw_line).strip()
        line = _clean_extracted_value(normalized_line)
        if not line:
            if buffer:
                merged_lines.append(buffer)
                buffer = ""
                buffer_closed = False
            continue
        current_closed = normalized_line.endswith((".", "!", "?", ";", ":"))
        if not buffer:
            buffer = line
        elif buffer_closed:
            merged_lines.append(buffer)
            buffer = line
        else:
            buffer = f"{buffer} {line}".strip()
        buffer_closed = current_closed
        if current_closed and buffer:
            merged_lines.append(buffer)
            buffer = ""
            buffer_closed = False
    if buffer:
        merged_lines.append(buffer)
    return "\n".join(merged_lines)


def _extract_named_entity(sentence: str, context_pattern: str) -> Optional[str]:
    context_match = re.search(rf"{context_pattern}", sentence, re.IGNORECASE)
    if not context_match:
        return None
    tail = sentence[context_match.end() :].lstrip(" :-,")
    match = re.match(r"(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})", tail)
    if not match:
        return None
    return _clean_name_fragment(match.group("value"))


def _extract_temporal_sentence(sentences: list[str]) -> Optional[str]:
    best_sentence = None
    best_score = 0.0
    for sentence in sentences:
        date_matches = _collect_pattern_matches(sentence, _DATE_PATTERNS)
        time_matches = _collect_pattern_matches(sentence, _TIME_PATTERNS)
        if not date_matches and not time_matches:
            continue
        lowered = sentence.lower()
        score = 0.0
        if date_matches:
            score += 1.2
        if time_matches:
            score += 0.9
        if date_matches and time_matches:
            score += 0.6
        if any(keyword in lowered for keyword in _INCIDENT_KEYWORDS):
            score += 1.0
        if re.search(r"\b(?:on|today, on|night of|at around|at about|when)\b", lowered):
            score += 0.4
        if any(marker in lowered for marker in _ADMIN_CONTEXT_MARKERS):
            score -= 1.5
        if score > best_score:
            best_sentence = sentence
            best_score = score
    return best_sentence


def _cleanup_location_value(value: str) -> Optional[str]:
    cleaned = _trim_temporal_suffix(value)
    if not cleaned:
        return None
    cleaned = re.sub(
        r",\s*(?:two|three|four|both|an?|the)?\s*(?:unknown|unidentified)?\s*(?:person|persons|men|women|people|offenders?|accused|suspects?)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r",\s*(?:he|she|they)\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:at|in|on|from|for)\s*$", "", cleaned, flags=re.IGNORECASE).strip(" ,;:-")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return _clean_extracted_value(cleaned)


_LOCATION_FALSE_POSITIVE_PREFIXES = (
    "present ",
    "this time",
    "that time",
    "the moment",
    "once ",
    "first ",
)

def _is_plausible_location(value: Optional[str]) -> bool:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if len(cleaned) < 4:
        return False
    if re.match(r"^\d{1,2}:\d{2}\s*(?:hr|hrs|hes|AM|PM|am|pm|[AP]\.?M\.?)?\s*$", cleaned):
        return False
    if any(lowered.startswith(prefix) for prefix in _LOCATION_FALSE_POSITIVE_PREFIXES):
        return False
    if re.search(r"\b(?:hospital|nursing home|clinic)\b", lowered) and re.search(
        r"\b(?:floor|room\s*no|ward|bed|mlc|ip\s*no|treatment)\b", lowered
    ):
        return False
    if any(noise in lowered for noise in _NON_LOCATION_HINTS) and not any(
        hint in lowered for hint in _LOCATION_HINTS
    ) and not re.search(r"\b(?:my house|my shop|my office|parking area|city bus|bus route)\b", lowered):
        return False
    return True


def _extract_location_fragment(sentence: str, header_address: Optional[str] = None) -> Optional[str]:
    lowered = sentence.lower()
    if "above address" in lowered or "above-mentioned address" in lowered:
        return header_address if header_address else None

    patterns = [
        r"\brear side of\s+(?P<value>[^.;]+)",
        r"\blane near\s+(?P<value>[^.;]+)",
        r"\bnear\s+(?P<value>[^.;]+)",
        r"\boutside\s+(?P<value>[^.;]+)",
        r"\binside\s+(?P<value>[^.;]+)",
        r"\bin\s+(?P<value>(?:a\s+)?(?:crowded\s+)?city bus[^.;]*)",
        r"\bfrom\s+(?P<value>my (?:house|shop|office|storage room)|the parking area[^.;]*)",
        r"\bfrom\s+(?P<value>[A-Z][^.;]{4,}?\s+to\s+[A-Z][^.;]+)",
        r"\bat\s+(?P<value>[^.;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if not match:
            continue
        value = _cleanup_location_value(match.group("value"))
        if value and any(
            marker in value.lower()
            for marker in (
                "register my complaint",
                "take necessary action",
                "collect cctv",
                "trace the offenders",
                "recover the stolen property",
                "kindly register",
            )
        ):
            continue
        if _is_plausible_location(value):
            return value
    return None


def _extract_reason_fragment(sentence: str) -> Optional[str]:
    patterns = [
        r"\bbecause\s+(?P<value>[^.;]+)",
        r"\bdue to\s+(?P<value>[^.;]+)",
        r"\b(?:motive|reason)\s*(?:is|was|appears to be|seems to be)?\s*(?P<value>[^.;]+)",
        r"\b(?:appears|seems)\s+to\s+be\s+(?P<value>[^.;]+)",
        r"(?P<value>\bwhile\s+overtaking\b[^.;]*)",
        r"(?P<value>\bcoming\s+from\s+(?:the\s+)?opposite\s+(?:direction|side)\b[^.;]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return _clean_extracted_value(match.group("value"))
    return None


def _is_reason_fragment_valid(fragment: Optional[str], sentence: str) -> bool:
    cleaned = _clean_extracted_value(fragment)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    sentence_lower = sentence.lower()
    if any(lowered.startswith(prefix) for prefix in _REASON_NOISE_PREFIXES):
        return False
    if not any(keyword in sentence_lower or keyword in lowered for keyword in _MOTIVE_KEYWORDS):
        return False
    return True


def _extract_method_fragment(sentence: str, subject_value: Optional[str] = None) -> Optional[str]:
    explicit_patterns = [
        r"\bfront door latch damaged(?: and [^.;]+)?",
        r"\bhandbag zip was partly open\b",
        r"\bpulled\s+[^.;]+",
        r"\b(?:took|taken|removed|snatched|stolen)\s+[^.;]+? from [^.;]+",
        r"\b(?:vehicle|motorcycle)\s+was\s+missing\s+from\s+the\s+parking area\b[^.;]*",
        r"\bdeliberate fire setting\b",
        r"\bfire set to [^.;]+",
        r"\bcame from behind on a [^.;]+",
        r"\bsped away\b[^.;]*",
        r"\b(?:bike|vehicle|car|truck|auto|lorry|bus)\s+[^.;]*?(?:opposite\s+direction|opposite\s+me)[^.;]*?\b(?:hit|collided|struck)\b[^.;]*",
        r"\bwhile\s+overtaking\b[^.;]*?\b(?:hit|collided|struck|crashed)\b[^.;]*",
        r"\b(?:hit|collided\s+with|crashed\s+into|knocked)\b[^.;]*",
        r"\bcoming\s+from\s+(?:the\s+)?opposite\s+direction\b[^.;]*",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            return _clean_extracted_value(match.group(0))

    lowered = sentence.lower()
    if "crowded" in lowered and "bus" in lowered:
        return "during a crowded bus journey"

    if subject_value:
        subject_lower = subject_value.lower()
        if "fire set" in subject_lower:
            return _clean_extracted_value(subject_value)
        if "snatching by" in subject_lower or "in city bus" in subject_lower:
            return _clean_extracted_value(subject_value)

    return None


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
    extra_score: Optional[Callable[[str], float]] = None,
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

    dominant = max(counts, key=lambda k: counts[k])
    dominant_share = counts[dominant] / total
    language_code = dominant if dominant_share >= 0.45 else "unknown"
    strongest_non_english = max(("hi", "te"), key=lambda k: counts[k])
    strongest_non_english_count = counts[strongest_non_english]
    if dominant in {"hi", "te"} and counts[dominant] >= 6:
        language_code = dominant
    elif dominant == "en":
        # OCR output for Telugu/Hindi complaints often contains many noisy Latin
        # characters from form labels, names, or bad handwriting recognition.
        # Treat the document as non-English when an Indic script remains
        # substantial and close to the English character count.
        if (
            strongest_non_english_count >= 6
            and (strongest_non_english_count / total) >= 0.35
            and counts["en"] < strongest_non_english_count * 1.5
        ):
            language_code = strongest_non_english
        elif counts["en"] >= strongest_non_english_count * 2:
            language_code = "en"
        else:
            language_code = "unknown"

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


def _build_translation_result(
    normalized_text: str,
    detected_language: str,
    target_language: str,
) -> dict[str, Any]:
    return {
        "english_text": normalized_text,
        "source_language": detected_language,
        "target_language": target_language,
        "status": "not_needed",
        "provider": "identity",
        "model": None,
        "error": None,
    }


def _translate_to_english_via_google(
    normalized_text: str,
    detected_language: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    result = _build_translation_result(
        normalized_text,
        detected_language,
        config["target_language"],
    )

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
        logger.warning("Google Cloud Translation failed: %s", exc)
        result.update(
            {
                "status": "failed",
                "provider": "google_cloud_translate",
                "error": str(exc),
            }
        )
        return result


def _extract_openai_error_message(error_body: str) -> str:
    cleaned_body = _normalize_whitespace(error_body)
    if not cleaned_body:
        return "OpenAI translation request failed."
    try:
        payload = json.loads(cleaned_body)
    except json.JSONDecodeError:
        return cleaned_body

    error = payload.get("error")
    if isinstance(error, dict):
        message = _clean_extracted_value(error.get("message"))
        if message:
            return message
    return cleaned_body


def _extract_openai_output_text(payload: dict[str, Any]) -> str:
    direct_output = payload.get("output_text")
    if isinstance(direct_output, str):
        return direct_output

    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text") or content.get("value")
                if isinstance(text, str) and text.strip():
                    chunks.append(text)
    return "\n".join(chunks)


def _build_openai_ssl_context() -> Optional[ssl.SSLContext]:
    try:
        import certifi
    except ImportError:  # pragma: no cover - depends on local environment
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _translate_to_english_via_openai(
    normalized_text: str,
    detected_language: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    result = _build_translation_result(
        normalized_text,
        detected_language,
        config["target_language"],
    )
    result["provider"] = "openai_responses"
    result["model"] = config["openai_model"]

    if not config["openai_enabled"]:
        result.update(
            {
                "status": "unavailable",
                "error": "Set OPENAI_TRANSLATION_ENABLED=true to enable OpenAI translation.",
            }
        )
        return result

    if not config["openai_api_key"]:
        result.update(
            {
                "status": "unavailable",
                "error": "Set OPENAI_API_KEY or OPENAI_TRANSLATION_API_KEY to enable OpenAI translation.",
            }
        )
        return result

    chunks = _chunk_text_for_translation(normalized_text, max_chars=12000)
    translated_chunks = []
    source_language_name = _LANGUAGE_NAMES.get(detected_language, "Unknown")

    for chunk in chunks:
        payload: dict[str, Any] = {
            "model": config["openai_model"],
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Translate the following police complaint into clear, literal English. "
                                "Preserve names, dates, times, addresses, lists, line breaks, and uncertainty. "
                                "Do not summarize, explain, or omit details. Return only the translated English text."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Source language: {source_language_name}\n\n{chunk}",
                        }
                    ],
                },
            ],
        }
        reasoning_effort = config["openai_reasoning_effort"]
        if reasoning_effort in {"none", "low", "medium", "high", "xhigh"}:
            payload["reasoning"] = {"effort": reasoning_effort}

        request = urllib.request.Request(
            f"{config['openai_base_url']}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config['openai_api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            ssl_context = _build_openai_ssl_context()
            with urllib.request.urlopen(request, timeout=180, context=ssl_context) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            result.update(
                {
                    "status": "failed",
                    "error": _extract_openai_error_message(error_body),
                }
            )
            return result
        except Exception as exc:  # pragma: no cover - depends on live network config
            logger.warning("OpenAI translation request failed: %s", exc)
            result.update(
                {
                    "status": "failed",
                    "error": str(exc),
                }
            )
            return result

        translated_chunk = _normalize_whitespace(_extract_openai_output_text(response_payload))
        if not translated_chunk:
            result.update(
                {
                    "status": "failed",
                    "error": "OpenAI translation completed but returned no translated text.",
                }
            )
            return result
        translated_chunks.append(translated_chunk)

    translated_text = "\n\n".join(translated_chunks).strip()
    if translated_text and (detected_language == "unknown" or re.search(r"[A-Za-z]", translated_text)):
        result.update(
            {
                "english_text": translated_text,
                "status": "translated",
            }
        )
        return result

    result.update(
        {
            "status": "failed",
            "error": "OpenAI translation completed but the output did not appear to be English text.",
        }
    )
    return result


def _resolve_translation_provider_sequence(config: dict[str, Any]) -> list[str]:
    provider = config["provider"]
    fallback_provider = config["fallback_provider"]

    if provider == "none":
        return []
    if provider == "google":
        sequence = ["google"]
    elif provider == "openai":
        sequence = ["openai"]
    else:
        sequence = ["google"] if config["project_id"] else ["openai"]

    if fallback_provider != "none" and fallback_provider not in sequence:
        sequence.append(fallback_provider)
    return sequence


def _translate_to_english(text: str, detected_language: str) -> dict[str, Any]:
    normalized_text = _normalize_whitespace(text)
    config = get_translation_config()
    result = _build_translation_result(
        normalized_text,
        detected_language,
        config["target_language"],
    )
    if not normalized_text:
        return result

    if detected_language == "en":
        return result

    if not config["enabled"]:
        result.update({"status": "disabled", "provider": "none"})
        return result

    provider_sequence = _resolve_translation_provider_sequence(config)
    if not provider_sequence:
        result.update(
            {
                "status": "unavailable",
                "provider": "none",
                "error": "No translation provider is configured.",
            }
        )
        return result

    attempt_errors: list[str] = []
    last_result = result
    for provider in provider_sequence:
        if provider == "google":
            current_result = _translate_to_english_via_google(
                normalized_text,
                detected_language,
                config,
            )
        else:
            current_result = _translate_to_english_via_openai(
                normalized_text,
                detected_language,
                config,
            )

        if current_result["status"] == "translated":
            return current_result

        if current_result["status"] not in {"failed", "unavailable"}:
            return current_result

        if current_result.get("error"):
            attempt_errors.append(
                f"{current_result['provider']}: {current_result['error']}"
            )
        last_result = current_result

    if attempt_errors:
        last_result = dict(last_result)
        last_result["error"] = "; ".join(attempt_errors)
    return last_result


def _extract_json_object_from_text(value: str) -> Optional[dict[str, Any]]:
    cleaned = _normalize_whitespace(value)
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    else:
        values = []
    return _dedupe_keep_order(
        [item for item in (_clean_extracted_value(entry) for entry in values) if item]
    )


def _confidence_label_to_score(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return round(max(0.0, min(1.0, float(value))), 2)
    if not isinstance(value, str):
        return round(default, 2)
    normalized = value.strip().lower()
    mapping = {
        "very high": 0.95,
        "high": 0.88,
        "medium": 0.68,
        "low": 0.45,
        "very low": 0.25,
    }
    return mapping.get(normalized, round(default, 2))


def _normalize_confidence_label(value: Any, default: str = "low") -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower()
    if normalized in {"very high", "high"}:
        return "high"
    if normalized == "medium":
        return "medium"
    if normalized in {"very low", "low"}:
        return "low"
    return default


def _normalize_match_text(value: Any) -> str:
    cleaned = _clean_extracted_value(value) or ""
    normalized = cleaned.lower()
    normalized = re.sub(r"[^a-z0-9\u0900-\u097F\u0C00-\u0C7F]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_match_tokens(value: Any) -> list[str]:
    normalized = _normalize_match_text(value)
    if not normalized:
        return []
    tokens = normalized.split()
    return [
        token
        for token in tokens
        if token not in _LLM_VALIDATION_STOPWORDS and (len(token) > 2 or token.isdigit())
    ]


def _answer_declares_unknown(value: Any) -> bool:
    normalized = _normalize_match_text(value)
    if not normalized:
        return True
    return any(marker in normalized for marker in _UNKNOWN_FIELD_MARKERS)


def _match_text_contains(haystack: Any, needle: Any) -> bool:
    normalized_haystack = _normalize_match_text(haystack)
    normalized_needle = _normalize_match_text(needle)
    if not normalized_haystack or not normalized_needle:
        return False
    return normalized_needle in normalized_haystack


def _extract_supported_evidence(evidence: list[str], source_text: str) -> list[str]:
    supported = []
    for snippet in evidence:
        cleaned = _clean_extracted_value(snippet)
        if not cleaned:
            continue
        if _match_text_contains(source_text, cleaned):
            supported.append(cleaned)
    return _dedupe_keep_order(supported)


def _token_overlap_ratio(value: Any, supporting_text: Any) -> float:
    value_tokens = set(_extract_match_tokens(value))
    if not value_tokens:
        return 0.0
    supporting_tokens = set(_extract_match_tokens(supporting_text))
    if not supporting_tokens:
        return 0.0
    return len(value_tokens & supporting_tokens) / len(value_tokens)


def _value_supported_by_source(
    value: Any,
    evidence: list[str],
    source_text: str,
    *,
    field_name: str,
) -> bool:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return False

    supporting_text = "\n".join(_dedupe_keep_order([*evidence, source_text]))
    if _match_text_contains(supporting_text, cleaned):
        return True

    if field_name == "when":
        temporal_fragments = _collect_pattern_matches(cleaned, _DATE_PATTERNS) + _collect_pattern_matches(
            cleaned, _TIME_PATTERNS
        )
        if temporal_fragments:
            return all(_match_text_contains(supporting_text, fragment) for fragment in temporal_fragments)

    overlap_ratio = _token_overlap_ratio(cleaned, supporting_text)
    threshold = {
        "who": 0.5,
        "what": 0.45,
        "when": 0.5,
        "where": 0.5,
        "why": 0.45,
        "how": 0.45,
    }.get(field_name, 0.5)
    if field_name == "why":
        normalized_value = _normalize_match_text(cleaned)
        normalized_support = _normalize_match_text(supporting_text)
        if any(
            phrase in normalized_value
            for phrase in ("reckless driving", "wrong side driving", "speeding", "negligence", "drunk driving")
        ) and any(
            phrase in normalized_support
            for phrase in (
                "opposite direction",
                "overtaking another vehicle",
                "hit me",
                "collided",
                "came from behind",
                "snatched",
            )
        ):
            return True
    return overlap_ratio >= threshold


def _role_value_supported_by_source(value: Any, evidence: list[str], source_text: str) -> bool:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return False
    if _is_unknown_actor(cleaned):
        role_fragment = re.sub(
            r"^(?:unknown|unidentified)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if any(_match_text_contains(source_text, pattern) for pattern in _UNKNOWN_ACTOR_PATTERNS) or any(
            _match_text_contains(snippet, pattern)
            for snippet in evidence
            for pattern in _UNKNOWN_ACTOR_PATTERNS
        ):
            return True
        if role_fragment:
            return _token_overlap_ratio(role_fragment, "\n".join([*evidence, source_text])) >= 0.5
        return False
    return _value_supported_by_source(cleaned, evidence, source_text, field_name="who")


def _answer_has_payload(answer: Any, *, field_name: str) -> bool:
    if not isinstance(answer, dict):
        return False
    if field_name == "who":
        return any(
            _normalize_string_list(answer.get(role))
            for role in ("complainant", "victim", "accused", "witnesses")
        ) or bool(_normalize_string_list(answer.get("evidence")))
    if field_name == "when":
        return any(
            _clean_extracted_value(answer.get(key))
            for key in ("answer", "value", "date", "time")
        ) or bool(_normalize_string_list(answer.get("evidence")))
    return bool(
        _clean_extracted_value(answer.get("answer") or answer.get("value"))
        or _normalize_string_list(answer.get("evidence"))
    )


def _validate_field_question_answer(
    answer: Any,
    *,
    field_name: str,
    source_text: str,
    min_confidence_score: float,
    require_evidence: bool,
) -> dict[str, Any]:
    validation = {
        "attempted": False,
        "accepted": False,
        "reason": None,
        "sanitized_answer": None,
    }
    if not isinstance(answer, dict):
        return validation
    if not _answer_has_payload(answer, field_name=field_name):
        return validation

    validation["attempted"] = True
    confidence_label = _normalize_confidence_label(answer.get("confidence"), "low")
    confidence_score = _confidence_label_to_score(confidence_label, 0.0)
    if confidence_score < min_confidence_score:
        validation["reason"] = "confidence_below_threshold"
        return validation

    evidence = _extract_supported_evidence(
        _normalize_string_list(answer.get("evidence")),
        source_text,
    )
    if require_evidence and not evidence:
        validation["reason"] = "evidence_not_found_in_source"
        return validation

    if field_name == "when":
        date_value = _clean_extracted_value(answer.get("date"))
        time_value = _clean_extracted_value(answer.get("time"))
        if date_value and not _value_supported_by_source(date_value, evidence, source_text, field_name="when"):
            date_value = None
        if time_value and not _value_supported_by_source(time_value, evidence, source_text, field_name="when"):
            time_value = None
        answer_value = _clean_extracted_value(answer.get("answer") or answer.get("value"))
        if answer_value and not _answer_declares_unknown(answer_value):
            if not _value_supported_by_source(answer_value, evidence, source_text, field_name="when"):
                answer_value = None
        else:
            answer_value = None
        if not answer_value:
            answer_value = _clean_extracted_value(
                "; ".join(part for part in (date_value, time_value) if part)
            )
        if not answer_value:
            validation["reason"] = "answer_not_supported_by_source"
            return validation
        validation["accepted"] = True
        validation["sanitized_answer"] = {
            "answer": answer_value,
            "date": date_value or "",
            "time": time_value or "",
            "confidence": confidence_label,
            "evidence": evidence,
        }
        return validation

    answer_value = _clean_extracted_value(answer.get("answer") or answer.get("value"))
    if not answer_value or _answer_declares_unknown(answer_value):
        validation["reason"] = "unknown_or_empty"
        return validation
    if not _value_supported_by_source(answer_value, evidence, source_text, field_name=field_name):
        validation["reason"] = "answer_not_supported_by_source"
        return validation

    validation["accepted"] = True
    validation["sanitized_answer"] = {
        "answer": answer_value,
        "confidence": confidence_label,
        "evidence": evidence,
    }
    return validation


def _validate_who_question_answer(
    answer: Any,
    *,
    source_text: str,
    min_confidence_score: float,
    require_evidence: bool,
) -> dict[str, Any]:
    validation = {
        "attempted": False,
        "accepted": False,
        "reason": None,
        "sanitized_answer": None,
        "accepted_roles": [],
        "rejected_roles": {},
    }
    if not isinstance(answer, dict):
        return validation
    if not _answer_has_payload(answer, field_name="who"):
        return validation

    validation["attempted"] = True
    confidence_label = _normalize_confidence_label(answer.get("confidence"), "low")
    confidence_score = _confidence_label_to_score(confidence_label, 0.0)
    if confidence_score < min_confidence_score:
        validation["reason"] = "confidence_below_threshold"
        return validation

    evidence = _extract_supported_evidence(
        _normalize_string_list(answer.get("evidence")),
        source_text,
    )
    if require_evidence and not evidence:
        validation["reason"] = "evidence_not_found_in_source"
        return validation

    sanitized_answer = {
        "complainant": [],
        "victim": [],
        "accused": [],
        "witnesses": [],
        "confidence": confidence_label,
        "evidence": evidence,
    }
    for role in ("complainant", "victim", "accused", "witnesses"):
        values = _normalize_string_list(answer.get(role))
        if not values:
            continue
        accepted_values = [
            value for value in values if _role_value_supported_by_source(value, evidence, source_text)
        ]
        if accepted_values:
            sanitized_answer[role] = accepted_values
            validation["accepted_roles"].append(role)
        else:
            validation["rejected_roles"][role] = "answer_not_supported_by_source"

    if not validation["accepted_roles"]:
        validation["reason"] = "answer_not_supported_by_source"
        return validation

    validation["accepted"] = True
    validation["sanitized_answer"] = sanitized_answer
    return validation


def _validate_question_guided_answers(
    llm_payload: Optional[dict[str, Any]],
    *,
    source_text: str,
    config: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if not llm_payload or not isinstance(llm_payload.get("answers"), dict):
        return None

    validation_summary = {
        "accepted_fields": [],
        "accepted_details": [],
        "rejected_fields": [],
        "rejected_details": [],
        "rejected_reasons": {},
    }
    validated_payload = {
        "complaint_summary": _clean_extracted_value(llm_payload.get("complaint_summary")),
        "review_questions": _normalize_string_list(llm_payload.get("review_questions")),
        "answers": {},
        "validation": validation_summary,
    }
    answers = llm_payload["answers"]

    who_validation = _validate_who_question_answer(
        answers.get("who"),
        source_text=source_text,
        min_confidence_score=config["min_confidence_score"],
        require_evidence=bool(config["require_evidence"]),
    )
    if who_validation["accepted"] and who_validation["sanitized_answer"]:
        validated_payload["answers"]["who"] = who_validation["sanitized_answer"]
        validation_summary["accepted_fields"].append("who")
        validation_summary["accepted_details"].extend(
            [f"who.{role}" for role in who_validation["accepted_roles"]]
        )
        for role, reason in who_validation["rejected_roles"].items():
            detail = f"who.{role}"
            validation_summary["rejected_details"].append(detail)
            validation_summary["rejected_reasons"][detail] = reason
    elif who_validation["attempted"]:
        validation_summary["rejected_fields"].append("who")
        validation_summary["rejected_reasons"]["who"] = who_validation["reason"] or "validation_failed"

    for field_name in ("what", "when", "where", "why", "how"):
        field_validation = _validate_field_question_answer(
            answers.get(field_name),
            field_name=field_name,
            source_text=source_text,
            min_confidence_score=config["min_confidence_score"],
            require_evidence=bool(config["require_evidence"]),
        )
        if field_validation["accepted"] and field_validation["sanitized_answer"]:
            validated_payload["answers"][field_name] = field_validation["sanitized_answer"]
            validation_summary["accepted_fields"].append(field_name)
        elif field_validation["attempted"]:
            validation_summary["rejected_fields"].append(field_name)
            validation_summary["rejected_reasons"][field_name] = (
                field_validation["reason"] or "validation_failed"
            )

    validation_summary["accepted_fields"] = _dedupe_keep_order(validation_summary["accepted_fields"])
    validation_summary["accepted_details"] = _dedupe_keep_order(validation_summary["accepted_details"])
    validation_summary["rejected_fields"] = _dedupe_keep_order(validation_summary["rejected_fields"])
    validation_summary["rejected_details"] = _dedupe_keep_order(validation_summary["rejected_details"])
    return validated_payload


def _build_field_payload_from_question_answer(
    answer: Any,
    fallback_field: dict[str, Any],
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(answer, dict):
        return fallback_field

    value = _clean_extracted_value(answer.get("answer") or answer.get("value"))
    evidence = _normalize_string_list(answer.get("evidence"))
    confidence = _confidence_label_to_score(
        answer.get("confidence"),
        fallback_field.get("confidence_score") or 0.0,
    )

    if field_name == "when":
        date_value = _clean_extracted_value(answer.get("date"))
        time_value = _clean_extracted_value(answer.get("time"))
        if date_value or time_value:
            value = value or "; ".join(
                part for part in (date_value, time_value) if part
            )
            payload = _make_field_payload(
                value,
                evidence or fallback_field.get("evidence", []),
                confidence or 0.82,
                status="present" if confidence >= 0.72 else "uncertain",
                components={
                    "date": {
                        "status": "present" if date_value else "missing",
                        "value": date_value,
                    },
                    "time": {
                        "status": "present" if time_value else "missing",
                        "value": time_value,
                    },
                },
            )
            return payload
        return fallback_field

    if not value:
        return fallback_field

    return _make_field_payload(
        value,
        evidence or fallback_field.get("evidence", []),
        confidence or fallback_field.get("confidence_score") or 0.72,
        status="present" if confidence >= 0.72 else "uncertain",
    )


def _build_who_payload_from_question_answer(
    answer: Any,
    fallback_field: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(answer, dict):
        return fallback_field

    fallback_components = (
        fallback_field.get("components")
        if isinstance(fallback_field.get("components"), dict)
        else {}
    )
    evidence = _normalize_string_list(answer.get("evidence")) or fallback_field.get("evidence", [])
    components = {}
    role_order = ("complainant", "victim", "accused", "witnesses")
    for role in role_order:
        answer_values = _normalize_string_list(answer.get(role))
        fallback_component = fallback_components.get(role, {})
        fallback_values = fallback_component.get("values", []) if isinstance(fallback_component, dict) else []
        merged_values = answer_values or fallback_values
        inferred = bool(fallback_component.get("inferred")) if isinstance(fallback_component, dict) else False
        component = _build_component_payload(merged_values, inferred=inferred)
        if component["status"] != "missing":
            component["confidence_score"] = _confidence_label_to_score(
                answer.get("confidence"),
                component.get("confidence_score", 0.0),
            )
            if component["status"] == "present" and component["confidence_score"] < 0.72:
                component["status"] = "uncertain"
        components[role] = component

    role_fragments = []
    present_components = 0
    uncertain_components = 0
    for role in role_order:
        values = components[role]["values"]
        if values:
            role_fragments.append(f"{role}: {', '.join(values)}")
        if components[role]["status"] == "present":
            present_components += 1
        elif components[role]["status"] == "uncertain":
            uncertain_components += 1

    if present_components:
        status = "present"
        confidence_score = min(0.95, 0.7 + (present_components * 0.1))
    elif uncertain_components:
        status = "uncertain"
        confidence_score = 0.58
    else:
        return fallback_field

    return _make_field_payload(
        "; ".join(role_fragments),
        evidence,
        confidence_score,
        status=status,
        components=components,
    )


def _extract_complaint_insights_via_openai(
    english_text: str,
    heuristic_fields: dict[str, dict[str, Any]],
) -> Optional[dict[str, Any]]:
    normalized_text = _normalize_whitespace(english_text)
    if not normalized_text:
        return None

    config = get_question_guided_extraction_config()
    if not config["enabled"] or not config["api_key"]:
        return None

    heuristic_snapshot = {
        field_name: {
            "status": field_value.get("status"),
            "value": field_value.get("value"),
            "components": field_value.get("components"),
        }
        for field_name, field_value in heuristic_fields.items()
    }
    input_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": _EXTRACTION_SYSTEM_PROMPT}],
        },
    ]
    for example in _EXTRACTION_FEW_SHOT_EXAMPLES:
        input_messages.append({
            "role": example["role"],
            "content": [{
                "type": "output_text" if example["role"] == "assistant" else "input_text",
                "text": example["content"],
            }],
        })
    input_messages.append({
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": (
                    "Complaint text:\n"
                    + normalized_text
                    + "\n\n---\nHeuristic pre-extraction (WARNING — known failure modes: "
                    "WHERE may contain hospital/current location instead of incident site; "
                    "WHAT may be an entire paragraph instead of a concise summary; "
                    "WHY and HOW are often missing for non-theft complaints like accidents; "
                    "ACCUSED may be empty when an unknown offender role is described in the text). "
                    "Re-derive every answer independently from the complaint text above:\n"
                    + json.dumps(heuristic_snapshot, ensure_ascii=False, indent=2)
                ),
            }
        ],
    })
    payload: dict[str, Any] = {
        "model": config["model"],
        "input": input_messages,
    }
    reasoning_effort = config["reasoning_effort"]
    if reasoning_effort in {"none", "low", "medium", "high", "xhigh"}:
        payload["reasoning"] = {"effort": reasoning_effort}

    request = urllib.request.Request(
        f"{config['base_url']}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        ssl_context = _build_openai_ssl_context()
        with urllib.request.urlopen(request, timeout=180, context=ssl_context) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning(
            "Question-guided OpenAI extraction failed: %s",
            _extract_openai_error_message(exc.read().decode("utf-8", errors="replace")),
        )
        return None
    except Exception as exc:  # pragma: no cover - depends on live network config
        logger.warning("Question-guided OpenAI extraction failed: %s", exc)
        return None

    output_text = _normalize_whitespace(_extract_openai_output_text(response_payload))
    return _extract_json_object_from_text(output_text)


def _merge_question_guided_fields(
    heuristic_fields: dict[str, dict[str, Any]],
    llm_payload: Optional[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not llm_payload or not isinstance(llm_payload.get("answers"), dict):
        return heuristic_fields

    merged_fields = dict(heuristic_fields)
    answers = llm_payload["answers"]
    merged_fields["who"] = _build_who_payload_from_question_answer(
        answers.get("who"),
        heuristic_fields.get("who", {}),
    )
    for field_name in ("what", "when", "where", "why", "how"):
        merged_fields[field_name] = _build_field_payload_from_question_answer(
            answers.get(field_name),
            heuristic_fields.get(field_name, {}),
            field_name=field_name,
        )
    return merged_fields


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
    from_value = _extract_from_value(lines)
    signature_name = _extract_signature_name(lines)

    for value, line in _extract_labeled_values(lines, _ROLE_LABELS.get(role, []), max_matches=3):
        if role == "complainant":
            extracted_people = [item for item in [_extract_name_from_identity_line(value)] if item]
        else:
            extracted_people = _split_people_value(value)
        if extracted_people:
            values.extend(extracted_people)
            evidence.append(line)

    if role == "complainant":
        for candidate, candidate_evidence in (
            (_extract_name_from_identity_line(from_value or ""), from_value),
            (signature_name, "Signature block"),
        ):
            if candidate:
                values.append(candidate)
                if candidate_evidence:
                    evidence.append(str(candidate_evidence))
        for line in lines:
            if not re.match(
                r"^\s*(?:i\b|my name is\b|statement(?:\s+recorded)?\s+of\b)",
                line,
                re.IGNORECASE,
            ):
                continue
            extracted_name = _extract_name_from_identity_line(line)
            if extracted_name:
                values.append(extracted_name)
                evidence.append(line)
        patterns = [
            r"\bmy name is\s+(?P<value>[^,.;\n]+)",
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
            r"\bsuspect(?:s)?\b\s+(?:is|was|are|were|named|name)\s*[:\-]?\s*(?P<value>[^.;\n]+)",
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
        for sentence in sentences:
            lowered = sentence.lower()
            if any(token in lowered for token in ("foul play", "dispute", "threat", "accused", "suspect", "worker")):
                named_person = _extract_named_entity(
                    sentence,
                    r"(?:former worker named|worker named|person named|man named|woman named|accused named|suspect named|named)",
                )
                if named_person:
                    values.append(named_person)
                    evidence.append(sentence)

            generic_match = re.search(
                r"\b(?:unknown|unidentified)\s+(?:man|woman|person|persons|accused|suspect|offender|men|boys|rider|driver|caller|vehicle)\b",
                sentence,
                re.IGNORECASE,
            )
            if generic_match:
                values.append(_standardize_unknown_actor(generic_match.group(0)))
                evidence.append(sentence)

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
    complainant_vals = set(components["complainant"]["values"])
    victim_vals = set(components["victim"]["values"])
    if complainant_vals and complainant_vals == victim_vals:
        role_fragments.append(f"complainant/victim: {', '.join(components['complainant']['values'])}")
        skip_roles = {"complainant", "victim"}
    else:
        skip_roles = set()
    for role in role_order:
        if role in skip_roles:
            continue
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


_WHAT_MAX_LENGTH = 200


def _trim_verbose_what(value: str) -> str:
    if len(value) <= _WHAT_MAX_LENGTH:
        return value
    trimmed = re.sub(
        r"^Date:\s*[^,]+,\s*(?:time\s+)?(?:around\s+|about\s+|approx(?:\.|imately)?\s+)?[^,]+,\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    trimmed = re.sub(
        r"^when\s+I\s+was\s+\w+ing\s+[^,]+,\s*",
        "",
        trimmed,
        flags=re.IGNORECASE,
    )
    trimmed = re.sub(
        r"^when\s+I\s+was\s+\w+ing\s+[^,]+,\s*",
        "",
        trimmed,
        flags=re.IGNORECASE,
    )
    trimmed = re.sub(
        r"^in the middle of the route,\s*",
        "",
        trimmed,
        flags=re.IGNORECASE,
    )
    trimmed = trimmed.strip(" ,;")
    if trimmed and len(trimmed) >= 20:
        return trimmed[0].upper() + trimmed[1:] if len(trimmed) > 1 else trimmed.upper()
    return value


def _extract_what(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    subject_value = _extract_subject_value(lines)
    if subject_value:
        return _make_field_payload(
            _strip_reporting_prefix(subject_value),
            ["Subject"],
            0.92,
            status="present",
        )

    labeled_matches = [
        (value, evidence)
        for value, evidence in _extract_labeled_values(lines, _WHAT_LABELS, max_matches=4)
        if _score_subject_candidate(value) > 0
    ]
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(_strip_reporting_prefix(value), [evidence], 0.86, status="present")

    best_sentence, score = _pick_best_sentence(sentences, _INCIDENT_KEYWORDS)
    if not best_sentence:
        return _make_field_payload(None, [], 0.0, status="missing")

    cleaned_sentence = _strip_reporting_prefix(best_sentence)
    cleaned_sentence = _trim_verbose_what(cleaned_sentence)
    if score >= 3.0:
        return _make_field_payload(cleaned_sentence, [best_sentence], 0.84, status="present")
    return _make_field_payload(cleaned_sentence, [best_sentence], 0.58, status="uncertain")


def _extract_when(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _WHEN_LABELS, max_matches=2)
    header_date = _extract_header_date(lines)
    evidence = [item[1] for item in labeled_matches]
    best_sentence = _extract_temporal_sentence(sentences)
    if best_sentence:
        evidence.append(best_sentence)

    date_candidates = _collect_pattern_matches(best_sentence or "", _DATE_PATTERNS)
    time_candidates = _collect_pattern_matches(best_sentence or "", _TIME_PATTERNS)
    if not date_candidates and header_date:
        date_candidates = [header_date]
        evidence.append("Date header")

    if labeled_matches and _score_date_candidate(labeled_matches[0][0]) > 0:
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
    cleaned = re.sub(r"\s*\d{1,2}:\d{2}\s*(?:hr|hrs|hes)\b.*$", "", cleaned, flags=re.IGNORECASE)
    for pattern in _DATE_PATTERNS + _TIME_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return _clean_extracted_value(cleaned)


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
    from_value = _extract_from_value(lines)
    header_address = _extract_address_from_identity_line(from_value)
    subject_value = _extract_subject_value(lines)
    candidates: list[tuple[str, str, float]] = []

    for value, evidence in labeled_matches:
        cleaned = _cleanup_location_value(value)
        if _is_plausible_location(cleaned):
            candidates.append((cleaned, evidence, 0.88))

    if header_address and any("above address" in sentence.lower() for sentence in sentences):
        candidates.append((header_address, "above address reference", 0.9))

    if subject_value:
        subject_lower = subject_value.lower()
        if header_address and any(token in subject_lower for token in ("from my house", "my storage room", "my shop")):
            candidates.append((header_address, subject_value, 0.95))
        subject_location = _extract_location_fragment(subject_value, header_address=header_address)
        if subject_location:
            candidates.append((subject_location, subject_value, 0.78))

    for sentence in sentences:
        fragment = _extract_location_fragment(sentence, header_address=header_address)
        if not fragment:
            continue
        score = 0.72 + min(0.18, _score_sentence(sentence, _INCIDENT_KEYWORDS) / 10)
        if any(hint in fragment.lower() for hint in _LOCATION_HINTS):
            score += 0.06
        if "," in fragment:
            score += 0.08
        if fragment.lower().startswith(("our lane", "the parking area")):
            score -= 0.12
        if fragment.lower().startswith("the parking area"):
            score -= 0.08
        if "above address" in sentence.lower():
            score = max(score, 0.9)
        sentence_lower = sentence.lower()
        if any(marker in sentence_lower for marker in (
            "brought me to", "admitted to", "taken to", "shifted to",
            "receiving treatment", "taking treatment", "am being treated",
        )):
            score -= 0.35
        if any(marker in sentence_lower for marker in (
            "i request you",
            "kindly register",
            "take necessary action",
            "collect cctv",
            "trace the offenders",
            "recover the stolen property",
        )):
            score -= 0.55
        candidates.append((fragment, sentence, score))

    if not candidates:
        return _make_field_payload(None, [], 0.0, status="missing")

    value, evidence, confidence = max(candidates, key=lambda item: item[2])
    return _make_field_payload(value, [evidence], confidence, status="present")


def _extract_why(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _WHY_LABELS, max_matches=2)
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(value, [evidence], 0.82, status="present")

    candidate_sentences = [
        sentence
        for sentence in sentences
        if any(keyword in sentence.lower() for keyword in _MOTIVE_KEYWORDS)
        or "due to" in sentence.lower()
        or "appears to be" in sentence.lower()
        or "seems to be" in sentence.lower()
    ]
    if not candidate_sentences:
        return _make_field_payload(None, [], 0.0, status="missing")

    best_sentence = max(
        candidate_sentences,
        key=lambda sentence: sum(1.0 for keyword in _MOTIVE_KEYWORDS if keyword in sentence.lower()),
    )
    fragment = _extract_reason_fragment(best_sentence)
    if fragment and _is_reason_fragment_valid(fragment, best_sentence):
        return _make_field_payload(fragment, [best_sentence], 0.82, status="present")
    return _make_field_payload(None, [], 0.0, status="missing")


_HOW_MAX_LENGTH = 120


def _trim_verbose_how(value: str) -> str:
    if len(value) <= _HOW_MAX_LENGTH:
        return value
    trimmed = re.sub(
        r"^Date:\s*[^,]+,\s*(?:time\s+)?(?:around\s+|about\s+|approx(?:\.|imately)?\s+)?[^,]+,\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    trimmed = re.sub(
        r"^when\s+I\s+was\s+\w+ing\s+[^,]+,\s*",
        "",
        trimmed,
        flags=re.IGNORECASE,
    )
    trimmed = re.sub(
        r"^in the middle of the route,\s*",
        "",
        trimmed,
        flags=re.IGNORECASE,
    )
    trimmed = trimmed.strip(" ,;")
    if trimmed and len(trimmed) >= 20:
        return trimmed[0].upper() + trimmed[1:] if len(trimmed) > 1 else trimmed.upper()
    return value


def _extract_how(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    labeled_matches = _extract_labeled_values(lines, _HOW_LABELS, max_matches=2)
    if labeled_matches:
        value, evidence = labeled_matches[0]
        return _make_field_payload(value, [evidence], 0.82, status="present")

    subject_value = _extract_subject_value(lines)
    if subject_value and "in city bus" in subject_value.lower() and any(
        "crowded" in sentence.lower() and "bus" in sentence.lower() for sentence in sentences
    ):
        return _make_field_payload(
            "during a crowded city bus journey",
            [subject_value],
            0.8,
            status="present",
        )

    candidates: list[tuple[str, float]] = []
    for sentence in sentences:
        lowered = sentence.lower()
        score = 0.0
        for hint in _METHOD_HINTS:
            if hint in lowered:
                score += 1.0
        if re.search(r"\b(?:took|taken|removed|snatched|pulled|damaged|missing|fire set|crowded|hit|collided|crashed|rammed|knocked)\b", lowered):
            score += 0.8
        if score > 0:
            candidates.append((sentence, score))

    if subject_value:
        subject_lower = subject_value.lower()
        subject_score = 0.0
        for hint in ("fire set", "snatching by", "in city bus", "from my house"):
            if hint in subject_lower:
                subject_score += 1.4
        if subject_score > 0:
            candidates.append((subject_value, subject_score))

    if not candidates:
        return _make_field_payload(None, [], 0.0, status="missing")

    best_sentence, score = max(candidates, key=lambda item: item[1])
    fragment = _extract_method_fragment(best_sentence, subject_value=subject_value)
    if fragment:
        return _make_field_payload(_trim_verbose_how(fragment), [best_sentence], 0.8, status="present")
    if score >= 1.8:
        return _make_field_payload(_trim_verbose_how(best_sentence), [best_sentence], 0.72, status="present")
    return _make_field_payload(_trim_verbose_how(best_sentence), [best_sentence], 0.56, status="uncertain")


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

    missing_details = []
    uncertain_details = []

    component_groups = {
        "who": {
            "complainant": "who.complainant",
            "victim": "who.victim",
            "accused": "who.accused",
            "witnesses": "who.witnesses",
        },
        "when": {
            "date": "when.date",
            "time": "when.time",
        },
    }
    for field_name, component_labels in component_groups.items():
        field_payload = complaint_fields.get(field_name, {})
        if field_payload.get("status") == "missing":
            continue
        components = field_payload.get("components", {})
        for component_name, detail_label in component_labels.items():
            component = components.get(component_name, {})
            component_status = component.get("status", "missing")
            if component_status == "uncertain":
                uncertain_details.append(detail_label)
            elif component_status == "missing":
                missing_details.append(detail_label)

    _READABLE_LABELS: dict[str, str] = {
        "who": "Who", "what": "What", "when": "When",
        "where": "Where", "why": "Why", "how": "How",
        "who.complainant": "complainant identity",
        "who.victim": "victim identity",
        "who.accused": "accused identity",
        "who.witnesses": "witness information",
        "when.date": "incident date",
        "when.time": "incident time",
    }

    def _readable(names: list[str]) -> str:
        return ", ".join(_READABLE_LABELS.get(n, n) for n in names)

    summary_parts = []
    if missing_fields:
        summary_parts.append(
            f"The following fields could not be identified: {_readable(missing_fields)}."
        )
    if uncertain_fields:
        summary_parts.append(
            f"The following fields require confirmation: {_readable(uncertain_fields)}."
        )
    if missing_details:
        summary_parts.append(
            f"Some details are missing: {_readable(missing_details)}."
        )
    if uncertain_details:
        summary_parts.append(
            f"Some details require confirmation: {_readable(uncertain_details)}."
        )
    if not summary_parts:
        summary_parts.append("All 5W + 1H fields were successfully identified.")

    summary = " ".join(summary_parts)

    requires_review = bool(missing_fields or uncertain_fields or pipeline_flags)
    return {
        "available_fields": present_fields,
        "missing_fields": missing_fields,
        "uncertain_fields": uncertain_fields,
        "missing_details": missing_details,
        "uncertain_details": uncertain_details,
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


def _normalize_review_question(value: str) -> Optional[str]:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return None
    cleaned = cleaned.rstrip(" .")
    if not cleaned.endswith("?"):
        cleaned = f"{cleaned}?"
    return cleaned


def _get_primary_role_values(
    complaint_fields: dict[str, dict[str, Any]],
    role_order: tuple[str, ...],
) -> list[str]:
    who_components = complaint_fields.get("who", {}).get("components", {})
    if not isinstance(who_components, dict):
        return []
    for role in role_order:
        component = who_components.get(role, {})
        if not isinstance(component, dict):
            continue
        values = component.get("values", [])
        if isinstance(values, list) and values:
            return [str(value) for value in values if _clean_extracted_value(str(value))]
    return []


def _format_people_list(values: list[str]) -> Optional[str]:
    cleaned = _dedupe_keep_order(
        [value for value in (_clean_extracted_value(item) for item in values) if value]
    )
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{cleaned[0]} and others"


def _strip_complaint_prefix(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return None
    cleaned = re.sub(
        r"^(?:complaint|report|statement|petition)\s+(?:regarding|about|of)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return _clean_extracted_value(cleaned)


def _build_complaint_brief(
    complaint_fields: dict[str, dict[str, Any]],
    llm_payload: Optional[dict[str, Any]],
) -> Optional[str]:
    llm_summary = None
    if isinstance(llm_payload, dict):
        llm_summary = _clean_extracted_value(llm_payload.get("complaint_summary"))
    if llm_summary:
        return llm_summary

    lead_actor = _format_people_list(
        _get_primary_role_values(complaint_fields, ("victim", "complainant"))
    )
    accused = _format_people_list(
        _get_primary_role_values(complaint_fields, ("accused",))
    )
    what_value = _strip_complaint_prefix(complaint_fields.get("what", {}).get("value"))
    where_value = _clean_extracted_value(complaint_fields.get("where", {}).get("value"))
    when_value = _clean_extracted_value(complaint_fields.get("when", {}).get("value"))
    how_value = _clean_extracted_value(complaint_fields.get("how", {}).get("value"))
    why_value = _clean_extracted_value(complaint_fields.get("why", {}).get("value"))

    # Reject WHERE values that look like garbage translation artefacts:
    # too short, contain first-person pronouns, or lack any location-like word.
    _LOCATION_NOISE = re.compile(
        r"\b(my |I |we |went there|came back|returning|received|hours?,)",
        re.IGNORECASE,
    )
    if where_value and (len(where_value) < 5 or _LOCATION_NOISE.search(where_value)):
        where_value = None

    sentences: list[str] = []

    # Opening sentence: who reported what
    if lead_actor and what_value:
        sentences.append(f"{lead_actor} reported that {what_value}.")
    elif what_value:
        sentences.append(what_value[0].upper() + what_value[1:] + ("." if not what_value.endswith(".") else ""))

    # When and where as a single context sentence
    context_parts: list[str] = []
    if when_value:
        context_parts.append(f"on {when_value}")
    if where_value:
        context_parts.append(f"at {where_value}")
    if context_parts:
        sentences.append(f"The incident occurred {', '.join(context_parts)}.")

    # How — already a descriptive phrase, just capitalise and add period
    if how_value:
        how_sentence = how_value[0].upper() + how_value[1:]
        if not how_sentence.endswith("."):
            how_sentence += "."
        sentences.append(how_sentence)

    if accused:
        sentences.append(f"The accused is identified as {accused}.")
    if why_value:
        sentences.append(f"The apparent motive is {why_value}.")

    if not sentences:
        return _build_incident_overview(complaint_fields)
    return " ".join(sentences[:4])


def _build_review_questions(
    complaint_fields: dict[str, dict[str, Any]],
    gaps: dict[str, Any],
    llm_payload: Optional[dict[str, Any]],
) -> list[str]:
    questions: list[str] = []
    if isinstance(llm_payload, dict):
        for raw_question in _normalize_string_list(llm_payload.get("review_questions")):
            question = _normalize_review_question(raw_question)
            if question:
                questions.append(question)

    if not gaps.get("requires_review"):
        return _dedupe_keep_order(questions)

    for label in gaps.get("missing_details", []) or []:
        if label in _REVIEW_QUESTION_MAP:
            question = _normalize_review_question(_REVIEW_QUESTION_MAP[label])
            if question:
                questions.append(question)

    for label in gaps.get("uncertain_details", []) or []:
        if label in _REVIEW_QUESTION_MAP:
            question = _normalize_review_question(_REVIEW_QUESTION_MAP[label])
            if question:
                questions.append(question)

    for field_name in gaps.get("missing_fields", []) or []:
        if field_name in _REVIEW_QUESTION_MAP:
            question = _normalize_review_question(_REVIEW_QUESTION_MAP[field_name])
            if question:
                questions.append(question)

    for field_name in gaps.get("uncertain_fields", []) or []:
        if field_name in _REVIEW_QUESTION_MAP:
            question = _normalize_review_question(_REVIEW_QUESTION_MAP[field_name])
            if question:
                questions.append(question)

    if not questions and complaint_fields.get("who", {}).get("status") != "present":
        fallback_question = _normalize_review_question(_REVIEW_QUESTION_MAP["who"])
        if fallback_question:
            questions.append(fallback_question)

    return _dedupe_keep_order(questions)[:6]


def _score_to_confidence_label(score: float) -> str:
    if score >= 0.82:
        return "high"
    if score >= 0.58:
        return "medium"
    return "low"


def _normalize_fir_field(value: Any, fallback: str = "Not stated") -> str:
    cleaned = _clean_extracted_value(value)
    return cleaned or fallback


def _extract_year_from_temporal_value(value: Optional[str]) -> Optional[str]:
    cleaned = _clean_extracted_value(value)
    if not cleaned:
        return None
    match = re.search(r"(20\d{2}|\d{2})(?!.*\d)", cleaned)
    if not match:
        return None
    year = match.group(1)
    if len(year) == 2:
        year = f"20{year}"
    return year


def _extract_contact_number(text: str) -> Optional[str]:
    matches = re.findall(r"(?<!\d)(?:\+91[-\s]?)?([6-9]\d{9})(?!\d)", text)
    if not matches:
        return None
    return matches[0]


def _extract_information_received(lines: list[str], sentences: list[str]) -> dict[str, Any]:
    triggers = ("received on", "statement recorded", "recorded by", "petition", "reported on")
    candidates = [line for line in lines if any(trigger in line.lower() for trigger in triggers)]
    candidates.extend(
        sentence for sentence in sentences if any(trigger in sentence.lower() for trigger in triggers)
    )
    for candidate in candidates:
        date_matches = _collect_pattern_matches(candidate, _DATE_PATTERNS)
        time_matches = _collect_pattern_matches(candidate, _TIME_PATTERNS)
        if not date_matches and not time_matches:
            continue
        return {
            "date": date_matches[0] if date_matches else None,
            "time": time_matches[0] if time_matches else None,
            "evidence": _clean_extracted_value(candidate),
        }
    return {"date": None, "time": None, "evidence": None}


def _extract_informant_address(lines: list[str], english_text: str) -> Optional[str]:
    from_value = _extract_from_value(lines)
    header_address = _extract_address_from_identity_line(from_value)
    if header_address:
        return header_address

    patterns = (
        r"\b(?:residing at|resident of|r/o|r\/o|address(?: is)?)\s+(?P<value>[^.\n]+)",
        r"\bR/O\s+(?P<value>[^.\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, english_text, re.IGNORECASE)
        if match:
            address = _clean_extracted_value(match.group("value"))
            if address:
                return address
    return None


def _extract_police_station(lines: list[str], english_text: str) -> Optional[str]:
    candidate_rows = lines + [english_text]
    patterns = (
        r"\b(?:statement recorded by|recorded by|reported to|before)\s+(?:ps|p\.s\.|police station)\s*(?P<value>[A-Za-z][A-Za-z .'-]{1,40}?)(?=\s+(?:on|at|dated)\b|[.,]|$)",
        r"\b(?P<value>[A-Za-z][A-Za-z .'-]{1,40}?)\s+(?:police station|ps)\b",
        r"\b(?:inspector|sub-?inspector)\s+of\s+police,\s*(?P<value>[A-Za-z][A-Za-z .'-]{1,40}?)(?=[.,]|$)",
    )
    for row in candidate_rows:
        cleaned_row = _normalize_whitespace(row)
        if not cleaned_row:
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, cleaned_row, re.IGNORECASE):
                value = _clean_extracted_value(match.group("value"))
                if not value:
                    continue
                value = re.sub(r"\b(?:ps|p\.s\.|police station)\b", "", value, flags=re.IGNORECASE)
                value = value.strip(" ,.-")
                lowered = value.lower()
                if not value or any(
                    noise in lowered for noise in ("statement", "recorded", "police", "inspector")
                ):
                    continue
                if len(value.split()) > 5:
                    continue
                return value.title()
    return None


def _guess_district_unit(address: Optional[str], where_value: Optional[str], police_station: Optional[str]) -> Optional[str]:
    for raw_candidate in (address, where_value):
        cleaned = _clean_extracted_value(raw_candidate)
        if not cleaned:
            continue
        parts = [_clean_extracted_value(part) for part in cleaned.split(",")]
        for part in reversed(parts):
            if part:
                return part
    if police_station:
        return police_station
    return None


def _collect_matching_snippets(
    complaint_fields: dict[str, dict[str, Any]],
    sentences: list[str],
    *,
    keywords: tuple[str, ...],
    field_names: tuple[str, ...],
    max_items: int = 3,
) -> list[str]:
    evidence: list[str] = []
    for field_name in field_names:
        field = complaint_fields.get(field_name, {})
        evidence.extend(_normalize_string_list(field.get("evidence")))
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            evidence.append(sentence)
    cleaned = [_clean_extracted_value(item) for item in evidence if _clean_extracted_value(item)]
    return _dedupe_keep_order(cleaned)[:max_items]


def _extract_loss_or_property_summary(
    lines: list[str],
    sentences: list[str],
    complaint_fields: dict[str, dict[str, Any]],
) -> Optional[str]:
    subject_value = _extract_subject_value(lines)
    if subject_value and any(
        token in subject_value.lower()
        for token in (
            "theft",
            "stolen",
            "snatching",
            "mobile",
            "vehicle",
            "motorcycle",
            "cash",
            "gold",
            "wallet",
            "purse",
            "fire",
            "fraud",
            "debited",
            "damage",
        )
    ):
        return _strip_reporting_prefix(subject_value)

    keywords = (
        "rs.",
        "cash",
        "gold",
        "wallet",
        "purse",
        "mobile",
        "phone",
        "motorcycle",
        "vehicle",
        "chain",
        "ring",
        "ornaments",
        "debited",
        "account",
        "goods",
        "damaged",
        "stolen",
        "missing",
        "snatched",
        "property",
    )
    candidates: list[tuple[float, str]] = []
    for sentence in sentences:
        lowered = sentence.lower()
        score = 0.0
        if re.search(r"\brs\.?\s*\d", lowered):
            score += 2.0
        if any(keyword in lowered for keyword in ("debited", "stolen", "missing", "snatched", "damaged", "burned")):
            score += 1.5
        score += sum(0.25 for keyword in keywords if keyword in lowered)
        if score > 0:
            candidates.append((score, sentence))
    if candidates:
        return _clean_extracted_value(max(candidates, key=lambda item: item[0])[1])

    what_value = _clean_extracted_value(complaint_fields.get("what", {}).get("value"))
    if what_value and any(keyword in what_value.lower() for keyword in keywords):
        return what_value
    return None


def _extract_injury_or_harm_summary(sentences: list[str], english_text: str) -> Optional[str]:
    keywords = (
        "injury",
        "injuries",
        "hurt",
        "fracture",
        "fractures",
        "broken",
        "bone",
        "operation",
        "bleeding",
        "scratch",
        "wound",
        "pain",
        "treatment",
        "hospital",
    )
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            return _clean_extracted_value(sentence)
    if any(keyword in english_text.lower() for keyword in keywords):
        return "Injury or bodily harm is described in the complaint."
    return None


def _infer_unknown_accused_label(english_text: str, complaint_fields: dict[str, dict[str, Any]]) -> Optional[str]:
    accused_values = _get_primary_role_values(complaint_fields, ("accused",))
    if accused_values:
        return None
    lowered = english_text.lower()
    if any(token in lowered for token in ("bank officer", "otp", "caller", "account blocked")):
        return "Unknown caller impersonating a bank representative"
    if any(token in lowered for token in ("bike", "car", "vehicle", "overtaking", "collision", "accident")):
        return "Unknown rider or driver of the offending vehicle"
    if any(token in lowered for token in ("theft", "stolen", "missing", "snatched", "robbery")):
        return "Unknown accused person(s)"
    return None


def _select_preferred_name(candidates: list[str], english_text: str) -> Optional[str]:
    cleaned_candidates = _dedupe_keep_order(
        [value for value in (_clean_name_fragment(item) for item in candidates) if value]
    )
    if not cleaned_candidates:
        return None

    lowered_text = english_text.lower()
    for candidate in cleaned_candidates:
        candidate_pattern = re.escape(candidate.lower())
        if re.search(rf"\bi,\s*{candidate_pattern}\b", lowered_text):
            return candidate
        if re.search(rf"\bmy name is\s+{candidate_pattern}\b", lowered_text):
            return candidate

    return min(cleaned_candidates, key=lambda item: (len(item), item))


def _extract_preferred_informant_name(
    lines: list[str],
    sentences: list[str],
    english_text: str,
    complaint_fields: dict[str, dict[str, Any]],
) -> Optional[str]:
    role_candidates = _get_primary_role_values(complaint_fields, ("complainant", "victim"))
    preferred_role_name = _select_preferred_name(role_candidates, english_text)
    if preferred_role_name:
        return preferred_role_name

    for candidate in [*sentences, *lines]:
        cleaned_candidate = _clean_extracted_value(candidate)
        if not cleaned_candidate:
            continue
        if not re.search(r"\b(?:i\s*,|my name is|i am|statement of|complaint of|from)\b", cleaned_candidate, re.IGNORECASE):
            continue
        first_person_match = re.search(
            r"\bI,\s*(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,5})\s*,",
            cleaned_candidate,
            re.IGNORECASE,
        )
        if first_person_match:
            name = _clean_name_fragment(first_person_match.group("value"))
            if name:
                return name
        name = _extract_name_from_identity_line(cleaned_candidate)
        if name:
            return name
    return None


def _build_bns_section_payload(
    section: str,
    title: str,
    offence_head: str,
    confidence_score: float,
    evidence: list[str],
    rationale: str,
    *,
    fit: str = "primary",
    review_note: Optional[str] = None,
) -> dict[str, Any]:
    score = round(max(0.0, min(1.0, confidence_score)), 2)
    payload = {
        "section": section,
        "title": title,
        "offence_head": offence_head,
        "fit": fit,
        "confidence": _score_to_confidence_label(score),
        "confidence_score": score,
        "evidence": _dedupe_keep_order(
            [_clean_extracted_value(item) for item in evidence if _clean_extracted_value(item)]
        )[:3],
        "rationale": _clean_extracted_value(rationale),
        "act": "Bharatiya Nyaya Sanhita, 2023",
        "act_url": _BNS_REFERENCE_URL,
    }
    if review_note:
        payload["review_note"] = _clean_extracted_value(review_note)
    return payload


def _merge_bns_suggestions(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for suggestion in suggestions:
        section = _clean_extracted_value(suggestion.get("section"))
        if not section:
            continue
        if section not in merged:
            merged[section] = suggestion
            order.append(section)
            continue
        existing = merged[section]
        existing["evidence"] = _dedupe_keep_order(
            _normalize_string_list(existing.get("evidence")) + _normalize_string_list(suggestion.get("evidence"))
        )[:3]
        if float(suggestion.get("confidence_score") or 0.0) > float(existing.get("confidence_score") or 0.0):
            existing.update({
                "confidence": suggestion.get("confidence"),
                "confidence_score": suggestion.get("confidence_score"),
                "rationale": suggestion.get("rationale"),
                "fit": suggestion.get("fit", existing.get("fit")),
                "review_note": suggestion.get("review_note", existing.get("review_note")),
                "offence_head": suggestion.get("offence_head", existing.get("offence_head")),
            })
    return [merged[section] for section in order]


def _suggest_bns_sections(
    english_text: str,
    lines: list[str],
    sentences: list[str],
    complaint_fields: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    lowered = english_text.lower()
    subject_value = _extract_subject_value(lines) or ""
    subject_lower = subject_value.lower()
    what_lower = _normalize_match_text(complaint_fields.get("what", {}).get("value"))
    how_lower = _normalize_match_text(complaint_fields.get("how", {}).get("value"))
    where_lower = _normalize_match_text(complaint_fields.get("where", {}).get("value"))
    why_lower = _normalize_match_text(complaint_fields.get("why", {}).get("value"))

    vehicle_reference_like = any(
        token in lowered or token in what_lower or token in how_lower
        for token in ("bike", "car", "vehicle", "lorry", "truck", "bus", "auto")
    )
    impact_marker_like = any(
        token in lowered or token in what_lower or token in how_lower
        for token in (
            "accident",
            "collision",
            "crash",
            "overtaking",
            "head on",
            "head-on",
            "knocked down",
            "run over",
            "hit me",
            "collided",
            "came from the opposite direction",
        )
    )
    accident_like = impact_marker_like and vehicle_reference_like
    road_like = any(token in f"{where_lower} {lowered}" for token in ("road", "street", "lane", "junction", "cross", "highway"))
    grievous_hurt_like = any(
        token in lowered for token in ("fracture", "fractures", "broken", "bone", "surgery", "operation", "dislocation")
    )
    hurt_like = grievous_hurt_like or any(
        token in lowered for token in ("injury", "injuries", "hurt", "bleeding", "scratch", "wound", "pain")
    )
    theft_like = any(
        token in lowered or token in subject_lower or token in what_lower
        for token in ("theft", "stolen", "stole", "missing", "took", "removed", "wallet", "purse", "mobile", "motorcycle")
    ) and not accident_like
    snatching_like = any(
        token in lowered or token in subject_lower or token in how_lower
        for token in ("snatching", "snatched", "pulled the gold chain", "from my neck", "grabbed")
    )
    robbery_like = "robbery" in lowered or (
        any(token in lowered for token in ("snatched", "wallet", "gold ring"))
        and any(token in lowered for token in ("rod", "knife", "threat", "fear of", "hit me on the head", "assaulted"))
    )
    fraud_like = any(
        token in lowered or token in what_lower
        for token in ("fraud", "cheating", "cheated", "otp", "debited", "account would be blocked", "bank officer")
    )
    personation_like = any(
        token in lowered for token in ("impersonat", "claiming to be", "pretending to be", "posing as")
    )
    fire_like = any(
        token in lowered or token in subject_lower or token in how_lower
        for token in ("fire set", "arson", "flames", "smoke", "burn", "storage room", "deliberate fire")
    )
    house_like = bool(
        re.search(
            r"\b(?:house|home|dwelling|bedroom|storage room|shop|flat|apartment)\b",
            f"{lowered}\n{subject_lower}",
        )
    )
    transport_theft_like = theft_like and any(token in lowered or token in subject_lower for token in ("bus", "train", "means of transportation"))
    break_in_like = any(
        token in lowered
        for token in ("door latch damaged", "forced open", "broke open", "cupboard open", "house-breaking", "house breaking")
    )
    intimidation_like = any(token in lowered or token in why_lower for token in ("threat", "threatened", "intimidat"))
    assault_like = any(token in lowered or token in what_lower for token in ("assault", "attack", "beaten", "hit"))
    dangerous_weapon_like = any(token in lowered for token in ("rod", "knife", "blade", "acid", "iron rod"))
    money_loss_like = any(token in lowered for token in ("rs.", "debited", "cash", "gold", "wallet", "purse", "property"))

    suggestions: list[dict[str, Any]] = []

    if accident_like and road_like:
        suggestions.append(
            _build_bns_section_payload(
                "281",
                "Rash driving or riding on a public way",
                "Road accident / rash driving",
                0.9 if any(token in lowered for token in ("overtaking", "opposite direction", "hit me")) else 0.76,
                _collect_matching_snippets(
                    complaint_fields,
                    sentences,
                    keywords=("overtaking", "opposite direction", "hit me", "collision", "crash", "road", "route"),
                    field_names=("what", "where", "how"),
                ),
                "The complaint describes a vehicle being driven on a public road in a rash or unsafe manner that led to the collision.",
            )
        )
        if grievous_hurt_like:
            suggestions.append(
                _build_bns_section_payload(
                    "125(b)",
                    "Act endangering life or personal safety of others",
                    "Grievous hurt by rash or negligent act",
                    0.9,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("fracture", "broken", "bone", "surgery", "operation", "injury"),
                        field_names=("what", "how"),
                    ),
                    "The complaint alleges grievous hurt, including fracture or surgery-related injury, caused by a rash or negligent vehicle act.",
                    fit="related",
                )
            )
        elif hurt_like:
            suggestions.append(
                _build_bns_section_payload(
                    "125(a)",
                    "Act endangering life or personal safety of others",
                    "Hurt by rash or negligent act",
                    0.74,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("injury", "hurt", "bleeding", "fell down", "scratch"),
                        field_names=("what", "how"),
                    ),
                    "The complaint alleges hurt caused by a rash or negligent vehicle act.",
                    fit="related",
                )
            )

    if fraud_like:
        if money_loss_like:
            suggestions.append(
                _build_bns_section_payload(
                    "318(4)",
                    "Cheating",
                    "Cheating with delivery of property",
                    0.9,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("otp", "debited", "shared the otp", "bank officer", "account"),
                        field_names=("what", "how", "why"),
                    ),
                    "The complaint describes deception that induced the complainant to part with money or authorize a fraudulent debit.",
                )
            )
        if personation_like or any(token in lowered for token in ("bank officer", "sbi", "caller claiming", "pretending")):
            suggestions.append(
                _build_bns_section_payload(
                    "319",
                    "Cheating by personation",
                    "Impersonation-based cheating",
                    0.88,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("claiming to be", "bank officer", "pretending", "impersonat"),
                        field_names=("what", "how"),
                    ),
                    "The complaint says the offender pretended to be another person or institution in order to cheat the complainant.",
                    fit="related",
                )
            )

    if fire_like:
        suggestions.append(
            _build_bns_section_payload(
                "326",
                "Mischief by injury, inundation, fire or explosive substance, etc.",
                "Mischief by fire",
                0.88 if any(token in lowered for token in ("deliberate", "suspect foul play", "threatened")) else 0.72,
                _collect_matching_snippets(
                    complaint_fields,
                    sentences,
                    keywords=("fire", "flames", "smoke", "storage room", "burn", "threatened"),
                    field_names=("what", "how", "why"),
                ),
                "The complaint describes intentional or suspicious fire damage to property.",
            )
        )

    if robbery_like:
        suggestions.append(
            _build_bns_section_payload(
                "309",
                "Robbery",
                "Robbery",
                0.9,
                _collect_matching_snippets(
                    complaint_fields,
                    sentences,
                    keywords=("robbery", "snatched", "rod", "hit me", "wallet", "gold ring"),
                    field_names=("what", "how"),
                ),
                "The complaint alleges theft from the person accompanied by violence, hurt, threat, or immediate force.",
            )
        )
        if hurt_like or dangerous_weapon_like:
            suggestions.append(
                _build_bns_section_payload(
                    "118",
                    "Voluntarily causing hurt or grievous hurt by dangerous weapons or means",
                    "Weapon-based hurt",
                    0.7,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("rod", "knife", "blade", "hit me", "bleeding"),
                        field_names=("what", "how"),
                    ),
                    "The complaint also describes hurt caused using a potentially dangerous weapon or means.",
                    fit="related",
                    review_note="Police should confirm the exact weapon and medical injury before final sectioning.",
                )
            )
    elif snatching_like:
        suggestions.append(
            _build_bns_section_payload(
                "304",
                "Snatching",
                "Snatching",
                0.9,
                _collect_matching_snippets(
                    complaint_fields,
                    sentences,
                    keywords=("snatching", "snatched", "pulled", "from my neck", "chain"),
                    field_names=("what", "how"),
                ),
                "The complaint describes sudden taking of property from the person by snatching.",
            )
        )
        if hurt_like:
            suggestions.append(
                _build_bns_section_payload(
                    "115",
                    "Voluntarily causing hurt",
                    "Hurt",
                    0.62,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("scratch", "hurt", "bleeding", "fell down"),
                        field_names=("how",),
                    ),
                    "The complaint also mentions bodily hurt caused during the snatching.",
                    fit="related",
                )
            )
    elif theft_like:
        if house_like or transport_theft_like:
            suggestions.append(
                _build_bns_section_payload(
                    "305",
                    "Theft in a dwelling house, or means of transportation or place of worship, etc.",
                    "Aggravated theft",
                    0.86 if house_like else 0.68,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("house", "home", "shop", "room", "bus", "vehicle", "parking area", "cupboard"),
                        field_names=("what", "where", "how"),
                    ),
                    "The complaint places the theft inside a dwelling, shop, storage area, or transport setting covered by the specific theft provision.",
                )
            )
        suggestions.append(
            _build_bns_section_payload(
                "303",
                "Theft",
                "Theft",
                0.88,
                _collect_matching_snippets(
                    complaint_fields,
                    sentences,
                    keywords=("theft", "stolen", "missing", "wallet", "mobile", "motorcycle", "cash"),
                    field_names=("what", "how"),
                ),
                "The complaint alleges dishonest removal of movable property without consent.",
                fit="related" if house_like or transport_theft_like else "primary",
            )
        )
        if house_like and break_in_like:
            suggestions.append(
                _build_bns_section_payload(
                    "331",
                    "Punishment for house-trespass or house-breaking",
                    "House-breaking",
                    0.67,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("door latch damaged", "forced open", "broke open", "cupboard open"),
                        field_names=("how",),
                    ),
                    "The complaint also suggests entry or breaking into the premises to commit the theft.",
                    fit="related",
                    review_note="Police should verify whether the facts support house-breaking / house-trespass in addition to theft.",
                )
            )

    if not accident_like and assault_like and not robbery_like:
        if dangerous_weapon_like:
            suggestions.append(
                _build_bns_section_payload(
                    "118",
                    "Voluntarily causing hurt or grievous hurt by dangerous weapons or means",
                    "Weapon-based hurt",
                    0.82 if grievous_hurt_like else 0.74,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("rod", "knife", "blade", "weapon", "bleeding"),
                        field_names=("what", "how"),
                    ),
                    "The complaint describes hurt caused by a dangerous weapon or offensive means.",
                )
            )
        elif grievous_hurt_like:
            suggestions.append(
                _build_bns_section_payload(
                    "117",
                    "Voluntarily causing grievous hurt",
                    "Grievous hurt",
                    0.84,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("fracture", "broken", "bone", "grievous"),
                        field_names=("what", "how"),
                    ),
                    "The complaint alleges grievous hurt, including fracture or similarly serious bodily harm.",
                )
            )
        elif hurt_like:
            suggestions.append(
                _build_bns_section_payload(
                    "115",
                    "Voluntarily causing hurt",
                    "Hurt",
                    0.74,
                    _collect_matching_snippets(
                        complaint_fields,
                        sentences,
                        keywords=("hit", "hurt", "injury", "bleeding", "pain"),
                        field_names=("what", "how"),
                    ),
                    "The complaint alleges bodily hurt caused by the accused.",
                )
            )

    if intimidation_like:
        suggestions.append(
            _build_bns_section_payload(
                "351",
                "Criminal intimidation",
                "Criminal intimidation",
                0.68,
                _collect_matching_snippets(
                    complaint_fields,
                    sentences,
                    keywords=("threat", "threatened", "suffer loss", "intimidat"),
                    field_names=("why", "how"),
                ),
                "The complaint includes threats or intimidation connected with the incident.",
                fit="related",
            )
        )

    merged = _merge_bns_suggestions(suggestions)
    priority = {"primary": 0, "related": 1}
    return sorted(
        merged,
        key=lambda item: (
            priority.get(str(item.get("fit")), 9),
            -float(item.get("confidence_score") or 0.0),
            str(item.get("section") or ""),
        ),
    )


def _build_fir_narrative(
    complaint_fields: dict[str, dict[str, Any]],
    complaint_brief: Optional[str],
    property_summary: Optional[str],
    injury_summary: Optional[str],
    accused_text: Optional[str],
    witness_text: Optional[str],
) -> str:
    parts: list[str] = []
    brief = _clean_extracted_value(complaint_brief)
    if brief and not any(
        marker in brief.lower()
        for marker in ("went to the bank", "came to the police station", "taking treatment", "receiving treatment")
    ):
        if not brief.endswith("."):
            brief += "."
        parts.append(brief)

    how_value = _clean_extracted_value(complaint_fields.get("how", {}).get("value"))
    if (
        how_value
        and len(how_value) >= 18
        and not how_value.endswith(("Rs", "Rs."))
        and (not brief or _normalize_match_text(how_value) not in _normalize_match_text(brief))
    ):
        parts.append(how_value[0].upper() + how_value[1:] + ("." if not how_value.endswith(".") else ""))

    if property_summary:
        parts.append(f"Property, loss, or damage reported: {property_summary}.")
    if injury_summary:
        parts.append(f"Injury or harm reported: {injury_summary}.")
    if accused_text:
        parts.append(f"Known or suspected accused: {accused_text}.")
    if witness_text:
        parts.append(f"Witness or support information: {witness_text}.")

    why_value = _clean_extracted_value(complaint_fields.get("why", {}).get("value"))
    if why_value:
        parts.append(f"Apparent motive or cause stated in complaint: {why_value}.")

    return " ".join(parts[:6]) or "Complaint facts need police review before FIR drafting."


def _build_fir_draft(
    english_text: str,
    lines: list[str],
    sentences: list[str],
    complaint_fields: dict[str, dict[str, Any]],
    complaint_brief: Optional[str],
    review_questions: list[str],
) -> dict[str, Any]:
    who_components = complaint_fields.get("who", {}).get("components", {})
    complainant_name = _extract_preferred_informant_name(
        lines,
        sentences,
        english_text,
        complaint_fields,
    )
    complainant_values = (
        [complainant_name]
        if complainant_name
        else _get_primary_role_values(complaint_fields, ("complainant", "victim"))
    )
    victim_values = _get_primary_role_values(complaint_fields, ("victim", "complainant"))
    accused_values = _get_primary_role_values(complaint_fields, ("accused",))
    witness_values = _get_primary_role_values(complaint_fields, ("witnesses",))

    complainant_name = _format_people_list(complainant_values)
    victim_name = _format_people_list(victim_values) or complainant_name
    accused_name = _format_people_list(accused_values) or _infer_unknown_accused_label(english_text, complaint_fields)
    witness_name = _format_people_list(witness_values)

    address = _extract_informant_address(lines, english_text)
    contact_number = _extract_contact_number(english_text)
    police_station = _extract_police_station(lines, english_text)
    district_unit = _guess_district_unit(address, complaint_fields.get("where", {}).get("value"), police_station)
    when_components = complaint_fields.get("when", {}).get("components", {})
    occurrence_date = _clean_extracted_value(
        (when_components.get("date") or {}).get("value")
    ) or _clean_extracted_value(complaint_fields.get("when", {}).get("value"))
    occurrence_time = _clean_extracted_value((when_components.get("time") or {}).get("value"))
    information_received = _extract_information_received(lines, sentences)
    property_summary = _extract_loss_or_property_summary(lines, sentences, complaint_fields)
    injury_summary = _extract_injury_or_harm_summary(sentences, english_text)
    bns_sections = _suggest_bns_sections(english_text, lines, sentences, complaint_fields)
    primary_heads = _dedupe_keep_order(
        [item.get("offence_head") for item in bns_sections if item.get("fit") == "primary" and item.get("offence_head")]
    )
    offence_head = ", ".join(primary_heads) if primary_heads else _normalize_fir_field(complaint_fields.get("what", {}).get("value"))
    fir_narrative = _build_fir_narrative(
        complaint_fields,
        complaint_brief,
        property_summary,
        injury_summary,
        accused_name,
        witness_name,
    )
    sections_text = (
        "; ".join(
            f"BNS {item['section']} - {item['title']} ({item['confidence']})"
            for item in bns_sections
        )
        if bns_sections
        else "No confident BNS suggestion generated. Police review required."
    )
    delay_summary = "Not clearly stated in the complaint."
    if occurrence_date and information_received.get("date"):
        if _normalize_match_text(occurrence_date) == _normalize_match_text(information_received["date"]):
            delay_summary = "The complaint appears to have been reported on the same date."
        else:
            delay_summary = (
                f"Incident date appears as {occurrence_date}; information receipt appears as "
                f"{information_received['date']}. Delay should be verified by the police station."
            )

    formatted_lines = [
        "TELANGANA POLICE - DRAFT FIRST INFORMATION REPORT",
        "Status: Draft for police review only",
        "Format Basis: Telangana FIR Print workflow / NCRB IIF-I style draft",
        "1. District / Commissionerate / Unit: "
        + _normalize_fir_field(district_unit, "To be identified from jurisdiction review"),
        "2. Police Station: "
        + _normalize_fir_field(police_station, "To be identified from complaint routing"),
        "3. FIR Number / Year: To be assigned by police station"
        + (f" / {_extract_year_from_temporal_value(occurrence_date)}" if _extract_year_from_temporal_value(occurrence_date) else ""),
        "4. Date and Time of Registration: To be assigned by police station",
        "5. Mode of Information: "
        + (
            "Written complaint / statement"
            if "statement" in english_text.lower() or "petition" in english_text.lower()
            else "Written complaint / e-complaint"
        ),
        "6. Date and Time of Information Received at Police Station: "
        + (
            ", ".join(
                part for part in (
                    _clean_extracted_value(information_received.get("date")),
                    _clean_extracted_value(information_received.get("time")),
                ) if part
            )
            or "Not stated in complaint"
        ),
        "7. Date and Time of Occurrence: "
        + (", ".join(part for part in (occurrence_date, occurrence_time) if part) or "Not stated in complaint"),
        "8. Place of Occurrence: "
        + _normalize_fir_field(complaint_fields.get("where", {}).get("value")),
        "9. Nature of Offence: " + offence_head,
        "10. Name of Informant / Complainant: " + _normalize_fir_field(complainant_name),
        "11. Address of Informant / Complainant: " + _normalize_fir_field(address),
        "12. Contact Number: " + _normalize_fir_field(contact_number),
        "13. Victim / Affected Person: " + _normalize_fir_field(victim_name),
        "14. Known / Suspected Accused: " + _normalize_fir_field(accused_name),
        "15. Witnesses / Support Persons: " + _normalize_fir_field(witness_name),
        "16. Property / Loss / Damage Reported: " + _normalize_fir_field(property_summary),
        "17. Injury / Harm Reported: " + _normalize_fir_field(injury_summary),
        "18. Delay in Reporting: " + delay_summary,
        "19. Gist of Complaint:",
        fir_narrative,
        "20. Proposed BNS Sections for Police Review:",
        sections_text,
        "21. Review Questions / Verification Points: "
        + ("; ".join(review_questions) if review_questions else "None"),
    ]

    return {
        "status": "draft_for_police_review",
        "format": "telangana_iif1_style",
        "title": "Draft First Information Report",
        "disclaimer": (
            "Police-review draft only. FIR number, police-station registration details, "
            "and final sectioning must be confirmed by the competent Telangana police authority."
        ),
        "reference": {
            "state": "Telangana",
            "format_basis": "Telangana FIR Print workflow / NCRB IIF-I style draft",
            "bns_act_url": _BNS_REFERENCE_URL,
            "bnss_procedure_url": _BNSS_REFERENCE_URL,
            "telangana_service_url": _TELANGANA_FIR_FAQ_URL,
        },
        "jurisdiction": {
            "district_unit": district_unit,
            "police_station": police_station,
            "state": "Telangana",
        },
        "registration": {
            "fir_number": None,
            "fir_year": _extract_year_from_temporal_value(occurrence_date),
            "registration_date": None,
            "registration_time": None,
            "mode_of_information": (
                "Written complaint / statement"
                if "statement" in english_text.lower() or "petition" in english_text.lower()
                else "Written complaint / e-complaint"
            ),
            "information_received_date": information_received.get("date"),
            "information_received_time": information_received.get("time"),
            "information_received_evidence": information_received.get("evidence"),
        },
        "occurrence": {
            "date": occurrence_date,
            "time": occurrence_time,
            "place": _clean_extracted_value(complaint_fields.get("where", {}).get("value")),
            "nature_of_offence": offence_head,
        },
        "informant": {
            "name": complainant_name,
            "address": address,
            "contact_number": contact_number,
        },
        "parties": {
            "victim": victim_name,
            "accused": accused_name,
            "witnesses": witness_name,
            "who_components": who_components,
        },
        "case_profile": {
            "complaint_brief": complaint_brief,
            "property_or_loss": property_summary,
            "injury_or_harm": injury_summary,
            "delay_summary": delay_summary,
        },
        "narrative": {
            "gist": fir_narrative,
            "review_questions": review_questions,
        },
        "proposed_bns_sections": bns_sections,
        "formatted_text": "\n".join(formatted_lines),
    }


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
    body_lines = _extract_body_lines(english_lines)
    body_text = _merge_wrapped_lines(body_lines)
    extraction_text = body_text or english_text
    english_sentences = _split_sentences(body_text or english_text)

    language_info = {
        "detected": detected_language,
        "detected_name": _LANGUAGE_NAMES.get(detected_language, "Unknown"),
        "detection_method": language_detection["method"],
        "detection_confidence_score": language_detection["confidence_score"],
        "translation_target": "en",
        "translation_status": translation_result["status"],
        "translation_provider": translation_result["provider"],
        "translation_model": translation_result.get("model"),
        "translation_error": translation_result["error"],
    }

    heuristic_fields = {
        "who": _extract_who(english_lines, english_sentences, extraction_text),
        "what": _extract_what(english_lines, english_sentences),
        "when": _extract_when(english_lines, english_sentences),
        "where": _extract_where(english_lines, english_sentences),
        "why": _extract_why(english_lines, english_sentences),
        "how": _extract_how(english_lines, english_sentences),
    }
    raw_llm_payload = _extract_complaint_insights_via_openai(english_text, heuristic_fields)
    llm_payload = _validate_question_guided_answers(
        raw_llm_payload,
        source_text=extraction_text,
        config=extraction_config,
    ) if (extraction_config := get_question_guided_extraction_config()) else None
    complaint_fields = _merge_question_guided_fields(heuristic_fields, llm_payload)
    complaint_assessment = _assess_police_complaint_relevance(extraction_text)
    gaps = _build_gap_summary(complaint_fields, language_info, complaint_assessment)
    confidence = _build_confidence_summary(complaint_fields, gaps)
    validation_summary = (
        llm_payload.get("validation")
        if isinstance(llm_payload, dict) and isinstance(llm_payload.get("validation"), dict)
        else {}
    )
    question_guided_applied = bool(validation_summary.get("accepted_fields"))
    extraction_meta = {
        "strategy": "heuristic_plus_question_guided" if question_guided_applied else "heuristic_only",
        "question_guided_applied": question_guided_applied,
        "question_guided_response_received": bool(
            raw_llm_payload and isinstance(raw_llm_payload, dict) and raw_llm_payload.get("answers")
        ),
        "question_guided_enabled": bool(extraction_config["enabled"]),
        "question_guided_model": extraction_config["model"] if question_guided_applied else None,
        "question_guided_min_confidence": extraction_config["min_confidence_label"],
        "question_guided_requires_evidence": bool(extraction_config["require_evidence"]),
        "question_guided_validation": validation_summary,
        "source_text_strategy": "body_merged_lines",
    }
    complaint_brief = _build_complaint_brief(complaint_fields, llm_payload)
    review_questions = _build_review_questions(complaint_fields, gaps, llm_payload)
    fir_draft = _build_fir_draft(
        english_text,
        english_lines,
        english_sentences,
        complaint_fields,
        complaint_brief,
        review_questions,
    )

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
            "complaint_brief": complaint_brief,
            "incident_overview": _build_incident_overview(complaint_fields),
            "gap_statement": gaps["summary"],
            "review_questions": review_questions,
            "extraction_strategy": extraction_meta["strategy"],
        },
        "fir_draft": fir_draft,
        "meta": {
            "detected_format": "POLICE_COMPLAINT",
            "parser_used": "police_complaint",
            "line_count": len(raw_lines),
            "english_line_count": len(english_lines),
            "body_line_count": len(body_lines),
            "sentence_count": len(english_sentences),
            "complaint_assessment": complaint_assessment,
            "source_language_counts": language_detection["counts"],
            "extraction": extraction_meta,
        },
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
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
        logger.info("%s", json.dumps(parsed_result, ensure_ascii=False, indent=2))
