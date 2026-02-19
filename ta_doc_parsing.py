# -*- coding: utf-8 -*-
"""Utilities for parsing TA/HSBC documents via Google Document AI."""

import os
import re
from typing import Optional

from google.api_core.client_options import ClientOptions
from google.cloud import documentai


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
    # Backward-compatible wrapper that reads from a local file path.
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
    # You must set the `api_endpoint` if you use a location other than "us".
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

    client = documentai.DocumentProcessorServiceClient(client_options=opts)

    if processor_version_id:
        # The full resource name of the processor version, e.g:
        # `projects/{project_id}/locations/{location}/processors/{processor_id}/processorVersions/{processor_version_id}`
        name = client.processor_version_path(
            project_id, location, processor_id, processor_version_id
        )
    else:
        # The full resource name of the processor, e.g.:
        # `projects/{project_id}/locations/{location}/processors/{processor_id}`
        name = client.processor_path(project_id, location, processor_id)

    # Load binary data
    raw_document = documentai.RawDocument(content=content, mime_type=mime_type)

    # Configure the process request
    request = documentai.ProcessRequest(
        name=name,
        raw_document=raw_document,
        field_mask=field_mask,
    )

    return client.process_document(request=request)


# [END documentai_process_document]

# Call the function to process the document
# result = process_document_sample(project_id, location, processor_id, file_path, mime_type, field_mask)

import json

def normalize_lines(raw: str):
    return [l.strip() for l in raw.split("\n") if l.strip()]

def detect_format(lines):
    text = " ".join(lines)
    if "DAILY SUBSCRIPTION / REDEMPTION BOOKING SUMMARY" in text:
        return "TA"
    if (
        "Daily Subscription Booking Summary" in text
        or "Daily Redemption Booking Summary" in text
        or "HSBC Amanah Malaysia Berhad" in text
    ):
        return "HSBC"
    # extend with more heuristics if needed
    return "UNKNOWN"

def parse_ta(lines):
    # sender: first line (or use last legal-entity line if you prefer)
    sender = lines[0]

    # booking date: line after 'Booking Date'
    booking_date = None
    for i, l in enumerate(lines):
        if l.lower() == "booking date" and i + 1 < len(lines):
            booking_date = lines[i + 1]
            break

    # transaction type: look for 'Redemption' / 'Subscription' before table
    transaction_type = None
    for l in lines:
        if l.lower() in ("redemption", "subscription"):
            transaction_type = l.capitalize()
            break

    # transactions: serial no + fund name + units + amount
    transactions = []
    i = 0
    while i < len(lines):
        if lines[i].isdigit():
            no = int(lines[i])
            fund_name = lines[i+1]
            units = lines[i+2]
            amount = lines[i+3]
            transactions.append({
                "no": no,
                "fund_name": fund_name,
                "units": units,
                "amount": amount
            })
            i += 4
        else:
            i += 1

    # totals
    total_by_fund_units = total_by_fund_amount = None
    grand_total_units = grand_total_amount = None
    for i, l in enumerate(lines):
        if l.lower() == "total by fund" and i + 2 < len(lines):
            total_by_fund_units = lines[i+1]
            total_by_fund_amount = lines[i+2]
        if l.lower() == "grand total" and i + 2 < len(lines):
            grand_total_units = lines[i+1]
            grand_total_amount = lines[i+2]

    return {
        "sender": sender,
        "booking_date": booking_date,
        "transaction_type": transaction_type,
        "transactions": transactions,
        "totals": {
            "total_by_fund_units": total_by_fund_units,
            "total_by_fund_amount": total_by_fund_amount,
            "grand_total_units": grand_total_units,
            "grand_total_amount": grand_total_amount
        }
    }

def _is_numeric_token(value: str) -> bool:
    normalized = value.strip().replace(" ", "")
    if not normalized:
        return False
    return bool(
        re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?", normalized)
    )


def _is_currency_code(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{3}", value.strip()))


def _find_value_after_label(lines, label):
    label_upper = label.upper()
    for i, line in enumerate(lines):
        if line.upper() == label_upper:
            j = i + 1
            while j < len(lines) and lines[j] == ":":
                j += 1
            if j < len(lines):
                return lines[j]
            break
    return None


def _first_numeric_after(lines, start_index, lookahead=5):
    for i in range(start_index, min(len(lines), start_index + lookahead)):
        if _is_numeric_token(lines[i]):
            return lines[i]
    return None


def _to_numeric_value(token: str):
    cleaned = token.strip().replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_generic_label_line(line: str) -> bool:
    stripped = line.strip()
    upper = stripped.upper()
    if not stripped:
        return True
    if upper in _GENERIC_LABEL_EXACT:
        return True
    if any(upper.startswith(prefix) for prefix in _GENERIC_LABEL_PREFIXES):
        return True
    if upper in _GENERIC_STATUS_TOKENS:
        return True
    if upper.endswith(" TOTALS"):
        return True
    return False


def _is_generic_record_code(line: str) -> bool:
    return bool(_GENERIC_CODE_PATTERN.fullmatch(line.strip()))


_DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{1,2}-\d{1,2}-\d{2,4}\b"),
    re.compile(
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*\s+\d{2,4}\b",
        re.IGNORECASE,
    ),
]

