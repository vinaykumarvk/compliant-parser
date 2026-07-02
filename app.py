from __future__ import annotations

import asyncio
import copy
import base64
import hashlib
import hmac
import io
import json as _json
import logging
import os
import queue
import secrets
import socket
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import sqlalchemy as sa
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from complaint_parsing import (
    _build_openai_ssl_context,
    _extract_openai_error_message,
    _extract_openai_output_text,
    get_translation_config,
    load_dotenv,
    parse_document,
    process_document_bytes,
)
from database import (
    auth_support_requests,
    dispose_engine,
    generated_petition_drafts,
    get_database_health,
    get_engine,
    get_session_factory,
    initialize_all_tables,
    initialize_database,
    parse_records,
    petitioner_packets,
    petitioner_verification_records,
    petition_checklist_evaluations,
    petition_checklist_questions,
    petition_draft_translations,
    petition_pilot_evaluations,
    petition_placeholders,
    petition_rewrite_requests,
    rewrite_audit_events,
    source_lineage_maps,
)
from external_interfaces import get_object_bytes, put_object_bytes, delete_object
from kis_indexing_status import (
    claim_next_kis_index_record,
    enqueue_kis_indexing,
    kis_record_payload,
    kis_record_projection,
    mark_kis_index_failure,
    normalize_kis_result_status,
    update_kis_index_status,
)
from petition_assistance import (
    FINAL_OR_REPLACED_STATUSES,
    FINAL_ACCEPTABLE_VALUE_STATUSES,
    PLACEHOLDER_VALUE_STATUSES,
    PetitionAssistanceError,
    build_draft_translation_payload,
    build_assistance_packet,
    evaluate_checklist_questions,
    infer_offence_type,
    merge_final_petition_text,
    sha256_text,
    summarize_pilot_metrics,
    validate_packet_body,
)

logger = logging.getLogger(__name__)

load_dotenv()

# Supported file types for Document AI processing.
ACCEPTED_MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


def _detect_mime_type(filename: str, content_type: str) -> str | None:
    """Return the MIME type if the file is an accepted format, or None."""
    ext = Path(filename).suffix.lower()
    if ext in ACCEPTED_MIME_TYPES:
        return ACCEPTED_MIME_TYPES[ext]
    # Fall back to content_type header if extension isn't recognized
    ct = (content_type or "").lower()
    for mime in ACCEPTED_MIME_TYPES.values():
        if mime in ct:
            return mime
    return None

_INDEX_HTML = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
_AUTH_SESSION_USER_KEY = "authenticated_user"


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _get_env(key: str, default: str | None = None) -> str | None:
    value = _clean_env_value(os.getenv(key))
    if value is None or value == "":
        return default
    return value


def _is_env_true(key: str, default: bool) -> bool:
    value = _get_env(key)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _get_max_upload_bytes(default_bytes: int = 15 * 1024 * 1024) -> int:
    raw_value = _get_env("MAX_PARSE_UPLOAD_BYTES")
    if not raw_value:
        return default_bytes
    try:
        return int(raw_value)
    except ValueError:
        return default_bytes


def get_auth_config() -> dict[str, str | bool]:
    config = {
        "username": _get_env("APP_ADMIN_USERNAME"),
        "password": _get_env("APP_ADMIN_PASSWORD"),
        "session_secret": _get_env("APP_SESSION_SECRET"),
        "session_https_only": _is_env_true("APP_SESSION_HTTPS_ONLY", False),
    }

    missing = [
        key
        for key, env_name in (
            ("username", "APP_ADMIN_USERNAME"),
            ("password", "APP_ADMIN_PASSWORD"),
            ("session_secret", "APP_SESSION_SECRET"),
        )
        if not config[key]
    ]
    if missing:
        env_names = {
            "username": "APP_ADMIN_USERNAME",
            "password": "APP_ADMIN_PASSWORD",
            "session_secret": "APP_SESSION_SECRET",
        }
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(env_names[key] for key in missing)
        )
    return config


MAX_PARSE_UPLOAD_BYTES = _get_max_upload_bytes()
_AUTH_CONFIG = get_auth_config()
_support_request_store: list[dict[str, Any]] = []


