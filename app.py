from __future__ import annotations

import asyncio
import io
import json as _json
import logging
import os
import queue
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from complaint_parsing import (
    get_translation_config,
    load_dotenv,
    parse_document,
    process_document_bytes,
)
from database import (
    dispose_engine,
    get_database_health,
    get_engine,
    initialize_database,
    parse_records,
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
    engine = await get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            parse_records.insert()
            .values(
                file_name=file_name,
                file_size=len(content),
                file_bytes=content,
                parsed_output=parsed_output,
                document_format=detected_format,
                completeness_score=_extract_completeness_score(parsed_output),
            )
            .returning(parse_records.c.id)
        )
        record_id = result.scalar()
    if record_id is None:
        raise RuntimeError("Database did not return a record id.")
    return str(record_id)


class LoginRequest(BaseModel):
    username: str
    password: str


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    get_doc_ai_config()
    try:
        await initialize_database()
    except Exception as exc:
        logger.warning("Database initialisation failed (history disabled): %s", exc)
    yield
    await dispose_engine()


app = FastAPI(title="Complaint Analyser", version="1.1.0", lifespan=lifespan)

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
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

# Simple in-process rate limiter for write endpoints (per-IP, sliding window).
_RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_RPM", "30"))
_rate_limit_log: dict[str, list[float]] = defaultdict(list)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


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

        return JSONResponse(
            content={
                "id": record_id,
                "file_name": filename,
                "document_format": document_format,
                "raw_text_length": len(raw_text),
                "parsed_output": parsed_output,
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

        done_payload = {
            "step": "done",
            "label": "Complete",
            "result": {
                "id": record_id,
                "file_name": filename,
                "document_format": document_format,
                "raw_text_length": len(raw_text),
                "parsed_output": parsed_output,
            },
        }
        yield f"data: {_json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
            ).where(parse_records.c.id == record_id)
        )
        record = row.first()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return JSONResponse(
        content={
            "id": str(record.id),
            "file_name": record.file_name,
            "file_size": record.file_size,
            "document_format": record.document_format,
            "completeness_score": record.completeness_score,
            "parsed_output": record.parsed_output,
            "created_at": record.created_at.isoformat() if record.created_at else None,
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
            sa.select(parse_records.c.file_bytes, parse_records.c.file_name).where(
                parse_records.c.id == record_id
            )
        )
        record = row.first()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    file_name = record.file_name or "document"
    mime = _detect_mime_type(file_name, "") or "application/octet-stream"
    return StreamingResponse(
        io.BytesIO(record.file_bytes),
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
        result = await conn.execute(
            parse_records.delete().where(parse_records.c.id == record_id)
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Record not found.")
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
        result = await conn.execute(parse_records.delete())
    return JSONResponse(content={"deleted_count": result.rowcount})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(_get_env("PORT", "8080") or "8080"),
        reload=False,
    )