_GENERIC_HEADER_NOISE = {
    "ATTN",
    "FAX",
    "TEL",
    "FROM",
    "BOOK DATE",
    "BOOKING DATE",
    "TRANSACTION DATE",
    "AUTHORISED SIGNATORIES",
    "DIGITALLY",
    "SIGNED BY",
}

_TRANSACTION_TYPE_ALIASES = {
    "subscription": "Subscription",
    "redemption": "Redemption",
    "purchase": "Subscription",
    "sell": "Redemption",
    "switch in": "Switch In",
    "switch out": "Switch Out",
    "switch": "Switch",
    "withdrawal": "Withdrawal",
}

_GENERIC_SECTION_PATTERN = re.compile(
    r"(?P<type>subscription|redemption|purchase|sell|withdrawal|switch(?:\s+in|\s+out)?)"
    r"(?:\s+(?:booking|transaction))?\s+summary",
    re.IGNORECASE,
)

_GENERIC_LABEL_EXACT = {
    "LINE",
    "ID",
    "LINE ID",
    "NO",
    "NO.",
    "BATCH",
    "TXN",
    "CODE",
    "FUND",
    "FUND NAME",
    "CASH AMOUNT",
    "CASH AMT",
    "AMOUNTS",
    "SUB AMT",
    "NET AMT",
    "CASH UNITS",
    "EPF UNITS",
    "EXIT FEE",
    "SERVICE TAX",
    "STATUS",
    "REMARKS",
    "FX",
    "RATE",
    "MEANING",
    "TOTAL",
    "GRAND TOTAL",
    "SUBTOTAL",
    "SUB TOTAL",
}

_GENERIC_LABEL_PREFIXES = (
    "SECTION ",
    "TABLE ",
    "A) ",
    "B) ",
    "NOTES",
    "FOOTER",
    "DISCLAIMER",
    "OPERATIONAL NOTES",
    "REFERENCE CODES",
    "SUMMARY TOTALS",
)

_GENERIC_STATUS_TOKENS = {"NEW", "NORMAL", "PENDING", "REJECTED", "APPROVED", "STANDARD"}

_GENERIC_CODE_PATTERN = re.compile(r"^(?:[SR]\d{3,4}|SUB|RED|BUY|SELL|NEW)$", re.IGNORECASE)

_INSTRUMENT_KEYWORD_PATTERN = re.compile(
    r"\b(FUND|TRUST|EQUITY|SUKUK|BOND|INCOME|GROWTH|MARKET|CLASS|PORTFOLIO|ASSET)\b",
    re.IGNORECASE,
)


def _extract_first_date(text):
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _find_booking_date_generic(lines):
    for label in ("BOOK DATE", "BOOKING DATE", "TRANSACTION DATE", "TRADE DATE", "VALUE DATE"):
        value = _find_value_after_label(lines, label)
        if value:
            extracted = _extract_first_date(value)
            if extracted:
                return extracted
            return value

    for line in lines:
        upper = line.upper()
        if upper.startswith("PRINT DATE"):
            continue
        extracted = _extract_first_date(line)
        if extracted:
            return extracted
    return None


def _is_generic_noise_line(line):
    stripped = line.strip()
    upper = stripped.upper()
    if not stripped or stripped == ":":
        return True
    if _is_generic_label_line(stripped):
        return True
    if upper in _GENERIC_HEADER_NOISE or upper in _HSBC_HEADER_NOISE:
        return True
    if upper.startswith("PAGE "):
        return True
    if upper.startswith("PRINT DATE"):
        return True
    if upper.startswith("PRINT TIMESTAMP"):
        return True
    if upper.startswith("SENDER REF"):
        return True
    if upper.startswith("BOOK DATE"):
        return True
    if "BOOKING SUMMARY" in upper:
        return True
    if "INSTRUCTION" in upper and len(upper) > 28:
        return True
    if _is_numeric_token(stripped):
        return True
    if _is_currency_code(stripped):
        return True
    if _is_generic_record_code(stripped):
        return True
    if stripped.upper() in _GENERIC_STATUS_TOKENS:
        return True
    if re.fullmatch(r"[A-Z]\)?", upper):
        return True
    return False


