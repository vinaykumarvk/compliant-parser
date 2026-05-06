from __future__ import annotations

import json
import os
import asyncio
import time
import uuid as _uuid
from collections import defaultdict
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit import compute_sha256, get_audit_log, log_audit_event, search_audit_logs, verify_audit_chain
from external_interfaces import (
    ExternalServiceError,
    ExternalServiceUnavailable,
    ai_boundary_status,
    external_interface_registry,
    infer_mime_type,
    is_document_ai_supported_mime,
    run_configured_ocr,
)
from hrms import HRMSProfile, authenticate_hrms
from governance import validate_kb_entry, validate_kb_promotion
from ai_workflows import (
    analyze_judgment_document,
    auto_recommend_bns_sections,
    auto_run_congruence_for_document,
    batch_recommend_sections,
    dismiss_congruence_alert,
    generate_investigation_plan,
    persist_section_recommendation,
    recommend_sections_from_text,
    usage_analytics,
)
from cases import (
    create_case,
    ensure_case_access,
    generate_case_identifiers,
    get_case,
    get_lifecycle_map,
    get_stage_guidance,
    list_cases,
    purge_old_document_versions,
    seed_demo_case,
    update_case,
    transition_case_status,
    attach_document,
    attach_documents,
    read_case_document_bytes,
    list_case_documents,
    get_case_document,
    list_document_versions,
    diff_document_versions,
    get_timeline,
    create_task,
    list_tasks,
    update_task,
    retry_cctns_sync,
    suggest_case_intake_from_petition,
    trigger_due_task_reminders,
    create_notification,
    list_notifications,
    mark_notification_read,
    list_police_stations_data,
    list_offence_types_data,
    search_offence_types_data,
)
from auth import (
    blacklist_token,
    check_lockout,
    clear_failed_attempts,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_blacklisted,
    record_failed_attempt,
    require_auth,
    require_permission,
    require_role,
    verify_password,
)
from database import get_db, get_engine, parse_records
from models import User


# --- Standard Error Format ---

class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

_ERROR_STATUS = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.AUTHENTICATION_ERROR: 401,
    ErrorCode.AUTHORIZATION_ERROR: 403,
    ErrorCode.ACCOUNT_LOCKED: 423,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.SERVER_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
}

class APIErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    request_id: str

class APIErrorResponse(BaseModel):
    error: APIErrorDetail


def raise_api_error(code: ErrorCode, message: str, field: Optional[str] = None) -> None:
    """Raise HTTPException with standard IQW error format."""
    request_id = str(_uuid.uuid4())[:8]
    status = _ERROR_STATUS.get(code, 500)
    raise HTTPException(
        status_code=status,
        detail={
            "error": {
                "code": code.value,
                "message": message,
                "field": field,
                "request_id": request_id,
            }
        },
    )


# --- Per-endpoint Rate Limiting (in-memory — transient by design) ---

_rate_logs: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

def check_rate_limit(request: Request, rpm: int = 100) -> None:
    """Check per-IP rate limit. Raises 429 if exceeded."""
    ip = request.client.host if request.client else "unknown"
    path = request.url.path
    key = f"{ip}:{path}"
    now = time.time()
    window = 60.0

    log = _rate_logs[key]
    timestamps = log.get("ts", [])
    timestamps = [t for t in timestamps if now - t < window]

    if len(timestamps) >= rpm:
        raise_api_error(
            ErrorCode.RATE_LIMITED,
            f"Rate limit exceeded. Maximum {rpm} requests per minute.",
        )

    timestamps.append(now)
    log["ts"] = timestamps


# --- Auth / User Pydantic Schemas ---

class LoginRequest(BaseModel):
    employee_id: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str

_VALID_ROLES = {"Senior_Command", "Zone_Officer", "SHO", "IO", "Clerk", "AI_Admin", "System_Admin", "Analyst", "Investigator", "Supervisor"}

class UserCreateRequest(BaseModel):
    employee_id: str
    full_name: str
    role: str
    password: str

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    def validate_role(self) -> None:
        if self.role not in _VALID_ROLES:
            raise ValueError(f"role must be one of {_VALID_ROLES}")
        if len(self.password) < 8:
            raise ValueError("password must be at least 8 characters")


# --- Case Workbench Pydantic Schemas ---

class CaseCreateRequest(BaseModel):
    case_type: str
    crime_no: Optional[str] = None
    petition_no: Optional[str] = None
    police_station_id: Optional[str] = None
    date_of_registration: Optional[str] = None
    primary_offence_type_id: Optional[str] = None
    secondary_offence_type_ids: Optional[list[str]] = None
    brief_facts: Optional[str] = None
    offence_type: Optional[str] = None
    ai_suggestion_context: Optional[dict[str, Any]] = None


class CaseUpdateRequest(BaseModel):
    case_type: Optional[str] = None
    crime_no: Optional[str] = None
    petition_no: Optional[str] = None
    police_station_id: Optional[str] = None
    date_of_registration: Optional[str] = None
    primary_offence_type_id: Optional[str] = None
    secondary_offence_type_ids: Optional[list[str]] = None
    brief_facts: Optional[str] = None
    offence_type: Optional[str] = None
    status: Optional[str] = None
    ai_suggestion_context: Optional[dict[str, Any]] = None


class StatusTransitionRequest(BaseModel):
    status: str


class TaskCreateRequest(BaseModel):
    task_name: str
    due_date: Optional[str] = None
    priority: Optional[str] = None
    source: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    snoozed_until: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None


class SectionRecommendationRequest(BaseModel):
    document_text: Optional[str] = None
    document_id: Optional[str] = None
    case_id: Optional[str] = None
    show_all: bool = False


class CongruenceDismissRequest(BaseModel):
    reason_code: str
    notes: Optional[str] = None


class InvestigationPlanUpdateRequest(BaseModel):
    investigation_steps: Optional[list[dict]] = None
    evidence_to_collect: Optional[list[dict]] = None
    documents_to_generate: Optional[list[str]] = None
    statutory_deadlines: Optional[list[dict]] = None


class KbEntryRequest(BaseModel):
    entry_type: str
    title: str
    content: dict
    applicable_offence_types: Optional[list[str]] = None
    change_description: Optional[str] = None


# --- DB-backed user helpers ---

async def _get_user_by_employee_id(employee_id: str, db: AsyncSession) -> Optional[dict]:
    """Look up a user by employee_id. Returns dict or None."""
    result = await db.execute(
        select(User).where(User.employee_id == employee_id, User.is_active == True)
    )
    user = result.scalars().first()
    if user is None:
        return None
    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "full_name": user.full_name,
        "rank": user.rank,
        "designation": user.designation,
        "police_station_id": user.police_station_id,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "password_hash": user.password_hash,
    }


async def _create_user(
    employee_id: str,
    full_name: str,
    role: str,
    password_hash: Optional[str],
    db: AsyncSession,
    rank: Optional[str] = None,
    designation: Optional[str] = None,
    police_station_id: Optional[str] = None,
) -> dict:
    """Create a new user in the DB."""
    user = User(
        employee_id=employee_id,
        full_name=full_name,
        rank=rank,
        designation=designation,
        police_station_id=police_station_id,
        role=role,
        password_hash=password_hash,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "full_name": user.full_name,
        "rank": user.rank,
        "designation": user.designation,
        "police_station_id": user.police_station_id,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
    }


async def _sync_hrms_user(profile: HRMSProfile, db: AsyncSession) -> dict:
    """Create or update the local user row from an authenticated HRMS profile."""
    result = await db.execute(
        select(User).where(User.employee_id == profile.employee_id, User.is_active == True)
    )
    user = result.scalars().first()
    if user is None:
        return await _create_user(
            employee_id=profile.employee_id,
            full_name=profile.full_name,
            role=profile.role,
            password_hash=None,
            db=db,
            rank=profile.rank,
            designation=profile.designation,
            police_station_id=profile.police_station_id,
        )
    user.full_name = profile.full_name
    user.rank = profile.rank
    user.designation = profile.designation
    user.police_station_id = profile.police_station_id
    user.role = profile.role
    await db.flush()
    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "full_name": user.full_name,
        "rank": user.rank,
        "designation": user.designation,
        "police_station_id": user.police_station_id,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "password_hash": user.password_hash,
    }


async def _list_users(db: AsyncSession) -> list[dict]:
    """Return all active users."""
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "employee_id": u.employee_id,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
        }
        for u in users
    ]


# --- V1 Router ---

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Sub-routers (will be populated by later phases)
auth_router = APIRouter(prefix="/auth", tags=["auth"])
cases_router = APIRouter(prefix="/cases", tags=["cases"])
analysis_router = APIRouter(prefix="/analysis", tags=["analysis"])
documents_router = APIRouter(prefix="/documents", tags=["documents"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])
senior_dashboard_router = APIRouter(prefix="/senior-dashboard", tags=["senior-dashboard"])
audit_log_router = APIRouter(prefix="/audit-logs", tags=["audit"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])
police_stations_router = APIRouter(prefix="/police-stations", tags=["police-stations"])
offence_types_router = APIRouter(prefix="/offence-types", tags=["offence-types"])


# --- Auth Endpoints ---

@auth_router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """Authenticate with employee_id + password, return token pair."""
    check_rate_limit(request, rpm=10)

    # Lockout check (raises if locked)
    check_lockout(body.employee_id)

    hrms_profile = await authenticate_hrms(body.employee_id, body.password)
    user = await _sync_hrms_user(hrms_profile, db) if hrms_profile else await _get_user_by_employee_id(body.employee_id, db)
    local_password_ok = bool(user and user.get("password_hash") and verify_password(body.password, user["password_hash"]))
    if user is None or (hrms_profile is None and not local_password_ok):
        record_failed_attempt(body.employee_id)
        raise_api_error(
            ErrorCode.AUTHENTICATION_ERROR,
            "Invalid Employee ID or password. Please try again.",
        )

    clear_failed_attempts(body.employee_id)

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"], role=user["role"])

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user["id"],
            "name": user["full_name"],
            "role": user["role"],
            "employee_id": user["employee_id"],
            "rank": user.get("rank"),
            "designation": user.get("designation"),
            "police_station_id": user.get("police_station_id"),
        },
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request) -> TokenResponse:
    """Exchange a valid refresh token for a new access token."""
    check_rate_limit(request, rpm=10)

    if is_blacklisted(body.refresh_token):
        raise_api_error(ErrorCode.AUTHENTICATION_ERROR, "Token has been revoked.")

    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise_api_error(ErrorCode.AUTHENTICATION_ERROR, "Token is not a refresh token.")

    new_access = create_access_token(payload["sub"], payload.get("role", ""))
    return TokenResponse(access_token=new_access)


@auth_router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(require_auth)) -> dict:
    """Blacklist the caller's current access token."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token:
        blacklist_token(token)
    return {"message": "Logged out successfully."}


@auth_router.get("/me")
async def me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
) -> dict:
    """Return the authenticated user's current synced profile."""
    user_row = await db.get(User, current_user.get("sub"))
    if user_row is not None:
        return {
            "id": user_row.id,
            "name": user_row.full_name,
            "role": user_row.role.value if hasattr(user_row.role, "value") else user_row.role,
            "employee_id": user_row.employee_id,
            "rank": user_row.rank,
            "designation": user_row.designation,
            "police_station_id": user_row.police_station_id,
        }
    return {
        "id": current_user.get("sub"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
        "employee_id": current_user.get("employee_id"),
    }


# --- Admin / User-Management Endpoints ---

class KISProviderCreateRequest(BaseModel):
    provider: str
    allowed_models: list[str]
    active: bool = True
    budget: dict[str, Any] = {}


class KISProviderUpdateRequest(BaseModel):
    allowed_models: Optional[list[str]] = None
    active: Optional[bool] = None
    budget: Optional[dict[str, Any]] = None


class KISCredentialCreateRequest(BaseModel):
    api_key: str
    expires_at: Optional[str] = None


class KISRebuildRequest(BaseModel):
    rebuild_vectors: bool = True
    recompile_wiki: bool = True
    promote_facts: bool = True
    create_snapshot: bool = False
    publish_snapshot: bool = False


class KISRollbackRequest(BaseModel):
    version: int


@admin_router.get("/users")
async def list_users_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("System_Admin")),
) -> list[dict]:
    """Return all users (System_Admin only)."""
    return await _list_users(db)


