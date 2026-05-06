from __future__ import annotations

"""PII protection for outbound LLM calls.

The LLM boundary must not receive raw personally identifiable information.
This module replaces detected PII with stable opaque tokens before a prompt is
sent, keeps the original values encrypted in memory, and restores tokens after
the response returns.
"""

import base64
import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from cryptography.fernet import Fernet


class PIIProtectionError(RuntimeError):
    """Raised when outbound text still contains high-confidence PII."""


_TRUE_VALUES = {"1", "true", "yes", "on"}
_TOKEN_RE = re.compile(r"\[\[PII_[A-Z_]+_\d{4}\]\]")


@dataclass(frozen=True)
class PIIMatch:
    pii_type: str
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class PIIRedaction:
    token: str
    pii_type: str
    encrypted_value: str
    value_hash: str


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _is_true(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in _TRUE_VALUES


def _app_env() -> str:
    return (_env("APP_ENV") or _env("ENV") or "development").lower()


def _fernet_from_secret(secret: str) -> Fernet:
    if len(secret) == 44:
        try:
            return Fernet(secret.encode("utf-8"))
        except Exception:
            pass
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _build_fernet() -> Fernet:
    secret = (
        _env("IQW_PII_ENCRYPTION_KEY")
        or _env("PII_ENCRYPTION_KEY")
        or _env("APP_SESSION_SECRET")
        or _env("SESSION_SECRET_KEY")
        or _env("SECRET_KEY")
        or _env("JWT_SECRET_KEY")
        or _env("JWT_SECRET")
    )
    if not secret and _app_env() in {"production", "prod"}:
        raise PIIProtectionError(
            "PII encryption key is required in production. Set IQW_PII_ENCRYPTION_KEY."
        )
    return _fernet_from_secret(secret or "iqw-local-ephemeral-pii-protection-key")


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _value_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _looks_like_token(value: str) -> bool:
    return bool(_TOKEN_RE.fullmatch(value.strip()))


def _safe_match_value(value: str) -> Optional[str]:
    cleaned = _normalize_value(value)
    if not cleaned or _looks_like_token(cleaned):
        return None
    if len(cleaned) > 240:
        cleaned = cleaned[:240].strip(" ,;:-")
    return cleaned or None


def _iter_regex_matches(
    text: str,
    pattern: str,
    pii_type: str,
    *,
    flags: int = re.IGNORECASE,
    group: str | int = 0,
) -> Iterable[PIIMatch]:
    for match in re.finditer(pattern, text, flags):
        try:
            raw = match.group(group)
            start, end = match.span(group)
        except (IndexError, KeyError):
            raw = match.group(0)
            start, end = match.span(0)
        value = _safe_match_value(raw)
        if value:
            yield PIIMatch(pii_type=pii_type, value=value, start=start, end=end)


_COMMON_FALSE_NAMES = {
    "Bharatiya Nyaya Sanhita",
    "Indian Penal Code",
    "Code Criminal Procedure",
    "Google Document AI",
    "OpenAI",
    "Gemini",
    "Police Station",
    "First Information Report",
    "High Court",
    "Supreme Court",
}


def _is_probable_false_name(value: str) -> bool:
    cleaned = _normalize_value(value).strip(" ,.;:-")
    if cleaned in _COMMON_FALSE_NAMES:
        return True
    lowered = cleaned.lower()
    return lowered.startswith(("section ", "bns ", "bnss ", "ipc ", "fir "))


def detect_pii(text: str, *, include_names: bool = True) -> list[PIIMatch]:
    """Detect PII in free text using conservative rule-based recognizers."""
    if not text:
        return []

    patterns: list[tuple[str, str, str | int]] = [
        ("email", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", 0),
        ("phone", r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)", 0),
        ("phone", r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{2}[-\s]\d{3}[-\s]\d{4}(?!\d)", 0),
        ("aadhaar", r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)", 0),
        ("pan", r"\b[A-Z]{5}\d{4}[A-Z]\b", 0),
        ("passport", r"\b[A-Z]\d{7}\b", 0),
        ("ifsc", r"\b[A-Z]{4}0[A-Z0-9]{6}\b", 0),
        ("upi_id", r"\b[A-Z0-9._-]{2,128}@[A-Z][A-Z0-9]{2,64}\b", 0),
        ("bank_account", r"\b(?:a/c|acct|account)\s*(?:no\.?|number)?\s*[:#-]?\s*(?P<value>\d{6,18})\b", "value"),
        ("vehicle_number", r"\b[A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,3}[-\s]?\d{4}\b", 0),
        (
            "address",
            r"\b(?:residing at|resident of|address(?: is)?|r/o)\s+"
            r"(?P<value>[^.;\n]{5,180}?)(?=,\s*(?:phone|mobile|email|aadhaar|pan|vehicle)\b|[.;\n]|$)",
            "value",
        ),
        (
            "address",
            r"(?:निवासी|पता)\s+(?P<value>[\u0900-\u097F0-9\s,.-]{5,180}?)(?=[।.;\n]|$)",
            "value",
        ),
        (
            "address",
            r"(?:చిరునామా|నివాసి)\s+(?P<value>[\u0C00-\u0C7F0-9\s,.-]{5,180}?)(?=[।.;\n]|$)",
            "value",
        ),
    ]
    matches: list[PIIMatch] = []
    for pii_type, pattern, group in patterns:
        matches.extend(_iter_regex_matches(text, pattern, pii_type, group=group))

    if include_names and _is_true("IQW_PII_MASK_NAMES", True):
        name_patterns: list[tuple[str, str | int, int]] = [
            (
                r"\b(?:complainant|victim|accused|witness|informant|petitioner|applicant)"
                r"(?:\s+name)?\s*(?:is|was|named|:|-)?\s*(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,5})",
                "value",
                re.IGNORECASE,
            ),
            (
                r"\b(?:I|i)\s*,?\s*(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,5})"
                r"\s+(?:resident|residing|s/o|d/o|w/o|aged|age|submit|would|was|received)",
                "value",
                0,
            ),
            (
                r"\b(?:my name is|name is)\s+(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,5})",
                "value",
                re.IGNORECASE,
            ),
            (
                r"\b(?:s/o|d/o|w/o|son of|daughter of|wife of)\s+(?P<value>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,5})",
                "value",
                re.IGNORECASE,
            ),
            (
                r"(?:मैं|मेरा नाम|नाम)\s+(?P<value>[\u0900-\u097F]+(?:\s+[\u0900-\u097F]+){0,4})"
                r"(?=\s+(?:निवासी|पुत्र|पत्नी|ने|से|का|की|को)|[।,.]|$)",
                "value",
                0,
            ),
            (
                r"(?:నేను|నా పేరు|పేరు)\s+(?P<value>[\u0C00-\u0C7F]+(?:\s+[\u0C00-\u0C7F]+){0,4})"
                r"(?=\s+(?:నివాసి|కుమారుడు|కుమార్తె|భార్య|నుండి)|[।,.]|$)",
                "value",
                0,
            ),
            (r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4}\b", 0, 0),
        ]
        for pattern, group, flags in name_patterns:
            for match in _iter_regex_matches(text, pattern, "person_name", group=group, flags=flags):
                if not _is_probable_false_name(match.value):
                    matches.append(match)

    return _remove_overlapping_matches(matches)


def detect_high_risk_pii(text: str) -> list[PIIMatch]:
    """Detect structured PII that should never remain after masking."""
    high_risk_types = {
        "email",
        "phone",
        "aadhaar",
        "pan",
        "passport",
        "ifsc",
        "upi_id",
        "bank_account",
        "vehicle_number",
    }
    return [match for match in detect_pii(text, include_names=False) if match.pii_type in high_risk_types]


def _remove_overlapping_matches(matches: list[PIIMatch]) -> list[PIIMatch]:
    ordered = sorted(matches, key=lambda item: (item.start, -(item.end - item.start)))
    accepted: list[PIIMatch] = []
    occupied: list[tuple[int, int]] = []
    for match in ordered:
        if any(not (match.end <= start or match.start >= end) for start, end in occupied):
            continue
        accepted.append(match)
        occupied.append((match.start, match.end))
    return sorted(accepted, key=lambda item: item.start)


class PIIProtectionContext:
    """Stateful token map for one LLM request/response round trip."""

    def __init__(self) -> None:
        self._fernet = _build_fernet()
        self._counters: dict[str, int] = {}
        self._by_value: dict[tuple[str, str], PIIRedaction] = {}
        self._by_token: dict[str, PIIRedaction] = {}

    @property
    def redactions(self) -> list[PIIRedaction]:
        return list(self._by_token.values())

    def protect_text(self, text: str, *, context: str = "llm") -> str:
        if not text:
            return text
        matches = detect_pii(text)
        if not matches:
            self.assert_safe_for_llm(text, context=context)
            return text

        pieces: list[str] = []
        cursor = 0
        for match in matches:
            pieces.append(text[cursor:match.start])
            pieces.append(self._token_for(match.pii_type, match.value))
            cursor = match.end
        pieces.append(text[cursor:])
        protected = "".join(pieces)
        self.assert_safe_for_llm(protected, context=context)
        return protected

    def protect_json(self, value: Any, *, context: str = "llm") -> Any:
        if isinstance(value, str):
            return self.protect_text(value, context=context)
        if isinstance(value, list):
            return [self.protect_json(item, context=context) for item in value]
        if isinstance(value, tuple):
            return tuple(self.protect_json(item, context=context) for item in value)
        if isinstance(value, dict):
            return {
                key: self.protect_json(item, context=f"{context}.{key}")
                for key, item in value.items()
            }
        return value

    def restore_text(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return text
        restored = text
        for token, redaction in sorted(
            self._by_token.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if token in restored:
                restored = restored.replace(token, self._decrypt(redaction.encrypted_value))
        return restored

    def restore_json(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.restore_text(value)
        if isinstance(value, list):
            return [self.restore_json(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.restore_json(item) for item in value)
        if isinstance(value, dict):
            return {key: self.restore_json(item) for key, item in value.items()}
        return value

    def metadata(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for redaction in self._by_token.values():
            counts[redaction.pii_type] = counts.get(redaction.pii_type, 0) + 1
        return {
            "pii_redacted_before_llm": True,
            "tokens_restored_after_llm": True,
            "redaction_count": len(self._by_token),
            "redaction_types": sorted(counts),
            "redactions_by_type": counts,
            "encrypted_token_map_in_memory": True,
            "raw_pii_sent_to_llm": False,
        }

    def assert_safe_for_llm(self, text: str, *, context: str = "llm") -> None:
        if not _is_true("IQW_LLM_PRIVACY_STRICT", True):
            return
        residual = detect_high_risk_pii(_TOKEN_RE.sub("", text or ""))
        if residual:
            types = sorted({item.pii_type for item in residual})
            raise PIIProtectionError(
                f"Outbound {context} still contains high-risk PII after masking: {', '.join(types)}"
            )

    def _token_for(self, pii_type: str, value: str) -> str:
        normalized = _normalize_value(value)
        key = (pii_type, normalized.lower())
        existing = self._by_value.get(key)
        if existing:
            return existing.token

        self._counters[pii_type] = self._counters.get(pii_type, 0) + 1
        token = f"[[PII_{pii_type.upper()}_{self._counters[pii_type]:04d}]]"
        encrypted_value = self._fernet.encrypt(normalized.encode("utf-8")).decode("ascii")
        redaction = PIIRedaction(
            token=token,
            pii_type=pii_type,
            encrypted_value=encrypted_value,
            value_hash=_value_hash(normalized),
        )
        self._by_value[key] = redaction
        self._by_token[token] = redaction
        return token

    def _decrypt(self, encrypted_value: str) -> str:
        return self._fernet.decrypt(encrypted_value.encode("ascii")).decode("utf-8")


def protect_for_llm(
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, str, PIIProtectionContext]:
    """Protect a system/user prompt pair with one shared token map."""
    context = PIIProtectionContext()
    protected_system = context.protect_text(system_prompt, context="system_prompt")
    protected_user = context.protect_text(user_prompt, context="user_prompt")
    return protected_system, protected_user, context