def _find_sender_generic(lines):
    for label in ("FROM", "SENDER", "INSTITUTION", "BANK", "FUND MANAGER"):
        value = _find_value_after_label(lines, label)
        if value and not _is_numeric_token(value):
            return value

    org_keywords = (
        "BERHAD",
        "BANK",
        "INVESTMENT",
        "MANAGEMENT",
        "ASSET",
        "LIMITED",
        "LTD",
        "TRUST",
    )
    for line in lines[:80]:
        upper = line.upper()
        if any(keyword in upper for keyword in org_keywords) and not _is_generic_noise_line(line):
            return line

    for line in lines[:25]:
        if re.search(r"[A-Za-z]", line) and not _is_generic_noise_line(line):
            return line
    return None


def _normalize_transaction_type(raw_value):
    normalized = " ".join(raw_value.lower().split())
    return _TRANSACTION_TYPE_ALIASES.get(normalized, raw_value.strip().title())


def _extract_transaction_type_from_text(lines):
    text = " ".join(lines)
    found = []
    for key, normalized in _TRANSACTION_TYPE_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", text, re.IGNORECASE):
            if normalized not in found:
                found.append(normalized)
    if not found:
        return "Unknown"
    if len(found) == 1:
        return found[0]
    return "Multiple"


def _classify_generic_section_heading(line):
    stripped = line.strip()
    upper = stripped.upper()
    if not stripped:
        return None
    if len(stripped) > 90:
        return None
    if stripped.endswith("."):
        return None

    has_heading_hint = bool(
        re.search(r"\b(SECTION|TABLE)\b", upper)
        or re.match(r"^[A-Z]\)\s*", upper)
        or upper.startswith(
            (
                "SUBSCRIPTION",
                "SUBSCRIPTIONS",
                "REDEMPTION",
                "REDEMPTIONS",
                "PURCHASE",
                "PURCHASES",
                "SELL",
            )
        )
    )
    if not has_heading_hint:
        return None

    if upper in {
        "SUBSCRIPTION",
        "SUBSCRIPTIONS",
        "REDEMPTION",
        "REDEMPTIONS",
        "PURCHASE",
        "PURCHASES",
        "SELL",
    }:
        return None
    if upper.startswith(
        (
            "SUBSCRIPTION",
            "SUBSCRIPTIONS",
            "REDEMPTION",
            "REDEMPTIONS",
            "PURCHASE",
            "PURCHASES",
            "SELL",
        )
    ) and not re.search(r"(SUMMARY|INSTRUCTION|[-:()])", upper):
        return None

    if re.search(r"\b(REDEMPTION|REDEMPTIONS|SELL)\b", upper):
        return "Redemption"
    if re.search(r"\b(SUBSCRIPTION|SUBSCRIPTIONS|PURCHASE)\b", upper):
        return "Subscription"
    return None


def _extract_generic_sections(lines):
    sections = []
    for i, line in enumerate(lines):
        match = _GENERIC_SECTION_PATTERN.search(line)
        section_type = None
        if match:
            section_type = _normalize_transaction_type(match.group("type"))
        else:
            section_type = _classify_generic_section_heading(line)
        if not section_type:
            continue
        if sections and sections[-1][0] == section_type and i - sections[-1][1] <= 3:
            continue
        sections.append((section_type, i))
    return sections


def _looks_like_instrument_name(line):
    upper = line.upper()
    if _is_generic_label_line(line):
        return False
    if any(
        noise in upper
        for noise in (
            "KINDLY",
            "PLEASE NOTE",
            "PLEASE PROCESS",
            "AUTHORISED SIGNATORIES",
            "DIGITALLY",
            "FAXING",
            "CONTACT",
            "MALAYSIA",
            "KUALA LUMPUR",
            "PRINT DATE",
            "INSTRUCTION",
            "INSTRUCTIONS",
            "SUMMARY",
            "TRANSMISSION",
            "REFERENCE CODES",
            "DISCLAIMER",
            "OPERATIONAL NOTES",
            "CONSOLIDATED",
        )
    ):
        return False
    if _INSTRUMENT_KEYWORD_PATTERN.search(upper):
        return True
    return bool(re.search(r"[A-Za-z]", line) and 4 <= len(line) <= 90)


def _extract_name_from_block(block_lines):
    name_parts = []
    for line in block_lines:
        stripped = line.strip()
        if _is_generic_noise_line(stripped):
            if name_parts and (_is_numeric_token(stripped) or _is_currency_code(stripped)):
                break
            continue
        if not _looks_like_instrument_name(stripped):
            if name_parts:
                break
            continue
        name_parts.append(stripped)

    deduped = []
    for part in name_parts:
        if not deduped or deduped[-1] != part:
            deduped.append(part)

    if not deduped:
        return None
    return " ".join(deduped)


def _normalize_fund_key(fund_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (fund_name or "").lower())


