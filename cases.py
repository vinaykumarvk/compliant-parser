from __future__ import annotations

"""Case management service layer for the IQW platform.

In-memory implementation that mirrors the target DB schema.  Every public
function returns plain dicts so the API layer can serialise them directly.
"""

import re
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from audit import compute_sha256

# ---------------------------------------------------------------------------
# Lazy import helper (avoids circular deps with api_v1)
# ---------------------------------------------------------------------------

def _api_error(code: str, message: str, field: Optional[str] = None) -> None:
    from api_v1 import ErrorCode, raise_api_error
    raise_api_error(ErrorCode(code), message, field)


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_cases: Dict[str, dict] = {}
_case_documents: Dict[str, dict] = {}
_case_activities: Dict[str, dict] = {}
_action_tracker_tasks: Dict[str, dict] = {}
_notifications: Dict[str, dict] = {}
_police_stations: Dict[str, dict] = {}
_offence_types: Dict[str, dict] = {}


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
# Case CRUD
# ---------------------------------------------------------------------------

def create_case(data: dict, user_id: str) -> dict:
    """Create a new case after validating crime/petition numbers."""
    crime_no = data.get("crime_no", "")
    if crime_no and not validate_crime_no(crime_no):
        _api_error("VALIDATION_ERROR", "Invalid Crime No. format. Expected NNNN/YYYY.", "crime_no")

    petition_no = data.get("petition_no", "")
    if petition_no and not validate_petition_no(petition_no):
        _api_error("VALIDATION_ERROR", "Invalid Petition No. format. Expected PET/PS/YYYY/NNNN.", "petition_no")

    case_id = str(_uuid.uuid4())
    now = _now_iso()
    case = {
        "id": case_id,
        "case_type": data.get("case_type", "FIR"),
        "crime_no": crime_no,
        "petition_no": petition_no,
        "brief_facts": data.get("brief_facts", ""),
        "offence_type": data.get("offence_type", ""),
        "police_station_id": data.get("police_station_id", ""),
        "primary_offence_type_id": data.get("primary_offence_type_id"),
        "secondary_offence_type_ids": data.get("secondary_offence_type_ids", []),
        "status": "Open",
        "cctns_sync_status": "Pending",
        "created_by": user_id,
        "io_id": data.get("io_id", user_id),
        "created_at": now,
        "updated_at": now,
    }
    _cases[case_id] = case

    add_activity(case_id, "Case_Created", user_id, "Case registered and opened.")
    return case


def get_case(case_id: str) -> Optional[dict]:
    """Return a single case or None."""
    return _cases.get(case_id)


def list_cases(user_id: str, role: str, filters: Optional[dict] = None) -> dict:
    """List cases visible to the caller with pagination.

    IO sees only own cases; System_Admin / Admin sees all.
    Filters: status, police_station_id, date_from, date_to, page, page_size.
    Returns: {"items": [...], "total": N, "page": P, "page_size": S}
    """
    if role in ("System_Admin", "Admin"):
        items = list(_cases.values())
    else:
        items = [c for c in _cases.values() if c["io_id"] == user_id]

    if filters:
        if filters.get("status"):
            items = [c for c in items if c["status"] == filters["status"]]
        if filters.get("police_station_id"):
            items = [c for c in items if c["police_station_id"] == filters["police_station_id"]]
        if filters.get("date_from"):
            items = [c for c in items if c["created_at"] >= filters["date_from"]]
        if filters.get("date_to"):
            items = [c for c in items if c["created_at"] <= filters["date_to"]]

    # Sort by created_at descending
    items.sort(key=lambda c: c.get("created_at", ""), reverse=True)

    total = len(items)
    page = int((filters or {}).get("page", 1))
    page_size = int((filters or {}).get("page_size", 20))
    start = (page - 1) * page_size
    end = start + page_size

    return {"items": items[start:end], "total": total, "page": page, "page_size": page_size}