@admin_router.post("/users")
async def create_user_endpoint(
    body: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Create a new user (System_Admin only)."""
    if body.role not in _VALID_ROLES:
        raise_api_error(ErrorCode.VALIDATION_ERROR, f"role must be one of {sorted(_VALID_ROLES)}", field="role")
    if len(body.password) < 8:
        raise_api_error(ErrorCode.VALIDATION_ERROR, "password must be at least 8 characters", field="password")
    existing = await _get_user_by_employee_id(body.employee_id, db)
    if existing is not None:
        raise_api_error(
            ErrorCode.CONFLICT,
            f"User with employee_id '{body.employee_id}' already exists.",
            field="employee_id",
        )

    password_hash = hash_password(body.password)
    user = await _create_user(body.employee_id, body.full_name, body.role, password_hash, db)
    return user


@admin_router.get("/external-interfaces")
async def external_interfaces_endpoint(
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Return configured external service boundaries without exposing secrets."""

    def configured(*names: str) -> bool:
        return all(bool((os.getenv(name) or "").strip()) for name in names)

    return {
        "interfaces": external_interface_registry(),
        "configured": {
            "hrms": configured("HRMS_AUTH_URL"),
            "cctns": configured("CCTNS_SYNC_URL"),
            "dsc": (os.getenv("DSC_TOKEN_PRESENT", "").lower() in {"1", "true", "yes"}),
            "google_document_ai": configured("DOC_AI_PROJECT_ID", "DOC_AI_LOCATION", "DOC_AI_PROCESSOR_ID"),
            "openai_llm": configured("OPENAI_API_KEY"),
            "gemini_llm": configured("GEMINI_API_KEY"),
            "self_hosted_ocr": configured("IQW_SELF_HOSTED_OCR_URL"),
            "self_hosted_llm": configured("IQW_SELF_HOSTED_LLM_URL"),
            "object_storage": (
                configured("OBJECT_STORAGE_BUCKET")
                or configured("GCS_BUCKET")
                or configured("S3_BUCKET")
                or configured("MINIO_BUCKET")
            ),
            "opensearch": configured("OPENSEARCH_URL"),
            "redis_queue": configured("REDIS_URL") or configured("CELERY_BROKER_URL"),
            "temporal": configured("TEMPORAL_ADDRESS"),
            "notification_gateway": configured("NOTIFICATION_GATEWAY_URL"),
        },
        "ai_boundary": ai_boundary_status(),
        "stub_policy": {
            "llm_stubs_allowed": os.getenv("IQW_ALLOW_LLM_STUBS", "true").lower() in {"1", "true", "yes", "on"},
            "purpose": "Local/test fallback only; production should configure live services and disable LLM stubs.",
        },
    }


@admin_router.get("/kis/status")
async def kis_status_endpoint(
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Return KIS operational health without exposing secrets."""
    from kis_client import KISClient, KISClientError, KISUnavailable, kis_status

    status = kis_status()
    payload: dict[str, Any] = {"kis": status, "available": False}
    if status.get("configured"):
        try:
            client = KISClient()
            latest = client.latest_snapshot().get("snapshot")
            quality = client.run_quality_gates()
            graph = client.graph_stats()
            wiki = client.list_wiki_articles()
            facts = client.list_facts()
            payload.update(
                {
                    "available": True,
                    "latest_snapshot": latest,
                    "quality_gates": quality,
                    "graph": graph,
                    "wiki_article_count": len(wiki.get("items", [])),
                    "fact_count": len(facts.get("items", [])),
                }
            )
        except (KISClientError, KISUnavailable) as exc:
            payload["error"] = exc.__class__.__name__
    try:
        from kis_indexing_status import kis_index_status_counts, list_kis_indexing_records

        payload["indexing_counts"] = await kis_index_status_counts()
        payload["recent_indexing"] = await list_kis_indexing_records(limit=10)
    except Exception as exc:
        payload["indexing_status_error"] = exc.__class__.__name__
    return payload


@admin_router.get("/kis/indexing-records")
async def kis_indexing_records_endpoint(
    limit: int = 50,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Return recent parse records with persisted KIS indexing state."""
    from kis_indexing_status import kis_index_status_counts, list_kis_indexing_records

    return {
        "items": await list_kis_indexing_records(limit=limit),
        "counts": await kis_index_status_counts(),
    }


@admin_router.get("/kis/maintenance")
async def kis_maintenance_dashboard_endpoint(
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Return KIS domain-admin maintenance dashboard data."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().maintenance_dashboard()
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS maintenance unavailable: {exc.__class__.__name__}")


@admin_router.post("/kis/providers")
async def create_kis_provider_endpoint(
    body: KISProviderCreateRequest,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Create a KIS domain provider allowlist."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().create_provider(
            provider=body.provider,
            allowed_models=body.allowed_models,
            active=body.active,
            budget=body.budget,
        )
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS provider create failed: {exc.__class__.__name__}")


@admin_router.patch("/kis/providers/{provider_config_id}")
async def update_kis_provider_endpoint(
    provider_config_id: str,
    body: KISProviderUpdateRequest,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Update a KIS domain provider allowlist."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().update_provider(
            provider_config_id,
            allowed_models=body.allowed_models,
            active=body.active,
            budget=body.budget,
        )
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS provider update failed: {exc.__class__.__name__}")


@admin_router.post("/kis/providers/{provider_config_id}/credentials")
async def create_kis_credential_endpoint(
    provider_config_id: str,
    body: KISCredentialCreateRequest,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Create an encrypted KIS provider credential; never returns the secret."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().create_credential(provider_config_id, api_key=body.api_key, expires_at=body.expires_at)
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS credential create failed: {exc.__class__.__name__}")


@admin_router.post("/kis/providers/{provider_config_id}/credentials/{credential_id}:revoke")
async def revoke_kis_credential_endpoint(
    provider_config_id: str,
    credential_id: str,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Revoke a KIS provider credential."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().revoke_credential(provider_config_id, credential_id)
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS credential revoke failed: {exc.__class__.__name__}")


@admin_router.post("/kis/rebuild")
async def rebuild_kis_knowledge_base_endpoint(
    body: KISRebuildRequest,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Run KIS knowledge maintenance: vectors, wiki, graph, and optional snapshot."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().rebuild_knowledge_base(
            rebuild_vectors=body.rebuild_vectors,
            recompile_wiki=body.recompile_wiki,
            promote_facts=body.promote_facts,
            create_snapshot=body.create_snapshot,
            publish_snapshot=body.publish_snapshot,
        )
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS rebuild failed: {exc.__class__.__name__}")


@admin_router.post("/kis/snapshots:rollback")
async def rollback_kis_snapshot_endpoint(
    body: KISRollbackRequest,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Rollback the active KIS snapshot to a previous version."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        return KISClient().rollback_snapshot(body.version)
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS snapshot rollback failed: {exc.__class__.__name__}")


@admin_router.post("/kis/reindex/{record_id}")
async def reindex_kis_parse_record_endpoint(
    record_id: str,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Re-index a parse history record into KIS."""
    from kis_client import index_uploaded_document_via_kis
    from kis_indexing_status import normalize_kis_result_status, update_kis_index_status

    engine = await get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(
                parse_records.c.id,
                parse_records.c.file_name,
                parse_records.c.document_format,
                parse_records.c.parsed_output,
            ).where(parse_records.c.id == record_id)
        )
        record = result.first()
    if record is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Parse record '{record_id}' not found.")
    await update_kis_index_status(record_id, status="running")
    try:
        result = await asyncio.to_thread(
            index_uploaded_document_via_kis,
            record_id=str(record.id),
            file_name=record.file_name or "document",
            parsed_output=record.parsed_output if isinstance(record.parsed_output, dict) else {},
            document_format=record.document_format or "UNKNOWN",
            publish_snapshot=False,
        )
        status = normalize_kis_result_status(result)
        await update_kis_index_status(
            record_id,
            status=status,
            result=result,
            error_code=None if status != "failed" else result.get("reason") or result.get("error"),
            error_detail=None if status != "failed" else result.get("reason") or result.get("error"),
        )
        return {**result, "kis_index_status": status}
    except Exception as exc:
        try:
            await update_kis_index_status(
                record_id,
                status="failed",
                error_code=exc.__class__.__name__,
                error_detail="KIS re-index failed.",
            )
        except Exception:
            pass
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS re-index failed: {exc.__class__.__name__}")


@admin_router.post("/kis/indexing:retry-failed")
async def retry_failed_kis_indexing_endpoint(
    limit: int = 100,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Requeue failed KIS indexing records for background retry."""
    from kis_indexing_status import requeue_failed_kis_indexing

    count = await requeue_failed_kis_indexing(limit=limit)
    return {"requeued": count}


@admin_router.post("/kis/snapshots:publish")
async def publish_kis_snapshot_endpoint(
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Publish a new KIS snapshot only when quality gates pass."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        client = KISClient()
        quality = client.run_quality_gates()
        if not quality.get("passed"):
            return {"published": False, "quality_gates": quality}
        snapshot = client.create_snapshot()
        published = client.publish_snapshot(snapshot["id"])
        return {"published": True, "quality_gates": quality, "snapshot": published}
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS snapshot publish failed: {exc.__class__.__name__}")


@admin_router.get("/kis/facts")
async def kis_facts_endpoint(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Return KIS facts for admin review without exposing credentials."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        facts = KISClient().list_facts().get("items", [])
        if status:
            facts = [fact for fact in facts if fact.get("status") == status]
        return {"items": facts[: max(1, min(int(limit or 50), 200))], "total": len(facts)}
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS facts unavailable: {exc.__class__.__name__}")


@admin_router.post("/kis/facts/{fact_id}:approve")
async def approve_kis_fact_endpoint(
    fact_id: str,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Approve a candidate KIS fact and promote it to the graph."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        client = KISClient()
        fact = client.review_fact(fact_id, status="approved")
        promoted = client.promote_fact(fact["id"])
        return {"approved": True, "fact": fact, "promoted": promoted}
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS fact approval failed: {exc.__class__.__name__}")


@admin_router.post("/kis/facts/{fact_id}:reject")
async def reject_kis_fact_endpoint(
    fact_id: str,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Reject a candidate KIS fact."""
    from kis_client import KISClient, KISClientError, KISUnavailable

    try:
        fact = KISClient().review_fact(fact_id, status="rejected")
        return {"rejected": True, "fact": fact}
    except (KISClientError, KISUnavailable) as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"KIS fact rejection failed: {exc.__class__.__name__}")


@admin_router.get("/ai-review-queue")
async def ai_review_queue_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("AI_Admin", "System_Admin")),
) -> list[dict]:
    """Dedicated AI Admin uncertainty queue sorted by severity."""
    from models import AIAnalysisResult

    result = await db.execute(select(AIAnalysisResult).where(AIAnalysisResult.has_uncertainty_flag == True))  # noqa: E712
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    items = []
    for row in result.scalars().all():
        confidence = row.confidence_score.value if hasattr(row.confidence_score, "value") else row.confidence_score
        severity = "High" if confidence == "Low" else "Medium"
        items.append({
            "id": row.id,
            "severity": severity,
            "analysis_type": row.analysis_type.value if hasattr(row.analysis_type, "value") else row.analysis_type,
            "ai_output": row.result_json,
            "source_input_hash": row.input_text_hash,
            "model_version": row.model_version,
            "prompt_version": row.prompt_version,
            "uncertainty_tags": row.uncertainty_tags or [],
        })
    return sorted(items, key=lambda item: severity_order.get(item["severity"], 9))


@admin_router.post("/ai-review-queue/{analysis_id}/correction")
async def ai_review_correction_endpoint(
    analysis_id: str,
    body: KbEntryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("AI_Admin", "System_Admin")),
) -> dict:
    """Record AI Admin correction and create a draft KB update."""
    from models import AIAnalysisResult, KnowledgeBaseEntry

    analysis = await db.get(AIAnalysisResult, analysis_id)
    if analysis is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Analysis '{analysis_id}' not found.")
    analysis.io_reviewed = True
    analysis.io_review_action = "AI_Admin_Correction"
    analysis.io_review_notes = body.change_description
    entry = KnowledgeBaseEntry(
        entry_type=body.entry_type,
        title=body.title,
        content={**body.content, "rationale": body.change_description, "source_analysis_id": analysis_id},
        applicable_offence_types=body.applicable_offence_types,
        status="Draft",
        version=1,
        created_by=current_user["sub"],
    )
    db.add(entry)
    await db.flush()
    return {"id": entry.id, "status": "Draft", "updates_knowledge_base": True}


@admin_router.post("/kb-entries")
async def create_kb_entry_endpoint(
    body: KbEntryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("AI_Admin", "System_Admin")),
) -> dict:
    """Create checklist/SOP/template KB entry in Draft status."""
    from models import KnowledgeBaseEntry

    entry = KnowledgeBaseEntry(
        entry_type=body.entry_type,
        title=body.title,
        content={**body.content, "change_description": body.change_description},
        applicable_offence_types=body.applicable_offence_types,
        status="Draft",
        version=1,
        created_by=current_user["sub"],
    )
    db.add(entry)
    await db.flush()
    return {"id": entry.id, "title": entry.title, "status": "Draft", "version": entry.version}


@admin_router.post("/kb-entries/{entry_id}/promote")
async def promote_kb_entry_endpoint(
    entry_id: str,
    target_status: str = "Staging",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("AI_Admin", "System_Admin")),
) -> dict:
    """Promote KB entry to Staging or Production."""
    from models import KnowledgeBaseEntry

    entry = await db.get(KnowledgeBaseEntry, entry_id)
    if entry is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"KB entry '{entry_id}' not found.")
    try:
        validate_kb_promotion(entry.status, target_status, entry.validation_status)
    except ValueError as exc:
        raise_api_error(ErrorCode.VALIDATION_ERROR, str(exc), "target_status")
    entry.status = target_status
    entry.promoted_by = current_user["sub"]
    from datetime import datetime, timezone
    entry.promoted_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": entry.id, "status": target_status, "version": entry.version, "promoted_at": entry.promoted_at.isoformat()}


@admin_router.post("/kb-entries/{entry_id}/validate")
async def validate_kb_entry_endpoint(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("AI_Admin", "System_Admin")),
) -> dict:
    """Run lightweight validation tests against a staging KB entry."""
    from models import KnowledgeBaseEntry

    entry = await db.get(KnowledgeBaseEntry, entry_id)
    if entry is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"KB entry '{entry_id}' not found.")
    report = validate_kb_entry(entry.entry_type, entry.title, entry.content)
    from datetime import datetime, timezone

    entry.validation_status = report["validation_status"]
    entry.validation_report = report
    entry.validated_by = current_user["sub"]
    entry.validated_at = datetime.now(timezone.utc)
    await db.flush()
    return {
        "id": entry.id,
        "status": entry.status.value if hasattr(entry.status, "value") else entry.status,
        "validation_status": entry.validation_status,
        "tests": report["tests"],
        "passed": report["passed"],
        "can_promote_to_production": report["passed"] and (entry.status.value if hasattr(entry.status, "value") else entry.status) == "Staging",
    }


@admin_router.post("/kb-entries/{entry_id}/rollback")
async def rollback_kb_entry_endpoint(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("AI_Admin", "System_Admin")),
) -> dict:
    """Roll back a production KB entry to its previous version."""
    from models import KnowledgeBaseEntry

    entry = await db.get(KnowledgeBaseEntry, entry_id)
    if entry is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"KB entry '{entry_id}' not found.")
    if not entry.previous_version_id:
        raise_api_error(ErrorCode.VALIDATION_ERROR, "No previous version available for rollback.")
    previous = await db.get(KnowledgeBaseEntry, entry.previous_version_id)
    if previous is None:
        raise_api_error(ErrorCode.NOT_FOUND, "Previous KB version not found.")
    previous.status = "Production"
    previous.promoted_by = current_user["sub"]
    from datetime import datetime, timezone
    previous.promoted_at = datetime.now(timezone.utc)
    entry.status = "Deprecated"
    await db.flush()
    return {"rolled_back_to": previous.id, "status": "Production", "audited": True}


# --- Audit Log Endpoints (immutable — no PUT/PATCH/DELETE) ---

@audit_log_router.get("/")
async def list_audit_logs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Search audit logs with optional filters. System_Admin only."""
    filters = {}
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    if user_id:
        filters["user_id"] = user_id
    if action_type:
        filters["action_type"] = action_type
    if entity_type:
        filters["entity_type"] = entity_type
    results = await search_audit_logs(filters=filters, page=page, page_size=page_size, db=db)
    return results


@audit_log_router.get("/integrity")
async def verify_audit_log_integrity(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Verify hash-chain continuity for append-only audit logs."""
    return await verify_audit_chain(db=db)


@audit_log_router.get("/{log_id}")
async def get_single_audit_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Retrieve a single audit log entry by ID. System_Admin only."""
    entry = await get_audit_log(log_id, db=db)
    if entry is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Audit log entry '{log_id}' not found.")
    return entry


async def _ensure_case_document_access(document_id: str, user: dict, db: AsyncSession):
    from models import CaseDocument

    doc = await db.get(CaseDocument, document_id)
    if doc is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Document '{document_id}' not found.")
    await ensure_case_access(doc.case_id, user, db)
    return doc


async def _ensure_generated_document_access(doc_id: str, user: dict, db: AsyncSession):
    from models import GeneratedDocument

    doc = await db.get(GeneratedDocument, doc_id)
    if doc is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Generated document '{doc_id}' not found.")
    await ensure_case_access(doc.case_id, user, db)
    return doc


# --- Document Integrity Endpoint ---

@documents_router.post("/{document_id}/verify-integrity")
async def verify_document_integrity(
    document_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
) -> dict:
    """Verify document integrity by recomputing SHA-256 from stored bytes."""
    doc = await _ensure_case_document_access(document_id, current_user, db)

    file_bytes = await read_case_document_bytes(doc)
    if file_bytes is None:
        raise_api_error(ErrorCode.VALIDATION_ERROR, "Stored document bytes are not available for integrity verification.", "document_id")

    recomputed_hash = compute_sha256(file_bytes)
    verified = recomputed_hash == doc.sha256_hash
    if verified:
        return {
            "verified": True,
            "document_id": document_id,
            "sha256": recomputed_hash,
            "message": "Document integrity verified. No modifications detected.",
        }

    ip_address = request.client.host if request.client else None
    await log_audit_event(
        current_user.get("sub"),
        "AI_Analysis",
        "CaseDocument",
        document_id,
        details={
            "event": "integrity_mismatch",
            "stored_sha256": doc.sha256_hash,
            "computed_sha256": recomputed_hash,
        },
        ip_address=ip_address,
        session_id=request.headers.get("X-Session-Id"),
        db=db,
    )
    admins = await db.execute(select(User).where(User.role == "System_Admin", User.is_active == True))
    for admin in admins.scalars().all():
        await create_notification(
            admin.id,
            "critical",
            "WARNING: Document integrity check failed. The file may have been modified since upload.",
            entity_type="document",
            entity_id=document_id,
            db=db,
        )
    return {
        "verified": False,
        "document_id": document_id,
        "sha256": recomputed_hash,
        "message": "WARNING: Document integrity check failed. The file may have been modified since upload.",
    }


@documents_router.get("/{document_id}/content")
async def get_document_content(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
) -> Response:
    """Return raw document bytes with correct Content-Type for inline rendering."""
    doc = await _ensure_case_document_access(document_id, current_user, db)
    file_bytes = await read_case_document_bytes(doc)
    if file_bytes is None:
        raise_api_error(ErrorCode.NOT_FOUND, "Document content is not available.")
    mime = infer_mime_type(doc.file_name or "file")
    return Response(content=file_bytes, media_type=mime, headers={
        "Content-Disposition": f'inline; filename="{doc.file_name or document_id}"',
    })


@documents_router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
) -> Response:
    """Return raw document bytes as an attachment download."""
    doc = await _ensure_case_document_access(document_id, current_user, db)
    file_bytes = await read_case_document_bytes(doc)
    if file_bytes is None:
        raise_api_error(ErrorCode.NOT_FOUND, "Document content is not available.")
    mime = infer_mime_type(doc.file_name or "file")
    return Response(content=file_bytes, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{doc.file_name or document_id}"',
    })


# --- Case Workbench Endpoints ---

@cases_router.post("/")
async def create_case_endpoint(
    body: CaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("create_case")),
) -> dict:
    """Create a new case."""
    data = body.model_dump(exclude_none=True)
    result = await create_case(data, user["sub"], db)
    return result


@cases_router.get("/")
async def list_cases_endpoint(
    status: Optional[str] = None,
    police_station_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """List cases with optional filters."""
    filters: dict[str, Any] = {
        "page": page,
        "page_size": page_size,
    }
    if status:
        filters["status"] = status
    if police_station_id:
        filters["police_station_id"] = police_station_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    return await list_cases(user["sub"], user["role"], filters, db=db)


@cases_router.get("/lifecycle")
async def get_lifecycle_endpoint(user: dict = Depends(require_auth)) -> dict:
    """Return the full case lifecycle map (transitions + stage guidance)."""
    return get_lifecycle_map()


@cases_router.post("/seed-demo")
async def seed_demo_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Create a demo case for first-time users (any authenticated user)."""
    return await seed_demo_case(user["sub"], db)


@cases_router.get("/number-preview")
async def case_number_preview_endpoint(
    police_station_id: str,
    case_type: str = "Petition",
    date_of_registration: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return the next station-scoped case number and registration date."""
    return await generate_case_identifiers(
        police_station_id=police_station_id,
        case_type=case_type,
        db=db,
        registration_datetime=date_of_registration,
    )


@cases_router.post("/intake-suggestions")
async def case_intake_suggestions_endpoint(
    petition_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("create_case")),
) -> dict:
    """Use Google Document AI OCR and a live LLM to suggest editable intake fields."""
    try:
        return await suggest_case_intake_from_petition(
            file_name=petition_file.filename or "petition",
            file_bytes=await petition_file.read(),
            mime_type=petition_file.content_type,
            user_id=user["sub"],
            db=db,
        )
    except ExternalServiceUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ExternalServiceError as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))


@cases_router.get("/{case_id}")
async def get_case_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Get case detail by ID."""
    await ensure_case_access(case_id, user, db)
    result = await get_case(case_id, db)
    if result is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Case '{case_id}' not found.")
    return result


@cases_router.put("/{case_id}")
async def update_case_endpoint(
    case_id: str,
    body: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Update a case."""
    await ensure_case_access(case_id, user, db)
    data = body.model_dump(exclude_none=True)
    result = await update_case(case_id, data, user["sub"], db)
    return result


@cases_router.patch("/{case_id}/status")
async def transition_case_status_endpoint(
    case_id: str,
    body: StatusTransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("transition_case_status")),
) -> dict:
    """Transition case status."""
    await ensure_case_access(case_id, user, db)
    result = await transition_case_status(case_id, body.status, user["sub"], db)
    return result


@cases_router.post("/{case_id}/cctns/retry")
async def retry_cctns_sync_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Retry CCTNS sync for a pending or failed case."""
    await ensure_case_access(case_id, user, db)
    return await retry_cctns_sync(case_id, user["sub"], db)


@cases_router.post("/{case_id}/documents")
async def upload_case_document_endpoint(
    case_id: str,
    document_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("upload_document")),
) -> dict:
    """Upload a document to a case."""
    await ensure_case_access(case_id, user, db)
    file_bytes = await file.read()
    result = await attach_document(
        case_id=case_id,
        file_name=file.filename or "unnamed",
        document_type=document_type,
        file_bytes=file_bytes,
        user_id=user["sub"],
        db=db,
        mime_type=file.content_type,
    )
    try:
        result["congruence_alerts"] = await auto_run_congruence_for_document(case_id, result["id"], user["sub"], db)
        result["congruence_status"] = "Completed"
    except ExternalServiceUnavailable as exc:
        result["congruence_alerts"] = []
        result["congruence_status"] = "Skipped"
        result["congruence_message"] = str(exc)
    except ExternalServiceError as exc:
        result["congruence_alerts"] = []
        result["congruence_status"] = "Failed"
        result["congruence_message"] = str(exc)
    try:
        result["section_recommendation"] = await auto_recommend_bns_sections(case_id, result["id"], user["sub"], db)
    except ExternalServiceUnavailable:
        result["section_recommendation"] = {"section_recommendation_status": "Skipped"}
    except ExternalServiceError:
        result["section_recommendation"] = {"section_recommendation_status": "Failed"}
    return result


@cases_router.post("/{case_id}/documents/bulk")
async def upload_case_documents_bulk_endpoint(
    case_id: str,
    document_type: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("upload_document")),
) -> dict:
    """Upload up to 20 documents to a case in one request."""
    await ensure_case_access(case_id, user, db)
    payload = []
    for upload in files:
        payload.append(
            {
                "file_name": upload.filename or "unnamed",
                "document_type": document_type,
                "file_bytes": await upload.read(),
                "mime_type": upload.content_type,
            }
    )
    docs = await attach_documents(case_id, payload, user["sub"], db)
    alerts = []
    congruence_status = "Completed"
    congruence_message = None
    section_recommendations = []
    for doc in docs:
        try:
            alerts.extend(await auto_run_congruence_for_document(case_id, doc["id"], user["sub"], db))
        except ExternalServiceUnavailable as exc:
            congruence_status = "Skipped"
            congruence_message = str(exc)
        except ExternalServiceError as exc:
            congruence_status = "Failed"
            congruence_message = str(exc)
        try:
            sr = await auto_recommend_bns_sections(case_id, doc["id"], user["sub"], db)
            section_recommendations.append(sr)
        except (ExternalServiceUnavailable, ExternalServiceError):
            section_recommendations.append({"section_recommendation_status": "Failed"})
    return {
        "items": docs,
        "total": len(docs),
        "congruence_alerts": alerts,
        "congruence_status": congruence_status,
        "congruence_message": congruence_message,
        "section_recommendations": section_recommendations,
    }


@cases_router.get("/{case_id}/documents")
async def list_case_documents_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List all documents for a case."""
    await ensure_case_access(case_id, user, db)
    return await list_case_documents(case_id, db)


@cases_router.get("/{case_id}/documents/{doc_id}")
async def get_case_document_endpoint(
    case_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Get document detail."""
    await ensure_case_access(case_id, user, db)
    result = await get_case_document(case_id, doc_id, db)
    if result is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Document '{doc_id}' not found.")
    return result


@cases_router.get("/{case_id}/documents/{doc_id}/versions")
async def list_case_document_versions_endpoint(
    case_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List version history for a case document."""
    await ensure_case_access(case_id, user, db)
    return await list_document_versions(case_id, doc_id, db)


@cases_router.get("/{case_id}/documents/{left_doc_id}/diff/{right_doc_id}")
async def diff_case_document_versions_endpoint(
    case_id: str,
    left_doc_id: str,
    right_doc_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return a unified diff between two case document versions."""
    await ensure_case_access(case_id, user, db)
    return await diff_document_versions(case_id, left_doc_id, right_doc_id, db)


@cases_router.delete("/{case_id}/documents/old-versions")
async def purge_old_versions_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Delete all superseded document versions for a case, freeing storage."""
    await ensure_case_access(case_id, user, db)
    return await purge_old_document_versions(case_id, user["sub"], db)


@cases_router.get("/{case_id}/timeline")
async def get_case_timeline_endpoint(
    case_id: str,
    sort: str = "desc",
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """Get case timeline events."""
    await ensure_case_access(case_id, user, db)
    return await get_timeline(case_id, sort_asc=(sort == "asc"), db=db)


@cases_router.get("/{case_id}/tasks")
async def list_case_tasks_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List tasks for a case."""
    await ensure_case_access(case_id, user, db)
    return await list_tasks(case_id, db)


@cases_router.post("/{case_id}/tasks")
async def create_case_task_endpoint(
    case_id: str,
    body: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Create a task for a case."""
    await ensure_case_access(case_id, user, db)
    data = body.model_dump(exclude_none=True)
    return await create_task(case_id, data, user["sub"], db)


@cases_router.put("/{case_id}/tasks/{task_id}")
async def update_case_task_endpoint(
    case_id: str,
    task_id: str,
    body: TaskUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Update a task."""
    await ensure_case_access(case_id, user, db)
    data = body.model_dump(exclude_none=True)
    return await update_task(case_id, task_id, data, user["sub"], db)


@cases_router.post("/tasks/reminders/run")
async def run_task_reminders_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Trigger due-date reminders for tasks due in 3 days, 1 day, or today."""
    notes = await trigger_due_task_reminders(db)
    return {"items": notes, "total": len(notes)}


# --- Notifications Endpoints ---

@notifications_router.get("/")
async def list_notifications_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List unread notifications for the current user."""
    return await list_notifications(user["sub"], db=db)


@notifications_router.patch("/{notification_id}/read")
async def mark_notification_read_endpoint(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Mark a notification as read."""
    return await mark_notification_read(notification_id, db)


# --- Analytics Endpoints ---

@analytics_router.get("/summary")
async def analytics_summary_endpoint(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    io_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Usage/adoption dashboard data with IO scoping."""
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "police_station_id": police_station_id,
        "io_id": io_id,
    }
    return await usage_analytics({k: v for k, v in filters.items() if v}, user, db)


@analytics_router.get("/monthly-trend-report")
async def analytics_monthly_report_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> JSONResponse:
    """Generate monthly trend report as PDF bytes encoded for the JSON API."""
    import base64
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    data = await usage_analytics({}, user, db)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("IQW Monthly Usage Trend Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Cases created: {data['totals']['cases_created']}", styles["Normal"]),
        Paragraph(f"Documents uploaded: {data['totals']['documents_uploaded']}", styles["Normal"]),
        Paragraph(f"AI checks performed: {data['totals']['ai_checks_performed']}", styles["Normal"]),
    ]
    doc.build(story)
    return JSONResponse({"format": "pdf", "data": base64.b64encode(buf.getvalue()).decode("ascii")})


# --- Senior Officer Dashboard Endpoints ---

class DashboardAlertRuleRequest(BaseModel):
    metric_key: str
    threshold_operator: str = ">="
    threshold_value: float
    scope_type: str = "all"
    period: str = "weekly"
    severity: str = "warning"
    notification_channels: Optional[list[str]] = None
    minimum_sample_size: int = 5
    is_active: bool = True


class DashboardAlertRulePatch(BaseModel):
    threshold_operator: Optional[str] = None
    threshold_value: Optional[float] = None
    period: Optional[str] = None
    severity: Optional[str] = None
    notification_channels: Optional[list[str]] = None
    minimum_sample_size: Optional[int] = None
    is_active: Optional[bool] = None


class DashboardExportRequest(BaseModel):
    report_type: str = "overview"
    export_format: str = "csv"
    purpose: str
    schedule: Optional[str] = None


class DashboardMetricDefinitionPatch(BaseModel):
    display_name: Optional[str] = None
    owner_role: Optional[str] = None
    permitted_use: Optional[str] = None
    prohibited_use: Optional[str] = None
    confidence_tier: Optional[str] = None
    minimum_sample_size: Optional[int] = None
    source_tables: Optional[list[str]] = None
    exclusions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class DashboardMetricDisputeRequest(BaseModel):
    metric_key: str
    scope_type: str = "filtered"
    scope_id: Optional[str] = None
    reason_code: str = "data_quality"
    explanation: Optional[str] = None


class DashboardMetricDisputeReviewRequest(BaseModel):
    status: str = "resolved"
    resolution_notes: Optional[str] = None
    original_value: Optional[dict] = None
    corrected_value: Optional[dict] = None


class DashboardValidationStateRequest(BaseModel):
    state: str
    findings: Optional[dict] = None


class DashboardRecommendationReviewRequest(BaseModel):
    status: str = "reviewed"
    dismiss_days: Optional[int] = None


class DashboardSavedViewRequest(BaseModel):
    name: str
    is_default: bool = False


def _senior_dashboard_filters(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
):
    from senior_dashboard import DashboardValidationError, normalize_filters

    try:
        return normalize_filters(
            period=period,
            date_from=date_from,
            date_to=date_to,
            police_station_id=police_station_id,
            zone=zone,
            io_id=io_id,
            role=role,
            status=status,
            case_type=case_type,
            offence_category=offence_category,
            sort=sort,
        )
    except DashboardValidationError as exc:
        raise_api_error(ErrorCode.VALIDATION_ERROR, str(exc), field=exc.field)


async def _senior_dashboard_response(
    metric_fn,
    *,
    event_type: str,
    db: AsyncSession,
    user: dict,
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
) -> dict:
    from senior_dashboard import (
        DashboardAuthorizationError,
        DashboardConflictError,
        DashboardValidationError,
        record_dashboard_usage,
    )

    filters = _senior_dashboard_filters(
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )
    try:
        payload = await metric_fn(db, user, filters)
    except DashboardAuthorizationError as exc:
        raise_api_error(ErrorCode.AUTHORIZATION_ERROR, str(exc))
    except DashboardConflictError as exc:
        raise_api_error(ErrorCode.CONFLICT, str(exc), field=exc.field)
    except DashboardValidationError as exc:
        raise_api_error(ErrorCode.VALIDATION_ERROR, str(exc), field=exc.field)
    await record_dashboard_usage(
        db,
        user,
        event_type,
        {"filters": payload.get("filters"), "scope": payload.get("scope")},
    )
    return payload


async def _senior_dashboard_direct(awaitable) -> dict:
    from senior_dashboard import DashboardAuthorizationError, DashboardConflictError, DashboardValidationError

    try:
        return await awaitable
    except DashboardAuthorizationError as exc:
        raise_api_error(ErrorCode.AUTHORIZATION_ERROR, str(exc))
    except DashboardConflictError as exc:
        raise_api_error(ErrorCode.CONFLICT, str(exc), field=exc.field)
    except DashboardValidationError as exc:
        raise_api_error(ErrorCode.VALIDATION_ERROR, str(exc), field=exc.field)


@senior_dashboard_router.get("/overview")
async def senior_dashboard_overview_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return PII-safe senior dashboard overview metrics."""
    from senior_dashboard import overview_metrics

    return await _senior_dashboard_response(
        overview_metrics,
        event_type="dashboard.overview",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/officers")
async def senior_dashboard_officers_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return officer productivity metrics for the caller's scope."""
    from senior_dashboard import officer_metrics

    return await _senior_dashboard_response(
        officer_metrics,
        event_type="dashboard.officers",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/stations")
async def senior_dashboard_stations_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return station comparison metrics for the caller's scope."""
    from senior_dashboard import station_metrics

    return await _senior_dashboard_response(
        station_metrics,
        event_type="dashboard.stations",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/lifecycle")
async def senior_dashboard_lifecycle_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return lifecycle funnel and backlog metrics."""
    from senior_dashboard import lifecycle_metrics

    return await _senior_dashboard_response(
        lifecycle_metrics,
        event_type="dashboard.lifecycle",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/processing-times")
async def senior_dashboard_processing_times_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return complaint-to-FIR draft processing-time metrics."""
    from senior_dashboard import processing_time_metrics

    return await _senior_dashboard_response(
        processing_time_metrics,
        event_type="dashboard.processing_times",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/feature-adoption")
async def senior_dashboard_feature_adoption_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return feature adoption and AI effectiveness metrics."""
    from senior_dashboard import feature_adoption_metrics

    return await _senior_dashboard_response(
        feature_adoption_metrics,
        event_type="dashboard.feature_adoption",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/metric-definitions")
async def senior_dashboard_metric_definitions_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return versioned metric definitions and permitted-use labels."""
    from senior_dashboard import ensure_dashboard_access, metric_definition_payloads, normalize_filters, record_dashboard_usage

    filters = normalize_filters()
    await _senior_dashboard_direct(_noop_dashboard_access(ensure_dashboard_access, user, filters))
    items = await metric_definition_payloads(db)
    await record_dashboard_usage(db, user, "dashboard.metric_definitions", {"filters": filters.public()})
    return {"items": items, "total": len(items)}


async def _noop_dashboard_access(fn, user: dict, filters) -> dict:
    fn(user, filters)
    return {"ok": True}


@senior_dashboard_router.patch("/metric-definitions/{metric_key}")
async def senior_dashboard_metric_definition_patch_endpoint(
    metric_key: str,
    body: DashboardMetricDefinitionPatch,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import update_metric_definition

    return await _senior_dashboard_direct(update_metric_definition(db, user, metric_key, body.dict(exclude_unset=True)))


@senior_dashboard_router.get("/source-maps")
async def senior_dashboard_source_maps_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import ensure_dashboard_access, normalize_filters, source_map_payloads

    filters = normalize_filters()
    await _senior_dashboard_direct(_noop_dashboard_access(ensure_dashboard_access, user, filters))
    items = await source_map_payloads(db)
    return {"items": items, "total": len(items)}


@senior_dashboard_router.get("/filters")
async def senior_dashboard_filters_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import filter_options

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, sort)
    return await _senior_dashboard_direct(filter_options(db, user, filters))


@senior_dashboard_router.get("/documents")
async def senior_dashboard_documents_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import document_analytics_metrics

    return await _senior_dashboard_response(
        document_analytics_metrics,
        event_type="dashboard.documents",
        db=db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        police_station_id=police_station_id,
        zone=zone,
        io_id=io_id,
        role=role,
        status=status,
        case_type=case_type,
        offence_category=offence_category,
        sort=sort,
    )


@senior_dashboard_router.get("/officers/{user_id}")
async def senior_dashboard_officer_detail_endpoint(
    user_id: str,
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import officer_detail_metrics

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, None, None, status, case_type, offence_category, None)
    return await _senior_dashboard_direct(officer_detail_metrics(db, user, filters, user_id))


@senior_dashboard_router.get("/stations/{station_id}")
async def senior_dashboard_station_detail_endpoint(
    station_id: str,
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import station_detail_metrics

    filters = _senior_dashboard_filters(period, date_from, date_to, None, zone, io_id, role, status, case_type, offence_category, None)
    return await _senior_dashboard_direct(station_detail_metrics(db, user, filters, station_id))


@senior_dashboard_router.get("/lifecycle/{status}/cases")
async def senior_dashboard_lifecycle_stage_cases_endpoint(
    status: str,
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import lifecycle_stage_cases

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, None, case_type, offence_category, None)
    return await _senior_dashboard_direct(lifecycle_stage_cases(db, user, filters, status))


@senior_dashboard_router.get("/alert-rules")
async def senior_dashboard_alert_rules_endpoint(db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import list_alert_rules

    return await _senior_dashboard_direct(list_alert_rules(db, user))


@senior_dashboard_router.post("/alert-rules")
async def senior_dashboard_alert_rule_create_endpoint(body: DashboardAlertRuleRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import create_alert_rule

    return await _senior_dashboard_direct(create_alert_rule(db, user, body.dict()))


@senior_dashboard_router.patch("/alert-rules/{rule_id}")
async def senior_dashboard_alert_rule_patch_endpoint(rule_id: str, body: DashboardAlertRulePatch, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import update_alert_rule

    return await _senior_dashboard_direct(update_alert_rule(db, user, rule_id, body.dict(exclude_unset=True)))


@senior_dashboard_router.get("/alerts")
async def senior_dashboard_alerts_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import list_alerts

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, None)
    return await _senior_dashboard_direct(list_alerts(db, user, filters))


@senior_dashboard_router.post("/alerts/{alert_id}:acknowledge")
async def senior_dashboard_alert_ack_endpoint(alert_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import acknowledge_alert

    return await _senior_dashboard_direct(acknowledge_alert(db, user, alert_id))


@senior_dashboard_router.get("/exports")
async def senior_dashboard_exports_endpoint(db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import list_export_jobs

    return await _senior_dashboard_direct(list_export_jobs(db, user))


@senior_dashboard_router.post("/exports")
async def senior_dashboard_export_create_endpoint(
    body: DashboardExportRequest,
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import create_export_job

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, sort)
    return await _senior_dashboard_direct(
        create_export_job(db, user, filters, report_type=body.report_type, export_format=body.export_format, purpose=body.purpose, schedule=body.schedule)
    )


@senior_dashboard_router.get("/exports/{job_id}")
async def senior_dashboard_export_get_endpoint(job_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import get_export_job

    return await _senior_dashboard_direct(get_export_job(db, user, job_id))


@senior_dashboard_router.post("/exports/{job_id}:retry")
async def senior_dashboard_export_retry_endpoint(job_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import retry_export_job

    return await _senior_dashboard_direct(retry_export_job(db, user, job_id))


@senior_dashboard_router.post("/exports/{job_id}:revoke")
async def senior_dashboard_export_revoke_endpoint(job_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import revoke_export_job

    return await _senior_dashboard_direct(revoke_export_job(db, user, job_id))


@senior_dashboard_router.post("/snapshots:refresh")
async def senior_dashboard_snapshot_refresh_endpoint(
    metric_key: str = "overview",
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import refresh_dashboard_snapshot

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, sort)
    return await _senior_dashboard_direct(refresh_dashboard_snapshot(db, user, filters, metric_key))


@senior_dashboard_router.get("/metric-disputes")
async def senior_dashboard_disputes_endpoint(db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import list_metric_disputes

    return await _senior_dashboard_direct(list_metric_disputes(db, user))


@senior_dashboard_router.post("/metric-disputes")
async def senior_dashboard_dispute_create_endpoint(body: DashboardMetricDisputeRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import create_metric_dispute

    return await _senior_dashboard_direct(create_metric_dispute(db, user, body.dict()))


@senior_dashboard_router.post("/metric-disputes/{dispute_id}:review")
async def senior_dashboard_dispute_review_endpoint(dispute_id: str, body: DashboardMetricDisputeReviewRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import review_metric_dispute

    return await _senior_dashboard_direct(review_metric_dispute(db, user, dispute_id, body.dict(exclude_unset=True)))


@senior_dashboard_router.get("/training-recommendations")
async def senior_dashboard_recommendations_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import list_training_recommendations

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, None)
    return await _senior_dashboard_direct(list_training_recommendations(db, user, filters))


@senior_dashboard_router.post("/training-recommendations/{recommendation_id}:review")
async def senior_dashboard_recommendation_review_endpoint(recommendation_id: str, body: DashboardRecommendationReviewRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import review_training_recommendation

    return await _senior_dashboard_direct(review_training_recommendation(db, user, recommendation_id, body.dict(exclude_unset=True)))


@senior_dashboard_router.get("/validation-state/{feature_key}")
async def senior_dashboard_validation_state_endpoint(feature_key: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import get_validation_state

    return await _senior_dashboard_direct(get_validation_state(db, user, feature_key))


@senior_dashboard_router.patch("/validation-state/{feature_key}")
async def senior_dashboard_validation_state_patch_endpoint(feature_key: str, body: DashboardValidationStateRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import update_validation_state

    return await _senior_dashboard_direct(update_validation_state(db, user, feature_key, body.dict(exclude_unset=True)))


@senior_dashboard_router.get("/predictive-signals")
async def senior_dashboard_predictive_signals_endpoint(
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import predictive_signals

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, None)
    return await _senior_dashboard_direct(predictive_signals(db, user, filters))


@senior_dashboard_router.get("/saved-views")
async def senior_dashboard_saved_views_endpoint(db: AsyncSession = Depends(get_db), user: dict = Depends(require_auth)) -> dict:
    from senior_dashboard import list_saved_views

    return await _senior_dashboard_direct(list_saved_views(db, user))


@senior_dashboard_router.post("/saved-views")
async def senior_dashboard_saved_view_create_endpoint(
    body: DashboardSavedViewRequest,
    period: str = "last_30_days",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    police_station_id: Optional[str] = None,
    zone: Optional[str] = None,
    io_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    offence_category: Optional[str] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    from senior_dashboard import save_dashboard_view

    filters = _senior_dashboard_filters(period, date_from, date_to, police_station_id, zone, io_id, role, status, case_type, offence_category, sort)
    return await _senior_dashboard_direct(save_dashboard_view(db, user, body.name, filters, body.is_default))


# --- Police Stations Endpoints ---

@police_stations_router.get("/")
async def list_police_stations_endpoint(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List all police stations."""
    return await list_police_stations_data(db)


# --- Offence Types Endpoints ---

@offence_types_router.get("/")
async def list_offence_types_endpoint(
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List or search offence types."""
    if q:
        return await search_offence_types_data(q, db)
    return await list_offence_types_data(db)


# --- Quality Engine Endpoints ---

from quality_engine import run_quality_check, run_llm_quality_check  # noqa: E402


class QualityCheckRequest(BaseModel):
    document_id: Optional[str] = None
    document_text: Optional[str] = None
    document_type: str = "Generic"
    offence_type: Optional[str] = None
    case_id: Optional[str] = None


async def _load_kb_checklist(
    document_type: str,
    offence_type: Optional[str],
    db: AsyncSession,
) -> Optional[list[dict]]:
    """Load a production checklist from KnowledgeBaseEntry if one matches."""
    from models import KnowledgeBaseEntry

    result = await db.execute(
        select(KnowledgeBaseEntry).where(
            KnowledgeBaseEntry.entry_type == "Checklist",
            KnowledgeBaseEntry.status == "Production",
        )
    )
    for entry in result.scalars().all():
        content = entry.content or {}
        entry_doc_type = content.get("document_type") or content.get("documentType")
        applies_to = entry.applicable_offence_types or content.get("applicable_offence_types") or []
        if entry_doc_type and entry_doc_type != document_type:
            continue
        if offence_type and applies_to and offence_type not in applies_to:
            continue
        items = content.get("items") or content.get("checklist")
        if isinstance(items, list) and items:
            return items
    return None


@analysis_router.post("/quality-check")
async def run_quality_check_endpoint(
    body: QualityCheckRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Run a checklist-driven quality check on document text."""
    text = body.document_text or ""
    doc = None
    if body.document_id:
        from models import CaseDocument
        doc = await db.get(CaseDocument, body.document_id)
        if doc:
            await ensure_case_access(doc.case_id, user, db)
        if doc and doc.ocr_extracted_text:
            text = doc.ocr_extracted_text
        elif doc and not text:
            file_bytes = await read_case_document_bytes(doc)
            text = (file_bytes or b"").decode("utf-8", errors="replace")

    # Resolve case context for context-aware quality check
    case_context = None
    resolved_case_id = body.case_id or (doc.case_id if doc else None)
    offence_type = body.offence_type
    if resolved_case_id:
        from models import Case as CaseModel
        case_obj = await db.get(CaseModel, resolved_case_id)
        if case_obj:
            case_context = {}
            if case_obj.brief_facts:
                case_context["brief_facts"] = case_obj.brief_facts
            if case_obj.offence_type:
                case_context["offence_type"] = case_obj.offence_type
                if not offence_type:
                    offence_type = case_obj.offence_type
            if case_obj.date_of_occurrence:
                case_context["date_of_occurrence"] = str(case_obj.date_of_occurrence)
            if case_obj.petition_analysis:
                case_context["petition_analysis"] = case_obj.petition_analysis

    checklist_override = await _load_kb_checklist(body.document_type, offence_type, db)
    if checklist_override:
        # KB-specific checklist — use keyword engine
        result = run_quality_check(
            text,
            body.document_type,
            offence_type,
            checklist_override=checklist_override,
            case_context=case_context,
        )
    else:
        # LLM semantic analysis with keyword fallback
        result = await asyncio.to_thread(
            run_llm_quality_check, text, body.document_type, offence_type,
            case_context,
        )

    llm_meta = result.get("llm_meta", {})
    provider = llm_meta.get("provider", "keyword")
    is_semantic = result.get("analysis_mode") == "semantic"

    if doc is not None:
        from models import AIAnalysisResult, Citation

        analysis = AIAnalysisResult(
            case_id=doc.case_id,
            document_id=doc.id,
            analysis_type="Quality_Check",
            model_name=f"{provider}:llm_semantic" if is_semantic else "IQW checklist engine",
            model_version="1.0",
            prompt_version="semantic-v1" if is_semantic else "checklist-v1",
            input_text_hash=compute_sha256(text.encode("utf-8")),
            result_json=result,
            confidence_score=result["confidence_score"],
            latency_ms=result["latency_ms"],
            created_by=user["sub"],
        )
        db.add(analysis)
        await db.flush()
        result["persisted_analysis_id"] = analysis.id
        for finding in result["findings"]:
            citation_data = finding.get("citation") or {}
            citation = Citation(
                analysis_id=analysis.id,
                source_document_id=doc.id,
                excerpt_text=citation_data.get("excerpt"),
                char_offset_start=citation_data.get("char_start"),
                char_offset_end=citation_data.get("char_end"),
                citation_purpose=citation_data.get("purpose"),
                created_by=user["sub"],
            )
            db.add(citation)
            await db.flush()
            finding["citation"]["citation_id"] = citation.id
            finding["citation"]["source_document_id"] = doc.id
    if resolved_case_id:
        result["case_id"] = resolved_case_id
    if doc is not None:
        result["document_id"] = doc.id
    return result


@analysis_router.post("/section-recommendation")
async def recommend_sections_endpoint(
    body: SectionRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Recommend BNS/IPC sections with ingredients, missing facts, and disclaimer."""
    text = body.document_text or ""
    case_id = body.case_id
    if body.document_id:
        from models import CaseDocument

        doc = await db.get(CaseDocument, body.document_id)
        if doc is None:
            raise_api_error(ErrorCode.NOT_FOUND, f"Document '{body.document_id}' not found.")
        await ensure_case_access(doc.case_id, user, db)
        if not text:
            file_bytes = await read_case_document_bytes(doc)
            text = doc.ocr_extracted_text or (file_bytes or b"").decode("utf-8", errors="replace")
        case_id = case_id or doc.case_id
    try:
        result = recommend_sections_from_text(text, show_all=body.show_all)
    except ExternalServiceUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ExternalServiceError as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    if case_id:
        result = await persist_section_recommendation(case_id, body.document_id, text, result, user["sub"], db)
    return result


@cases_router.post("/{case_id}/congruence/run")
async def run_congruence_endpoint(
    case_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Run congruence detection for one case document."""
    await ensure_case_access(case_id, user, db)
    try:
        alerts = await auto_run_congruence_for_document(case_id, document_id, user["sub"], db)
    except ExternalServiceUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ExternalServiceError as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    return {"items": alerts, "total": len(alerts)}


@cases_router.get("/{case_id}/congruence-alerts")
async def list_congruence_alerts_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list[dict]:
    """List congruence alerts for a case."""
    from models import CongruenceAlert

    await ensure_case_access(case_id, user, db)
    result = await db.execute(select(CongruenceAlert).where(CongruenceAlert.case_id == case_id))
    alerts = []
    for alert in result.scalars().all():
        alerts.append({
            "id": alert.id,
            "alert_type": alert.alert_type.value if hasattr(alert.alert_type, "value") else alert.alert_type,
            "severity": alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
            "description": alert.description,
            "excerpt_doc_a": alert.excerpt_doc_a,
            "excerpt_doc_b": alert.excerpt_doc_b,
            "is_dismissed": alert.is_dismissed,
            "feeds_model_refinement": alert.feeds_model_refinement,
        })
    return alerts


@cases_router.patch("/{case_id}/congruence-alerts/{alert_id}/dismiss")
async def dismiss_congruence_alert_endpoint(
    case_id: str,
    alert_id: str,
    body: CongruenceDismissRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Dismiss false-positive congruence alert with reason and notes."""
    await ensure_case_access(case_id, user, db)
    try:
        return await dismiss_congruence_alert(alert_id, body.reason_code, body.notes or "", user["sub"], db)
    except ValueError as exc:
        raise_api_error(ErrorCode.NOT_FOUND, str(exc))


@cases_router.post("/{case_id}/investigation-plan")
async def generate_investigation_plan_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Generate an editable case-specific investigation plan."""
    await ensure_case_access(case_id, user, db)
    try:
        return await generate_investigation_plan(case_id, user["sub"], db)
    except ExternalServiceUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ExternalServiceError as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ValueError as exc:
        raise_api_error(ErrorCode.NOT_FOUND, str(exc))


@cases_router.get("/{case_id}/investigation-plan")
async def get_investigation_plan_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return the current investigation plan for a case."""
    from models import InvestigationPlan

    await ensure_case_access(case_id, user, db)
    result = await db.execute(select(InvestigationPlan).where(InvestigationPlan.case_id == case_id))
    plan = result.scalars().first()
    if plan is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Investigation plan for case '{case_id}' not found.")
    return {
        "id": plan.id,
        "case_id": plan.case_id,
        "offence_type_detected": plan.offence_type_detected,
        "investigation_steps": plan.investigation_steps,
        "evidence_to_collect": plan.evidence_to_collect,
        "documents_to_generate": plan.documents_to_generate,
        "statutory_deadlines": plan.statutory_deadlines,
        "is_editable": plan.is_editable,
    }


@cases_router.put("/{case_id}/investigation-plan")
async def update_investigation_plan_endpoint(
    case_id: str,
    body: InvestigationPlanUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Edit an investigation plan."""
    from models import InvestigationPlan

    await ensure_case_access(case_id, user, db)
    result = await db.execute(select(InvestigationPlan).where(InvestigationPlan.case_id == case_id))
    plan = result.scalars().first()
    if plan is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Investigation plan for case '{case_id}' not found.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(plan, key, value)
    await db.flush()
    return await get_investigation_plan_endpoint(case_id, db, user)


@cases_router.get("/{case_id}/readiness")
async def case_readiness_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Run a context-aware quality/readiness check for a case using its petition document."""
    case = await ensure_case_access(case_id, user, db)

    # Find the latest Petition-type document for this case
    from models import CaseDocument, AIAnalysisResult, Citation
    result_rows = await db.execute(
        select(CaseDocument)
        .where(CaseDocument.case_id == case_id, CaseDocument.document_type == "Petition")
        .order_by(CaseDocument.created_at.desc())
        .limit(1)
    )
    doc = result_rows.scalars().first()
    if doc is None:
        return {"status": "no_petition", "message": "No petition document found for this case."}

    # Extract text from the petition document
    text = ""
    if doc.ocr_extracted_text:
        text = doc.ocr_extracted_text
    else:
        file_bytes = await read_case_document_bytes(doc)
        text = (file_bytes or b"").decode("utf-8", errors="replace")

    # Build case context from case data and petition_analysis
    case_context = {}
    if case.brief_facts:
        case_context["brief_facts"] = case.brief_facts
    if case.offence_type:
        case_context["offence_type"] = case.offence_type
    if case.date_of_occurrence:
        case_context["date_of_occurrence"] = str(case.date_of_occurrence)
    if case.petition_analysis:
        case_context["petition_analysis"] = case.petition_analysis

    offence_type = case.offence_type
    document_type = doc.document_type or "Petition"

    # Run quality check (KB checklist → keyword engine, else → LLM semantic)
    checklist_override = await _load_kb_checklist(document_type, offence_type, db)
    if checklist_override:
        qc_result = run_quality_check(
            text, document_type, offence_type,
            checklist_override=checklist_override,
            case_context=case_context,
        )
    else:
        qc_result = await asyncio.to_thread(
            run_llm_quality_check, text, document_type, offence_type, case_context,
        )

    # Persist as AIAnalysisResult
    llm_meta = qc_result.get("llm_meta", {})
    provider = llm_meta.get("provider", "keyword")
    is_semantic = qc_result.get("analysis_mode") == "semantic"

    analysis = AIAnalysisResult(
        case_id=case_id,
        document_id=doc.id,
        analysis_type="Quality_Check",
        model_name=f"{provider}:llm_semantic" if is_semantic else "IQW checklist engine",
        model_version="1.0",
        prompt_version="semantic-v1" if is_semantic else "checklist-v1",
        input_text_hash=compute_sha256(text.encode("utf-8")),
        result_json=qc_result,
        confidence_score=qc_result.get("confidence_score", 0),
        latency_ms=qc_result.get("latency_ms", 0),
        created_by=user["sub"],
    )
    db.add(analysis)
    await db.flush()
    qc_result["persisted_analysis_id"] = analysis.id

    for finding in qc_result.get("findings", []):
        citation_data = finding.get("citation") or {}
        citation = Citation(
            analysis_id=analysis.id,
            source_document_id=doc.id,
            excerpt_text=citation_data.get("excerpt"),
            char_offset_start=citation_data.get("char_start"),
            char_offset_end=citation_data.get("char_end"),
            citation_purpose=citation_data.get("purpose"),
            created_by=user["sub"],
        )
        db.add(citation)
        await db.flush()
        finding["citation"]["citation_id"] = citation.id
        finding["citation"]["source_document_id"] = doc.id

    qc_result["case_id"] = case_id
    qc_result["document_id"] = doc.id
    return qc_result


@cases_router.post("/{case_id}/judgments/analyze")
async def analyze_judgment_endpoint(
    case_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Upload and analyze a court judgment PDF/TXT up to 50 MB."""
    await ensure_case_access(case_id, user, db)
    file_bytes = await file.read()
    name = file.filename or "judgment.txt"
    if not name.lower().endswith((".pdf", ".txt")):
        raise_api_error(ErrorCode.VALIDATION_ERROR, "File type not supported. Accepted formats: PDF, TXT.", "file")
    if len(file_bytes) > 50 * 1024 * 1024:
        raise_api_error(ErrorCode.VALIDATION_ERROR, "File exceeds 50 MB limit.", "file")
    doc = await attach_document(
        case_id=case_id,
        file_name=name,
        document_type="Other",
        file_bytes=file_bytes,
        user_id=user["sub"],
        db=db,
        mime_type=file.content_type,
        upload_method="Bulk_Upload",
    )
    from models import CaseDocument

    stored = await db.get(CaseDocument, doc["id"])
    try:
        return await analyze_judgment_document(stored, user["sub"], db)
    except ExternalServiceUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ExternalServiceError as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))


# --- Document Generation Endpoints ---

from document_generator import (  # noqa: E402
    export_docx,
    export_pdf,
    generate_document,
    get_template,
    list_templates,
    sign_generated_document,
    update_generated_document,
)

templates_router = APIRouter(prefix="/templates", tags=["templates"])


@templates_router.get("/")
async def list_templates_endpoint(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list:
    """List available document templates."""
    return await list_templates(category, db=db)


@templates_router.get("/{template_id}")
async def get_template_endpoint(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Get template detail with placeholders."""
    tpl = await get_template(template_id, db=db)
    if tpl is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Template '{template_id}' not found.")
    return tpl


class GenerateDocumentRequest(BaseModel):
    template_id: str
    case_data: Optional[dict] = None


async def _case_autofill_data(case_id: str, db: AsyncSession) -> dict:
    """Build template data from case, police station, and IO profile."""
    from models import Case, PoliceStation, User

    case = await db.get(Case, case_id)
    if case is None:
        return {}
    station = await db.get(PoliceStation, case.police_station_id) if case.police_station_id else None
    io_user = await db.get(User, case.io_id) if case.io_id else None
    case_number = case.crime_no or case.petition_no or case.id
    return {
        "case_id": case.id,
        "case_number": case_number,
        "crime_no": case.crime_no,
        "petition_no": case.petition_no,
        "police_station": station.name if station else case.police_station_id,
        "io_name": io_user.full_name if io_user else case.io_id,
        "io_rank": io_user.rank if io_user else "",
        "date": time.strftime("%Y-%m-%d"),
        "brief_facts": case.brief_facts,
        "offence_type": case.offence_type or case.primary_offence_type_id,
        "accused_details": "",
    }


@cases_router.post("/{case_id}/documents/generate")
async def generate_document_endpoint(
    case_id: str,
    body: GenerateDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Generate a document from a template using case data."""
    await ensure_case_access(case_id, user, db)
    case_data = await _case_autofill_data(case_id, db)
    case_data.update(body.case_data or {})
    case_data["case_id"] = case_id
    try:
        return await generate_document(body.template_id, case_data, user["sub"], db=db)
    except ValueError as exc:
        raise_api_error(ErrorCode.NOT_FOUND, str(exc))


class UpdateGeneratedDocRequest(BaseModel):
    content: str


class SignGeneratedDocRequest(BaseModel):
    pin: Optional[str] = None


@v1_router.put("/generated-documents/{doc_id}")
async def update_generated_doc_endpoint(
    doc_id: str,
    body: UpdateGeneratedDocRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Save IO edits to generated document content."""
    await _ensure_generated_document_access(doc_id, user, db)
    try:
        return await update_generated_document(doc_id, body.content, user["sub"], db=db)
    except ValueError as exc:
        message = str(exc)
        if "read-only" in message:
            raise_api_error(ErrorCode.VALIDATION_ERROR, message)
        raise_api_error(ErrorCode.NOT_FOUND, message)


@v1_router.post("/generated-documents/{doc_id}/sign")
async def sign_generated_doc_endpoint(
    doc_id: str,
    body: SignGeneratedDocRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Apply DSC signature to a generated document."""
    await _ensure_generated_document_access(doc_id, user, db)
    try:
        return await sign_generated_document(doc_id, user["sub"], body.pin, db=db)
    except RuntimeError as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
    except ValueError as exc:
        raise_api_error(ErrorCode.VALIDATION_ERROR, str(exc))


@v1_router.get("/generated-documents/{doc_id}/export")
async def export_generated_doc_endpoint(
    doc_id: str,
    format: str = "docx",
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> JSONResponse:
    """Export generated document as DOCX or PDF."""
    import base64
    await _ensure_generated_document_access(doc_id, user, db)
    try:
        if format == "pdf":
            data = await export_pdf(doc_id, db=db)
            return JSONResponse({"format": "pdf", "data": base64.b64encode(data).decode()})
        data = await export_docx(doc_id, db=db)
        return JSONResponse({"format": "docx", "data": base64.b64encode(data).decode()})
    except ValueError as exc:
        raise_api_error(ErrorCode.NOT_FOUND, str(exc))


# --- OCR Enhancement Endpoints ---

from ocr_enhancements import (  # noqa: E402
    acknowledge_ocr,
    build_ocr_review_payload,
    detect_language_enhanced,
    get_acknowledgement_status,
    tag_segment_confidence,
)


@documents_router.post("/{document_id}/acknowledge-ocr")
async def acknowledge_ocr_endpoint(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """IO acknowledges low-confidence OCR segments."""
    await _ensure_case_document_access(document_id, user, db)
    return acknowledge_ocr(document_id, user["sub"])


@documents_router.get("/{document_id}/ocr-status")
async def get_ocr_status_endpoint(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Get OCR acknowledgement status for a document."""
    await _ensure_case_document_access(document_id, user, db)
    status = get_acknowledgement_status(document_id)
    return status or {"document_id": document_id, "acknowledged": False}


@documents_router.get("/{document_id}/ocr-review")
async def get_ocr_review_endpoint(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict:
    """Return original/extracted/translation panes with segment confidence tags."""
    from models import CaseDocument

    doc = await db.get(CaseDocument, document_id)
    if doc is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Document '{document_id}' not found.")
    await ensure_case_access(doc.case_id, user, db)
    text = doc.ocr_extracted_text
    file_bytes = await read_case_document_bytes(doc) if not text else None
    if not text and file_bytes:
        mime_type = infer_mime_type(doc.file_name, doc.mime_type)
        if is_document_ai_supported_mime(mime_type):
            try:
                ocr_result = run_configured_ocr(
                    file_bytes,
                    file_name=doc.file_name,
                    mime_type=mime_type,
                )
                text = ocr_result.text
                doc.ocr_extracted_text = text
                doc.ocr_status = "Completed"
            except ExternalServiceUnavailable as exc:
                raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, str(exc))
            except ExternalServiceError as exc:
                raise_api_error(ErrorCode.SERVER_ERROR, str(exc))
        else:
            text = file_bytes.decode("utf-8", errors="replace")
    payload = build_ocr_review_payload(document_id, text or "", doc.file_name)
    doc.language_detected = payload["language"]["language"]
    if payload["segments"]:
        doc.ocr_confidence = "Low" if payload["requires_acknowledgement"] else payload["segments"][0]["confidence"]
    doc.ocr_status = "Completed"
    await db.flush()
    return payload


# --- Knowledge Search Endpoints ---

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge-search"])


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class AIQueryRequest(BaseModel):
    query: str
    kb: str = "policy"
    top_k: int = 8
    case_id: Optional[str] = None


@knowledge_router.post("/policy/search")
async def knowledge_policy_search(
    body: KnowledgeSearchRequest,
    current_user: dict = Depends(require_auth),
) -> dict:
    """Search the Policy KB (BNS/BNSS/BSA statutes + MHA policy docs)."""
    from kis_client import KB_POLICY, KISClientError, KISUnavailable, get_kis_client, is_kis_configured, get_multi_kb_config

    multi = get_multi_kb_config()
    if not is_kis_configured(multi.policy):
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, "Policy knowledge base is not configured.")
    try:
        client = get_kis_client(KB_POLICY)
        results = client.hybrid_search(body.query, top_k=body.top_k)
        return {"kb": "policy", "query": body.query, "results": results}
    except KISUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"Policy KB unavailable: {exc}")
    except KISClientError as exc:
        raise_api_error(ErrorCode.SERVER_ERROR, f"Policy KB error: {exc}")


@knowledge_router.post("/cases/search")
async def knowledge_cases_search(
    body: KnowledgeSearchRequest,
    current_user: dict = Depends(require_auth),
) -> dict:
    """Search the Cases KB (case documents + metadata)."""
    from kis_client import KB_CASES, KISClientError, KISUnavailable, get_kis_client, is_kis_configured, get_multi_kb_config

    multi = get_multi_kb_config()
    if not is_kis_configured(multi.cases):
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, "Cases knowledge base is not configured.")
    try:
        client = get_kis_client(KB_CASES)
        results = client.hybrid_search(body.query, top_k=body.top_k)
        return {"kb": "cases", "query": body.query, "results": results}
    except KISUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"Cases KB unavailable: {exc}")
    except KISClientError as exc:
        raise_api_error(ErrorCode.SERVER_ERROR, f"Cases KB error: {exc}")


@knowledge_router.get("/status")
async def knowledge_status(
    current_user: dict = Depends(require_auth),
) -> dict:
    """Return configuration status for both knowledge bases."""
    from kis_client import is_kis_configured, get_multi_kb_config, kis_status

    multi = get_multi_kb_config()
    return {
        "policy": {
            "configured": is_kis_configured(multi.policy),
            **kis_status(multi.policy),
        },
        "cases": {
            "configured": is_kis_configured(multi.cases),
            **kis_status(multi.cases),
        },
    }


@knowledge_router.post("/ai-query")
async def knowledge_ai_query(
    body: AIQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
) -> dict:
    """AI-powered Q&A over a knowledge base.

    1. Search the specified KB for relevant context
    2. Feed the search results + user question to the LLM
    3. Return a synthesized answer with source citations
    """
    from kis_client import (
        KB_POLICY, KB_CASES,
        KISClientError, KISUnavailable,
        get_kis_client, is_kis_configured, get_multi_kb_config,
    )

    kb_name = body.kb.lower()
    if kb_name not in (KB_POLICY, KB_CASES):
        raise_api_error(ErrorCode.VALIDATION_ERROR, f"kb must be 'policy' or 'cases', got '{body.kb}'", field="kb")

    multi = get_multi_kb_config()
    config = multi.policy if kb_name == KB_POLICY else multi.cases
    if not is_kis_configured(config):
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"{kb_name.title()} knowledge base is not configured.")

    # Step 1: Search the KB for relevant context
    try:
        client = get_kis_client(kb_name)
        search_results = client.hybrid_search(body.query, top_k=body.top_k)
    except KISUnavailable as exc:
        raise_api_error(ErrorCode.SERVICE_UNAVAILABLE, f"{kb_name.title()} KB unavailable: {exc}")
    except KISClientError as exc:
        raise_api_error(ErrorCode.SERVER_ERROR, f"{kb_name.title()} KB error: {exc}")

    # Extract context snippets from search results
    items = search_results.get("items") or search_results.get("results") or []
    if isinstance(search_results, dict) and not items:
        # Try nested structure
        for key in ("items", "results"):
            nested = search_results.get(key)
            if isinstance(nested, list) and nested:
                items = nested
                break

    context_parts = []
    sources = []
    for i, item in enumerate(items[:body.top_k]):
        title = item.get("title") or item.get("source_title") or f"Source {i + 1}"
        text = item.get("text") or item.get("content") or item.get("snippet") or ""
        score = item.get("score")
        uri = item.get("source_uri") or item.get("citation") or ""
        if text:
            context_parts.append(f"[Source {i + 1}: {title}]\n{text}")
            sources.append({
                "index": i + 1,
                "title": title,
                "score": score,
                "source_uri": uri,
                "excerpt": text[:300] if len(text) > 300 else text,
            })

    # Build case context if applicable
    case_context = ""
    if body.case_id and kb_name == KB_CASES:
        try:
            case = await get_case(body.case_id, current_user, db)
            if case:
                case_context = (
                    f"\nCase context: Crime No {case.get('crime_no', 'N/A')}, "
                    f"Type: {case.get('case_type', 'N/A')}, "
                    f"Status: {case.get('status', 'N/A')}, "
                    f"Facts: {(case.get('brief_facts') or 'N/A')[:500]}"
                )
        except Exception:
            pass  # Case context is optional

    # Step 2: Send to LLM for synthesis
    if kb_name == KB_POLICY:
        system_prompt = (
            "You are a legal knowledge assistant for Indian police officers. "
            "Answer questions about BNS (Bharatiya Nyaya Sanhita), BNSS (Bharatiya Nagarik Suraksha Sanhita), "
            "BSA (Bharatiya Sakshya Adhiniyam), and MHA policy documents. "
            "Use ONLY the provided source excerpts to answer. Cite source numbers in your answer. "
            "If the sources do not contain enough information, say so clearly. "
            "Be precise, cite section numbers, and note any caveats. "
            "Return JSON with keys: answer (string), confidence (high/medium/low), "
            "cited_sources (array of source indices), follow_up_suggestions (array of strings)."
        )
    else:
        system_prompt = (
            "You are an investigation assistant for Indian police officers. "
            "Answer questions about case documents, evidence, witness statements, and investigation status. "
            "Use ONLY the provided source excerpts to answer. Cite source numbers in your answer. "
            "Be factual and precise. Do not speculate beyond what the sources state. "
            "Return JSON with keys: answer (string), confidence (high/medium/low), "
            "cited_sources (array of source indices), follow_up_suggestions (array of strings)."
        )

    context_text = "\n\n".join(context_parts) if context_parts else "No relevant sources found in the knowledge base."
    user_prompt = json.dumps({
        "question": body.query,
        "knowledge_base_context": context_text,
        "case_context": case_context or None,
    }, ensure_ascii=False)

    try:
        from ai_workflows import _llm_json
        data, meta = _llm_json(system_prompt, json.loads(user_prompt), task="ai_knowledge_query")
    except (ExternalServiceUnavailable, ExternalServiceError) as exc:
        # LLM unavailable — return search results only with a stub answer
        return {
            "query": body.query,
            "kb": kb_name,
            "answer": "AI answer generation is not available. Review the source results below.",
            "confidence": "low",
            "cited_sources": list(range(1, len(sources) + 1)),
            "follow_up_suggestions": [],
            "sources": sources,
            "llm_provider": "unavailable",
            "llm_mode": "search_only",
        }

    if data is None:
        data = {
            "answer": "AI answer generation is not configured. Review the source results below.",
            "confidence": "low",
            "cited_sources": list(range(1, len(sources) + 1)),
            "follow_up_suggestions": [],
        }

    return {
        "query": body.query,
        "kb": kb_name,
        "answer": data.get("answer", ""),
        "confidence": data.get("confidence", "medium"),
        "cited_sources": data.get("cited_sources", []),
        "follow_up_suggestions": data.get("follow_up_suggestions", []),
        "sources": sources,
        "llm_provider": meta.get("provider", "unknown"),
        "llm_mode": meta.get("mode", "unknown"),
    }


@admin_router.post("/kis/policy-sync:trigger")
async def kis_policy_sync_trigger(
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Trigger sync from RAG-app PostgreSQL into KIS Policy KB."""
    from kis_policy_sync import sync_policy_kb

    try:
        result = await sync_policy_kb()
        return {"status": "completed", **result.to_dict()}
    except ValueError as exc:
        raise_api_error(ErrorCode.VALIDATION_ERROR, str(exc))
    except Exception as exc:
        raise_api_error(ErrorCode.SERVER_ERROR, f"Policy sync failed: {exc}")


@admin_router.post("/section-recommendation:batch-reprocess")
async def batch_section_recommendation_endpoint(
    limit: int = 500,
    concurrency: int = 3,
    dry_run: bool = False,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Batch-reprocess documents that lack BNS section recommendations."""
    return await batch_recommend_sections(
        limit=limit,
        concurrency=concurrency,
        dry_run=dry_run,
        user_id=current_user["sub"],
    )


@admin_router.post("/parse:batch-reparse")
async def batch_reparse_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Re-run the full OCR + parse pipeline on existing parse records.

    Retrieves original files from object storage, re-processes through
    Document AI OCR, re-parses, and updates records in-place. Useful after
    parser logic changes (e.g. confidence scoring fixes).
    """
    import logging

    from app import (
        _detect_mime_type,
        _extract_completeness_score,
        enrich_parsed_output_with_checklist,
        get_doc_ai_config,
    )
    from complaint_parsing import parse_document, process_document_bytes
    from external_interfaces import get_object_bytes

    logger = logging.getLogger(__name__)

    try:
        config = get_doc_ai_config()
    except RuntimeError as exc:
        raise_api_error(ErrorCode.SERVER_ERROR, f"Document AI configuration unavailable: {exc}")

    engine = await get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(
                    parse_records.c.id,
                    parse_records.c.file_name,
                    parse_records.c.file_storage_uri,
                )
                .where(parse_records.c.file_storage_uri.isnot(None))
                .order_by(parse_records.c.created_at.asc())
                .limit(limit)
            )
        ).fetchall()

    total = len(rows)
    reparsed = 0
    errors: list[dict] = []

    for row in rows:
        record_id = row[0]
        file_name = row[1]
        file_storage_uri = row[2]
        try:
            # Retrieve original file
            content = await get_object_bytes(file_storage_uri)

            # Detect MIME type from filename
            detected_mime = _detect_mime_type(file_name, "")
            if not detected_mime:
                detected_mime = "application/pdf"

            # OCR via Document AI
            ocr_result = await asyncio.to_thread(
                process_document_bytes,
                project_id=str(config["DOC_AI_PROJECT_ID"]),
                location=str(config["DOC_AI_LOCATION"]),
                processor_id=str(config["DOC_AI_PROCESSOR_ID"]),
                content=content,
                mime_type=detected_mime,
                field_mask=config["DOC_AI_FIELD_MASK"],
                credentials=config.get("_credentials"),
            )
            raw_text = ocr_result.document.text or ""

            # Parse
            parsed_output = await asyncio.to_thread(parse_document, raw_text)

            # Enrich with checklist
            parsed_output = await enrich_parsed_output_with_checklist(parsed_output)

            # Extract metadata
            detected_format = (
                parsed_output.get("meta", {}).get("detected_format")
                if isinstance(parsed_output, dict)
                else None
            ) or "UNKNOWN"
            completeness = _extract_completeness_score(parsed_output)

            # Update record in-place
            async with engine.begin() as conn:
                await conn.execute(
                    parse_records.update()
                    .where(parse_records.c.id == record_id)
                    .values(
                        parsed_output=parsed_output,
                        completeness_score=completeness,
                        document_format=detected_format,
                        kis_index_status="pending",
                    )
                )

            reparsed += 1
        except Exception as exc:
            logger.warning("batch-reparse failed for record %s: %s", record_id, exc, exc_info=True)
            errors.append({"id": record_id, "error": str(exc)})

    return {
        "total": total,
        "reparsed": reparsed,
        "failed": len(errors),
        "errors": errors,
    }


@admin_router.post("/parse:batch-re-enrich-checklist")
async def batch_re_enrich_checklist_endpoint(
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Re-run checklist enrichment on existing parse records.

    Lightweight alternative to batch-reparse: does not re-OCR or re-parse,
    just re-evaluates the checklist against the existing parsed_output.
    Use after checklist question fixes (e.g. duplicate removal).
    """
    import logging

    from app import _extract_completeness_score, enrich_parsed_output_with_checklist

    logger = logging.getLogger(__name__)

    engine = await get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(
                    parse_records.c.id,
                    parse_records.c.parsed_output,
                )
                .where(parse_records.c.parsed_output.isnot(None))
                .order_by(parse_records.c.created_at.asc())
                .limit(limit)
            )
        ).fetchall()

    total = len(rows)
    enriched_count = 0
    errors: list[dict] = []

    for row in rows:
        record_id = row[0]
        parsed_output = row[1]
        try:
            if not isinstance(parsed_output, dict):
                continue

            updated = await enrich_parsed_output_with_checklist(parsed_output)
            completeness = _extract_completeness_score(updated)

            async with engine.begin() as conn:
                await conn.execute(
                    parse_records.update()
                    .where(parse_records.c.id == record_id)
                    .values(
                        parsed_output=updated,
                        completeness_score=completeness,
                    )
                )
            enriched_count += 1
        except Exception as exc:
            logger.warning("batch-re-enrich failed for record %s: %s", record_id, exc, exc_info=True)
            errors.append({"id": record_id, "error": str(exc)})

    return {
        "total": total,
        "enriched": enriched_count,
        "failed": len(errors),
        "errors": errors,
    }


@admin_router.post("/parse:batch-enrich-bns")
async def batch_enrich_bns_endpoint(
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Backfill statutory_text and applicability_rank on existing BNS sections.

    Lightweight pass: reads each parse record's proposed_bns_sections,
    adds statutory_text from the built-in BNS_STATUTORY_TEXTS dict, and
    assigns applicability_rank by confidence_score descending.
    """
    import logging

    from complaint_parsing import BNS_STATUTORY_TEXTS

    logger = logging.getLogger(__name__)

    engine = await get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(
                    parse_records.c.id,
                    parse_records.c.parsed_output,
                )
                .where(parse_records.c.parsed_output.isnot(None))
                .order_by(parse_records.c.created_at.asc())
                .limit(limit)
            )
        ).fetchall()

    total = len(rows)
    enriched_count = 0
    skipped_count = 0
    errors: list[dict] = []

    for row in rows:
        record_id = row[0]
        parsed_output = row[1]
        try:
            if not isinstance(parsed_output, dict):
                skipped_count += 1
                continue
            fir_draft = parsed_output.get("fir_draft")
            if not isinstance(fir_draft, dict):
                skipped_count += 1
                continue
            sections = fir_draft.get("proposed_bns_sections")
            if not isinstance(sections, list) or not sections:
                skipped_count += 1
                continue

            changed = False
            # Sort by confidence descending and assign ranks
            ranked = sorted(sections, key=lambda s: -(float(s.get("confidence_score") or 0)))
            for idx, section in enumerate(ranked):
                if not section.get("applicability_rank"):
                    section["applicability_rank"] = idx + 1
                    changed = True
                if not section.get("statutory_text"):
                    base_code = (section.get("section") or "").split("(")[0]
                    text = BNS_STATUTORY_TEXTS.get(base_code)
                    if text:
                        section["statutory_text"] = text
                        changed = True
                section.setdefault("ingredient_mapping", [])

            if not changed:
                skipped_count += 1
                continue

            fir_draft["proposed_bns_sections"] = sections
            async with engine.begin() as conn:
                await conn.execute(
                    parse_records.update()
                    .where(parse_records.c.id == record_id)
                    .values(parsed_output=parsed_output)
                )
            enriched_count += 1
        except Exception as exc:
            logger.warning("batch-enrich-bns failed for record %s: %s", record_id, exc, exc_info=True)
            errors.append({"id": record_id, "error": str(exc)})

    return {
        "total": total,
        "enriched": enriched_count,
        "skipped": skipped_count,
        "failed": len(errors),
        "errors": errors,
    }


@v1_router.get("/health")
async def v1_health() -> dict[str, str]:
    """V1 API health check."""
    return {"status": "ok", "version": "1.0.0"}


# Mount sub-routers
v1_router.include_router(auth_router)
v1_router.include_router(cases_router)
v1_router.include_router(analysis_router)
v1_router.include_router(documents_router)
v1_router.include_router(admin_router)
v1_router.include_router(analytics_router)
v1_router.include_router(senior_dashboard_router)
v1_router.include_router(audit_log_router)
v1_router.include_router(notifications_router)
v1_router.include_router(police_stations_router)
v1_router.include_router(offence_types_router)
v1_router.include_router(templates_router)
v1_router.include_router(knowledge_router)