def _should_join_fund_continuation(current_line: str, next_line: str) -> bool:
    nxt = next_line.strip()
    if not nxt:
        return False
    if _is_numeric_token(nxt) or _is_currency_code(nxt):
        return False
    if _is_generic_label_line(nxt) or _is_generic_record_code(nxt):
        return False
    if nxt.upper() in _GENERIC_STATUS_TOKENS:
        return False

    current = current_line.strip()
    if current.endswith("-"):
        return True
    if nxt.startswith("("):
        return True
    if len(nxt) <= 24 and re.search(r"[A-Za-z]", nxt):
        return True
    if nxt.upper().startswith(("CLASS", "FUND")) and len(nxt) <= 32:
        return True
    return False


def _is_fund_candidate_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _is_generic_noise_line(stripped):
        return False
    if _is_generic_record_code(stripped):
        return False
    if stripped.upper() in _GENERIC_STATUS_TOKENS:
        return False
    if _is_numeric_token(stripped) or _is_currency_code(stripped):
        return False
    if not _looks_like_instrument_name(stripped):
        return False
    if _INSTRUMENT_KEYWORD_PATTERN.search(stripped):
        return True
    return False


def _extract_fund_candidates_from_section(section_lines):
    candidates = []
    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        if not _is_fund_candidate_line(line):
            i += 1
            continue

        name_parts = [line]
        j = i + 1
        while j < len(section_lines) and _should_join_fund_continuation(
            name_parts[-1], section_lines[j]
        ):
            name_parts.append(section_lines[j].strip())
            j += 1

        fund_name = " ".join(part for part in name_parts if part).strip()
        if fund_name:
            candidates.append({"fund_name": fund_name, "start": i, "end": j})
        i = j

    return candidates


def _select_amount_candidates(numeric_tokens, section_type):
    if not numeric_tokens:
        return []

    normalized_type = _normalize_transaction_type(section_type or "Unknown")
    if normalized_type == "Redemption":
        return [numeric_tokens[0]]

    parsed = []
    for token in numeric_tokens:
        value = _to_numeric_value(token)
        if value is not None:
            parsed.append((token, value))
    if not parsed:
        return [numeric_tokens[0]]

    principal_window = []
    for token, value in parsed:
        if principal_window and abs(value) <= 20:
            break
        principal_window.append((token, value))

    primary = [token for token, value in principal_window if abs(value) >= 50]
    if not primary:
        primary = [token for token, value in parsed if abs(value) >= 50]
    if not primary:
        primary = [parsed[0][0]]

    deduped = []
    for token in primary:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return deduped


