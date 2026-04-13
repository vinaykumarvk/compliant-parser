from __future__ import annotations

"""Case management service layer for the IQW platform.

Async SQLAlchemy ORM implementation.  Every public function returns plain
dicts so the API layer can serialise them directly.
"""

import re
import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from audit import compute_sha256
from models import (
    Case, CaseDocument, CaseActivity, ActionTrackerTask,
    Notification, PoliceStation, OffenceType,
)


# ---------------------------------------------------------------------------
# Lazy import helper (avoids circular deps with api_v1)
# ---------------------------------------------------------------------------

def _api_error(code: str, message: str, field: Optional[str] = None) -> None:
    from api_v1 import ErrorCode, raise_api_error
    raise_api_error(ErrorCode(code), message, field)


# ---------------------------------------------------------------------------
# Deprecated in-memory stubs — kept for backward compat with tests that
# import them.  No longer used by service functions.
# ---------------------------------------------------------------------------

_cases: Dict[str, dict] = {}               # DEPRECATED — use ORM
_case_documents: Dict[str, dict] = {}      # DEPRECATED — use ORM
_case_activities: Dict[str, dict] = {}     # DEPRECATED — use ORM
_action_tracker_tasks: Dict[str, dict] = {}  # DEPRECATED — use ORM
_notifications: Dict[str, dict] = {}       # DEPRECATED — use ORM
_police_stations: Dict[str, dict] = {}     # DEPRECATED — use ORM
_offence_types: Dict[str, dict] = {}       # DEPRECATED — use ORM


# ---------------------------------------------------------------------------
# Status state machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: Dict[str, List[str]] = {
    "Open": ["Under_Investigation"],
    "Under_Investigation": ["Charge_Sheet_Filed", "Closed", "Transferred"],
    "Charge_Sheet_Filed": ["Closed"],
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_CRIME_NO_RE = re.compile(r"^\d{4}/\d{4}$")
_PETITION_NO_RE = re.compile(r"^PET/[A-Z]{2,10}/\d{4}/\d{4}$")


def validate_crime_no(crime_no: str) -> bool:
    """Return True when *crime_no* matches NNNN/YYYY."""
    return bool(_CRIME_NO_RE.match(crime_no))


def validate_petition_no(petition_no: str) -> bool:
    """Return True when *petition_no* matches PET/PS/YYYY/NNNN."""
    return bool(_PETITION_NO_RE.match(petition_no))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# ORM → dict helper
# ---------------------------------------------------------------------------

def _to_dict(obj, key_map: Optional[dict] = None) -> dict:
    """Convert ORM model to plain dict, applying optional key renames."""
    from sqlalchemy import inspect as sa_inspect
    result = {}
    for attr in sa_inspect(type(obj)).column_attrs:
        key = attr.key
        val = getattr(obj, key)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif hasattr(val, 'value'):  # Enum
            val = val.value
        elif isinstance(val, date) and not isinstance(val, datetime):
            val = val.isoformat()
        out_key = key_map.get(key, key) if key_map else key
        result[out_key] = val
    return result


# Key-rename maps for models whose ORM column names differ from the legacy
# dict keys that the API layer expects.

_DOCUMENT_KEY_MAP = {
    "sha256_hash": "sha256",
    "file_size_bytes": "size_bytes",
    "created_by": "uploaded_by",
    "created_at": "uploaded_at",
}

_POLICE_STATION_KEY_MAP = {
    "station_code": "code",
}


# ---------------------------------------------------------------------------
# Case CRUD
# ---------------------------------------------------------------------------

async def create_case(data: dict, user_id: str, db: AsyncSession) -> dict:
    """Create a new case after validating crime/petition numbers."""
    crime_no = data.get("crime_no", "")
    if crime_no and not validate_crime_no(crime_no):
        _api_error("VALIDATION_ERROR", "Invalid Crime No. format. Expected NNNN/YYYY.", "crime_no")

    petition_no = data.get("petition_no", "")
    if petition_no and not validate_petition_no(petition_no):
        _api_error("VALIDATION_ERROR", "Invalid Petition No. format. Expected PET/PS/YYYY/NNNN.", "petition_no")

    case = Case(
        case_type=data.get("case_type", "FIR"),
        crime_no=crime_no,
        petition_no=petition_no,
        brief_facts=data.get("brief_facts", ""),
        offence_type=data.get("offence_type", ""),
        police_station_id=data.get("police_station_id", ""),
        primary_offence_type_id=data.get("primary_offence_type_id"),
        secondary_offence_type_ids=data.get("secondary_offence_type_ids", []),
        status="Open",
        cctns_sync_status="Pending",
        created_by=user_id,
        io_id=data.get("io_id", user_id),
    )
    db.add(case)
    await db.flush()  # assigns id

    await add_activity(case.id, "Case_Created", user_id, "Case registered and opened.", db=db)
    return _to_dict(case)