def get_doc_ai_config() -> dict[str, str | None]:
    config = {
        "GOOGLE_APPLICATION_CREDENTIALS": _get_env("DOC_AI_CREDENTIALS_PATH") or _get_env("GOOGLE_APPLICATION_CREDENTIALS"),
        "DOC_AI_PROJECT_ID": _get_env("DOC_AI_PROJECT_ID"),
        "DOC_AI_LOCATION": _get_env("DOC_AI_LOCATION"),
        "DOC_AI_PROCESSOR_ID": _get_env("DOC_AI_PROCESSOR_ID"),
        "DOC_AI_MIME_TYPE": _get_env("DOC_AI_MIME_TYPE", "application/pdf"),
        "DOC_AI_FIELD_MASK": _get_env("DOC_AI_FIELD_MASK", "text"),
    }

    missing = [
        key
        for key in (
            "DOC_AI_PROJECT_ID",
            "DOC_AI_LOCATION",
            "DOC_AI_PROCESSOR_ID",
        )
        if not config.get(key)
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    # Resolve the credentials file, trying the .env value as fallback if the
    # shell env var points to a stale path.
    creds_path = config["GOOGLE_APPLICATION_CREDENTIALS"]
    resolved_creds_path = None
    if creds_path:
        resolved_creds_path = Path(creds_path).expanduser()
        if not resolved_creds_path.is_absolute():
            resolved_creds_path = (Path(__file__).resolve().parent / resolved_creds_path).resolve()
        if not resolved_creds_path.exists():
            from dotenv import dotenv_values
            dotenv_creds = dotenv_values().get("GOOGLE_APPLICATION_CREDENTIALS")
            if dotenv_creds and dotenv_creds != creds_path:
                candidate = Path(dotenv_creds).expanduser()
                if not candidate.is_absolute():
                    candidate = (Path(__file__).resolve().parent / candidate).resolve()
                if candidate.exists():
                    logger.info(
                        "Shell GOOGLE_APPLICATION_CREDENTIALS (%s) not found — using .env value (%s)",
                        resolved_creds_path, candidate,
                    )
                    resolved_creds_path = candidate

    if resolved_creds_path and resolved_creds_path.exists():
        config["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved_creds_path)
        # Point the env var to the correct file so google.auth.default() also works.
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved_creds_path)
        from google.oauth2 import service_account as _sa
        config["_credentials"] = _sa.Credentials.from_service_account_file(
            str(resolved_creds_path)
        )
    else:
        if creds_path:
            logger.warning(
                "GOOGLE_APPLICATION_CREDENTIALS path does not exist (%s) — falling back to Application Default Credentials",
                resolved_creds_path or creds_path,
            )
        config["GOOGLE_APPLICATION_CREDENTIALS"] = None
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    return config


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    window = _rate_limit_log[client_ip]
    window[:] = [timestamp for timestamp in window if now - timestamp < 60]
    if len(window) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    window.append(now)


def _get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _extract_completeness_score(parsed_output: object) -> float | None:
    if not isinstance(parsed_output, dict):
        return None
    gaps = parsed_output.get("gaps", {})
    if not isinstance(gaps, dict):
        return None
    completeness = gaps.get("completeness_score")
    if isinstance(completeness, (int, float)):
        return float(completeness)
    return None


_CHECKLIST_ACTION_STATUSES = {"missing", "uncertain"}
_CHECKLIST_STATUS_ORDER = {"missing": 0, "uncertain": 1, "present": 2, "not_applicable": 3}
_CHECKLIST_SEVERITY_ORDER = {
    "critical": 4,
    "mandatory": 3,
    "high": 3,
    "recommended": 2,
    "medium": 2,
    "optional": 1,
    "low": 1,
}


def _normalize_checklist_status(value: Any) -> str:
    status = str(value or "not_applicable").strip().lower()
    return status if status in _CHECKLIST_STATUS_ORDER else "uncertain"


def _checklist_severity_rank(value: Any) -> int:
    return _CHECKLIST_SEVERITY_ORDER.get(str(value or "").strip().lower(), 0)


def _checklist_evaluation_public(item: dict[str, Any]) -> dict[str, Any]:
    status = _normalize_checklist_status(item.get("evaluation_status"))
    return {
        "question_id": item.get("question_id") or item.get("id"),
        "checklist_version": item.get("checklist_version") or 1,
        "category": item.get("category") or "general",
        "purpose": item.get("purpose") or "petition",
        "offence_type": item.get("offence_type"),
        "source_section": item.get("source_section"),
        "question_text": item.get("question_text"),
        "expected_field_key": item.get("expected_field_key"),
        "severity": item.get("severity") or "recommended",
        "evaluation_status": status,
        "evidence_excerpt": item.get("evidence_excerpt"),
        "missing_detail": item.get("missing_detail"),
        "follow_up_action": item.get("follow_up_action"),
        "guidance": item.get("guidance"),
        "evaluation_reason": item.get("evaluation_reason"),
        "display_order": item.get("display_order") or 0,
    }


def _dedupe_evaluations(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse evaluations that produce identical user-facing output.

    Multiple checklist questions within the same category can produce the same
    ``missing_detail`` text.  When that happens we keep only the
    highest-severity entry so the UI never shows duplicate action items.
    Evaluations with status ``present`` or ``not_applicable`` are kept as-is
    (they don't surface as action items).
    """
    deduped: list[dict[str, Any]] = []
    seen_action_keys: dict[str, int] = {}
    for item in evaluations:
        status = str(item.get("evaluation_status") or "")
        md = (item.get("missing_detail") or "").strip().lower()
        cat = (item.get("category") or "").strip().lower()
        # Only deduplicate actionable items that share the same missing_detail
        if status in ("missing", "uncertain") and md:
            key = f"{cat}::{md}"
            if key in seen_action_keys:
                # Keep the one with higher severity
                existing_idx = seen_action_keys[key]
                existing_sev = _checklist_severity_rank(deduped[existing_idx].get("severity"))
                new_sev = _checklist_severity_rank(item.get("severity"))
                if new_sev > existing_sev:
                    deduped[existing_idx] = item
                continue
            seen_action_keys[key] = len(deduped)
        deduped.append(item)
    return deduped


def _build_checklist_analysis_payload(
    parsed_output: dict[str, Any],
    evaluations: list[dict[str, Any]],
    *,
    purpose: str = "petition",
) -> dict[str, Any]:
    public_evaluations = _dedupe_evaluations(
        [_checklist_evaluation_public(item) for item in evaluations or []]
    )
    public_evaluations.sort(
        key=lambda item: (
            _CHECKLIST_STATUS_ORDER.get(str(item.get("evaluation_status") or ""), 99),
            -_checklist_severity_rank(item.get("severity")),
            int(item.get("display_order") or 0),
            str(item.get("category") or ""),
        )
    )

    counts = {status: 0 for status in _CHECKLIST_STATUS_ORDER}
    versions: list[int] = []
    for item in public_evaluations:
        status = _normalize_checklist_status(item.get("evaluation_status"))
        counts[status] = counts.get(status, 0) + 1
        try:
            versions.append(int(item.get("checklist_version") or 0))
        except (TypeError, ValueError):
            pass

    applicable_count = counts.get("present", 0) + counts.get("missing", 0) + counts.get("uncertain", 0)
    readiness_score = round(counts.get("present", 0) / applicable_count, 2) if applicable_count else None
    action_items = [
        item
        for item in public_evaluations
        if item.get("evaluation_status") in _CHECKLIST_ACTION_STATUSES
    ]
    mandatory_action_count = sum(
        1
        for item in action_items
        if _checklist_severity_rank(item.get("severity")) >= _CHECKLIST_SEVERITY_ORDER["mandatory"]
    )
    recommended_action_count = len(action_items) - mandatory_action_count

    if not public_evaluations:
        summary = "No active checklist questions were available for this purpose."
    elif action_items:
        summary = (
            f"{len(action_items)} checklist item(s) need petitioner confirmation or additional detail "
            f"before the petition can be treated as foolproof."
        )
    else:
        summary = "All applicable checklist items are satisfied by the parsed petition content."

    return {
        "status": "ready" if public_evaluations else "empty",
        "purpose": purpose,
        "offence_type": infer_offence_type(parsed_output),
        "checklist_version": max(versions) if versions else None,
        "total_questions": len(public_evaluations),
        "applicable_questions": applicable_count,
        "readiness_score": readiness_score,
        "counts": counts,
        "mandatory_action_count": mandatory_action_count,
        "recommended_action_count": recommended_action_count,
        "summary": summary,
        "top_findings": action_items[:12],
        "evaluations": public_evaluations,
    }


async def enrich_parsed_output_with_checklist(
    parsed_output: object,
    *,
    purpose: str = "petition",
    conn: Any | None = None,
) -> object:
    if not isinstance(parsed_output, dict):
        return parsed_output

    enriched = copy.deepcopy(parsed_output)
    existing_analysis = enriched.get("checklist_analysis")
    if not isinstance(existing_analysis, dict):
        existing_analysis = None

    try:
        # Only fetch questions from the latest active checklist version
        # to avoid duplicates across versions.
        latest_version_subq = (
            sa.select(sa.func.max(petition_checklist_questions.c.checklist_version))
            .where(petition_checklist_questions.c.is_active == sa.true())
            .scalar_subquery()
        )
        query = (
            sa.select(*petition_checklist_questions.c)
            .where(
                petition_checklist_questions.c.is_active == sa.true(),
                petition_checklist_questions.c.checklist_version == latest_version_subq,
            )
            .order_by(
                petition_checklist_questions.c.display_order.asc(),
                petition_checklist_questions.c.category.asc(),
            )
        )
        if conn is not None:
            questions = await _fetch_all_mappings(conn, query)
        else:
            engine = await get_engine()
            async with engine.connect() as local_conn:
                questions = await _fetch_all_mappings(local_conn, query)

        evaluations = evaluate_checklist_questions(enriched, questions, purpose=purpose)
        enriched["checklist_analysis"] = _build_checklist_analysis_payload(
            enriched,
            evaluations,
            purpose=purpose,
        )
    except Exception:
        logger.warning("Checklist analysis could not be generated for parsed output.", exc_info=True)
        if existing_analysis is None:
            enriched["checklist_analysis"] = {
                "status": "unavailable",
                "purpose": purpose,
                "summary": "Checklist analysis could not be generated for this record.",
                "counts": {},
                "top_findings": [],
                "evaluations": [],
            }
    return enriched


def _is_invalid_input_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        phrase in message
        for phrase in (
            "unsupported input file format",
            "not a valid pdf",
            "unable to parse pdf",
        )
    )


def _require_authenticated_session(request: Request) -> str:
    username = request.session.get(_AUTH_SESSION_USER_KEY)
    expected_username = _AUTH_CONFIG["username"]
    if not isinstance(username, str) or username != expected_username:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return username


async def save_parse_record(
    file_name: str,
    content: bytes,
    parsed_output: object,
    detected_format: str,
) -> str:
    record_id = str(uuid.uuid4())
    safe_name = Path(file_name or "document").name or "document"
    storage = await put_object_bytes(
        f"parse-records/{record_id}/{safe_name}",
        content,
        _detect_mime_type(safe_name, "") or "application/octet-stream",
    )
    engine = await get_engine()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                parse_records.insert()
                .values(
                    id=record_id,
                    file_name=file_name,
                    file_size=len(content),
                    file_bytes=None,
                    file_storage_uri=storage.uri,
                    file_storage_provider=storage.provider,
                    file_sha256=hashlib.sha256(content).hexdigest(),
                    parsed_output=parsed_output,
                    document_format=detected_format,
                    completeness_score=_extract_completeness_score(parsed_output),
                    kis_index_status="pending",
                )
                .returning(parse_records.c.id)
            )
            record_id = result.scalar()
    except Exception:
        await delete_object(storage.uri)
        raise
    if record_id is None:
        raise RuntimeError("Database did not return a record id.")
    return str(record_id)


async def _record_kis_index_status(
    record_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    try:
        await update_kis_index_status(
            record_id,
            status=status,
            result=result,
            error_code=error_code,
            error_detail=error_detail,
        )
    except Exception as exc:
        logger.warning("Failed to persist KIS index status for parse record %s: %s", record_id, exc)


def _kis_background_indexing_enabled() -> bool:
    return _is_env_true("IQW_KIS_BACKGROUND_INDEXING", True)


def _kis_worker_config() -> dict[str, int]:
    def read_int(name: str, default: int, minimum: int = 1) -> int:
        raw = _get_env(name)
        if raw is None:
            return default
        try:
            return max(minimum, int(raw))
        except ValueError:
            return default

    return {
        "poll_seconds": read_int("IQW_KIS_WORKER_POLL_SECONDS", 5),
        "lock_seconds": read_int("IQW_KIS_WORKER_LOCK_SECONDS", 900, 60),
        "max_retries": read_int("IQW_KIS_MAX_RETRIES", 5),
        "retry_base_seconds": read_int("IQW_KIS_RETRY_BASE_SECONDS", 60),
        "retry_max_seconds": read_int("IQW_KIS_RETRY_MAX_SECONDS", 3600),
    }


def _wake_kis_worker() -> None:
    if _kis_worker_wakeup is not None:
        _kis_worker_wakeup.set()


def _kis_configured() -> bool:
    try:
        from kis_client import is_kis_configured

        return is_kis_configured()
    except Exception:
        return False


async def _run_kis_indexing(
    *,
    record_id: str,
    file_name: str,
    parsed_output: object,
    document_format: str,
    publish_snapshot: bool,
) -> dict[str, Any]:
    from kis_client import index_uploaded_document_via_kis

    return await asyncio.to_thread(
        index_uploaded_document_via_kis,
        record_id=record_id,
        file_name=file_name,
        parsed_output=parsed_output if isinstance(parsed_output, dict) else {},
        document_format=document_format,
        publish_snapshot=publish_snapshot,
    )


async def _index_parse_record_with_kis(
    *,
    record_id: str,
    file_name: str,
    parsed_output: object,
    document_format: str,
) -> dict[str, Any]:
    await _record_kis_index_status(record_id, status="running")
    try:
        result = await _run_kis_indexing(
            record_id=record_id,
            file_name=file_name,
            parsed_output=parsed_output,
            document_format=document_format,
            publish_snapshot=_is_env_true("IQW_KIS_AUTO_PUBLISH_SNAPSHOT", False),
        )
        status = normalize_kis_result_status(result)
        await _record_kis_index_status(
            record_id,
            status=status,
            result=result,
            error_code=None if status != "failed" else result.get("reason") or result.get("error"),
            error_detail=None if status != "failed" else result.get("reason") or result.get("error"),
        )
        return result
    except Exception as exc:
        logger.warning("KIS indexing failed for parse record %s: %s", record_id, exc)
        await _record_kis_index_status(
            record_id,
            status="failed",
            error_code=exc.__class__.__name__,
            error_detail="KIS indexing failed.",
        )
        if not _is_env_true("IQW_KIS_FALLBACK_ON_ERROR", True):
            raise HTTPException(status_code=503, detail="Document parsed but KIS indexing failed.") from exc
        return {"enabled": True, "indexed": False, "error": "kis_indexing_failed"}


async def _queue_parse_record_for_kis(
    *,
    record_id: str,
    file_name: str,
    parsed_output: object,
    document_format: str,
) -> dict[str, Any]:
    if not _kis_configured():
        result = {"enabled": False, "indexed": False, "queued": False, "reason": "kis_not_configured"}
        await _record_kis_index_status(record_id, status="disabled", result=result)
        return result
    if not _kis_background_indexing_enabled():
        return await _index_parse_record_with_kis(
            record_id=record_id,
            file_name=file_name,
            parsed_output=parsed_output,
            document_format=document_format,
        )
    await enqueue_kis_indexing(record_id)
    _wake_kis_worker()
    return {
        "enabled": True,
        "indexed": False,
        "queued": True,
        "kis_index_status": "pending",
        "reason": "background_indexing_queued",
    }


async def _process_next_kis_queue_item(worker_id: str) -> bool:
    config = _kis_worker_config()
    record = await claim_next_kis_index_record(
        worker_id=worker_id,
        lock_seconds=config["lock_seconds"],
        max_attempts=config["max_retries"],
    )
    if not record:
        return False

    record_id = str(record["id"])
    attempt_count = int(record.get("kis_attempt_count") or 1)
    try:
        result = await _run_kis_indexing(
            record_id=record_id,
            file_name=record.get("file_name") or "document",
            parsed_output=record.get("parsed_output") if isinstance(record.get("parsed_output"), dict) else {},
            document_format=record.get("document_format") or "UNKNOWN",
            publish_snapshot=_is_env_true("IQW_KIS_AUTO_PUBLISH_SNAPSHOT", False),
        )
        status = normalize_kis_result_status(result)
        if status == "failed":
            await mark_kis_index_failure(
                record_id,
                error_code=result.get("reason") or result.get("error") or "kis_indexing_failed",
                error_detail=result.get("reason") or result.get("error") or "KIS indexing failed.",
                attempt_count=attempt_count,
                max_attempts=config["max_retries"],
                retry_base_seconds=config["retry_base_seconds"],
                retry_max_seconds=config["retry_max_seconds"],
            )
            return True
        await _record_kis_index_status(record_id, status=status, result=result)
        return True
    except Exception as exc:
        logger.warning("KIS background indexing failed for parse record %s: %s", record_id, exc)
        await mark_kis_index_failure(
            record_id,
            error_code=exc.__class__.__name__,
            error_detail="KIS background indexing failed.",
            attempt_count=attempt_count,
            max_attempts=config["max_retries"],
            retry_base_seconds=config["retry_base_seconds"],
            retry_max_seconds=config["retry_max_seconds"],
        )
        return True


async def _kis_indexing_worker_loop() -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    logger.info("KIS indexing worker started: %s", worker_id)
    assert _kis_worker_stop is not None
    assert _kis_worker_wakeup is not None
    while not _kis_worker_stop.is_set():
        try:
            processed = await _process_next_kis_queue_item(worker_id)
            if processed:
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("KIS indexing worker loop error: %s", exc)

        poll_seconds = _kis_worker_config()["poll_seconds"]
        try:
            await asyncio.wait_for(_kis_worker_wakeup.wait(), timeout=poll_seconds)
            _kis_worker_wakeup.clear()
        except asyncio.TimeoutError:
            pass
    logger.info("KIS indexing worker stopped: %s", worker_id)


def _dashboard_background_worker_enabled() -> bool:
    return _is_env_true("IQW_DASHBOARD_BACKGROUND_WORKER", True)


def _dashboard_worker_config() -> dict[str, int]:
    raw = _get_env("IQW_DASHBOARD_WORKER_POLL_SECONDS")
    try:
        poll_seconds = max(1, int(raw)) if raw is not None else 5
    except ValueError:
        poll_seconds = 5
    return {"poll_seconds": poll_seconds}


async def _process_next_dashboard_queue_item() -> bool:
    from senior_dashboard import process_next_dashboard_background_job

    factory = await get_session_factory()
    async with factory() as session:
        processed = await process_next_dashboard_background_job(session)
        await session.commit()
        return processed


async def _dashboard_worker_loop() -> None:
    from senior_dashboard import set_dashboard_worker_wakeup

    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    logger.info("Senior dashboard worker started: %s", worker_id)
    assert _dashboard_worker_stop is not None
    assert _dashboard_worker_wakeup is not None
    set_dashboard_worker_wakeup(_dashboard_worker_wakeup)
    while not _dashboard_worker_stop.is_set():
        try:
            processed = await _process_next_dashboard_queue_item()
            if processed:
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Senior dashboard worker loop error: %s", exc)

        try:
            await asyncio.wait_for(_dashboard_worker_wakeup.wait(), timeout=_dashboard_worker_config()["poll_seconds"])
            _dashboard_worker_wakeup.clear()
        except asyncio.TimeoutError:
            pass
    set_dashboard_worker_wakeup(None)
    logger.info("Senior dashboard worker stopped: %s", worker_id)


class LoginRequest(BaseModel):
    username: str
    password: str


class SupportRequest(BaseModel):
    request_type: str
    user_identifier: str
    message: Optional[str] = None


class SupportRequestStatusUpdate(BaseModel):
    status: str
    resolution_note: Optional[str] = None


class RewriteRequestCreate(BaseModel):
    parse_record_id: str
    case_id: Optional[str] = None
    basis_text_type: Optional[str] = None
    include_original_language: bool = False


class RewriteDraftUpdate(BaseModel):
    body_markdown: str
    update_note: Optional[str] = None


class RewriteApprovalRequest(BaseModel):
    approval_note: str
    allow_english_only_issue: bool = False
    lineage_review_confirmed: bool = False


class PlaceholderReturnValue(BaseModel):
    placeholder_id: str
    petitioner_value: Optional[str] = None
    value_status: str


class RewriteReturnValuesRequest(BaseModel):
    values: list[PlaceholderReturnValue]
    update_note: Optional[str] = None


class PetitionerVerificationRequest(BaseModel):
    consent_status: str
    petitioner_name: Optional[str] = None
    verification_language: Optional[str] = None
    signature_mode: Optional[str] = None
    witness_note: Optional[str] = None
    signed_packet_uri: Optional[str] = None
    copy_provided_at: Optional[datetime] = None
    correction_note: Optional[str] = None


class RewriteAcceptRequest(BaseModel):
    acceptance_note: str


class RewriteTranslationRequest(BaseModel):
    target_language: Optional[str] = None
    target_language_name: Optional[str] = None


class RewriteSemanticValidationRequest(BaseModel):
    semantic_validation_status: str
    reviewer_note: Optional[str] = None
    sho_override_reason: Optional[str] = None


class ChecklistQuestionCreate(BaseModel):
    checklist_version: int = 1
    category: str
    purpose: str = "petition"
    offence_type: Optional[str] = None
    question_text: str
    expected_field_key: Optional[str] = None
    severity: str = "recommended"
    source_section: Optional[str] = None
    guidance: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class ChecklistQuestionUpdate(BaseModel):
    checklist_version: Optional[int] = None
    category: Optional[str] = None
    purpose: Optional[str] = None
    offence_type: Optional[str] = None
    question_text: Optional[str] = None
    expected_field_key: Optional[str] = None
    severity: Optional[str] = None
    source_section: Optional[str] = None
    guidance: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class PilotEvaluationCreate(BaseModel):
    semantic_drift_flag: bool = False
    unsupported_fact_count: int = 0
    petitioner_comprehension_status: Optional[str] = None
    refusal_or_correction: bool = False
    officer_override_used: bool = False
    quality_notes: list[str] = []


def _support_ticket_public(ticket: dict[str, Any]) -> dict[str, Any]:
    def serialize(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    return {
        "id": ticket["id"],
        "request_type": ticket["request_type"],
        "user_identifier": ticket["user_identifier"],
        "message": ticket.get("message") or "",
        "status": ticket["status"],
        "created_at": serialize(ticket["created_at"]),
        "updated_at": serialize(ticket.get("updated_at")),
        "resolved_at": serialize(ticket.get("resolved_at")),
        "resolved_by": ticket.get("resolved_by"),
        "persistence": ticket.get("persistence", "database"),
    }


def _is_database_config_missing(exc: Exception) -> bool:
    return isinstance(exc, RuntimeError) and "DATABASE_URL or CLOUD_SQL_CONNECTION_NAME" in str(exc)


def _append_support_request_memory(ticket: dict[str, Any]) -> dict[str, Any]:
    fallback_ticket = dict(ticket)
    fallback_ticket["persistence"] = "memory_fallback"
    _support_request_store.append(fallback_ticket)
    if len(_support_request_store) > 500:
        del _support_request_store[:-500]
    return fallback_ticket


async def _save_auth_support_request(ticket: dict[str, Any]) -> dict[str, Any]:
    try:
        engine = await get_engine()
    except RuntimeError as exc:
        if _is_database_config_missing(exc):
            logger.warning("Auth support request stored in memory fallback because database is not configured.")
            return _append_support_request_memory(ticket)
        raise

    async with engine.begin() as conn:
        await conn.execute(auth_support_requests.insert().values(**ticket))
    persisted = dict(ticket)
    persisted["persistence"] = "database"
    return persisted


async def _list_auth_support_requests(limit: int = 100) -> list[dict[str, Any]]:
    try:
        engine = await get_engine()
    except RuntimeError as exc:
        if _is_database_config_missing(exc):
            return list(reversed(_support_request_store[-limit:]))
        raise

    stmt = (
        sa.select(auth_support_requests)
        .order_by(auth_support_requests.c.created_at.desc())
        .limit(limit)
    )
    async with engine.connect() as conn:
        result = await conn.execute(stmt)
        return [dict(row._mapping) for row in result]


async def _update_auth_support_request_status(ticket_id: str, status: str, resolved_by: str) -> dict[str, Any] | None:
    allowed_statuses = {"open", "in_review", "resolved", "dismissed"}
    normalized_status = status.strip().lower().replace("-", "_")
    if normalized_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Unsupported support request status.")

    now_clause = sa.func.now()
    resolved_at_value = now_clause if normalized_status in {"resolved", "dismissed"} else None
    try:
        engine = await get_engine()
    except RuntimeError as exc:
        if not _is_database_config_missing(exc):
            raise
        for ticket in _support_request_store:
            if ticket["id"] == ticket_id:
                ticket["status"] = normalized_status
                ticket["updated_at"] = time.time()
                if normalized_status in {"resolved", "dismissed"}:
                    ticket["resolved_at"] = ticket["updated_at"]
                    ticket["resolved_by"] = resolved_by
                else:
                    ticket["resolved_at"] = None
                    ticket["resolved_by"] = None
                return ticket
        return None

    async with engine.begin() as conn:
        stmt = (
            auth_support_requests.update()
            .where(auth_support_requests.c.id == ticket_id)
            .values(
                status=normalized_status,
                updated_at=now_clause,
                resolved_at=resolved_at_value,
                resolved_by=resolved_by if normalized_status in {"resolved", "dismissed"} else None,
            )
            .returning(auth_support_requests)
        )
        result = await conn.execute(stmt)
        row = result.first()
        return dict(row._mapping) if row else None


async def _seed_admin_user() -> None:
    """Create or update the System_Admin user from env vars."""
    from auth import hash_password
    from models import User, UserRole

    admin_user = os.getenv("APP_ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("APP_ADMIN_PASSWORD", "admin")
    pw_hash = hash_password(admin_pass)

    engine = await get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(sa.text("SELECT count(*) FROM users"))
        count = result.scalar()
        if count and count > 0:
            # Update existing admin to match env vars
            await conn.execute(
                sa.text(
                    "UPDATE users SET employee_id = :eid, password_hash = :pw "
                    "WHERE id = (SELECT id FROM users WHERE role = 'System_Admin' LIMIT 1)"
                ),
                {"eid": admin_user, "pw": pw_hash},
            )
            logger.info("Updated admin user credentials: %s", admin_user)
            return
        import uuid as _uuid_mod
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, employee_id, full_name, role, password_hash, is_active, is_deleted, created_at) "
                "VALUES (:id, :eid, :name, :role, :pw, true, false, now())"
            ),
            {
                "id": str(_uuid_mod.uuid4()),
                "eid": admin_user,
                "name": "System Administrator",
                "role": "System_Admin",
                "pw": pw_hash,
            },
        )
    logger.info("Seeded initial admin user: %s", admin_user)


async def _seed_reference_data() -> None:
    """Seed police stations, offence types, and document templates."""
    from database import get_session_factory
    from cases import seed_police_stations, seed_offence_types
    from document_generator import seed_templates

    factory = await get_session_factory()
    async with factory() as session:
        with session.no_autoflush:
            await seed_police_stations(session)
            await seed_offence_types(session)
            await seed_templates(session)
        await session.commit()
    logger.info("Seeded reference data (police stations, offence types, templates)")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global _kis_worker_stop
    global _kis_worker_task
    global _kis_worker_wakeup
    global _dashboard_worker_stop
    global _dashboard_worker_task
    global _dashboard_worker_wakeup

    get_doc_ai_config()
    try:
        await initialize_database()
    except Exception as exc:
        logger.warning("Database initialisation failed (history disabled): %s", exc)
    try:
        await initialize_all_tables()
    except Exception as exc:
        logger.warning("IQW table initialisation failed: %s", exc)
    # Seed initial admin user if no users exist
    try:
        await _seed_admin_user()
    except Exception as exc:
        logger.warning("Admin user seeding skipped: %s", exc)
    # Seed reference data (police stations, offence types, templates)
    try:
        await _seed_reference_data()
    except Exception as exc:
        logger.warning("Reference data seeding skipped: %s", exc)
    if _kis_background_indexing_enabled():
        _kis_worker_stop = asyncio.Event()
        _kis_worker_wakeup = asyncio.Event()
        _kis_worker_task = asyncio.create_task(_kis_indexing_worker_loop())
    if _dashboard_background_worker_enabled():
        _dashboard_worker_stop = asyncio.Event()
        _dashboard_worker_wakeup = asyncio.Event()
        _dashboard_worker_task = asyncio.create_task(_dashboard_worker_loop())
    yield
    if _kis_worker_task is not None:
        if _kis_worker_stop is not None:
            _kis_worker_stop.set()
        if _kis_worker_wakeup is not None:
            _kis_worker_wakeup.set()
        _kis_worker_task.cancel()
        try:
            await _kis_worker_task
        except asyncio.CancelledError:
            pass
        _kis_worker_task = None
        _kis_worker_stop = None
        _kis_worker_wakeup = None
    if _dashboard_worker_task is not None:
        if _dashboard_worker_stop is not None:
            _dashboard_worker_stop.set()
        if _dashboard_worker_wakeup is not None:
            _dashboard_worker_wakeup.set()
        _dashboard_worker_task.cancel()
        try:
            await _dashboard_worker_task
        except asyncio.CancelledError:
            pass
        _dashboard_worker_task = None
        _dashboard_worker_stop = None
        _dashboard_worker_wakeup = None
    await dispose_engine()


app = FastAPI(title="ADS Complaint Analyser", version="1.1.0", lifespan=lifespan)
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

from api_v1 import v1_router  # noqa: E402
app.include_router(v1_router)

from audit import AuditMiddleware  # noqa: E402
app.add_middleware(AuditMiddleware)

app.add_middleware(
    SessionMiddleware,
    secret_key=str(_AUTH_CONFIG["session_secret"]),
    same_site="strict",
    https_only=bool(_AUTH_CONFIG["session_https_only"]),
    max_age=60 * 60 * 12,
)

_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
    )

# Simple in-process rate limiter for write endpoints (per-IP, sliding window).
_RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_RPM", "30"))
_rate_limit_log: dict[str, list[float]] = defaultdict(list)
_kis_worker_task: asyncio.Task | None = None
_kis_worker_stop: asyncio.Event | None = None
_kis_worker_wakeup: asyncio.Event | None = None
_dashboard_worker_task: asyncio.Task | None = None
_dashboard_worker_stop: asyncio.Event | None = None
_dashboard_worker_wakeup: asyncio.Event | None = None


@app.get("/manifest.json")
def serve_manifest() -> JSONResponse:
    """Serve PWA manifest."""
    manifest_path = Path(__file__).resolve().parent / "manifest.json"
    if manifest_path.exists():
        import json as _manifest_json
        data = _manifest_json.loads(manifest_path.read_text(encoding="utf-8"))
        return JSONResponse(content=data, headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(status_code=404, detail="Manifest not found")


@app.get("/sw.js")
def serve_sw() -> HTMLResponse:
    """Serve service worker from root scope."""
    sw_path = Path(__file__).resolve().parent / "sw.js"
    if sw_path.exists():
        content = sw_path.read_text(encoding="utf-8")
        return HTMLResponse(
            content=content,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
        )
    raise HTTPException(status_code=404, detail="Service worker not found")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(
        content=_INDEX_HTML,
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/sso")
async def platform_sso(request: Request, token: str = Query(..., min_length=16, max_length=4096)) -> Response:
    """Platform launch-token exchange: verifies the policing-platform SSO token
    (HMAC-SHA256, audience "iqw") and establishes the local session."""
    secret = os.environ.get("PLATFORM_SSO_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Platform SSO is not enabled.")
    payload = _verify_platform_sso_token(token, secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Launch token is invalid or expired.")
    request.session.clear()
    request.session[_AUTH_SESSION_USER_KEY] = str(_AUTH_CONFIG["username"])
    logger.info(
        "platform SSO login: subject=%s tenant=%s", payload.get("u"), payload.get("t")
    )
    return RedirectResponse(url="/", status_code=302)


def _verify_platform_sso_token(token: str, secret: str) -> dict | None:
    dot = token.rfind(".")
    if dot <= 0:
        return None
    payload_b64, signature = token[:dot], token[dot + 1 :]
    expected = (
        base64.urlsafe_b64encode(
            hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("a") != "iqw":
        return None
    expiry = payload.get("e")
    if not isinstance(expiry, (int, float)) or expiry <= time.time() * 1000:
        return None
    return payload


@app.get("/health")
@app.get("/api/health")
async def health() -> JSONResponse:
    status_code = 200

    try:
        config = get_doc_ai_config()
        document_ai_status = "ok"
    except RuntimeError:
        config = {
            "DOC_AI_LOCATION": None,
            "DOC_AI_FIELD_MASK": None,
        }
        document_ai_status = "error"
        status_code = 503

    database_health = await get_database_health()
    if database_health["status"] != "ok":
        status_code = 503

    translation_config = get_translation_config()
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "error",
            "parser_mode": "police_complaint",
            "auth_required": True,
            "document_ai_status": document_ai_status,
            "location": config["DOC_AI_LOCATION"],
            "field_mask": config["DOC_AI_FIELD_MASK"],
            "database_status": database_health["status"],
            "database_table_ready": database_health["table_ready"],
            "translation_enabled": translation_config["enabled"],
            "translation_provider": translation_config["provider"],
            "translation_fallback_provider": translation_config["fallback_provider"],
            "translation_target_language": translation_config["target_language"],
            "openai_translation_enabled": translation_config["openai_enabled"],
            "openai_translation_model": translation_config["openai_model"],
            "openai_api_key_configured": translation_config["openai_api_key_configured"],
            "gemini_translation_enabled": translation_config["gemini_enabled"],
            "gemini_api_key_configured": translation_config["gemini_api_key_configured"],
            "translation_refinement_enabled": translation_config["refinement_enabled"],
            "translation_refinement_provider": translation_config["refinement_provider"],
            "translation_refinement_model": translation_config["refinement_model"],
            "translation_qe_enabled": translation_config["quality_estimation_enabled"],
        },
    )


@app.get("/api/auth/session")
async def get_session_status(request: Request) -> JSONResponse:
    username = request.session.get(_AUTH_SESSION_USER_KEY)
    is_authenticated = isinstance(username, str) and username == _AUTH_CONFIG["username"]
    return JSONResponse(
        content={
            "authenticated": is_authenticated,
            "user": username if is_authenticated else None,
        }
    )


@app.post("/api/auth/login")
async def login(payload: LoginRequest, request: Request) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))

    username = payload.username.strip()
    password = payload.password
    expected_username = str(_AUTH_CONFIG["username"])
    expected_password = str(_AUTH_CONFIG["password"])

    username_ok = secrets.compare_digest(username, expected_username)
    password_ok = secrets.compare_digest(password, expected_password)
    if not username_ok or not password_ok:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    request.session.clear()
    request.session[_AUTH_SESSION_USER_KEY] = expected_username
    return JSONResponse(
        content={
            "authenticated": True,
            "user": expected_username,
        }
    )


@app.post("/api/auth/logout")
async def logout(request: Request) -> JSONResponse:
    request.session.clear()
    return JSONResponse(content={"authenticated": False})


@app.post("/api/auth/support-request")
async def create_auth_support_request(payload: SupportRequest, request: Request) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    request_type = payload.request_type.strip().lower().replace("-", "_")
    if request_type not in {"password_reset", "access_request"}:
        raise HTTPException(status_code=400, detail="Unsupported support request type.")

    user_identifier = payload.user_identifier.strip()
    if not user_identifier or len(user_identifier) > 120:
        raise HTTPException(status_code=400, detail="Employee ID or official email is required.")

    message = (payload.message or "").strip()
    if len(message) > 500:
        message = message[:500]

    ticket = {
        "id": f"SUP-{uuid.uuid4().hex[:10].upper()}",
        "request_type": request_type,
        "user_identifier": user_identifier,
        "message": message,
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "resolved_at": None,
        "resolved_by": None,
        "client_fingerprint": hashlib.sha256(_get_client_ip(request).encode("utf-8")).hexdigest()[:16],
    }
    try:
        stored_ticket = await _save_auth_support_request(ticket)
    except Exception as exc:
        logger.warning("Auth support request persistence failed: %s", exc)
        raise HTTPException(status_code=503, detail="Could not persist support request.") from exc
    logger.info(
        "auth support request created id=%s type=%s persistence=%s",
        stored_ticket["id"],
        stored_ticket["request_type"],
        stored_ticket.get("persistence", "database"),
    )
    return JSONResponse(
        status_code=201,
        content={
            "ticket_id": stored_ticket["id"],
            "status": stored_ticket["status"],
            "request_type": stored_ticket["request_type"],
            "persistence": stored_ticket.get("persistence", "database"),
        },
    )


@app.get("/api/auth/support-requests")
async def list_auth_support_requests(_current_user: str = Depends(_require_authenticated_session)) -> JSONResponse:
    try:
        tickets = await _list_auth_support_requests(100)
    except Exception as exc:
        logger.warning("Auth support request listing failed: %s", exc)
        raise HTTPException(status_code=503, detail="Could not load support requests.") from exc
    return JSONResponse(
        content={
            "items": [_support_ticket_public(ticket) for ticket in tickets]
        }
    )


@app.patch("/api/auth/support-requests/{ticket_id}")
async def update_auth_support_request(
    ticket_id: str,
    payload: SupportRequestStatusUpdate,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    ticket = await _update_auth_support_request_status(ticket_id, payload.status, current_user)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support request not found.")
    return JSONResponse(content=_support_ticket_public(ticket))


@app.post("/api/parse")
@app.post("/parse")
async def parse_uploaded_file(
    request: Request,
    file: UploadFile = File(...),
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    filename = Path(file.filename or "").name
    content_type = file.content_type or ""

    detected_mime = _detect_mime_type(filename, content_type)
    if not detected_mime:
        supported = ", ".join(sorted({ext.lstrip(".").upper() for ext in ACCEPTED_MIME_TYPES}))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Accepted formats: {supported}.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_PARSE_UPLOAD_BYTES:
        max_mb = MAX_PARSE_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds the {max_mb} MB size limit.",
        )

    try:
        config = get_doc_ai_config()
    except RuntimeError as exc:
        logger.warning("Document AI configuration unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Document AI configuration is not ready.") from exc

    try:
        result = process_document_bytes(
            project_id=str(config["DOC_AI_PROJECT_ID"]),
            location=str(config["DOC_AI_LOCATION"]),
            processor_id=str(config["DOC_AI_PROCESSOR_ID"]),
            content=content,
            mime_type=detected_mime,
            field_mask=config["DOC_AI_FIELD_MASK"],
            credentials=config.get("_credentials"),
        )
        raw_text = result.document.text or ""
        parsed_output = parse_document(raw_text)
        parsed_output = await enrich_parsed_output_with_checklist(parsed_output)
        detected_format = (
            parsed_output.get("meta", {}).get("detected_format")
            if isinstance(parsed_output, dict)
            else None
        )
        document_format = detected_format or "UNKNOWN"

        try:
            record_id = await save_parse_record(
                file_name=filename,
                content=content,
                parsed_output=parsed_output,
                detected_format=document_format,
            )
        except Exception as exc:
            logger.exception("Failed to persist parse record to database")
            raise HTTPException(
                status_code=503,
                detail="Document parsed but could not be saved to history.",
            ) from exc
        kis_indexing = await _queue_parse_record_for_kis(
            record_id=record_id,
            file_name=filename,
            parsed_output=parsed_output,
            document_format=document_format,
        )

        return JSONResponse(
            content={
                "id": record_id,
                "file_name": filename,
                "document_format": document_format,
                "raw_text_length": len(raw_text),
                "parsed_output": parsed_output,
                "kis_indexing": kis_indexing,
            }
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        if _is_invalid_input_error(exc):
            raise HTTPException(
                status_code=422,
                detail="Uploaded file could not be processed as a valid document.",
            ) from exc
        logger.exception("Document processing failed")
        raise HTTPException(
            status_code=500,
            detail="Document processing failed. Check server logs for details.",
        ) from exc


@app.post("/api/parse/stream")
async def parse_uploaded_file_stream(
    request: Request,
    file: UploadFile = File(...),
    case_id: Optional[str] = Query(None),
    case_document_id: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    _current_user: str = Depends(_require_authenticated_session),
) -> StreamingResponse:
    """SSE streaming variant of /api/parse — sends pipeline progress events."""
    _check_rate_limit(_get_client_ip(request))
    filename = Path(file.filename or "").name
    content_type = file.content_type or ""

    detected_mime = _detect_mime_type(filename, content_type)
    if not detected_mime:
        supported = ", ".join(sorted({ext.lstrip(".").upper() for ext in ACCEPTED_MIME_TYPES}))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Accepted formats: {supported}.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_PARSE_UPLOAD_BYTES:
        max_mb = MAX_PARSE_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds the {max_mb} MB size limit.",
        )

    # Create CaseDocument BEFORE the pipeline so it appears in case doc list immediately
    created_case_document_id: Optional[str] = None
    if case_id and not case_document_id:
        try:
            from cases import attach_document
            factory = await get_session_factory()
            async with factory() as session:
                doc_result = await attach_document(
                    case_id=case_id,
                    file_name=filename,
                    document_type=document_type or "Other",
                    file_bytes=content,
                    user_id=_current_user,
                    db=session,
                    mime_type=detected_mime,
                    upload_method="Parse_Pipeline",
                )
                await session.commit()
                created_case_document_id = doc_result["id"]
                case_document_id = created_case_document_id
        except Exception:
            logger.exception("Failed to create CaseDocument for case %s", case_id)

    try:
        config = get_doc_ai_config()
    except RuntimeError as exc:
        logger.warning("Document AI configuration unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Document AI configuration is not ready.") from exc

    progress_queue: queue.Queue[dict[str, Any]] = queue.Queue()

    def _progress_cb(step_id: str, label: str, details: str | None) -> None:
        progress_queue.put({"step": step_id, "label": label, "details": details})

    async def _run_pipeline() -> dict[str, Any]:
        _progress_cb("ocr", "Processing document with OCR", None)
        result = await asyncio.to_thread(
            process_document_bytes,
            project_id=str(config["DOC_AI_PROJECT_ID"]),
            location=str(config["DOC_AI_LOCATION"]),
            processor_id=str(config["DOC_AI_PROCESSOR_ID"]),
            content=content,
            mime_type=detected_mime,
            field_mask=config["DOC_AI_FIELD_MASK"],
            credentials=config.get("_credentials"),
        )
        raw_text = result.document.text or ""
        parsed_output = await asyncio.to_thread(
            parse_document, raw_text, _progress_cb,
        )
        _progress_cb("checklist", "Evaluating active checklist", None)
        parsed_output = await enrich_parsed_output_with_checklist(parsed_output)
        return {"raw_text": raw_text, "parsed_output": parsed_output}

    async def _event_stream():
        pipeline_task = asyncio.create_task(_run_pipeline())
        pipeline_error: Exception | None = None
        pipeline_result: dict[str, Any] | None = None

        while not pipeline_task.done():
            # Drain queued progress events
            while True:
                try:
                    evt = progress_queue.get_nowait()
                    yield f"data: {_json.dumps(evt)}\n\n"
                except queue.Empty:
                    break
            await asyncio.sleep(0.1)

        # Drain any remaining events after task completion
        while True:
            try:
                evt = progress_queue.get_nowait()
                yield f"data: {_json.dumps(evt)}\n\n"
            except queue.Empty:
                break

        try:
            pipeline_result = pipeline_task.result()
        except Exception as exc:
            pipeline_error = exc

        if pipeline_error is not None:
            err_msg = str(pipeline_error)
            if _is_invalid_input_error(pipeline_error):
                err_msg = "Uploaded file could not be processed as a valid document."
            yield f"data: {_json.dumps({'step': 'error', 'label': 'Error', 'details': err_msg})}\n\n"
            return

        parsed_output = pipeline_result["parsed_output"]
        raw_text = pipeline_result["raw_text"]
        detected_format = (
            parsed_output.get("meta", {}).get("detected_format")
            if isinstance(parsed_output, dict) else None
        )
        document_format = detected_format or "UNKNOWN"

        try:
            record_id = await save_parse_record(
                file_name=filename,
                content=content,
                parsed_output=parsed_output,
                detected_format=document_format,
            )
        except Exception:
            logger.exception("Failed to persist parse record to database")
            yield f"data: {_json.dumps({'step': 'error', 'label': 'Error', 'details': 'Document parsed but could not be saved to history.'})}\n\n"
            return

        # Link parse record to case if uploaded from case context
        if case_id:
            try:
                engine = await get_engine()
                async with engine.begin() as conn:
                    await conn.execute(
                        parse_records.update()
                        .where(parse_records.c.id == record_id)
                        .values(case_id=case_id)
                    )
            except Exception:
                logger.warning("Failed to link parse record %s to case %s", record_id, case_id, exc_info=True)
        if case_document_id:
            try:
                from models import CaseDocument
                factory = await get_session_factory()
                async with factory() as session:
                    doc = await session.get(CaseDocument, case_document_id)
                    if doc:
                        doc.parsed_output = parsed_output
                        await session.commit()
            except Exception:
                logger.warning("Failed to update CaseDocument %s with parsed output", case_document_id, exc_info=True)

        kis_indexing = await _queue_parse_record_for_kis(
            record_id=record_id,
            file_name=filename,
            parsed_output=parsed_output,
            document_format=document_format,
        )

        done_payload = {
            "step": "done",
            "label": "Complete",
            "result": {
                "id": record_id,
                "file_name": filename,
                "document_format": document_format,
                "raw_text_length": len(raw_text),
                "parsed_output": parsed_output,
                "kis_indexing": kis_indexing,
                "case_id": case_id,
                "case_document_id": case_document_id,
            },
        }
        yield f"data: {_json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _rewrite_error(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "field": field, "metadata": metadata or {}}},
    )


def _validated_uuid(value: str, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise _rewrite_error(422, "INVALID_ID", f"{field} must be a valid UUID.", field) from exc


def _serialize_for_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_serialize_for_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_for_json(item) for key, item in value.items()}
    return value


def _mapping_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        mapping = row
    else:
        try:
            mapping = row._mapping
        except AttributeError:
            mapping = row if hasattr(row, "items") else dict(row)
    return {
        str(getattr(key, "key", key)): _serialize_for_json(value)
        for key, value in mapping.items()
    }


def _table_values(table: sa.Table, values: dict[str, Any]) -> dict[str, Any]:
    column_names = {column.name for column in table.c}
    return {key: value for key, value in values.items() if key in column_names}


async def _fetch_one_mapping(conn: Any, stmt: Any) -> dict[str, Any] | None:
    result = await conn.execute(stmt)
    row = result.mappings().first()
    return _mapping_to_dict(row) if row is not None else None


async def _fetch_all_mappings(conn: Any, stmt: Any) -> list[dict[str, Any]]:
    result = await conn.execute(stmt)
    return [_mapping_to_dict(row) for row in result.mappings().all()]


async def _insert_rewrite_audit_event(
    conn: Any,
    *,
    rewrite_request_id: str,
    actor_id: str,
    action_type: str,
    event_summary: str,
    before_hash: str | None = None,
    after_hash: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await conn.execute(
        rewrite_audit_events.insert().values(
            id=str(uuid.uuid4()),
            rewrite_request_id=rewrite_request_id,
            actor_id=actor_id,
            actor_role="browser_user",
            action_type=action_type,
            before_hash=before_hash,
            after_hash=after_hash,
            event_summary=event_summary,
            metadata=metadata or {},
        )
    )


async def _resolve_rewrite_parse_record(conn: Any, record_or_document_id: str) -> dict[str, Any] | None:
    record = await _fetch_one_mapping(
        conn,
        sa.select(
            parse_records.c.id,
            parse_records.c.file_name,
            parse_records.c.case_id,
            parse_records.c.parsed_output,
        ).where(parse_records.c.id == record_or_document_id),
    )
    if record is not None:
        return record

    try:
        from models import CaseDocument
    except Exception:
        return None

    case_documents = CaseDocument.__table__
    doc = await _fetch_one_mapping(
        conn,
        sa.select(
            case_documents.c.id,
            case_documents.c.case_id,
            case_documents.c.file_name,
            case_documents.c.file_size_bytes,
            case_documents.c.file_storage_uri,
            case_documents.c.file_storage_provider,
            case_documents.c.sha256_hash,
            case_documents.c.parsed_output,
        ).where(case_documents.c.id == record_or_document_id),
    )
    if doc is None:
        return None

    candidate_queries = []
    if doc.get("sha256_hash"):
        candidate_queries.append(
            sa.select(
                parse_records.c.id,
                parse_records.c.file_name,
                parse_records.c.case_id,
                parse_records.c.parsed_output,
            )
            .where(
                parse_records.c.case_id == doc.get("case_id"),
                parse_records.c.file_sha256 == doc.get("sha256_hash"),
            )
            .order_by(parse_records.c.created_at.desc())
            .limit(1)
        )
    candidate_queries.append(
        sa.select(
            parse_records.c.id,
            parse_records.c.file_name,
            parse_records.c.case_id,
            parse_records.c.parsed_output,
        )
        .where(
            parse_records.c.case_id == doc.get("case_id"),
            parse_records.c.file_name == doc.get("file_name"),
        )
        .order_by(parse_records.c.created_at.desc())
        .limit(1)
    )
    for query in candidate_queries:
        record = await _fetch_one_mapping(conn, query)
        if record is not None:
            return record

    parsed_output = doc.get("parsed_output")
    if not isinstance(parsed_output, dict):
        return None

    enriched_output = await enrich_parsed_output_with_checklist(parsed_output, conn=conn)
    document_format = (
        enriched_output.get("meta", {}).get("detected_format")
        if isinstance(enriched_output, dict)
        else None
    ) or "CASE_DOCUMENT"
    new_record_id = str(uuid.uuid4())
    await conn.execute(
        parse_records.insert().values(
            id=new_record_id,
            file_name=doc.get("file_name") or "case-document",
            file_size=int(doc.get("file_size_bytes") or 0),
            file_bytes=None,
            file_storage_uri=doc.get("file_storage_uri"),
            file_storage_provider=doc.get("file_storage_provider"),
            file_sha256=doc.get("sha256_hash"),
            case_id=doc.get("case_id"),
            parsed_output=enriched_output,
            document_format=document_format,
            completeness_score=_extract_completeness_score(enriched_output),
            kis_index_status="not_started",
        )
    )
    await conn.execute(
        case_documents.update()
        .where(case_documents.c.id == doc.get("id"))
        .values(parsed_output=enriched_output)
    )
    return {
        "id": new_record_id,
        "file_name": doc.get("file_name"),
        "case_id": doc.get("case_id"),
        "parsed_output": enriched_output,
    }


async def _get_rewrite_detail(conn: Any, rewrite_request_id: str) -> dict[str, Any] | None:
    request_row = await _fetch_one_mapping(
        conn,
        sa.select(*petition_rewrite_requests.c).where(
            petition_rewrite_requests.c.id == rewrite_request_id,
            petition_rewrite_requests.c.is_deleted == sa.false(),
        ),
    )
    if request_row is None:
        return None

    placeholders = await _fetch_all_mappings(
        conn,
        sa.select(*petition_placeholders.c)
        .where(petition_placeholders.c.rewrite_request_id == rewrite_request_id)
        .order_by(petition_placeholders.c.display_order.asc()),
    )
    drafts = await _fetch_all_mappings(
        conn,
        sa.select(*generated_petition_drafts.c)
        .where(generated_petition_drafts.c.rewrite_request_id == rewrite_request_id)
        .order_by(generated_petition_drafts.c.draft_version.desc()),
    )
    lineage = await _fetch_all_mappings(
        conn,
        sa.select(*source_lineage_maps.c)
        .where(source_lineage_maps.c.rewrite_request_id == rewrite_request_id)
        .order_by(source_lineage_maps.c.output_span_id.asc()),
    )
    petitioner_packet_rows = await _fetch_all_mappings(
        conn,
        sa.select(*petitioner_packets.c)
        .where(petitioner_packets.c.rewrite_request_id == rewrite_request_id)
        .order_by(petitioner_packets.c.created_at.desc()),
    )
    verification_rows = await _fetch_all_mappings(
        conn,
        sa.select(*petitioner_verification_records.c)
        .where(petitioner_verification_records.c.rewrite_request_id == rewrite_request_id)
        .order_by(petitioner_verification_records.c.verified_at.desc()),
    )
    translation_rows = await _fetch_all_mappings(
        conn,
        sa.select(*petition_draft_translations.c)
        .where(petition_draft_translations.c.rewrite_request_id == rewrite_request_id)
        .order_by(petition_draft_translations.c.created_at.desc()),
    )
    checklist_rows = await _fetch_all_mappings(
        conn,
        sa.select(*petition_checklist_evaluations.c)
        .where(petition_checklist_evaluations.c.rewrite_request_id == rewrite_request_id)
        .order_by(petition_checklist_evaluations.c.created_at.desc()),
    )
    pilot_rows = await _fetch_all_mappings(
        conn,
        sa.select(*petition_pilot_evaluations.c)
        .where(petition_pilot_evaluations.c.rewrite_request_id == rewrite_request_id)
        .order_by(petition_pilot_evaluations.c.created_at.desc()),
    )
    audit_events = await _fetch_all_mappings(
        conn,
        sa.select(*rewrite_audit_events.c)
        .where(rewrite_audit_events.c.rewrite_request_id == rewrite_request_id)
        .order_by(rewrite_audit_events.c.created_at.desc()),
    )
    latest_draft = drafts[0] if drafts else None
    validation = {
        "placeholder_integrity_passed": True,
        "missing_placeholder_tokens": [],
        "source_lineage_complete": bool(latest_draft and latest_draft.get("source_lineage_complete")),
        "unsupported_fact_count": int(latest_draft.get("unsupported_fact_count", 0)) if latest_draft else 0,
        "contradiction_count": int(latest_draft.get("contradiction_count", 0)) if latest_draft else 0,
        "source_lineage_status": request_row.get("source_lineage_status"),
        "contradiction_check_status": request_row.get("contradiction_check_status"),
        "quality_status": latest_draft.get("quality_status") if latest_draft else "missing_draft",
        "quality_notes": latest_draft.get("quality_notes") if latest_draft else ["No generated draft is available."],
    }
    if latest_draft:
        body = str(latest_draft.get("body_plain_text") or latest_draft.get("body_markdown") or "")
        missing_tokens = [item["token"] for item in placeholders if item.get("token") not in body]
        validation["placeholder_integrity_passed"] = not missing_tokens
        validation["missing_placeholder_tokens"] = missing_tokens

    return {
        "request": request_row,
        "placeholders": placeholders,
        "drafts": drafts,
        "draft": latest_draft,
        "lineage": lineage,
        "petitioner_packets": petitioner_packet_rows,
        "verification_records": verification_rows,
        "latest_verification": verification_rows[0] if verification_rows else None,
        "translations": translation_rows,
        "latest_translation": translation_rows[0] if translation_rows else None,
        "checklist_evaluations": checklist_rows,
        "pilot_evaluations": pilot_rows,
        "audit_events": audit_events,
        "validation": validation,
    }


def _draft_validation_from_edit(
    *,
    body_markdown: str,
    current_draft: dict[str, Any],
    placeholders: list[dict[str, Any]],
) -> dict[str, Any]:
    body_plain_text = body_markdown.strip() + "\n" if body_markdown.strip() else ""
    body_hash = sha256_text(body_plain_text)
    missing_tokens = [item["token"] for item in placeholders if item.get("token") not in body_plain_text]
    body_changed = body_hash != current_draft.get("sha256_hash")
    source_lineage_complete = (
        not body_changed
        and not missing_tokens
        and bool(current_draft.get("source_lineage_complete"))
        and int(current_draft.get("unsupported_fact_count") or 0) == 0
    )
    quality_notes: list[str] = []
    if missing_tokens:
        quality_notes.append("One or more protected placeholder tokens are missing from the edited draft.")
    if body_changed:
        quality_notes.append(
            "Officer edits require source-lineage review before approval because new wording may add or change facts."
        )
    if not quality_notes:
        quality_notes.append("Draft body is unchanged and existing lineage remains valid.")
    unsupported_fact_count = 0 if source_lineage_complete else len(missing_tokens) + (1 if body_changed else 0)
    return {
        "body_plain_text": body_plain_text,
        "sha256_hash": body_hash,
        "missing_placeholder_tokens": missing_tokens,
        "source_lineage_complete": source_lineage_complete,
        "source_lineage_status": "complete" if source_lineage_complete else "incomplete",
        "unsupported_fact_count": unsupported_fact_count,
        "quality_status": "passed" if source_lineage_complete else "needs_review",
        "quality_notes": quality_notes,
    }


def _openai_petition_translation_available(config: dict[str, Any]) -> bool:
    return bool(
        config.get("enabled")
        and config.get("openai_enabled")
        and config.get("openai_api_key")
    )


def _translate_petition_packet_via_openai(
    protected_body_markdown: str,
    target_language: str,
    target_language_name: str | None = None,
) -> str:
    config = get_translation_config()
    if not _openai_petition_translation_available(config):
        raise PetitionAssistanceError(
            "OPENAI_TRANSLATION_UNAVAILABLE",
            "OpenAI translation is not configured for petition packet translation.",
            "OPENAI_TRANSLATION_API_KEY",
        )

    target_label = target_language_name or target_language or "the petition source language"
    if str(target_language or "").strip().lower() in {"en", "english"}:
        return protected_body_markdown

    payload: dict[str, Any] = {
        "model": config["openai_model"],
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Translate the English missing-information assistance packet into the requested Indian language. "
                            "Return only the translated packet text. Preserve markdown headings, line breaks, dates, names, "
                            "numbers, signature blanks, and every __PETITION_PLACEHOLDER_###__ token exactly. "
                            "Do not add facts, omit facts, summarize, answer placeholders, or give legal advice. "
                            "Use natural police-station/public-service wording in the target script."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Target language: {target_label} ({target_language})\n\n"
                            f"{protected_body_markdown}"
                        ),
                    }
                ],
            },
        ],
    }
    reasoning_effort = str(config.get("openai_reasoning_effort") or "none").lower()
    if reasoning_effort in {"none", "low", "medium", "high", "xhigh"}:
        payload["reasoning"] = {"effort": reasoning_effort}

    request_obj = urllib.request.Request(
        f"{config['openai_base_url']}/responses",
        data=_json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['openai_api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        ssl_context = _build_openai_ssl_context()
        with urllib.request.urlopen(request_obj, timeout=180, context=ssl_context) as response:
            response_payload = _json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise PetitionAssistanceError(
            "OPENAI_TRANSLATION_FAILED",
            _extract_openai_error_message(error_body),
            "openai_responses",
        ) from exc
    except Exception as exc:
        raise PetitionAssistanceError(
            "OPENAI_TRANSLATION_FAILED",
            str(exc),
            "openai_responses",
        ) from exc

    translated = str(_extract_openai_output_text(response_payload) or "").strip()
    if not translated:
        raise PetitionAssistanceError(
            "OPENAI_TRANSLATION_EMPTY",
            "OpenAI translation returned no translated packet text.",
            "openai_responses.output_text",
        )
    return translated


@app.post("/api/rewrite-requests")
async def create_rewrite_request(
    payload: RewriteRequestCreate,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    parse_record_id = _validated_uuid(payload.parse_record_id, "parse_record_id")
    engine = await get_engine()
    async with engine.begin() as conn:
        record = await _resolve_rewrite_parse_record(conn, parse_record_id)
        if record is None:
            raise _rewrite_error(
                404,
                "PARSE_RECORD_NOT_FOUND",
                "Parse record or parsed case document not found.",
                "parse_record_id",
            )
        parse_record_id = str(record.get("id"))

        active = await _fetch_one_mapping(
            conn,
            sa.select(
                petition_rewrite_requests.c.id,
                petition_rewrite_requests.c.generation_status,
            )
            .where(
                petition_rewrite_requests.c.parse_record_id == parse_record_id,
                petition_rewrite_requests.c.is_deleted == sa.false(),
                petition_rewrite_requests.c.generation_status.notin_(sorted(FINAL_OR_REPLACED_STATUSES)),
            )
            .limit(1),
        )
        if active is not None:
            raise _rewrite_error(
                409,
                "ACTIVE_REQUEST_EXISTS",
                "An active assistance packet already exists for this parse record.",
                "parse_record_id",
                {
                    "active_request_id": active.get("id"),
                    "generation_status": active.get("generation_status"),
                },
            )

        parsed_output = record.get("parsed_output")
        if not isinstance(parsed_output, dict):
            raise _rewrite_error(
                422,
                "INVALID_PARSED_OUTPUT",
                "Parse record output is not available in the expected structure.",
                "parsed_output",
            )
        checklist_questions = await _fetch_all_mappings(
            conn,
            sa.select(*petition_checklist_questions.c)
            .where(petition_checklist_questions.c.is_active == sa.true())
            .order_by(
                petition_checklist_questions.c.checklist_version.desc(),
                petition_checklist_questions.c.display_order.asc(),
                petition_checklist_questions.c.category.asc(),
            ),
        )
        checklist_evaluations = evaluate_checklist_questions(
            parsed_output,
            checklist_questions,
            purpose="petition",
        )
        try:
            packet = build_assistance_packet(
                parse_record_id=parse_record_id,
                parsed_output=parsed_output,
                file_name=record.get("file_name"),
                case_id=payload.case_id or record.get("case_id"),
                created_by=current_user,
                checklist_evaluations=checklist_evaluations,
            )
        except PetitionAssistanceError as exc:
            raise _rewrite_error(422, exc.code, exc.message, exc.field) from exc

        request_values = _table_values(petition_rewrite_requests, packet["request"])
        request_values["created_by"] = current_user
        source_language = str(request_values.get("source_language") or "").lower()
        request_values["semantic_validation_status"] = "not_required" if source_language in {"en", "english"} else "pending"
        await conn.execute(petition_rewrite_requests.insert().values(**request_values))

        rewrite_request_id = packet["request"]["id"]
        draft_id = packet["draft"]["id"]
        placeholder_rows = [
            _table_values(
                petition_placeholders,
                {
                    **placeholder,
                    "rewrite_request_id": rewrite_request_id,
                },
            )
            for placeholder in packet["placeholders"]
        ]
        if placeholder_rows:
            await conn.execute(petition_placeholders.insert().values(placeholder_rows))

        draft_values = _table_values(
            generated_petition_drafts,
            {
                **packet["draft"],
                "created_by": current_user,
            },
        )
        await conn.execute(generated_petition_drafts.insert().values(**draft_values))

        lineage_rows = [
            _table_values(
                source_lineage_maps,
                {
                    **lineage,
                    "rewrite_request_id": rewrite_request_id,
                    "generated_petition_draft_id": draft_id,
                },
            )
            for lineage in packet["lineage"]
        ]
        if lineage_rows:
            await conn.execute(source_lineage_maps.insert().values(lineage_rows))

        checklist_rows = [
            _table_values(
                petition_checklist_evaluations,
                {
                    "id": str(uuid.uuid4()),
                    "rewrite_request_id": rewrite_request_id,
                    "question_id": item.get("id") or item.get("question_id"),
                    "checklist_version": item.get("checklist_version") or packet["request"].get("checklist_version") or 1,
                    "evaluation_status": item.get("evaluation_status") or "not_applicable",
                    "evidence_excerpt": item.get("evidence_excerpt"),
                    "question_text": item.get("question_text"),
                    "category": item.get("category"),
                    "purpose": item.get("purpose"),
                    "severity": item.get("severity"),
                    "missing_detail": item.get("missing_detail"),
                    "follow_up_action": item.get("follow_up_action"),
                    "guidance": item.get("guidance"),
                    "evaluation_reason": item.get("evaluation_reason"),
                    "created_by": current_user,
                },
            )
            for item in checklist_evaluations
            if item.get("id") or item.get("question_id")
        ]
        if checklist_rows:
            await conn.execute(petition_checklist_evaluations.insert().values(checklist_rows))

        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="generated",
            event_summary="Generated deterministic missing-information assistance packet.",
            after_hash=packet["draft"]["sha256_hash"],
            metadata={
                "parse_record_id": parse_record_id,
                "basis_text_type": packet["request"]["basis_text_type"],
                "warnings": packet["request"].get("warnings", []),
                "checklist_question_count": len(checklist_evaluations),
            },
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="source_lineage_checked",
            event_summary="Completed deterministic source-lineage validation.",
            after_hash=packet["draft"]["sha256_hash"],
            metadata=packet["validation"],
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)

    return JSONResponse(status_code=201, content=detail)


@app.get("/api/rewrite-requests/{rewrite_request_id}")
async def get_rewrite_request(
    rewrite_request_id: str,
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    engine = await get_engine()
    async with engine.connect() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    if detail is None:
        raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
    return JSONResponse(content=detail)


@app.patch("/api/rewrite-requests/{rewrite_request_id}/drafts/{draft_id}")
async def update_rewrite_draft(
    rewrite_request_id: str,
    draft_id: str,
    payload: RewriteDraftUpdate,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    draft_id = _validated_uuid(draft_id, "draft_id")
    body_markdown = payload.body_markdown.strip()
    if not body_markdown:
        raise _rewrite_error(400, "EMPTY_DRAFT", "Draft body is required.", "body_markdown")

    engine = await get_engine()
    async with engine.begin() as conn:
        request_row = await _fetch_one_mapping(
            conn,
            sa.select(*petition_rewrite_requests.c).where(
                petition_rewrite_requests.c.id == rewrite_request_id,
                petition_rewrite_requests.c.is_deleted == sa.false(),
            ),
        )
        if request_row is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        if request_row.get("generation_status") in {"approved", "printed", "shared", *FINAL_OR_REPLACED_STATUSES}:
            raise _rewrite_error(409, "DRAFT_LOCKED", "Approved, exported, or final packets cannot be edited.")

        current_draft = await _fetch_one_mapping(
            conn,
            sa.select(*generated_petition_drafts.c).where(
                generated_petition_drafts.c.id == draft_id,
                generated_petition_drafts.c.rewrite_request_id == rewrite_request_id,
            ),
        )
        if current_draft is None:
            raise _rewrite_error(404, "DRAFT_NOT_FOUND", "Draft not found.", "draft_id")

        placeholders = await _fetch_all_mappings(
            conn,
            sa.select(*petition_placeholders.c)
            .where(petition_placeholders.c.rewrite_request_id == rewrite_request_id)
            .order_by(petition_placeholders.c.display_order.asc()),
        )
        validation = _draft_validation_from_edit(
            body_markdown=body_markdown,
            current_draft=current_draft,
            placeholders=placeholders,
        )
        version_result = await conn.execute(
            sa.select(sa.func.coalesce(sa.func.max(generated_petition_drafts.c.draft_version), 0) + 1).where(
                generated_petition_drafts.c.rewrite_request_id == rewrite_request_id
            )
        )
        next_version = int(version_result.scalar() or 1)
        new_draft_id = str(uuid.uuid4())
        await conn.execute(
            generated_petition_drafts.insert().values(
                id=new_draft_id,
                rewrite_request_id=rewrite_request_id,
                draft_language=current_draft.get("draft_language") or "en",
                draft_version=next_version,
                title=current_draft.get("title") or "Missing Information Assistance Packet",
                body_markdown=body_markdown,
                body_plain_text=validation["body_plain_text"],
                placeholder_count=len(placeholders),
                mandatory_placeholder_count=sum(1 for item in placeholders if item.get("severity") == "mandatory"),
                generation_method="officer_edit",
                quality_status=validation["quality_status"],
                quality_notes=validation["quality_notes"],
                source_lineage_complete=validation["source_lineage_complete"],
                unsupported_fact_count=validation["unsupported_fact_count"],
                contradiction_count=0,
                sha256_hash=validation["sha256_hash"],
                created_by=current_draft.get("created_by") or current_user,
                updated_by=current_user,
            )
        )
        await conn.execute(
            petition_rewrite_requests.update()
            .where(petition_rewrite_requests.c.id == rewrite_request_id)
            .values(
                generation_status="needs_review" if validation["source_lineage_complete"] else "source_check_required",
                source_lineage_status=validation["source_lineage_status"],
                unsupported_fact_count=validation["unsupported_fact_count"],
                reviewed_by=current_user,
                updated_at=sa.func.now(),
            )
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="edited",
            event_summary=f"Saved officer draft edit as version {next_version}.",
            before_hash=current_draft.get("sha256_hash"),
            after_hash=validation["sha256_hash"],
            metadata={
                "draft_id": new_draft_id,
                "previous_draft_id": draft_id,
                "update_note": (payload.update_note or "").strip(),
                "missing_placeholder_tokens": validation["missing_placeholder_tokens"],
                "source_lineage_status": validation["source_lineage_status"],
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.post("/api/rewrite-requests/{rewrite_request_id}/approve")
async def approve_rewrite_request(
    rewrite_request_id: str,
    payload: RewriteApprovalRequest,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    approval_note = payload.approval_note.strip()
    if len(approval_note) < 10:
        raise _rewrite_error(400, "APPROVAL_NOTE_REQUIRED", "Approval note must be at least 10 characters.", "approval_note")
    if not payload.lineage_review_confirmed:
        raise _rewrite_error(
            409,
            "LINEAGE_REVIEW_REQUIRED",
            "Source-lineage review confirmation is required before approval.",
            "lineage_review_confirmed",
        )

    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        latest_draft = detail.get("draft")
        if not latest_draft:
            raise _rewrite_error(409, "DRAFT_NOT_FOUND", "No draft is available for approval.")
        validation = detail.get("validation") or {}
        if not validation.get("placeholder_integrity_passed"):
            raise _rewrite_error(
                409,
                "PLACEHOLDER_INTEGRITY_FAILED",
                "Protected placeholder tokens are missing from the latest draft.",
            )
        if not latest_draft.get("source_lineage_complete"):
            raise _rewrite_error(
                409,
                "SOURCE_LINEAGE_INCOMPLETE",
                "Source lineage is incomplete for the latest draft.",
            )
        if int(latest_draft.get("unsupported_fact_count") or 0) > 0:
            raise _rewrite_error(
                409,
                "UNSUPPORTED_FACT_DETECTED",
                "Unsupported facts must be resolved before approval.",
            )
        if int(latest_draft.get("contradiction_count") or 0) > 0:
            raise _rewrite_error(
                409,
                "CONTRADICTION_DETECTED",
                "Contradiction warnings must be resolved before approval.",
            )
        request_row = detail["request"]
        source_language = str(request_row.get("source_language") or "").lower()
        semantic_status = str(request_row.get("semantic_validation_status") or "not_required")
        semantic_override = False
        if source_language not in {"", "en", "english", "unknown"} and semantic_status not in {"passed", "override"}:
            if not payload.allow_english_only_issue:
                raise _rewrite_error(
                    409,
                    "SEMANTIC_VALIDATION_REQUIRED",
                    "Original-language semantic validation must pass, or an override must be recorded, before approval.",
                    "allow_english_only_issue",
                )
            semantic_override = True

        await conn.execute(
            petition_rewrite_requests.update()
            .where(petition_rewrite_requests.c.id == rewrite_request_id)
            .values(
                generation_status="approved",
                semantic_validation_status="override" if semantic_override else semantic_status,
                reviewed_by=current_user,
                approved_by=current_user,
                updated_at=sa.func.now(),
                approved_at=sa.func.now(),
            )
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="approved",
            event_summary="Approved assistance packet for export.",
            after_hash=latest_draft.get("sha256_hash"),
            metadata={
                "approval_note": approval_note,
                "allow_english_only_issue": payload.allow_english_only_issue,
                "lineage_review_confirmed": payload.lineage_review_confirmed,
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.post("/api/rewrite-requests/{rewrite_request_id}/export")
async def export_rewrite_request(
    rewrite_request_id: str,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        request_row = detail["request"]
        latest_draft = detail.get("draft")
        if not latest_draft:
            raise _rewrite_error(409, "DRAFT_NOT_FOUND", "No draft is available for export.")
        if request_row.get("generation_status") not in {"approved", "printed", "shared"}:
            raise _rewrite_error(
                409,
                "PACKET_NOT_APPROVED",
                "Only approved packets can be exported.",
            )

        if request_row.get("generation_status") != "shared":
            await conn.execute(
                petition_rewrite_requests.update()
                .where(petition_rewrite_requests.c.id == rewrite_request_id)
                .values(generation_status="printed", updated_at=sa.func.now())
            )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="exported",
            event_summary="Exported approved assistance packet.",
            after_hash=latest_draft.get("sha256_hash"),
            metadata={"draft_id": latest_draft.get("id"), "export_format": "markdown"},
        )

    return JSONResponse(
        content={
            "rewrite_request_id": rewrite_request_id,
            "draft_id": latest_draft.get("id"),
            "file_name": f"petition-assistance-{rewrite_request_id[:8]}.md",
            "content_type": "text/markdown; charset=utf-8",
            "sha256_hash": latest_draft.get("sha256_hash"),
            "content": latest_draft.get("body_markdown") or latest_draft.get("body_plain_text") or "",
        }
    )


@app.post("/api/rewrite-requests/{rewrite_request_id}/return-values")
async def save_rewrite_return_values(
    rewrite_request_id: str,
    payload: RewriteReturnValuesRequest,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    if not payload.values:
        raise _rewrite_error(400, "RETURN_VALUES_REQUIRED", "At least one placeholder value is required.", "values")

    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        placeholders = detail.get("placeholders") or []
        placeholders_by_id = {str(item.get("id")): item for item in placeholders}
        updated_rows: list[dict[str, Any]] = []
        for item in payload.values:
            placeholder_id = _validated_uuid(item.placeholder_id, "placeholder_id")
            if placeholder_id not in placeholders_by_id:
                raise _rewrite_error(404, "PLACEHOLDER_NOT_FOUND", "Placeholder not found.", "placeholder_id")
            value_status = item.value_status.strip().lower()
            if value_status not in PLACEHOLDER_VALUE_STATUSES:
                raise _rewrite_error(
                    400,
                    "UNSUPPORTED_VALUE_STATUS",
                    "Placeholder value status is not supported.",
                    "value_status",
                )
            petitioner_value = (item.petitioner_value or "").strip()
            if value_status == "accepted" and not petitioner_value:
                raise _rewrite_error(400, "PLACEHOLDER_VALUE_REQUIRED", "Accepted values cannot be blank.", "petitioner_value")
            await conn.execute(
                petition_placeholders.update()
                .where(
                    petition_placeholders.c.id == placeholder_id,
                    petition_placeholders.c.rewrite_request_id == rewrite_request_id,
                )
                .values(
                    petitioner_value=petitioner_value or None,
                    value_status=value_status,
                    updated_at=sa.func.now(),
                )
            )
            updated_rows.append(
                {
                    "placeholder_id": placeholder_id,
                    "value_status": value_status,
                    "has_value": bool(petitioner_value),
                }
            )

        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="return_values_saved",
            event_summary="Saved petitioner-returned placeholder values.",
            metadata={
                "updated": updated_rows,
                "update_note": (payload.update_note or "").strip(),
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.post("/api/rewrite-requests/{rewrite_request_id}/translations")
async def create_rewrite_translation(
    rewrite_request_id: str,
    payload: RewriteTranslationRequest,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        latest_draft = detail.get("draft")
        if not latest_draft:
            raise _rewrite_error(409, "DRAFT_NOT_FOUND", "No draft is available for translation.")
        request_row = detail["request"]
        target_language = payload.target_language or request_row.get("source_language") or "unknown"
        target_language_name = payload.target_language_name or request_row.get("source_language_name") or target_language
        config = get_translation_config()
        translator = None
        translation_error: dict[str, str | None] | None = None
        if _openai_petition_translation_available(config):
            translator = lambda protected_text, language: _translate_petition_packet_via_openai(
                protected_text,
                language,
                target_language_name,
            )
        try:
            translation_payload = build_draft_translation_payload(
                rewrite_request_id=rewrite_request_id,
                draft_id=latest_draft.get("id"),
                body_markdown=latest_draft.get("body_markdown") or latest_draft.get("body_plain_text") or "",
                target_language=target_language,
                target_language_name=target_language_name,
                translator=translator,
            )
        except PetitionAssistanceError as exc:
            raise _rewrite_error(503, exc.code, exc.message, exc.field) from exc
        if translator is None:
            translation_payload["semantic_validation_notes"] = [
                "OpenAI petition packet translation is not configured; stored English-only draft."
            ]
            translation_payload["english_only_reason"] = "OpenAI petition packet translation is not configured."
        elif translation_payload["semantic_validation_status"] == "placeholder_failed":
            translation_error = {
                "code": "PLACEHOLDER_INTEGRITY_FAILED",
                "message": "OpenAI translated the packet but did not preserve all protected placeholder tokens.",
            }
        await conn.execute(
            petition_draft_translations.insert().values(
                **_table_values(
                    petition_draft_translations,
                    {
                        **translation_payload,
                        "created_by": current_user,
                    },
                )
            )
        )
        request_semantic_status = translation_payload["semantic_validation_status"]
        await conn.execute(
            petition_rewrite_requests.update()
            .where(petition_rewrite_requests.c.id == rewrite_request_id)
            .values(
                semantic_validation_status=request_semantic_status,
                updated_at=sa.func.now(),
            )
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="translation_generated",
            event_summary=f"Generated {target_language_name} assistance packet translation record.",
            after_hash=translation_payload["sha256_hash"],
            metadata={
                "translation_id": translation_payload["id"],
                "provider": "openai_responses" if translator is not None else "english_only",
                "model": config.get("openai_model") if translator is not None else None,
                "semantic_validation_status": request_semantic_status,
                "placeholder_validation": translation_payload["validation"],
                "translation_error": translation_error,
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(status_code=201, content=detail)


@app.post("/api/rewrite-requests/{rewrite_request_id}/translations/{translation_id}/semantic-validation")
async def save_rewrite_translation_semantic_validation(
    rewrite_request_id: str,
    translation_id: str,
    payload: RewriteSemanticValidationRequest,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    translation_id = _validated_uuid(translation_id, "translation_id")
    status = payload.semantic_validation_status.strip().lower()
    if status not in {"passed", "failed", "override"}:
        raise _rewrite_error(400, "UNSUPPORTED_SEMANTIC_STATUS", "Unsupported semantic validation status.", "semantic_validation_status")
    if status == "override" and not (payload.sho_override_reason or "").strip():
        raise _rewrite_error(400, "OVERRIDE_REASON_REQUIRED", "Override reason is required.", "sho_override_reason")
    engine = await get_engine()
    async with engine.begin() as conn:
        translation = await _fetch_one_mapping(
            conn,
            sa.select(*petition_draft_translations.c).where(
                petition_draft_translations.c.id == translation_id,
                petition_draft_translations.c.rewrite_request_id == rewrite_request_id,
            ),
        )
        if translation is None:
            raise _rewrite_error(404, "TRANSLATION_NOT_FOUND", "Translation record not found.", "translation_id")
        notes = []
        if payload.reviewer_note:
            notes.append(payload.reviewer_note.strip())
        await conn.execute(
            petition_draft_translations.update()
            .where(petition_draft_translations.c.id == translation_id)
            .values(
                semantic_validation_status=status,
                semantic_validation_notes=notes,
                sho_override_reason=(payload.sho_override_reason or "").strip() or None,
                reviewed_by=current_user,
                updated_at=sa.func.now(),
            )
        )
        await conn.execute(
            petition_rewrite_requests.update()
            .where(petition_rewrite_requests.c.id == rewrite_request_id)
            .values(semantic_validation_status=status, reviewed_by=current_user, updated_at=sa.func.now())
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="semantic_validation_saved",
            event_summary=f"Recorded semantic validation status: {status}.",
            metadata={
                "translation_id": translation_id,
                "semantic_validation_status": status,
                "sho_override_reason": (payload.sho_override_reason or "").strip(),
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.post("/api/rewrite-requests/{rewrite_request_id}/petitioner-verification")
async def save_petitioner_verification(
    rewrite_request_id: str,
    payload: PetitionerVerificationRequest,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    consent_status = payload.consent_status.strip().lower()
    if consent_status not in {"verified", "refused", "correction_requested"}:
        raise _rewrite_error(400, "UNSUPPORTED_CONSENT_STATUS", "Unsupported petitioner consent status.", "consent_status")
    if consent_status == "verified":
        if not (payload.petitioner_name or "").strip():
            raise _rewrite_error(400, "PETITIONER_NAME_REQUIRED", "Petitioner name is required for verification.", "petitioner_name")
        if not (payload.signature_mode or "").strip():
            raise _rewrite_error(400, "SIGNATURE_MODE_REQUIRED", "Signature mode is required for verification.", "signature_mode")
    if consent_status == "correction_requested" and not (payload.correction_note or "").strip():
        raise _rewrite_error(400, "CORRECTION_NOTE_REQUIRED", "Correction note is required.", "correction_note")

    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        request_row = detail["request"]
        if request_row.get("generation_status") not in {"approved", "printed", "shared"}:
            raise _rewrite_error(
                409,
                "PACKET_NOT_APPROVED",
                "Petitioner verification can be recorded only after packet approval.",
            )
        latest_draft = detail.get("draft")
        if not latest_draft:
            raise _rewrite_error(409, "DRAFT_NOT_FOUND", "No draft is available for petitioner verification.")

        petitioner_packet_id = str(uuid.uuid4())
        packet_body = latest_draft.get("body_markdown") or latest_draft.get("body_plain_text") or ""
        await conn.execute(
            petitioner_packets.insert().values(
                id=petitioner_packet_id,
                rewrite_request_id=rewrite_request_id,
                generated_petition_draft_id=latest_draft.get("id"),
                presentation_language=payload.verification_language or "en",
                packet_body_markdown=packet_body,
                packet_hash=sha256_text(packet_body),
                delivery_mode="in_person",
                delivery_status="presented" if consent_status != "refused" else "refused",
                presented_at=sa.func.now(),
                created_by=current_user,
            )
        )
        verification_id = str(uuid.uuid4())
        await conn.execute(
            petitioner_verification_records.insert().values(
                id=verification_id,
                rewrite_request_id=rewrite_request_id,
                petitioner_packet_id=petitioner_packet_id,
                consent_status=consent_status,
                petitioner_name=(payload.petitioner_name or "").strip() or None,
                verification_language=(payload.verification_language or "").strip() or None,
                signature_mode=(payload.signature_mode or "").strip() or None,
                witness_note=(payload.witness_note or "").strip() or None,
                signed_packet_uri=(payload.signed_packet_uri or "").strip() or None,
                copy_provided_at=payload.copy_provided_at or (datetime.now(timezone.utc) if consent_status == "verified" else None),
                correction_note=(payload.correction_note or "").strip() or None,
                verified_by=current_user,
            )
        )
        await conn.execute(
            petition_rewrite_requests.update()
            .where(petition_rewrite_requests.c.id == rewrite_request_id)
            .values(
                petitioner_consent_status=consent_status,
                reviewed_by=current_user,
                updated_at=sa.func.now(),
            )
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="petitioner_verification_saved",
            event_summary=f"Recorded petitioner verification status: {consent_status}.",
            metadata={
                "verification_id": verification_id,
                "petitioner_packet_id": petitioner_packet_id,
                "consent_status": consent_status,
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.get("/api/rewrite-checklist/questions")
async def list_rewrite_checklist_questions(
    purpose: Optional[str] = None,
    include_inactive: bool = False,
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    engine = await get_engine()
    async with engine.connect() as conn:
        query = sa.select(*petition_checklist_questions.c)
        if not include_inactive:
            query = query.where(petition_checklist_questions.c.is_active == sa.true())
        if purpose:
            query = query.where(petition_checklist_questions.c.purpose == purpose.strip().lower())
        rows = await _fetch_all_mappings(
            conn,
            query.order_by(
                petition_checklist_questions.c.checklist_version.desc(),
                petition_checklist_questions.c.display_order.asc(),
                petition_checklist_questions.c.category.asc(),
            ),
        )
    return JSONResponse(content={"items": rows})


@app.post("/api/rewrite-checklist/questions")
async def create_rewrite_checklist_question(
    payload: ChecklistQuestionCreate,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    if not payload.category.strip() or not payload.question_text.strip():
        raise _rewrite_error(400, "CHECKLIST_QUESTION_REQUIRED", "Category and question text are required.")
    severity = payload.severity.strip().lower() or "recommended"
    if severity not in {"mandatory", "recommended", "optional"}:
        raise _rewrite_error(400, "UNSUPPORTED_CHECKLIST_SEVERITY", "Severity must be mandatory, recommended, or optional.", "severity")
    question_id = str(uuid.uuid4())
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            petition_checklist_questions.insert().values(
                id=question_id,
                checklist_version=payload.checklist_version,
                category=payload.category.strip().lower(),
                purpose=payload.purpose.strip().lower() or "petition",
                offence_type=(payload.offence_type or "").strip().lower() or None,
                question_text=payload.question_text.strip(),
                expected_field_key=(payload.expected_field_key or "").strip() or None,
                severity=severity,
                source_section=(payload.source_section or "").strip() or None,
                guidance=(payload.guidance or "").strip() or None,
                display_order=max(0, int(payload.display_order or 0)),
                is_active=payload.is_active,
                created_by=current_user,
            )
        )
        row = await _fetch_one_mapping(
            conn,
            sa.select(*petition_checklist_questions.c).where(petition_checklist_questions.c.id == question_id),
        )
    return JSONResponse(status_code=201, content=row)


@app.patch("/api/rewrite-checklist/questions/{question_id}")
async def update_rewrite_checklist_question(
    question_id: str,
    payload: ChecklistQuestionUpdate,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    question_id = _validated_uuid(question_id, "question_id")
    values: dict[str, Any] = {"updated_by": current_user, "updated_at": sa.func.now()}
    if payload.checklist_version is not None:
        values["checklist_version"] = max(1, int(payload.checklist_version))
    if payload.category is not None:
        if not payload.category.strip():
            raise _rewrite_error(400, "CHECKLIST_CATEGORY_REQUIRED", "Category is required.", "category")
        values["category"] = payload.category.strip().lower()
    if payload.purpose is not None:
        values["purpose"] = payload.purpose.strip().lower() or "petition"
    if payload.offence_type is not None:
        values["offence_type"] = payload.offence_type.strip().lower() or None
    if payload.question_text is not None:
        if not payload.question_text.strip():
            raise _rewrite_error(400, "CHECKLIST_QUESTION_REQUIRED", "Question text is required.", "question_text")
        values["question_text"] = payload.question_text.strip()
    if payload.expected_field_key is not None:
        values["expected_field_key"] = payload.expected_field_key.strip() or None
    if payload.severity is not None:
        severity = payload.severity.strip().lower() or "recommended"
        if severity not in {"mandatory", "recommended", "optional"}:
            raise _rewrite_error(400, "UNSUPPORTED_CHECKLIST_SEVERITY", "Severity must be mandatory, recommended, or optional.", "severity")
        values["severity"] = severity
    if payload.source_section is not None:
        values["source_section"] = payload.source_section.strip() or None
    if payload.guidance is not None:
        values["guidance"] = payload.guidance.strip() or None
    if payload.display_order is not None:
        values["display_order"] = max(0, int(payload.display_order))
    if payload.is_active is not None:
        values["is_active"] = bool(payload.is_active)

    engine = await get_engine()
    async with engine.begin() as conn:
        existing = await _fetch_one_mapping(
            conn,
            sa.select(petition_checklist_questions.c.id).where(petition_checklist_questions.c.id == question_id),
        )
        if existing is None:
            raise _rewrite_error(404, "CHECKLIST_QUESTION_NOT_FOUND", "Checklist question not found.", "question_id")
        await conn.execute(
            petition_checklist_questions.update()
            .where(petition_checklist_questions.c.id == question_id)
            .values(**values)
        )
        row = await _fetch_one_mapping(
            conn,
            sa.select(*petition_checklist_questions.c).where(petition_checklist_questions.c.id == question_id),
        )
    return JSONResponse(content=row)


@app.post("/api/rewrite-requests/{rewrite_request_id}/checklist-evaluations")
async def evaluate_rewrite_checklist(
    rewrite_request_id: str,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        latest_draft = detail.get("draft")
        if not latest_draft:
            raise _rewrite_error(409, "DRAFT_NOT_FOUND", "No draft is available for checklist evaluation.")
        request_row = detail["request"]
        parse_record_id = request_row.get("parse_record_id")
        record = await _fetch_one_mapping(
            conn,
            sa.select(parse_records.c.parsed_output).where(parse_records.c.id == parse_record_id),
        )
        parsed_output = record.get("parsed_output") if record else None
        if not isinstance(parsed_output, dict):
            raise _rewrite_error(422, "INVALID_PARSED_OUTPUT", "Parse record output is unavailable.", "parsed_output")
        questions = await _fetch_all_mappings(
            conn,
            sa.select(*petition_checklist_questions.c)
            .where(petition_checklist_questions.c.is_active == sa.true())
            .order_by(
                petition_checklist_questions.c.checklist_version.desc(),
                petition_checklist_questions.c.display_order.asc(),
            ),
        )
        evaluations = evaluate_checklist_questions(parsed_output, questions, purpose="petition")
        await conn.execute(
            petition_checklist_evaluations.delete().where(
                petition_checklist_evaluations.c.rewrite_request_id == rewrite_request_id
            )
        )
        rows = [
            _table_values(
                petition_checklist_evaluations,
                {
                    "id": str(uuid.uuid4()),
                    "rewrite_request_id": rewrite_request_id,
                    "question_id": item.get("id") or item.get("question_id"),
                    "checklist_version": item.get("checklist_version") or 1,
                    "evaluation_status": item.get("evaluation_status") or "not_applicable",
                    "evidence_excerpt": item.get("evidence_excerpt"),
                    "question_text": item.get("question_text"),
                    "category": item.get("category"),
                    "purpose": item.get("purpose"),
                    "severity": item.get("severity"),
                    "missing_detail": item.get("missing_detail"),
                    "follow_up_action": item.get("follow_up_action"),
                    "guidance": item.get("guidance"),
                    "evaluation_reason": item.get("evaluation_reason"),
                    "created_by": current_user,
                },
            )
            for item in evaluations
            if item.get("id") or item.get("question_id")
        ]
        if rows:
            await conn.execute(petition_checklist_evaluations.insert().values(rows))
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="checklist_evaluated",
            event_summary="Evaluated assistance packet against active checklist questions.",
            metadata={"question_count": len(rows)},
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.post("/api/rewrite-requests/{rewrite_request_id}/pilot-evaluation")
async def create_rewrite_pilot_evaluation(
    rewrite_request_id: str,
    payload: PilotEvaluationCreate,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        await conn.execute(
            petition_pilot_evaluations.insert().values(
                id=str(uuid.uuid4()),
                rewrite_request_id=rewrite_request_id,
                semantic_drift_flag=payload.semantic_drift_flag,
                unsupported_fact_count=max(0, payload.unsupported_fact_count),
                petitioner_comprehension_status=payload.petitioner_comprehension_status,
                refusal_or_correction=payload.refusal_or_correction,
                officer_override_used=payload.officer_override_used,
                quality_notes=payload.quality_notes,
                created_by=current_user,
            )
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(status_code=201, content=detail)


@app.get("/api/rewrite-pilot/report")
async def get_rewrite_pilot_report(
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    engine = await get_engine()
    async with engine.connect() as conn:
        rows = await _fetch_all_mappings(
            conn,
            sa.select(*petition_pilot_evaluations.c).order_by(petition_pilot_evaluations.c.created_at.desc()).limit(500),
        )
    return JSONResponse(content=summarize_pilot_metrics(rows))


@app.post("/api/rewrite-requests/{rewrite_request_id}/accept")
async def accept_rewrite_request(
    rewrite_request_id: str,
    payload: RewriteAcceptRequest,
    request: Request,
    current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    _check_rate_limit(_get_client_ip(request))
    rewrite_request_id = _validated_uuid(rewrite_request_id, "rewrite_request_id")
    acceptance_note = payload.acceptance_note.strip()
    if len(acceptance_note) < 10:
        raise _rewrite_error(400, "ACCEPTANCE_NOTE_REQUIRED", "Acceptance note must be at least 10 characters.", "acceptance_note")

    engine = await get_engine()
    async with engine.begin() as conn:
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
        if detail is None:
            raise _rewrite_error(404, "REWRITE_REQUEST_NOT_FOUND", "Rewrite request not found.", "rewrite_request_id")
        request_row = detail["request"]
        if request_row.get("generation_status") not in {"approved", "printed", "shared"}:
            raise _rewrite_error(409, "PACKET_NOT_APPROVED", "Only approved packets can be accepted.")
        verification = detail.get("latest_verification")
        if not verification or verification.get("consent_status") != "verified":
            raise _rewrite_error(
                409,
                "PETITIONER_VERIFICATION_REQUIRED",
                "Final acceptance requires petitioner verification metadata.",
            )
        latest_draft = detail.get("draft")
        if not latest_draft:
            raise _rewrite_error(409, "DRAFT_NOT_FOUND", "No draft is available for final acceptance.")
        placeholders = detail.get("placeholders") or []
        blocking = [
            item for item in placeholders
            if item.get("token") in (latest_draft.get("body_markdown") or "")
            and item.get("value_status") not in FINAL_ACCEPTABLE_VALUE_STATUSES
        ]
        if blocking:
            raise _rewrite_error(
                409,
                "PLACEHOLDER_VALUES_INCOMPLETE",
                "All remaining placeholders must be accepted, accepted as unknown, or marked for follow-up.",
                metadata={"placeholder_ids": [item.get("id") for item in blocking]},
            )

        merged = merge_final_petition_text(
            body_markdown=latest_draft.get("body_markdown") or latest_draft.get("body_plain_text") or "",
            placeholders=placeholders,
        )
        if merged["unresolved"]:
            raise _rewrite_error(
                409,
                "PLACEHOLDER_VALUES_INCOMPLETE",
                "One or more placeholders are not finalized.",
                metadata={"unresolved": merged["unresolved"]},
            )
        version_result = await conn.execute(
            sa.select(sa.func.coalesce(sa.func.max(generated_petition_drafts.c.draft_version), 0) + 1).where(
                generated_petition_drafts.c.rewrite_request_id == rewrite_request_id
            )
        )
        next_version = int(version_result.scalar() or 1)
        final_draft_id = str(uuid.uuid4())
        await conn.execute(
            generated_petition_drafts.insert().values(
                id=final_draft_id,
                rewrite_request_id=rewrite_request_id,
                draft_language="en",
                draft_version=next_version,
                title="Accepted Missing Information Assistance Packet",
                body_markdown=merged["body_markdown"],
                body_plain_text=merged["body_plain_text"],
                placeholder_count=len(placeholders),
                mandatory_placeholder_count=sum(1 for item in placeholders if item.get("severity") == "mandatory"),
                generation_method="petitioner_return_merge",
                quality_status="accepted",
                quality_notes=["Final text merged from petitioner-reviewed placeholder values."],
                source_lineage_complete=bool(latest_draft.get("source_lineage_complete")),
                unsupported_fact_count=0,
                contradiction_count=0,
                sha256_hash=merged["sha256_hash"],
                created_by=current_user,
            )
        )
        lineage_rows = [
            _table_values(
                source_lineage_maps,
                {
                    "id": str(uuid.uuid4()),
                    "rewrite_request_id": rewrite_request_id,
                    "generated_petition_draft_id": final_draft_id,
                    "output_span_id": f"petitioner-value-{index:03d}",
                    "output_text": replacement["replacement"],
                    "source_type": "petitioner_return_value",
                    "source_reference_id": replacement["placeholder_id"],
                    "source_excerpt": replacement["token"],
                    "source_char_start": None,
                    "source_char_end": None,
                    "lineage_confidence": 1.0,
                    "reviewer_status": "accepted",
                },
            )
            for index, replacement in enumerate(merged["replacements"], start=1)
        ]
        if lineage_rows:
            await conn.execute(source_lineage_maps.insert().values(lineage_rows))
        await conn.execute(
            petition_rewrite_requests.update()
            .where(petition_rewrite_requests.c.id == rewrite_request_id)
            .values(
                generation_status="accepted",
                petitioner_consent_status="verified",
                reviewed_by=current_user,
                approved_by=current_user,
                updated_at=sa.func.now(),
            )
        )
        await _insert_rewrite_audit_event(
            conn,
            rewrite_request_id=rewrite_request_id,
            actor_id=current_user,
            action_type="accepted",
            event_summary="Accepted final petitioner-verified assistance packet.",
            before_hash=latest_draft.get("sha256_hash"),
            after_hash=merged["sha256_hash"],
            metadata={
                "acceptance_note": acceptance_note,
                "verification_id": verification.get("id"),
                "replacement_count": len(merged["replacements"]),
            },
        )
        detail = await _get_rewrite_detail(conn, rewrite_request_id)
    return JSONResponse(content=detail)


@app.get("/api/history")
async def list_history(
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    """Return all parse records (metadata + gaps only, no blobs or full JSON)."""
    engine = await get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            sa.select(
                parse_records.c.id,
                parse_records.c.file_name,
                parse_records.c.file_size,
                parse_records.c.document_format,
                parse_records.c.completeness_score,
                parse_records.c.parsed_output["gaps"].label("gaps"),
                parse_records.c.parsed_output["fir_draft"]["jurisdiction"]["police_station"].label("police_station"),
                parse_records.c.parsed_output["fir_draft"]["occurrence"]["nature_of_offence"].label("nature_of_offence"),
                parse_records.c.parsed_output["language"]["detected_name"].label("language"),
                parse_records.c.parsed_output["fir_draft"]["proposed_bns_sections"].label("bns_sections"),
                parse_records.c.parsed_output["fir_draft"]["occurrence"]["date"].label("occurrence_date"),
                parse_records.c.created_at,
                *kis_record_projection(),
            ).order_by(parse_records.c.created_at.desc())
        )
        records = [
            {
                "id": str(row.id),
                "file_name": row.file_name,
                "file_size": row.file_size,
                "document_format": row.document_format,
                "completeness_score": row.completeness_score,
                "gaps": row.gaps,
                "police_station": row.police_station,
                "nature_of_offence": row.nature_of_offence,
                "language": row.language,
                "bns_sections": row.bns_sections,
                "occurrence_date": row.occurrence_date,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                **kis_record_payload(row),
            }
            for row in rows
        ]
    return JSONResponse(content=records)


@app.get("/api/history/{record_id}")
async def get_history_record(
    record_id: str,
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    """Return a single record with full parsed_output (no blob)."""
    engine = await get_engine()
    async with engine.connect() as conn:
        row = await conn.execute(
            sa.select(
                parse_records.c.id,
                parse_records.c.file_name,
                parse_records.c.file_size,
                parse_records.c.document_format,
                parse_records.c.completeness_score,
                parse_records.c.parsed_output,
                parse_records.c.created_at,
                *kis_record_projection(),
            ).where(parse_records.c.id == record_id)
        )
        record = row.first()
        parsed_output = (
            await enrich_parsed_output_with_checklist(record.parsed_output, conn=conn)
            if record is not None
            else None
        )
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return JSONResponse(
        content={
            "id": str(record.id),
            "file_name": record.file_name,
            "file_size": record.file_size,
            "document_format": record.document_format,
            "completeness_score": record.completeness_score,
            "parsed_output": parsed_output,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            **kis_record_payload(record),
        }
    )


@app.get("/api/history/{record_id}/pdf")
@app.get("/api/history/{record_id}/file")
async def get_history_file(
    record_id: str,
    _current_user: str = Depends(_require_authenticated_session),
) -> StreamingResponse:
    """Stream the stored file bytes for a record."""
    engine = await get_engine()
    async with engine.connect() as conn:
        row = await conn.execute(
            sa.select(
                parse_records.c.file_bytes,
                parse_records.c.file_name,
                parse_records.c.file_storage_uri,
            ).where(
                parse_records.c.id == record_id
            )
        )
        record = row.first()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    file_name = record.file_name or "document"
    mime = _detect_mime_type(file_name, "") or "application/octet-stream"
    uri = getattr(record, "file_storage_uri", None)
    content = await get_object_bytes(uri) if isinstance(uri, str) and uri else record.file_bytes
    if content is None:
        raise HTTPException(status_code=404, detail="Stored file is not available.")
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


@app.delete("/api/history/{record_id}")
async def delete_history_record(
    request: Request,
    record_id: str,
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    """Delete a single parse record."""
    _check_rate_limit(_get_client_ip(request))
    engine = await get_engine()
    async with engine.begin() as conn:
        existing = await conn.execute(
            sa.select(parse_records.c.file_storage_uri).where(parse_records.c.id == record_id)
        )
        row = existing.first()
        result = await conn.execute(
            parse_records.delete().where(parse_records.c.id == record_id)
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Record not found.")
    uri = getattr(row, "file_storage_uri", None) if row else None
    if isinstance(uri, str) and uri:
        await delete_object(uri)
    return JSONResponse(content={"deleted": True})


@app.delete("/api/history")
async def clear_history(
    request: Request,
    _current_user: str = Depends(_require_authenticated_session),
) -> JSONResponse:
    """Delete all parse records."""
    _check_rate_limit(_get_client_ip(request))
    engine = await get_engine()
    async with engine.begin() as conn:
        existing = await conn.execute(sa.select(parse_records.c.file_storage_uri))
        storage_uris = []
        for row in existing:
            uri = getattr(row, "file_storage_uri", None)
            if isinstance(uri, str) and uri:
                storage_uris.append(uri)
        result = await conn.execute(parse_records.delete())
    for uri in storage_uris:
        await delete_object(uri)
    return JSONResponse(content={"deleted_count": result.rowcount})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(_get_env("PORT", "8080") or "8080"),
        reload=False,
    )