def _extract_transactions_from_fund_rows(section_type, section_lines):
    candidates = _extract_fund_candidates_from_section(section_lines)
    if not candidates:
        return []

    transactions = []
    i = 0
    while i < len(candidates):
        run_end = i
        run_key = _normalize_fund_key(candidates[i]["fund_name"])
        while run_end + 1 < len(candidates):
            next_key = _normalize_fund_key(candidates[run_end + 1]["fund_name"])
            if not run_key or next_key != run_key:
                break
            if candidates[run_end + 1]["start"] - candidates[run_end]["start"] > 4:
                break
            run_end += 1

        segment_end = (
            candidates[run_end + 1]["start"]
            if run_end + 1 < len(candidates)
            else len(section_lines)
        )
        numeric_tokens = [
            value.strip()
            for value in section_lines[candidates[i]["end"] : segment_end]
            if _is_numeric_token(value.strip())
        ]
        amount_candidates = _select_amount_candidates(numeric_tokens, section_type)
        if not amount_candidates:
            i = run_end + 1
            continue

        normalized_type = _normalize_transaction_type(section_type or "Unknown")
        for offset, idx in enumerate(range(i, run_end + 1)):
            amount = (
                amount_candidates[offset]
                if offset < len(amount_candidates)
                else amount_candidates[0]
            )
            row = {
                "fund_name": candidates[idx]["fund_name"],
                "amount": amount,
            }
            if normalized_type == "Redemption":
                row["units"] = amount
            transactions.append(row)

        i = run_end + 1

    deduped = []
    seen = set()
    for row in transactions:
        key = (
            _normalize_fund_key(str(row.get("fund_name") or "")),
            str(row.get("amount") or ""),
            str(row.get("units") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _extract_totals_generic(lines):
    totals = {}
    for i, line in enumerate(lines):
        upper = line.upper()
        if upper in {"GRAND TOTAL", "TOTAL"}:
            amount = _first_numeric_after(lines, i + 1, lookahead=6)
            if amount is not None:
                totals["grand_total_amount"] = amount
        elif "TOTAL BY FUND" in upper:
            first_value = _first_numeric_after(lines, i + 1, lookahead=4)
            if first_value is not None:
                totals["total_by_fund"] = first_value
        elif "SUBSCRIPTION TOTAL" in upper:
            amount = _first_numeric_after(lines, i + 1, lookahead=6)
            if amount is not None:
                totals["subscription_total_amount"] = amount
        elif "REDEMPTION TOTAL" in upper:
            amount = _first_numeric_after(lines, i + 1, lookahead=6)
            if amount is not None:
                totals["redemption_total_amount"] = amount

    if "grand_total_amount" not in totals:
        # fallback: last numeric token in the section can often be the total
        for line in reversed(lines):
            if _is_numeric_token(line):
                totals["grand_total_amount"] = line
                break
    return totals


def _parse_generic_section(section_type, section_lines):
    subtotal_transactions = []
    subtotal_indices = [
        i
        for i, line in enumerate(section_lines)
        if line.upper() in {"SUB TOTAL", "SUBTOTAL"}
    ]

    block_start = 0
    for subtotal_idx in subtotal_indices:
        fund_name = _extract_name_from_block(section_lines[block_start:subtotal_idx])
        amount = _first_numeric_after(section_lines, subtotal_idx + 1, lookahead=6)
        if fund_name and amount is not None:
            subtotal_transactions.append({"fund_name": fund_name, "amount": amount})
        block_start = subtotal_idx + 1

    serial_transactions = []
    i = 0
    while i + 3 < len(section_lines):
        if (
            section_lines[i].isdigit()
            and _looks_like_instrument_name(section_lines[i + 1])
            and _is_numeric_token(section_lines[i + 2])
            and _is_numeric_token(section_lines[i + 3])
        ):
            serial_transactions.append(
                {
                    "no": int(section_lines[i]),
                    "fund_name": section_lines[i + 1],
                    "units": section_lines[i + 2],
                    "amount": section_lines[i + 3],
                }
            )
            i += 4
            continue
        i += 1

    row_transactions = _extract_transactions_from_fund_rows(section_type, section_lines)

    if serial_transactions:
        transactions = serial_transactions
    elif row_transactions:
        transactions = row_transactions
    else:
        transactions = subtotal_transactions

    return {
        "transaction_type": section_type,
        "transactions": transactions,
        "totals": _extract_totals_generic(section_lines),
    }


def parse_generic(lines):
    sender = _find_sender_generic(lines)
    booking_date = _find_booking_date_generic(lines)

    section_markers = _extract_generic_sections(lines)
    transaction_summaries = []
    if section_markers:
        for idx, (transaction_type, start_index) in enumerate(section_markers):
            end_index = (
                section_markers[idx + 1][1]
                if idx + 1 < len(section_markers)
                else len(lines)
            )
            section_lines = lines[start_index + 1 : end_index]
            transaction_summaries.append(
                _parse_generic_section(transaction_type, section_lines)
            )
    else:
        inferred_type = _extract_transaction_type_from_text(lines)
        transaction_summaries.append(_parse_generic_section(inferred_type, lines))

    non_empty_summaries = [
        summary
        for summary in transaction_summaries
        if isinstance(summary, dict) and summary.get("transactions")
    ]
    if non_empty_summaries:
        transaction_summaries = non_empty_summaries

    if len(transaction_summaries) == 1:
        only_section = transaction_summaries[0]
        return {
            "sender": sender,
            "booking_date": booking_date,
            "transaction_type": only_section["transaction_type"],
            "transactions": only_section["transactions"],
            "totals": only_section["totals"],
            "transaction_summaries": transaction_summaries,
        }

    combined_transactions = []
    totals_by_transaction_type = {}
    for section in transaction_summaries:
        section_key = section["transaction_type"].lower().replace(" ", "_")
        section_total = (section.get("totals") or {}).get("grand_total_amount")
        if section_total is not None:
            totals_by_transaction_type[section_key] = section_total
        for row in section["transactions"]:
            merged = dict(row)
            merged["transaction_type"] = section["transaction_type"]
            combined_transactions.append(merged)

    return {
        "sender": sender,
        "booking_date": booking_date,
        "transaction_type": "Multiple",
        "transactions": combined_transactions,
        "totals": {
            "by_transaction_type": totals_by_transaction_type,
        },
        "transaction_summaries": transaction_summaries,
    }


_CONFIDENCE_LOW_THRESHOLD = 0.8
_CONFIDENCE_CRITICAL_FLAGS = {
    "missing_fund_name",
    "missing_amount",
    "invalid_fund_name",
    "invalid_amount_format",
}


def _to_clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _score_transaction_quality(transaction_row):
    exceptions = []
    penalty = 0.0

    def add_exception(flag, penalty_points):
        nonlocal penalty
        if flag not in exceptions:
            exceptions.append(flag)
            penalty += penalty_points

    transaction_type = _normalize_transaction_type(
        _to_clean_text(transaction_row.get("transaction_type") or "Unknown")
        or "Unknown"
    )
    fund_name = _to_clean_text(transaction_row.get("fund_name"))
    amount = _to_clean_text(transaction_row.get("amount"))
    units = _to_clean_text(transaction_row.get("units"))

    if transaction_type == "Unknown":
        add_exception("unknown_transaction_type", 0.18)

    if not fund_name:
        add_exception("missing_fund_name", 0.35)
    elif not re.search(r"[A-Za-z]", fund_name):
        add_exception("invalid_fund_name", 0.25)
    elif len(fund_name) < 8:
        add_exception("short_fund_name", 0.08)

    if not amount:
        add_exception("missing_amount", 0.45)
    elif not _is_numeric_token(amount):
        add_exception("invalid_amount_format", 0.35)
    else:
        amount_value = _to_numeric_value(amount)
        if amount_value is not None and abs(amount_value) == 0:
            add_exception("zero_amount", 0.08)

    if units and not _is_numeric_token(units):
        add_exception("invalid_units_format", 0.08)
    elif transaction_type == "Redemption" and not units:
        add_exception("missing_units", 0.08)

    confidence_score = round(max(0.0, min(1.0, 1.0 - penalty)), 2)
    exception_score = int(round((1.0 - confidence_score) * 100))
    requires_review = (
        confidence_score < _CONFIDENCE_LOW_THRESHOLD
        or any(flag in _CONFIDENCE_CRITICAL_FLAGS for flag in exceptions)
    )

    return {
        "confidence_score": confidence_score,
        "exception_score": exception_score,
        "exception_flags": exceptions,
        "requires_review": requires_review,
    }


def _build_confidence_summary(transactions):
    rows = transactions if isinstance(transactions, list) else []
    scores = []
    low_confidence_count = 0
    review_required_count = 0
    exception_count = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        score = row.get("confidence_score")
        try:
            numeric_score = float(score)
        except (TypeError, ValueError):
            numeric_score = 0.0
        scores.append(max(0.0, min(1.0, numeric_score)))
        if numeric_score < _CONFIDENCE_LOW_THRESHOLD:
            low_confidence_count += 1
        if bool(row.get("requires_review")):
            review_required_count += 1
        flags = row.get("exception_flags")
        if isinstance(flags, list):
            exception_count += len(flags)

    if scores:
        average_score = round(sum(scores) / len(scores), 2)
        min_score = round(min(scores), 2)
        max_score = round(max(scores), 2)
    else:
        average_score = 0.0
        min_score = 0.0
        max_score = 0.0

    review_required = review_required_count > 0 or low_confidence_count > 0
    return {
        "average_score": average_score,
        "min_score": min_score,
        "max_score": max_score,
        "low_confidence_threshold": _CONFIDENCE_LOW_THRESHOLD,
        "low_confidence_count": low_confidence_count,
        "review_required_count": review_required_count,
        "exception_count": exception_count,
        "review_required": review_required,
    }


def _normalize_transaction_record(record, default_transaction_type):
    resolved_type = _normalize_transaction_type(default_transaction_type or "Unknown")

    if not isinstance(record, dict):
        normalized_row = {
            "transaction_type": resolved_type,
            "fund_name": None,
            "units": None,
            "amount": None,
        }
        normalized_row.update(_score_transaction_quality(normalized_row))
        return normalized_row

    normalized = dict(record)
    resolved_type = _normalize_transaction_type(
        normalized.get("transaction_type") or default_transaction_type or "Unknown"
    )

    # Canonical, schema-stable transaction payload across all document formats.
    normalized_row = {
        "transaction_type": resolved_type,
        "fund_name": normalized.get("fund_name"),
        "units": normalized.get("units"),
        "amount": normalized.get("amount"),
    }
    normalized_row.update(_score_transaction_quality(normalized_row))
    return normalized_row


def harmonize_output_structure(parsed_data):
    if not isinstance(parsed_data, dict):
        parsed_data = {}

    sender = parsed_data.get("sender")
    booking_date = parsed_data.get("booking_date")
    base_transaction_type = _normalize_transaction_type(
        parsed_data.get("transaction_type") or "Unknown"
    )
    raw_transactions = parsed_data.get("transactions")
    if not isinstance(raw_transactions, list):
        raw_transactions = []

    raw_summaries = parsed_data.get("transaction_summaries")
    if not isinstance(raw_summaries, list):
        raw_summaries = []

    normalized_summaries = []
    if raw_summaries:
        for summary in raw_summaries:
            summary = summary if isinstance(summary, dict) else {}
            summary_type = _normalize_transaction_type(
                summary.get("transaction_type") or base_transaction_type
            )
            summary_transactions = summary.get("transactions")
            if not isinstance(summary_transactions, list):
                summary_transactions = []
            normalized_transactions = [
                _normalize_transaction_record(item, summary_type)
                for item in summary_transactions
            ]
            summary_totals = summary.get("totals")
            if not isinstance(summary_totals, dict):
                summary_totals = {}
            normalized_summaries.append(
                {
                    "transaction_type": summary_type,
                    "transactions": normalized_transactions,
                    "transaction_count": len(normalized_transactions),
                    "totals": summary_totals,
                }
            )
    else:
        grouped = {}
        order = []
        for row in raw_transactions:
            normalized_row = _normalize_transaction_record(row, base_transaction_type)
            row_type = normalized_row["transaction_type"]
            if row_type not in grouped:
                grouped[row_type] = []
                order.append(row_type)
            grouped[row_type].append(normalized_row)

        if not grouped:
            grouped[base_transaction_type] = []
            order.append(base_transaction_type)

        base_totals = parsed_data.get("totals")
        if not isinstance(base_totals, dict):
            base_totals = {}

        for row_type in order:
            if len(order) == 1:
                section_totals = base_totals
            else:
                by_type_totals = base_totals.get("by_transaction_type")
                if isinstance(by_type_totals, dict):
                    section_totals = by_type_totals.get(
                        row_type.lower().replace(" ", "_"), {}
                    )
                    if not isinstance(section_totals, dict):
                        section_totals = {"grand_total_amount": section_totals}
                else:
                    section_totals = {}
            normalized_summaries.append(
                {
                    "transaction_type": row_type,
                    "transactions": grouped[row_type],
                    "transaction_count": len(grouped[row_type]),
                    "totals": section_totals,
                }
            )

    flat_transactions = []
    transaction_types = []
    by_transaction_type_totals = {}
    for summary in normalized_summaries:
        summary_type = summary["transaction_type"]
        flat_transactions.extend(summary["transactions"])
        if summary_type not in transaction_types:
            transaction_types.append(summary_type)
        key = summary_type.lower().replace(" ", "_")
        by_transaction_type_totals[key] = summary.get("totals", {})

    if len(transaction_types) == 1:
        primary_transaction_type = transaction_types[0]
    elif len(transaction_types) > 1:
        primary_transaction_type = "Multiple"
    else:
        primary_transaction_type = "Unknown"

    original_totals = parsed_data.get("totals")
    if not isinstance(original_totals, dict):
        original_totals = {}
    if len(normalized_summaries) == 1 and normalized_summaries[0].get("totals"):
        overall_totals = normalized_summaries[0]["totals"]
    else:
        overall_totals = original_totals.get("overall", {})
        if not isinstance(overall_totals, dict):
            overall_totals = {}

    confidence_summary = _build_confidence_summary(flat_transactions)

    return {
        "schema_version": "2.0",
        "sender": sender,
        "booking_date": booking_date,
        "transaction_type": primary_transaction_type,
        "primary_transaction_type": primary_transaction_type,
        "transaction_types": transaction_types,
        "transactions": flat_transactions,
        "transaction_summaries": normalized_summaries,
        "totals": {
            "overall": overall_totals,
            "by_transaction_type": by_transaction_type_totals,
        },
        "confidence": confidence_summary,
    }


def _extract_hsbc_sections(lines):
    sections = []
    pattern = re.compile(
        r"Daily\s+(Subscription|Redemption)\s+Booking Summary",
        re.IGNORECASE,
    )
    for i, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            sections.append((match.group(1).capitalize(), i))
    return sections


_HSBC_HEADER_NOISE = {
    "FUND NAME",
    "SERVICE CHARGE",
    "BANK SERVICE",
    "TAX AMOUNT",
    "(FCY)",
    "SALES CHARGE (%)",
    "BANK SERVICE TAX",
    "AMOUNT (LCY)",
    "NEGOTIATED (%)",
    "FM SERVICE TAX",
    "AMOUNT (FCY)",
    "CASH",
    "EPF",
    "FX RATE",
    "EXIT FEE (%)",
    "CASH (UNITS)",
    "EPF (UNITS)",
    "SERVICE TAX (%)",
    "RATE CODE",
    "SUB TOTAL",
    "GRAND TOTAL",
}


def _is_hsbc_name_noise(line):
    stripped = line.strip()
    upper = stripped.upper()
    if not stripped or stripped == ":":
        return True
    if upper in _HSBC_HEADER_NOISE:
        return True
    if upper.startswith("PAGE "):
        return True
    if upper.startswith("PRINT DATE"):
        return True
    if "BOOKING SUMMARY" in upper:
        return True
    if _is_numeric_token(stripped):
        return True
    if _is_currency_code(stripped):
        return True
    return False


def _extract_hsbc_fund_name(block_lines):
    name_parts = []
    for line in block_lines:
        stripped = line.strip()
        if _is_hsbc_name_noise(stripped):
            if name_parts and (_is_numeric_token(stripped) or _is_currency_code(stripped)):
                break
            continue
        if not re.search(r"[A-Za-z]", stripped):
            if name_parts:
                break
            continue
        name_parts.append(stripped)
    if not name_parts:
        return None
    return " ".join(name_parts)


def _parse_hsbc_section(section_type, section_lines):
    transactions = []
    subtotal_indices = [
        i for i, line in enumerate(section_lines) if line.upper() == "SUB TOTAL"
    ]
    block_start = 0
    for subtotal_idx in subtotal_indices:
        fund_name = _extract_hsbc_fund_name(section_lines[block_start:subtotal_idx])
        amount = _first_numeric_after(section_lines, subtotal_idx + 1, lookahead=5)
        if fund_name and amount is not None:
            transactions.append(
                {
                    "fund_name": fund_name,
                    "amount": amount,
                }
            )
        block_start = subtotal_idx + 1

    grand_total_amount = None
    for i, line in enumerate(section_lines):
        if line.upper() == "GRAND TOTAL":
            grand_total_amount = _first_numeric_after(section_lines, i + 1, lookahead=5)
            break

    return {
        "transaction_type": section_type,
        "transactions": transactions,
        "totals": {
            "grand_total_amount": grand_total_amount,
        },
    }


def parse_hsbc(lines):
    sender = _find_value_after_label(lines, "FROM")
    if sender is None:
        sender = next(
            (line for line in lines if "HSBC AMANAH MALAYSIA BERHAD" in line.upper()),
            None,
        )

    booking_date = _find_value_after_label(lines, "BOOK DATE")

    section_markers = _extract_hsbc_sections(lines)
    if not section_markers:
        fallback_section = _parse_hsbc_section("Unknown", lines)
        return {
            "sender": sender,
            "booking_date": booking_date,
            "transaction_type": fallback_section["transaction_type"],
            "transactions": fallback_section["transactions"],
            "totals": fallback_section["totals"],
        }

    transaction_summaries = []
    for idx, (transaction_type, start_index) in enumerate(section_markers):
        end_index = (
            section_markers[idx + 1][1]
            if idx + 1 < len(section_markers)
            else len(lines)
        )
        section_lines = lines[start_index + 1 : end_index]
        transaction_summaries.append(
            _parse_hsbc_section(transaction_type, section_lines)
        )

    if len(transaction_summaries) == 1:
        only_section = transaction_summaries[0]
        return {
            "sender": sender,
            "booking_date": booking_date,
            "transaction_type": only_section["transaction_type"],
            "transactions": only_section["transactions"],
            "totals": only_section["totals"],
            "transaction_summaries": transaction_summaries,
        }

    combined_transactions = []
    totals_by_transaction_type = {}
    for section in transaction_summaries:
        transaction_key = section["transaction_type"].lower()
        totals_by_transaction_type[transaction_key] = section["totals"][
            "grand_total_amount"
        ]
        for row in section["transactions"]:
            merged_row = dict(row)
            merged_row["transaction_type"] = section["transaction_type"]
            combined_transactions.append(merged_row)

    return {
        "sender": sender,
        "booking_date": booking_date,
        "transaction_type": "Multiple",
        "transactions": combined_transactions,
        "totals": {
            "by_transaction_type": totals_by_transaction_type,
        },
        "transaction_summaries": transaction_summaries,
    }

def parse_document(raw: str):
    lines = normalize_lines(raw)
    fmt = detect_format(lines)
    parser_map = {
        "TA": parse_ta,
        "HSBC": parse_hsbc,
    }
    parser = parser_map.get(fmt, parse_generic)
    parsed_data = parser(lines)
    if not isinstance(parsed_data, dict):
        raise ValueError("Parser must return a dictionary payload.")
    data = harmonize_output_structure(parsed_data)
    data["meta"] = {
        "detected_format": fmt,
        "parser_used": "generic" if parser is parse_generic else fmt.lower(),
        "line_count": len(lines),
    }
    return data

# Example usage:
# result = parse_document(raw)
# print(json.dumps(result, indent=2))

if __name__ == "__main__":
    load_dotenv()
    project_id = os.getenv("DOC_AI_PROJECT_ID")
    location = os.getenv("DOC_AI_LOCATION", "eu")
    processor_id = os.getenv("DOC_AI_PROCESSOR_ID")
    mime_type = os.getenv("DOC_AI_MIME_TYPE", "application/pdf")
    field_mask = os.getenv("DOC_AI_FIELD_MASK", "text,entities,fund name, amount")
    folder_path = os.getenv("DOC_INPUT_FOLDER")
    if not folder_path:
        raise ValueError("Set DOC_INPUT_FOLDER in .env to run batch parsing.")
    if not project_id or not processor_id:
        raise ValueError(
            "Set DOC_AI_PROJECT_ID and DOC_AI_PROCESSOR_ID in .env to run batch parsing."
        )

    file_list = os.listdir(folder_path)
    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)
        result = process_document_sample(
            project_id, location, processor_id, file_path, mime_type, field_mask
        )
        raw = result.document.text
        result = parse_document(raw)
        print(json.dumps(result, indent=2))