async def get_case(case_id: str, db: AsyncSession) -> Optional[dict]:
    """Return a single case or None."""
    result = await db.get(Case, case_id)
    return _to_dict(result) if result else None


async def list_cases(user_id: str, role: str, filters: Optional[dict] = None, *, db: AsyncSession) -> dict:
    """List cases visible to the caller with pagination.

    IO sees only own cases; System_Admin / Admin sees all.
    Filters: status, police_station_id, date_from, date_to, page, page_size.
    Returns: {"items": [...], "total": N, "page": P, "page_size": S}
    """
    stmt = select(Case).where(Case.is_deleted == False)  # noqa: E712

    if role not in ("System_Admin", "Admin"):
        stmt = stmt.where(Case.io_id == user_id)

    if filters:
        if filters.get("status"):
            stmt = stmt.where(Case.status == filters["status"])
        if filters.get("police_station_id"):
            stmt = stmt.where(Case.police_station_id == filters["police_station_id"])
        if filters.get("date_from"):
            stmt = stmt.where(Case.created_at >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(Case.created_at <= filters["date_to"])

    stmt = stmt.order_by(Case.created_at.desc())

    # total count
    count_stmt = select(sa.func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # paginate
    page = int((filters or {}).get("page", 1))
    page_size = int((filters or {}).get("page_size", 20))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    items = [_to_dict(c) for c in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def update_case(case_id: str, data: dict, user_id: str, db: AsyncSession) -> dict:
    """Update mutable fields on an existing case."""
    case = await db.get(Case, case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    mutable = ("brief_facts", "offence_type", "police_station_id",
               "primary_offence_type_id", "secondary_offence_type_ids")
    for key in mutable:
        if key in data:
            setattr(case, key, data[key])

    case.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await add_activity(case_id, "Case_Updated", user_id, "Case details updated.", db=db)
    return _to_dict(case)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

async def transition_case_status(case_id: str, new_status: str, user_id: str, db: AsyncSession) -> dict:
    """Move a case to *new_status* if the transition is valid."""
    case = await db.get(Case, case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    current = case.status if isinstance(case.status, str) else case.status.value
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        _api_error(
            "VALIDATION_ERROR",
            f"Cannot transition from '{current}' to '{new_status}'. "
            f"Allowed: {allowed}.",
            "status",
        )

    case.status = new_status
    case.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await add_activity(
        case_id, "Status_Change", user_id,
        f"Status changed from {current} to {new_status}.",
        db=db,
    )
    return _to_dict(case)


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------

async def attach_document(
    case_id: str,
    file_name: str,
    document_type: str,
    file_bytes: bytes,
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Attach a document to a case, computing its SHA-256 hash."""
    case = await db.get(Case, case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    sha256 = compute_sha256(file_bytes)
    doc = CaseDocument(
        case_id=case_id,
        file_name=file_name,
        document_type=document_type,
        sha256_hash=sha256,
        file_size_bytes=len(file_bytes),
        created_by=user_id,
    )
    db.add(doc)
    await db.flush()

    await add_activity(
        case_id, "Document_Attached", user_id,
        f"Document '{file_name}' attached.",
        entity_type="document", entity_id=doc.id,
        db=db,
    )
    return _to_dict(doc, key_map=_DOCUMENT_KEY_MAP)


async def list_case_documents(case_id: str, db: AsyncSession) -> list:
    """Return all documents for a given case."""
    result = await db.execute(
        select(CaseDocument).where(CaseDocument.case_id == case_id)
    )
    return [_to_dict(d, key_map=_DOCUMENT_KEY_MAP) for d in result.scalars().all()]


async def get_case_document(case_id: str, doc_id: str, db: AsyncSession) -> Optional[dict]:
    """Return a single document if it belongs to *case_id*."""
    result = await db.execute(
        select(CaseDocument).where(
            CaseDocument.id == doc_id,
            CaseDocument.case_id == case_id,
        )
    )
    doc = result.scalar_one_or_none()
    return _to_dict(doc, key_map=_DOCUMENT_KEY_MAP) if doc else None


# ---------------------------------------------------------------------------
# Timeline / activity
# ---------------------------------------------------------------------------

async def add_activity(
    case_id: str,
    activity_type: str,
    user_id: str,
    description: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    *,
    db: AsyncSession,
) -> dict:
    """Append an activity entry to the case timeline."""
    activity = CaseActivity(
        case_id=case_id,
        activity_type=activity_type,
        user_id=user_id,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(activity)
    await db.flush()
    return _to_dict(activity)


async def get_timeline(case_id: str, sort_asc: bool = False, *, db: AsyncSession) -> list:
    """Return the full activity timeline for a case (default: newest first)."""
    order = CaseActivity.created_at.asc() if sort_asc else CaseActivity.created_at.desc()
    result = await db.execute(
        select(CaseActivity)
        .where(CaseActivity.case_id == case_id)
        .order_by(order)
    )
    return [_to_dict(a) for a in result.scalars().all()]


# ---------------------------------------------------------------------------
# Action tracker
# ---------------------------------------------------------------------------

async def create_task(case_id: str, data: dict, user_id: str, db: AsyncSession) -> dict:
    """Create an action-tracker task linked to a case."""
    case = await db.get(Case, case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    due_date_raw = data.get("due_date")
    if isinstance(due_date_raw, str):
        due_date_val = date.fromisoformat(due_date_raw)
    elif isinstance(due_date_raw, date):
        due_date_val = due_date_raw
    else:
        due_date_val = None

    task = ActionTrackerTask(
        case_id=case_id,
        task_name=data.get("task_name", ""),
        due_date=due_date_val,
        priority=data.get("priority", "Medium"),
        status="Pending",
        source=data.get("source", "Manual"),
        created_by=user_id,
    )
    db.add(task)
    await db.flush()

    await add_activity(
        case_id, "Task_Created", user_id,
        f"Task '{task.task_name}' created.",
        entity_type="task", entity_id=task.id,
        db=db,
    )
    return _to_dict(task)


async def list_tasks(case_id: str, db: AsyncSession) -> list:
    """Return tasks for a case, sorted by due_date ascending."""
    result = await db.execute(
        select(ActionTrackerTask)
        .where(ActionTrackerTask.case_id == case_id)
        .order_by(ActionTrackerTask.due_date.asc().nullslast())
    )
    return [_to_dict(t) for t in result.scalars().all()]


async def update_task(case_id: str, task_id: str, data: dict, user_id: str, db: AsyncSession) -> dict:
    """Update an existing action-tracker task."""
    result = await db.execute(
        select(ActionTrackerTask).where(
            ActionTrackerTask.id == task_id,
            ActionTrackerTask.case_id == case_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        _api_error("NOT_FOUND", f"Task '{task_id}' not found for case '{case_id}'.")

    mutable = ("task_name", "due_date", "priority", "status", "snoozed_until")
    for key in mutable:
        if key in data:
            val = data[key]
            # Convert string dates to proper types
            if key == "due_date" and isinstance(val, str):
                val = date.fromisoformat(val)
            elif key == "snoozed_until" and isinstance(val, str):
                val = datetime.fromisoformat(val)
            setattr(task, key, val)

    task.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await add_activity(
        case_id, "Task_Updated", user_id,
        f"Task '{task.task_name}' updated.",
        entity_type="task", entity_id=task_id,
        db=db,
    )
    return _to_dict(task)


async def auto_populate_statutory_deadlines(case_id: str, offence_type: str, db: AsyncSession) -> list:
    """Create standard statutory-deadline tasks for a case.

    Deadlines are computed relative to the case creation date.
    """
    case = await db.get(Case, case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    base_date = case.created_at if isinstance(case.created_at, datetime) else datetime.fromisoformat(case.created_at)
    templates = [
        {"task_name": "Submit progress report", "days": 30, "priority": "Medium"},
        {"task_name": "File charge sheet", "days": 90, "priority": "High"},
        {"task_name": "Witness examination completion", "days": 60, "priority": "Medium"},
        {"task_name": "FSL report follow-up", "days": 45, "priority": "Medium"},
    ]

    io_id = case.io_id if isinstance(case.io_id, str) else str(case.io_id)

    created: list = []
    for tpl in templates:
        due = (base_date + timedelta(days=tpl["days"])).date().isoformat()
        task = await create_task(
            case_id,
            {
                "task_name": tpl["task_name"],
                "due_date": due,
                "priority": tpl["priority"],
                "source": "Statutory",
            },
            io_id,
            db,
        )
        created.append(task)

    return created


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

async def create_notification(
    user_id: str,
    type: str,
    message: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    *,
    db: AsyncSession,
) -> dict:
    """Create an in-app notification for a user."""
    note = Notification(
        user_id=user_id,
        type=type,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False,
    )
    db.add(note)
    await db.flush()
    return _to_dict(note)


async def list_notifications(user_id: str, unread_only: bool = True, *, db: AsyncSession) -> list:
    """Return notifications for a user, newest first."""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(Notification.created_at.desc())
    result = await db.execute(stmt)
    return [_to_dict(n) for n in result.scalars().all()]


async def mark_notification_read(notification_id: str, db: AsyncSession) -> dict:
    """Mark a single notification as read."""
    note = await db.get(Notification, notification_id)
    if note is None:
        _api_error("NOT_FOUND", f"Notification '{notification_id}' not found.")
    note.is_read = True
    await db.flush()
    return _to_dict(note)


# ---------------------------------------------------------------------------
# Seed data — police stations & offence types
# ---------------------------------------------------------------------------

async def list_police_stations_data(db: AsyncSession) -> list:
    """Return all active police stations."""
    result = await db.execute(
        select(PoliceStation).where(PoliceStation.is_active == True)  # noqa: E712
    )
    return [_to_dict(ps, key_map=_POLICE_STATION_KEY_MAP) for ps in result.scalars().all()]


async def list_offence_types_data(db: AsyncSession) -> list:
    """Return all active offence types."""
    result = await db.execute(
        select(OffenceType).where(OffenceType.is_active == True)  # noqa: E712
    )
    return [_to_dict(o) for o in result.scalars().all()]


async def search_offence_types_data(query: str, db: AsyncSession) -> list:
    """Search offence types by name (case-insensitive substring match)."""
    result = await db.execute(
        select(OffenceType)
        .where(OffenceType.is_active == True)  # noqa: E712
        .where(OffenceType.name.ilike(f"%{query}%"))
    )
    return [_to_dict(o) for o in result.scalars().all()]


async def seed_police_stations(db: AsyncSession) -> None:
    """Populate sample Hyderabad police stations (idempotent)."""
    stations = [
        {"id": "ps-001", "name": "Banjara Hills PS", "station_code": "BH", "district": "Hyderabad"},
        {"id": "ps-002", "name": "Begumpet PS", "station_code": "BG", "district": "Hyderabad"},
        {"id": "ps-003", "name": "Jubilee Hills PS", "station_code": "JH", "district": "Hyderabad"},
        {"id": "ps-004", "name": "Madhapur PS", "station_code": "MP", "district": "Cyberabad"},
        {"id": "ps-005", "name": "Saifabad PS", "station_code": "SF", "district": "Hyderabad"},
    ]
    for s in stations:
        existing = await db.get(PoliceStation, s["id"])
        if existing is None:
            db.add(PoliceStation(**s))
    await db.flush()


async def seed_offence_types(db: AsyncSession) -> None:
    """Populate common offence types with BNS/IPC sections (idempotent)."""
    offences = [
        {"id": "off-001", "name": "Theft", "bns_section": "303", "ipc_section": "379"},
        {"id": "off-002", "name": "Robbery", "bns_section": "309", "ipc_section": "392"},
        {"id": "off-003", "name": "Cheating", "bns_section": "318", "ipc_section": "420"},
        {"id": "off-004", "name": "Criminal Breach of Trust", "bns_section": "316", "ipc_section": "406"},
        {"id": "off-005", "name": "Assault", "bns_section": "115", "ipc_section": "323"},
        {"id": "off-006", "name": "Murder", "bns_section": "101", "ipc_section": "302"},
        {"id": "off-007", "name": "Kidnapping", "bns_section": "137", "ipc_section": "363"},
        {"id": "off-008", "name": "Dowry Death", "bns_section": "80", "ipc_section": "304B"},
        {"id": "off-009", "name": "Cyber Crime", "bns_section": "318", "ipc_section": "66 IT Act"},
        {"id": "off-010", "name": "Criminal Intimidation", "bns_section": "351", "ipc_section": "506"},
    ]
    for o in offences:
        existing = await db.get(OffenceType, o["id"])
        if existing is None:
            db.add(OffenceType(**o))
    await db.flush()