def update_case(case_id: str, data: dict, user_id: str) -> dict:
    """Update mutable fields on an existing case."""
    case = _cases.get(case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    mutable = ("brief_facts", "offence_type", "police_station_id",
               "primary_offence_type_id", "secondary_offence_type_ids")
    for key in mutable:
        if key in data:
            case[key] = data[key]

    case["updated_at"] = _now_iso()
    add_activity(case_id, "Case_Updated", user_id, "Case details updated.")
    return case


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def transition_case_status(case_id: str, new_status: str, user_id: str) -> dict:
    """Move a case to *new_status* if the transition is valid."""
    case = _cases.get(case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    current = case["status"]
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        _api_error(
            "VALIDATION_ERROR",
            f"Cannot transition from '{current}' to '{new_status}'. "
            f"Allowed: {allowed}.",
            "status",
        )

    case["status"] = new_status
    case["updated_at"] = _now_iso()
    add_activity(
        case_id, "Status_Change", user_id,
        f"Status changed from {current} to {new_status}.",
    )
    return case


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------

def attach_document(
    case_id: str,
    file_name: str,
    document_type: str,
    file_bytes: bytes,
    user_id: str,
) -> dict:
    """Attach a document to a case, computing its SHA-256 hash."""
    if case_id not in _cases:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    doc_id = str(_uuid.uuid4())
    sha256 = compute_sha256(file_bytes)
    now = _now_iso()
    doc = {
        "id": doc_id,
        "case_id": case_id,
        "file_name": file_name,
        "document_type": document_type,
        "sha256": sha256,
        "size_bytes": len(file_bytes),
        "uploaded_by": user_id,
        "uploaded_at": now,
    }
    _case_documents[doc_id] = doc

    add_activity(
        case_id, "Document_Attached", user_id,
        f"Document '{file_name}' attached.",
        entity_type="document", entity_id=doc_id,
    )
    return doc


def list_case_documents(case_id: str) -> list:
    """Return all documents for a given case."""
    return [d for d in _case_documents.values() if d["case_id"] == case_id]


def get_case_document(case_id: str, doc_id: str) -> Optional[dict]:
    """Return a single document if it belongs to *case_id*."""
    doc = _case_documents.get(doc_id)
    if doc and doc["case_id"] == case_id:
        return doc
    return None


# ---------------------------------------------------------------------------
# Timeline / activity
# ---------------------------------------------------------------------------

def add_activity(
    case_id: str,
    activity_type: str,
    user_id: str,
    description: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> dict:
    """Append an activity entry to the case timeline."""
    act_id = str(_uuid.uuid4())
    entry = {
        "id": act_id,
        "case_id": case_id,
        "activity_type": activity_type,
        "user_id": user_id,
        "description": description,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "created_at": _now_iso(),
    }
    _case_activities[act_id] = entry
    return entry


def get_timeline(case_id: str, sort_asc: bool = False) -> list:
    """Return the full activity timeline for a case (default: newest first)."""
    items = [a for a in _case_activities.values() if a["case_id"] == case_id]
    items.sort(key=lambda a: a["created_at"], reverse=not sort_asc)
    return items


# ---------------------------------------------------------------------------
# Action tracker
# ---------------------------------------------------------------------------

def create_task(case_id: str, data: dict, user_id: str) -> dict:
    """Create an action-tracker task linked to a case."""
    if case_id not in _cases:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    task_id = str(_uuid.uuid4())
    now = _now_iso()
    task = {
        "id": task_id,
        "case_id": case_id,
        "task_name": data.get("task_name", ""),
        "due_date": data.get("due_date"),
        "priority": data.get("priority", "Medium"),
        "status": "Pending",
        "source": data.get("source", "Manual"),
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }
    _action_tracker_tasks[task_id] = task

    add_activity(
        case_id, "Task_Created", user_id,
        f"Task '{task['task_name']}' created.",
        entity_type="task", entity_id=task_id,
    )
    return task


def list_tasks(case_id: str) -> list:
    """Return tasks for a case, sorted by due_date ascending."""
    items = [t for t in _action_tracker_tasks.values() if t["case_id"] == case_id]
    items.sort(key=lambda t: t.get("due_date") or "9999-12-31")
    return items


def update_task(case_id: str, task_id: str, data: dict, user_id: str) -> dict:
    """Update an existing action-tracker task."""
    task = _action_tracker_tasks.get(task_id)
    if task is None or task["case_id"] != case_id:
        _api_error("NOT_FOUND", f"Task '{task_id}' not found for case '{case_id}'.")

    mutable = ("task_name", "due_date", "priority", "status", "snoozed_until")
    for key in mutable:
        if key in data:
            task[key] = data[key]

    task["updated_at"] = _now_iso()
    add_activity(
        case_id, "Task_Updated", user_id,
        f"Task '{task['task_name']}' updated.",
        entity_type="task", entity_id=task_id,
    )
    return task


def auto_populate_statutory_deadlines(case_id: str, offence_type: str) -> list:
    """Create standard statutory-deadline tasks for a case.

    Deadlines are computed relative to the case creation date.
    """
    case = _cases.get(case_id)
    if case is None:
        _api_error("NOT_FOUND", f"Case '{case_id}' not found.")

    base_date = datetime.fromisoformat(case["created_at"])
    templates = [
        {"task_name": "Submit progress report", "days": 30, "priority": "Medium"},
        {"task_name": "File charge sheet", "days": 90, "priority": "High"},
        {"task_name": "Witness examination completion", "days": 60, "priority": "Medium"},
        {"task_name": "FSL report follow-up", "days": 45, "priority": "Medium"},
    ]

    created: list = []
    for tpl in templates:
        due = (base_date + timedelta(days=tpl["days"])).date().isoformat()
        task = create_task(
            case_id,
            {
                "task_name": tpl["task_name"],
                "due_date": due,
                "priority": tpl["priority"],
                "source": "Statutory",
            },
            case["io_id"],
        )
        created.append(task)

    return created


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notification(
    user_id: str,
    type: str,
    message: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> dict:
    """Create an in-app notification for a user."""
    nid = str(_uuid.uuid4())
    entry = {
        "id": nid,
        "user_id": user_id,
        "type": type,
        "message": message,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "is_read": False,
        "created_at": _now_iso(),
    }
    _notifications[nid] = entry
    return entry


def list_notifications(user_id: str, unread_only: bool = True) -> list:
    """Return notifications for a user, newest first."""
    items = [n for n in _notifications.values() if n["user_id"] == user_id]
    if unread_only:
        items = [n for n in items if not n["is_read"]]
    items.sort(key=lambda n: n["created_at"], reverse=True)
    return items


def mark_notification_read(notification_id: str) -> dict:
    """Mark a single notification as read."""
    note = _notifications.get(notification_id)
    if note is None:
        _api_error("NOT_FOUND", f"Notification '{notification_id}' not found.")
    note["is_read"] = True
    return note


# ---------------------------------------------------------------------------
# Seed data — police stations & offence types
# ---------------------------------------------------------------------------

def list_police_stations_data() -> list:
    """Return all police stations."""
    return list(_police_stations.values())


def list_offence_types_data() -> list:
    """Return all offence types."""
    return list(_offence_types.values())


def search_offence_types_data(query: str) -> list:
    """Search offence types by name (case-insensitive substring match)."""
    q = query.lower()
    return [o for o in _offence_types.values() if q in o["name"].lower()]


def seed_police_stations() -> None:
    """Populate sample Hyderabad police stations."""
    stations = [
        {"id": "ps-001", "name": "Banjara Hills PS", "code": "BH", "district": "Hyderabad", "zone": "West"},
        {"id": "ps-002", "name": "Begumpet PS", "code": "BG", "district": "Hyderabad", "zone": "North"},
        {"id": "ps-003", "name": "Jubilee Hills PS", "code": "JH", "district": "Hyderabad", "zone": "West"},
        {"id": "ps-004", "name": "Madhapur PS", "code": "MP", "district": "Cyberabad", "zone": "East"},
        {"id": "ps-005", "name": "Saifabad PS", "code": "SF", "district": "Hyderabad", "zone": "Central"},
    ]
    for s in stations:
        _police_stations[s["id"]] = s


def seed_offence_types() -> None:
    """Populate common offence types with BNS/IPC sections."""
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
        _offence_types[o["id"]] = o
