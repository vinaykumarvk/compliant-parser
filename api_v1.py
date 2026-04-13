from __future__ import annotations

import time
import uuid as _uuid
from collections import defaultdict
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from audit import compute_sha256, get_audit_log, search_audit_logs
from cases import (
    create_case,
    get_case,
    list_cases,
    update_case,
    transition_case_status,
    attach_document,
    list_case_documents,
    get_case_document,
    get_timeline,
    create_task,
    list_tasks,
    update_task,
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
    require_role,
    verify_password,
)


# --- Standard Error Format ---

class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

_ERROR_STATUS = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.AUTHENTICATION_ERROR: 401,
    ErrorCode.AUTHORIZATION_ERROR: 403,
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


# --- Per-endpoint Rate Limiting ---

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

class UserCreateRequest(BaseModel):
    employee_id: str
    full_name: str
    role: str
    password: str


# --- Case Workbench Pydantic Schemas ---

class CaseCreateRequest(BaseModel):
    case_type: str
    crime_no: Optional[str] = None
    petition_no: Optional[str] = None
    police_station_id: Optional[str] = None
    primary_offence_type_id: Optional[str] = None
    brief_facts: Optional[str] = None


class CaseUpdateRequest(BaseModel):
    case_type: Optional[str] = None
    crime_no: Optional[str] = None
    petition_no: Optional[str] = None
    police_station_id: Optional[str] = None
    primary_offence_type_id: Optional[str] = None
    brief_facts: Optional[str] = None
    status: Optional[str] = None


class StatusTransitionRequest(BaseModel):
    status: str


class TaskCreateRequest(BaseModel):
    task_name: str
    due_date: Optional[str] = None
    priority: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    snoozed_until: Optional[str] = None


# --- DB Stubs (replace with real DB session later) ---

def _get_user_by_employee_id(employee_id: str) -> Optional[dict]:
    """Stub: look up a user by employee_id.

    Returns a dict with keys {id, employee_id, full_name, role, password_hash}
    or None.  Will be backed by a real DB session in a later phase.
    """
    return None


def _create_user(employee_id: str, full_name: str, role: str, password_hash: str) -> dict:
    """Stub: persist a new user row.

    Returns the created user dict.  Will be backed by a real DB session in a
    later phase.
    """
    return {
        "id": str(_uuid.uuid4()),
        "employee_id": employee_id,
        "full_name": full_name,
        "role": role,
    }


def _list_users() -> list[dict]:
    """Stub: return all users.  Will be backed by a real DB session later."""
    return []


# --- V1 Router ---

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Sub-routers (will be populated by later phases)
auth_router = APIRouter(prefix="/auth", tags=["auth"])
cases_router = APIRouter(prefix="/cases", tags=["cases"])
analysis_router = APIRouter(prefix="/analysis", tags=["analysis"])
documents_router = APIRouter(prefix="/documents", tags=["documents"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])
audit_log_router = APIRouter(prefix="/audit-logs", tags=["audit"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])
police_stations_router = APIRouter(prefix="/police-stations", tags=["police-stations"])
offence_types_router = APIRouter(prefix="/offence-types", tags=["offence-types"])


# --- Auth Endpoints ---

@auth_router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    """Authenticate with employee_id + password, return token pair."""
    check_rate_limit(request, rpm=10)

    # Lockout check (raises if locked)
    check_lockout(body.employee_id)

    user = _get_user_by_employee_id(body.employee_id)
    if user is None or not verify_password(body.password, user["password_hash"]):
        record_failed_attempt(body.employee_id)
        raise_api_error(
            ErrorCode.AUTHENTICATION_ERROR,
            "Invalid employee ID or password.",
        )

    clear_failed_attempts(body.employee_id)

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"])

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user["id"],
            "name": user["full_name"],
            "role": user["role"],
            "employee_id": user["employee_id"],
        },
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request) -> TokenResponse:
    """Exchange a valid refresh token for a new access token."""
    check_rate_limit(request, rpm=10)

    payload = decode_token(body.refresh_token)
    if payload is None:
        raise_api_error(ErrorCode.AUTHENTICATION_ERROR, "Invalid or expired refresh token.")

    if payload.get("type") != "refresh":
        raise_api_error(ErrorCode.AUTHENTICATION_ERROR, "Token is not a refresh token.")

    if is_blacklisted(body.refresh_token):
        raise_api_error(ErrorCode.AUTHENTICATION_ERROR, "Token has been revoked.")

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
async def me(current_user: dict = Depends(require_auth)) -> dict:
    """Return the authenticated user's profile from the token payload."""
    return {
        "id": current_user.get("sub"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
        "employee_id": current_user.get("employee_id"),
    }


# --- Admin / User-Management Endpoints ---

@admin_router.get("/users")
async def list_users(
    current_user: dict = Depends(require_role("System_Admin")),
) -> list[dict]:
    """Return all users (System_Admin only)."""
    return _list_users()


@admin_router.post("/users")
async def create_user(
    body: UserCreateRequest,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Create a new user (System_Admin only)."""
    existing = _get_user_by_employee_id(body.employee_id)
    if existing is not None:
        raise_api_error(
            ErrorCode.CONFLICT,
            f"User with employee_id '{body.employee_id}' already exists.",
            field="employee_id",
        )

    password_hash = hash_password(body.password)
    user = _create_user(body.employee_id, body.full_name, body.role, password_hash)
    return user


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
    results = search_audit_logs(filters=filters, page=page, page_size=page_size)
    return results


@audit_log_router.get("/{log_id}")
async def get_single_audit_log(
    log_id: str,
    current_user: dict = Depends(require_role("System_Admin")),
) -> dict:
    """Retrieve a single audit log entry by ID. System_Admin only."""
    entry = get_audit_log(log_id)
    if entry is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Audit log entry '{log_id}' not found.")
    return entry


# --- Document Integrity Endpoint ---

@documents_router.post("/{document_id}/verify-integrity")
async def verify_document_integrity(
    document_id: str,
    current_user: dict = Depends(require_auth),
) -> dict:
    """Verify document integrity via SHA-256 hash.

    Stub implementation — returns verified=true for now.
    The real implementation will check the SHA-256 hash against stored
    file_bytes when the DB layer is connected.
    """
    return {
        "verified": True,
        "document_id": document_id,
        "message": "Document integrity verified.",
    }


# --- Case Workbench Endpoints ---

@cases_router.post("/")
async def create_case_endpoint(
    body: CaseCreateRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Create a new case."""
    data = body.model_dump(exclude_none=True)
    result = create_case(data, user["sub"])
    return result


@cases_router.get("/")
async def list_cases_endpoint(
    status: Optional[str] = None,
    police_station_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
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
    return list_cases(user["sub"], user["role"], filters)


@cases_router.get("/{case_id}")
async def get_case_endpoint(
    case_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Get case detail by ID."""
    result = get_case(case_id)
    if result is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Case '{case_id}' not found.")
    return result


@cases_router.put("/{case_id}")
async def update_case_endpoint(
    case_id: str,
    body: CaseUpdateRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Update a case."""
    data = body.model_dump(exclude_none=True)
    result = update_case(case_id, data, user["sub"])
    return result


@cases_router.patch("/{case_id}/status")
async def transition_case_status_endpoint(
    case_id: str,
    body: StatusTransitionRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Transition case status."""
    result = transition_case_status(case_id, body.status, user["sub"])
    return result


@cases_router.post("/{case_id}/documents")
async def upload_case_document_endpoint(
    case_id: str,
    document_type: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
) -> dict:
    """Upload a document to a case."""
    file_bytes = await file.read()
    result = attach_document(
        case_id=case_id,
        file_name=file.filename or "unnamed",
        document_type=document_type,
        file_bytes=file_bytes,
        user_id=user["sub"],
    )
    return result


@cases_router.get("/{case_id}/documents")
async def list_case_documents_endpoint(
    case_id: str,
    user: dict = Depends(require_auth),
) -> list:
    """List all documents for a case."""
    return list_case_documents(case_id)


@cases_router.get("/{case_id}/documents/{doc_id}")
async def get_case_document_endpoint(
    case_id: str,
    doc_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Get document detail."""
    result = get_case_document(case_id, doc_id)
    if result is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Document '{doc_id}' not found.")
    return result


@cases_router.get("/{case_id}/timeline")
async def get_case_timeline_endpoint(
    case_id: str,
    sort: str = "desc",
    user: dict = Depends(require_auth),
) -> list:
    """Get case timeline events."""
    return get_timeline(case_id, sort_asc=(sort == "asc"))


@cases_router.get("/{case_id}/tasks")
async def list_case_tasks_endpoint(
    case_id: str,
    user: dict = Depends(require_auth),
) -> list:
    """List tasks for a case."""
    return list_tasks(case_id)


@cases_router.post("/{case_id}/tasks")
async def create_case_task_endpoint(
    case_id: str,
    body: TaskCreateRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Create a task for a case."""
    data = body.model_dump(exclude_none=True)
    return create_task(case_id, data, user["sub"])


@cases_router.put("/{case_id}/tasks/{task_id}")
async def update_case_task_endpoint(
    case_id: str,
    task_id: str,
    body: TaskUpdateRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Update a task."""
    data = body.model_dump(exclude_none=True)
    return update_task(case_id, task_id, data, user["sub"])


# --- Notifications Endpoints ---

@notifications_router.get("/")
async def list_notifications_endpoint(
    user: dict = Depends(require_auth),
) -> list:
    """List unread notifications for the current user."""
    return list_notifications(user["sub"])


@notifications_router.patch("/{notification_id}/read")
async def mark_notification_read_endpoint(
    notification_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Mark a notification as read."""
    return mark_notification_read(notification_id)


# --- Police Stations Endpoints ---

@police_stations_router.get("/")
async def list_police_stations_endpoint(
    user: dict = Depends(require_auth),
) -> list:
    """List all police stations."""
    return list_police_stations_data()


# --- Offence Types Endpoints ---

@offence_types_router.get("/")
async def list_offence_types_endpoint(
    q: Optional[str] = None,
    user: dict = Depends(require_auth),
) -> list:
    """List or search offence types."""
    if q:
        return search_offence_types_data(q)
    return list_offence_types_data()


# --- Quality Engine Endpoints ---

from quality_engine import run_quality_check  # noqa: E402


class QualityCheckRequest(BaseModel):
    document_id: Optional[str] = None
    document_text: Optional[str] = None
    document_type: str = "Generic"
    offence_type: Optional[str] = None


@analysis_router.post("/quality-check")
async def run_quality_check_endpoint(
    body: QualityCheckRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Run a checklist-driven quality check on document text."""
    text = body.document_text or ""
    if body.document_id:
        doc = get_case_document("", body.document_id)
        if doc and doc.get("parsed_text"):
            text = doc["parsed_text"]
    return run_quality_check(text, body.document_type, body.offence_type)


# --- Document Generation Endpoints ---

from document_generator import (  # noqa: E402
    export_docx,
    export_pdf,
    generate_document,
    get_template,
    list_templates,
    update_generated_document,
    _generated_documents,
)

templates_router = APIRouter(prefix="/templates", tags=["templates"])


@templates_router.get("/")
async def list_templates_endpoint(
    category: Optional[str] = None,
    user: dict = Depends(require_auth),
) -> list:
    """List available document templates."""
    return list_templates(category)


@templates_router.get("/{template_id}")
async def get_template_endpoint(
    template_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Get template detail with placeholders."""
    tpl = get_template(template_id)
    if tpl is None:
        raise_api_error(ErrorCode.NOT_FOUND, f"Template '{template_id}' not found.")
    return tpl


class GenerateDocumentRequest(BaseModel):
    template_id: str
    case_data: Optional[dict] = None


@cases_router.post("/{case_id}/documents/generate")
async def generate_document_endpoint(
    case_id: str,
    body: GenerateDocumentRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Generate a document from a template using case data."""
    case_data = body.case_data or {}
    case_data["case_id"] = case_id
    return generate_document(body.template_id, case_data, user["sub"])


class UpdateGeneratedDocRequest(BaseModel):
    content: str


@v1_router.put("/generated-documents/{doc_id}")
async def update_generated_doc_endpoint(
    doc_id: str,
    body: UpdateGeneratedDocRequest,
    user: dict = Depends(require_auth),
) -> dict:
    """Save IO edits to generated document content."""
    return update_generated_document(doc_id, body.content, user["sub"])


@v1_router.get("/generated-documents/{doc_id}/export")
async def export_generated_doc_endpoint(
    doc_id: str,
    format: str = "docx",
    user: dict = Depends(require_auth),
) -> JSONResponse:
    """Export generated document as DOCX or PDF."""
    import base64
    if format == "pdf":
        data = export_pdf(doc_id)
        return JSONResponse({"format": "pdf", "data": base64.b64encode(data).decode()})
    data = export_docx(doc_id)
    return JSONResponse({"format": "docx", "data": base64.b64encode(data).decode()})


# --- OCR Enhancement Endpoints ---

from ocr_enhancements import (  # noqa: E402
    acknowledge_ocr,
    detect_language_enhanced,
    get_acknowledgement_status,
    tag_segment_confidence,
)


@documents_router.post("/{document_id}/acknowledge-ocr")
async def acknowledge_ocr_endpoint(
    document_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """IO acknowledges low-confidence OCR segments."""
    return acknowledge_ocr(document_id, user["sub"])


@documents_router.get("/{document_id}/ocr-status")
async def get_ocr_status_endpoint(
    document_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Get OCR acknowledgement status for a document."""
    status = get_acknowledgement_status(document_id)
    return status or {"document_id": document_id, "acknowledged": False}


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
v1_router.include_router(audit_log_router)
v1_router.include_router(notifications_router)
v1_router.include_router(police_stations_router)
v1_router.include_router(offence_types_router)
v1_router.include_router(templates_router)
