from __future__ import annotations

"""PII-safe senior-officer dashboard metrics over existing IQW tables."""

import csv
import base64
import asyncio
import hashlib
import io
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from statistics import median
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import parse_records
from models import (
    AIAnalysisResult,
    Case,
    CaseActivity,
    CaseDocument,
    DashboardAlertInstance,
    DashboardAlertRule,
    DashboardExportJob,
    DashboardMetricCorrection,
    DashboardMetricDefinition,
    DashboardMetricDispute,
    DashboardSavedView,
    DashboardMetricSnapshot,
    DashboardMetricSourceMap,
    DashboardTrainingRecommendation,
    DashboardValidationState,
    GeneratedDocument,
    Notification,
    PoliceStation,
    UsageEvent,
    User,
)


LOCAL_TIMEZONE = ZoneInfo(os.getenv("IQW_DASHBOARD_LOCAL_TIMEZONE", "Asia/Kolkata"))
ALLOWED_DASHBOARD_ROLES = {"Senior_Command", "Zone_Officer", "SHO", "AI_Admin", "System_Admin", "IO", "Clerk"}
SUPERVISORY_DASHBOARD_ROLES = {"Senior_Command", "Zone_Officer", "SHO", "System_Admin"}
ADMIN_DASHBOARD_ROLES = {"System_Admin"}
AI_DASHBOARD_ROLES = {"AI_Admin", "System_Admin", "Senior_Command"}
SELF_VIEW_ROLES = {"IO", "Clerk"}
LIFECYCLE_ORDER = [
    "Complaint_Received",
    "FIR_Registered",
    "Under_Investigation",
    "Charge_Sheet_Filed",
    "Closure_Report_Filed",
    "Court_Proceedings",
    "Transferred",
    "Disposed",
    "Closed_No_FIR",
]
FIR_OR_LATER = {
    "FIR_Registered",
    "Under_Investigation",
    "Charge_Sheet_Filed",
    "Closure_Report_Filed",
    "Court_Proceedings",
    "Transferred",
    "Disposed",
}
INVESTIGATION_COMPLETED = {"Charge_Sheet_Filed", "Closure_Report_Filed", "Court_Proceedings", "Disposed"}
COURT_PROGRESSED = {"Court_Proceedings", "Disposed"}

FORBIDDEN_DASHBOARD_KEYS = {
    "brief_facts",
    "ocr_extracted_text",
    "generated_content",
    "parsed_output",
    "file_bytes",
    "complaint",
    "summary",
    "fir_draft",
    "address",
    "phone",
}

METRIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "metric_key": "cases_created",
        "display_name": "Cases Created",
        "permitted_use": "workload_awareness",
        "prohibited_use": "disciplinary conclusion without case mix review",
        "source_tables": ["cases"],
        "confidence": "high",
        "owner_role": "System_Admin",
        "minimum_sample_size": 1,
        "exclusions": ["deleted cases", "records outside scope"],
    },
    {
        "metric_key": "firs_registered",
        "display_name": "FIRs Registered",
        "permitted_use": "lifecycle_awareness",
        "prohibited_use": "investigation quality conclusion",
        "source_tables": ["cases"],
        "confidence": "high",
        "owner_role": "System_Admin",
        "minimum_sample_size": 1,
        "exclusions": ["transitions not reflected in IQW status"],
    },
    {
        "metric_key": "fir_drafts_created",
        "display_name": "FIR Drafts Created",
        "permitted_use": "adoption_and_drafting_support",
        "prohibited_use": "officer diligence conclusion",
        "source_tables": ["generated_documents", "parse_records"],
        "confidence": "medium",
        "owner_role": "AI_Admin",
        "minimum_sample_size": 1,
        "exclusions": ["legacy drafts without subtype or FIR metadata"],
    },
    {
        "metric_key": "median_complaint_to_fir_draft_minutes",
        "display_name": "Median Complaint-to-FIR Draft Time",
        "permitted_use": "bottleneck_investigation",
        "prohibited_use": "faster-is-better officer ranking",
        "source_tables": ["cases", "generated_documents", "parse_records"],
        "confidence": "medium",
        "owner_role": "System_Admin",
        "minimum_sample_size": 5,
        "exclusions": ["negative durations", "unlinked parser records in officer comparisons"],
    },
    {
        "metric_key": "active_user_adoption_rate",
        "display_name": "Active User Adoption Rate",
        "permitted_use": "training_planning",
        "prohibited_use": "personnel action",
        "source_tables": ["users", "usage_events", "cases", "case_documents", "generated_documents", "ai_analysis_results"],
        "confidence": "medium",
        "owner_role": "AI_Admin",
        "minimum_sample_size": 5,
        "exclusions": ["inactive users", "users outside current posting scope"],
    },
    {
        "metric_key": "ai_checks_performed",
        "display_name": "AI Checks Performed",
        "permitted_use": "feature_adoption",
        "prohibited_use": "investigation quality conclusion",
        "source_tables": ["ai_analysis_results"],
        "confidence": "medium",
        "owner_role": "AI_Admin",
        "minimum_sample_size": 1,
        "exclusions": ["failed model calls not persisted as analysis rows"],
    },
    {
        "metric_key": "investigation_completed",
        "display_name": "Investigation Completion Count",
        "permitted_use": "lifecycle_monitoring",
        "prohibited_use": "outcome quality conclusion",
        "source_tables": ["cases"],
        "confidence": "high",
        "owner_role": "System_Admin",
        "minimum_sample_size": 1,
        "exclusions": ["external court validation"],
    },
    {
        "metric_key": "court_progressed",
        "display_name": "Court Progression Count",
        "permitted_use": "lifecycle_monitoring",
        "prohibited_use": "court success conclusion",
        "source_tables": ["cases"],
        "confidence": "medium",
        "owner_role": "System_Admin",
        "minimum_sample_size": 1,
        "exclusions": ["external court validation"],
    },
    {
        "metric_key": "ai_acceptance_rate",
        "display_name": "AI Acceptance Rate",
        "permitted_use": "ai_governance",
        "prohibited_use": "officer competence conclusion",
        "source_tables": ["ai_analysis_results"],
        "confidence": "high",
        "owner_role": "AI_Admin",
        "minimum_sample_size": 10,
        "exclusions": ["unreviewed outputs"],
    },
    {
        "metric_key": "low_confidence_rate",
        "display_name": "Low Confidence Rate",
        "permitted_use": "ai_kb_improvement",
        "prohibited_use": "officer competence conclusion",
        "source_tables": ["ai_analysis_results"],
        "confidence": "medium",
        "owner_role": "AI_Admin",
        "minimum_sample_size": 5,
        "exclusions": ["non-persisted AI calls"],
    },
]

SOURCE_MAPS: list[dict[str, Any]] = [
    {
        "metric_key": "cases_created",
        "primary_source": "cases.created_at",
        "secondary_source": "usage_events.case.create",
        "confidence_rule": "High when case row is present; Medium when inferred from event only.",
        "conflict_policy": "Return data-quality warning and lower confidence.",
    },
    {
        "metric_key": "fir_drafts_created",
        "primary_source": "generated_documents.document_subtype",
        "secondary_source": "parse_records.parsed_output.fir_draft",
        "confidence_rule": "High for generated documents; Medium for parser-only drafts.",
        "conflict_policy": "Deduplicate by case, hash, and timestamp window.",
    },
    {
        "metric_key": "median_complaint_to_fir_draft_minutes",
        "primary_source": "cases.created_at/generated_documents.created_at",
        "secondary_source": "case_documents.created_at/parse_records.created_at",
        "confidence_rule": "High when linked to case; Low when parser history is unlinked.",
        "conflict_policy": "Exclude negative durations and warn.",
    },
]

PII_VALUE_PATTERN = re.compile(
    r"(\b\d{10}\b|\b\d{12}\b|@|address|victim|accused|witness|complainant|phone|mobile)",
    re.IGNORECASE,
)

_dashboard_worker_wakeup: Optional[asyncio.Event] = None


class DashboardValidationError(ValueError):
    def __init__(self, message: str, field: str = "filters") -> None:
        super().__init__(message)
        self.field = field


class DashboardAuthorizationError(PermissionError):
    pass


class DashboardConflictError(ValueError):
    def __init__(self, message: str, field: str = "conflict") -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class DashboardFilters:
    period: str
    date_from: datetime
    date_to: datetime
    police_station_id: Optional[str] = None
    zone: Optional[str] = None
    io_id: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    case_type: Optional[str] = None
    offence_category: Optional[str] = None
    sort: Optional[str] = None

    def public(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "police_station_id": self.police_station_id,
            "zone": self.zone,
            "io_id": self.io_id,
            "role": self.role,
            "status": self.status,
            "case_type": self.case_type,
            "offence_category": self.offence_category,
            "sort": self.sort,
        }


def _role(user: dict[str, Any]) -> str:
    return str(user.get("role") or "")


def _user_id(user: dict[str, Any]) -> Optional[str]:
    value = user.get("sub") or user.get("id")
    return str(value) if value else None


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return None


def _parse_date(value: Optional[str], *, field: str, end_of_day: bool = False) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    try:
        if len(raw) == 10:
            parsed = datetime.combine(datetime.fromisoformat(raw).date(), time.max if end_of_day else time.min)
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DashboardValidationError(f"{field} is not a valid ISO date.", field) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
    return parsed.astimezone(timezone.utc)


def normalize_filters(
    *,
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
    now: Optional[datetime] = None,
) -> DashboardFilters:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    period = period or "last_30_days"
    start: datetime
    end: datetime
    if period == "last_7_days":
        end = now
        start = now - timedelta(days=7)
    elif period == "last_30_days":
        end = now
        start = now - timedelta(days=30)
    elif period == "current_month":
        end = now
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "previous_month":
        first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_this_month
        previous_last = first_this_month - timedelta(days=1)
        start = previous_last.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "custom":
        start = _parse_date(date_from, field="date_from")  # type: ignore[assignment]
        end = _parse_date(date_to, field="date_to", end_of_day=True)  # type: ignore[assignment]
        if start is None or end is None:
            raise DashboardValidationError("Custom period requires date_from and date_to.", "date_from")
    else:
        raise DashboardValidationError("Unsupported dashboard period.", "period")
    if start > end:
        raise DashboardValidationError("date_from must be before date_to.", "date_from")
    if end - start > timedelta(days=366):
        raise DashboardValidationError("Date range cannot exceed 366 days.", "date_to")
    return DashboardFilters(
        period=period,
        date_from=start,
        date_to=end,
        police_station_id=police_station_id or None,
        zone=zone or None,
        io_id=io_id or None,
        role=role or None,
        status=status or None,
        case_type=case_type or None,
        offence_category=offence_category or None,
        sort=sort or None,
    )


def ensure_dashboard_access(user: dict[str, Any], filters: DashboardFilters) -> None:
    resolve_dashboard_filters(user, filters, [])


def _jurisdiction_ids(user: dict[str, Any]) -> set[str]:
    raw = user.get("jurisdiction_ids") or []
    if isinstance(raw, str):
        return {part.strip() for part in raw.split(",") if part.strip()}
    if isinstance(raw, (list, tuple, set)):
        return {str(part) for part in raw if part}
    return set()


def _user_station_id(user: dict[str, Any]) -> Optional[str]:
    value = user.get("police_station_id")
    return str(value) if value else None


def _station_zone(station: Optional[PoliceStation]) -> Optional[str]:
    if not station:
        return None
    return getattr(station, "zone", None) or getattr(station, "district", None) or getattr(station, "city", None)


def _station_allowed_for_user(user: dict[str, Any], station: Optional[PoliceStation]) -> bool:
    role = _role(user)
    if role in {"System_Admin", "Senior_Command", "AI_Admin"}:
        return True
    station_id = getattr(station, "id", None)
    if role == "SHO":
        return bool(station_id and station_id == _user_station_id(user))
    if role == "Zone_Officer":
        ids = _jurisdiction_ids(user)
        zone = _station_zone(station)
        return not ids or (bool(station_id and station_id in ids) or bool(zone and zone in ids))
    return False


def resolve_dashboard_filters(
    user: dict[str, Any],
    filters: DashboardFilters,
    stations: list[PoliceStation],
) -> DashboardFilters:
    role = _role(user)
    if role not in ALLOWED_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("User is not authorized for senior dashboard.")
    if role in SELF_VIEW_ROLES:
        uid = _user_id(user)
        if filters.io_id and filters.io_id != uid:
            raise DashboardAuthorizationError(f"{role} can only view own dashboard metrics.")
        if filters.police_station_id:
            raise DashboardAuthorizationError(f"{role} cannot request station-wide dashboard metrics.")
        return replace(filters, io_id=uid)
    if role == "SHO":
        station_id = _user_station_id(user)
        if not station_id:
            raise DashboardAuthorizationError("No dashboard scope assigned.")
        if filters.police_station_id and filters.police_station_id != station_id:
            raise DashboardAuthorizationError("SHO can only view own station dashboard metrics.")
        return replace(filters, police_station_id=station_id)
    if role == "Zone_Officer":
        ids = _jurisdiction_ids(user)
        if filters.zone and ids and filters.zone not in ids:
            raise DashboardAuthorizationError("Zone officer cannot view the requested zone.")
        if filters.police_station_id and stations:
            station = next((item for item in stations if item.id == filters.police_station_id), None)
            if not _station_allowed_for_user(user, station):
                raise DashboardAuthorizationError("Requested station is outside dashboard scope.")
        if not filters.zone and ids:
            return replace(filters, zone=sorted(ids)[0])
    return filters


async def _all(db: AsyncSession, model: type) -> list[Any]:
    result = await db.execute(select(model))
    return list(result.scalars().all())


async def _parse_record_rows(db: AsyncSession) -> list[dict[str, Any]]:
    try:
        result = await db.execute(select(parse_records))
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for row in result.all() if hasattr(result, "all") else []:
        mapping = getattr(row, "_mapping", row)
        try:
            rows.append(dict(mapping))
        except Exception:
            continue
    return rows


def _within(value: Any, filters: DashboardFilters) -> bool:
    dt = _dt(value)
    return bool(dt and filters.date_from <= dt <= filters.date_to)


def _case_visible(
    case: Case,
    user: dict[str, Any],
    filters: DashboardFilters,
    station_by_id: Optional[dict[str, PoliceStation]] = None,
) -> bool:
    role = _role(user)
    uid = _user_id(user)
    if role in SELF_VIEW_ROLES and uid not in {case.io_id, case.created_by}:
        return False
    if role == "SHO" and _user_station_id(user) and case.police_station_id != _user_station_id(user):
        return False
    if role == "Zone_Officer" and station_by_id:
        station = station_by_id.get(case.police_station_id or "")
        if not _station_allowed_for_user(user, station):
            return False
    if filters.police_station_id and case.police_station_id != filters.police_station_id:
        return False
    if filters.zone and station_by_id:
        station = station_by_id.get(case.police_station_id or "")
        if _station_zone(station) != filters.zone:
            return False
    if filters.io_id and case.io_id != filters.io_id and case.created_by != filters.io_id:
        return False
    if filters.status and _enum_value(case.status) != filters.status:
        return False
    if filters.case_type and _enum_value(case.case_type) != filters.case_type:
        return False
    if filters.offence_category and (case.offence_type or "").lower() != filters.offence_category.lower():
        return False
    return True


def _filter_cases(
    cases: Iterable[Case],
    user: dict[str, Any],
    filters: DashboardFilters,
    station_by_id: Optional[dict[str, PoliceStation]] = None,
) -> list[Case]:
    return [case for case in cases if _case_visible(case, user, filters, station_by_id) and _within(case.created_at, filters)]


def _case_scope_ids(cases: Iterable[Case]) -> set[str]:
    return {case.id for case in cases}


def _owner(case: Case) -> str:
    return case.io_id or case.created_by or "unassigned"


def _is_fir_draft(doc: GeneratedDocument) -> bool:
    subtype = (doc.document_subtype or "").strip().lower()
    return subtype in {"fir_draft", "fir draft", "fir"}


def _parse_row_has_fir_draft(row: dict[str, Any]) -> bool:
    payload = row.get("parsed_output") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    keys = {str(key).lower() for key in payload.keys()}
    text = json.dumps(payload, default=str).lower() if payload else ""
    return "fir_draft" in keys or "fir draft" in text or bool(row.get("fir_draft"))


def _case_first_intake(case: Case, docs: list[CaseDocument], parse_rows: list[dict[str, Any]]) -> Optional[datetime]:
    values: list[datetime] = []
    created = _dt(case.created_at)
    if created:
        values.append(created)
    for doc in docs:
        if doc.case_id == case.id:
            dt = _dt(doc.created_at)
            if dt:
                values.append(dt)
    for row in parse_rows:
        if row.get("case_id") == case.id:
            dt = _dt(row.get("created_at"))
            if dt:
                values.append(dt)
    return min(values) if values else None


def _hash_filters(filters: DashboardFilters) -> str:
    encoded = json.dumps(filters.public(), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _filters_from_public(payload: dict[str, Any]) -> DashboardFilters:
    date_from = _parse_date(payload.get("date_from"), field="date_from")
    date_to = _parse_date(payload.get("date_to"), field="date_to", end_of_day=False)
    if date_from is None or date_to is None:
        return normalize_filters(period=payload.get("period") or "last_30_days")
    return DashboardFilters(
        period=payload.get("period") or "custom",
        date_from=date_from,
        date_to=date_to,
        police_station_id=payload.get("police_station_id"),
        zone=payload.get("zone"),
        io_id=payload.get("io_id"),
        role=payload.get("role"),
        status=payload.get("status"),
        case_type=payload.get("case_type"),
        offence_category=payload.get("offence_category"),
        sort=payload.get("sort"),
    )


def _user_payload_from_model(user: Optional[User], fallback_user_id: Optional[str] = None) -> dict[str, Any]:
    if user is None:
        return {"sub": fallback_user_id, "role": "System_Admin"}
    return {
        "sub": user.id,
        "id": user.id,
        "role": _enum_value(user.role),
        "police_station_id": user.police_station_id,
        "jurisdiction_scope": user.jurisdiction_scope,
        "jurisdiction_ids": user.jurisdiction_ids or [],
    }


def set_dashboard_worker_wakeup(event: Optional[asyncio.Event]) -> None:
    global _dashboard_worker_wakeup
    _dashboard_worker_wakeup = event


def wake_dashboard_worker() -> None:
    if _dashboard_worker_wakeup is not None:
        _dashboard_worker_wakeup.set()


def _safe_explanation(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if PII_VALUE_PATTERN.search(value):
        raise DashboardValidationError("Dispute explanation cannot include PII or complaint narrative details.", "explanation")
    return value.strip()[:1000]


def _max_timestamp(values: Iterable[Any]) -> Optional[str]:
    timestamps = [_dt(value) for value in values]
    present = [value for value in timestamps if value is not None]
    return max(present).isoformat() if present else None


def _warning(code: str, message: str, severity: str = "warning") -> dict[str, Any]:
    return {"code": code, "message": message, "severity": severity}


def _warnings(
    cases: list[Case],
    parse_rows: list[dict[str, Any]],
    *,
    extra: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    missing_station = len([case for case in cases if not case.police_station_id])
    missing_io = len([case for case in cases if not case.io_id])
    if missing_station:
        warnings.append(_warning("MISSING_STATION", f"{missing_station} case(s) do not have police station attribution."))
    if missing_io:
        warnings.append(_warning("MISSING_IO", f"{missing_io} case(s) do not have explicit IO assignment.", "info"))
    unlinked_parser = len(parse_rows)
    if unlinked_parser:
        warnings.append(_warning("UNLINKED_PARSE_RECORDS", f"{unlinked_parser} parser record(s) are unlinked and excluded from officer-level timing.", "info"))
    if len(cases) and len(cases) < 5:
        warnings.append(_warning("LOW_SAMPLE_SIZE", "Current filter scope has fewer than 5 cases; compare trends carefully.", "info"))
    if extra:
        warnings.extend(extra)
    return warnings


def _assert_payload_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_DASHBOARD_KEYS:
                raise AssertionError(f"Dashboard payload contains forbidden key: {key}")
            _assert_payload_safe(nested)
    elif isinstance(value, list):
        for item in value:
            _assert_payload_safe(item)


def _case_age_days(case: Case, filters: DashboardFilters) -> int:
    created = _dt(case.created_at) or filters.date_from
    return max(0, int((filters.date_to - created).total_seconds() // 86400))


async def dashboard_dataset(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    users = await _all(db, User)
    stations = await _all(db, PoliceStation)
    station_by_id = {station.id: station for station in stations}
    filters = resolve_dashboard_filters(user, filters, stations)
    all_cases = await _all(db, Case)
    users_by_id = {item.id: item for item in users}
    if filters.role:
        allowed_users = {
            item.id
            for item in users
            if str(_enum_value(getattr(item, "role", None))) == filters.role
        }
        all_cases = [
            case
            for case in all_cases
            if case.io_id in allowed_users or case.created_by in allowed_users
        ]
    visible_cases_all_dates = [case for case in all_cases if _case_visible(case, user, filters, station_by_id)]
    cases = _filter_cases(all_cases, user, filters, station_by_id)
    case_ids = _case_scope_ids(cases)
    visible_case_ids_all_dates = _case_scope_ids(visible_cases_all_dates)
    documents = [doc for doc in await _all(db, CaseDocument) if doc.case_id in case_ids and _within(doc.created_at, filters)]
    generated = [doc for doc in await _all(db, GeneratedDocument) if doc.case_id in case_ids and _within(doc.created_at, filters)]
    analyses = [row for row in await _all(db, AIAnalysisResult) if row.case_id in case_ids and _within(row.created_at, filters)]
    events = [row for row in await _all(db, UsageEvent) if _within(row.timestamp or row.created_at, filters)]
    activities = [row for row in await _all(db, CaseActivity) if row.case_id in visible_case_ids_all_dates and _within(row.created_at, filters)]
    parse_rows = [row for row in await _parse_record_rows(db) if _within(row.get("created_at"), filters)]
    linked_parse_rows = [row for row in parse_rows if row.get("case_id") in case_ids]
    unlinked_parse_rows = [row for row in parse_rows if row.get("case_id") not in case_ids]
    return {
        "filters": filters,
        "user": user,
        "users": users,
        "users_by_id": users_by_id,
        "stations": stations,
        "station_by_id": station_by_id,
        "cases": cases,
        "visible_cases_all_dates": visible_cases_all_dates,
        "documents": documents,
        "generated": generated,
        "analyses": analyses,
        "events": events,
        "activities": activities,
        "parse_rows": linked_parse_rows,
        "all_parse_rows": parse_rows,
        "unlinked_parse_rows": unlinked_parse_rows,
    }


def _freshness(data: dict[str, Any]) -> dict[str, Any]:
    values: list[Any] = []
    for key in ("cases", "documents", "generated", "analyses", "events", "activities"):
        for row in data.get(key, []):
            values.append(getattr(row, "timestamp", None) or getattr(row, "created_at", None))
    for row in data.get("parse_rows", []):
        values.append(row.get("created_at"))
    watermark = _max_timestamp(values)
    return {"last_refreshed_at": datetime.now(timezone.utc).isoformat(), "source_watermark_at": watermark}


async def overview_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    cases: list[Case] = data["cases"]
    generated: list[GeneratedDocument] = data["generated"]
    documents: list[CaseDocument] = data["documents"]
    analyses: list[AIAnalysisResult] = data["analyses"]
    fir_drafts = [doc for doc in generated if _is_fir_draft(doc)]
    active_users = set()
    for case in cases:
        if case.created_by:
            active_users.add(case.created_by)
        if case.io_id:
            active_users.add(case.io_id)
    for collection in (documents, generated, analyses):
        for item in collection:
            if item.created_by:
                active_users.add(item.created_by)
    lifecycle = lifecycle_summary_from_cases(cases, filters)
    processing = processing_time_summary_from_data(data, filters)
    payload = {
        "filters": filters.public(),
        "scope": _scope_payload(data["stations"], filters, user),
        "freshness": _freshness(data),
        "kpis": {
            "cases_created": len(cases),
            "firs_registered": len([case for case in cases if _enum_value(case.status) in FIR_OR_LATER]),
            "fir_drafts_created": len(fir_drafts),
            "documents_uploaded": len(documents),
            "generated_documents": len(generated),
            "ai_checks_performed": len(analyses),
            "investigation_completed": len([case for case in cases if _enum_value(case.status) in INVESTIGATION_COMPLETED]),
            "court_progressed": len([case for case in cases if _enum_value(case.status) in COURT_PROGRESSED]),
            "active_users": len(active_users),
            "median_complaint_to_fir_draft_minutes": processing["median_minutes"],
            "pending_fir_draft_backlog": processing["pending_draft_count"],
        },
        "lifecycle": lifecycle,
        "warnings": _warnings(cases, data["unlinked_parse_rows"]),
        "metric_definitions": METRIC_DEFINITIONS,
    }
    _assert_payload_safe(payload)
    return payload


def _scope_payload(stations: list[PoliceStation], filters: DashboardFilters, user: dict[str, Any]) -> dict[str, Any]:
    if filters.police_station_id:
        station = next((item for item in stations if item.id == filters.police_station_id), None)
        return {"type": "police_station", "id": filters.police_station_id, "label": station.name if station else filters.police_station_id}
    if filters.io_id:
        return {"type": "officer", "id": filters.io_id, "label": filters.io_id}
    if _role(user) == "IO":
        return {"type": "officer", "id": _user_id(user), "label": _user_id(user)}
    return {"type": "all", "id": None, "label": "All permitted records"}


def lifecycle_summary_from_cases(cases: list[Case], filters: DashboardFilters) -> list[dict[str, Any]]:
    counts = Counter(_enum_value(case.status) for case in cases)
    total = max(1, len(cases))
    result = []
    for status in LIFECYCLE_ORDER:
        stage_cases = [case for case in cases if _enum_value(case.status) == status]
        ages = [_case_age_days(case, filters) for case in stage_cases]
        station_backlog = Counter(case.police_station_id or "unassigned" for case in stage_cases)
        officer_backlog = Counter(_owner(case) for case in stage_cases)
        result.append(
            {
                "status": status,
                "count": counts.get(status, 0),
                "conversion_percentage": round((counts.get(status, 0) / total) * 100, 2),
                "median_age_days": median(ages) if ages else 0,
                "p90_age_days": _percentile(ages, 90) if ages else 0,
                "oldest_age_days": max(ages) if ages else 0,
                "station_backlog": [{"police_station_id": key, "count": value} for key, value in station_backlog.most_common(10)],
                "officer_backlog": [{"user_id": key, "count": value} for key, value in officer_backlog.most_common(10)],
            }
        )
    return result


async def lifecycle_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    payload = {
        "filters": filters.public(),
        "freshness": _freshness(data),
        "items": lifecycle_summary_from_cases(data["cases"], filters),
        "warnings": _warnings(data["cases"], data["unlinked_parse_rows"]),
    }
    _assert_payload_safe(payload)
    return payload


async def officer_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    users_by_id = {item.id: item for item in data["users"]}
    station_by_id = {item.id: item for item in data["stations"]}
    rows: dict[str, dict[str, Any]] = {}

    def row_for(user_id: str) -> dict[str, Any]:
        if user_id not in rows:
            usr = users_by_id.get(user_id)
            station = station_by_id.get(getattr(usr, "police_station_id", None)) if usr else None
            rows[user_id] = {
                "user_id": user_id,
                "employee_id": getattr(usr, "employee_id", None) if usr else None,
                "full_name": getattr(usr, "full_name", None) if usr else "Unassigned",
                "rank": getattr(usr, "rank", None) if usr else None,
                "role": _enum_value(getattr(usr, "role", None)) if usr else None,
                "police_station_id": getattr(usr, "police_station_id", None) if usr else None,
                "police_station_name": station.name if station else None,
                "cases_created": 0,
                "firs_registered": 0,
                "fir_drafts_created": 0,
                "documents_uploaded": 0,
                "generated_documents": 0,
                "ai_checks_performed": 0,
                "active_days": 0,
                "last_activity_at": None,
                "_active_dates": set(),
            }
        return rows[user_id]

    def touch(user_id: Optional[str], value: Any) -> None:
        if not user_id:
            return
        row = row_for(user_id)
        dt = _dt(value)
        if dt:
            row["_active_dates"].add(dt.date().isoformat())
            if not row["last_activity_at"] or dt.isoformat() > row["last_activity_at"]:
                row["last_activity_at"] = dt.isoformat()

    for case in data["cases"]:
        user_id = case.created_by or _owner(case)
        row_for(user_id)["cases_created"] += 1
        if _enum_value(case.status) in FIR_OR_LATER:
            row_for(_owner(case))["firs_registered"] += 1
        touch(user_id, case.created_at)
    for doc in data["documents"]:
        row_for(doc.created_by or "unassigned")["documents_uploaded"] += 1
        touch(doc.created_by, doc.created_at)
    for gen in data["generated"]:
        row = row_for(gen.created_by or "unassigned")
        row["generated_documents"] += 1
        if _is_fir_draft(gen):
            row["fir_drafts_created"] += 1
        touch(gen.created_by, gen.created_at)
    for analysis in data["analyses"]:
        row_for(analysis.created_by or "unassigned")["ai_checks_performed"] += 1
        touch(analysis.created_by, analysis.created_at)
    for event in data["events"]:
        touch(event.user_id or event.created_by, event.timestamp or event.created_at)
    for activity in data["activities"]:
        touch(activity.user_id or activity.created_by, activity.created_at)

    items = []
    for row in rows.values():
        row["active_days"] = len(row.pop("_active_dates"))
        items.append(row)
    items.sort(key=lambda item: (item["cases_created"], item["fir_drafts_created"], item["ai_checks_performed"]), reverse=True)
    if filters.sort:
        reverse = not filters.sort.startswith("-")
        key = filters.sort[1:] if filters.sort.startswith("-") else filters.sort
        items.sort(key=lambda item: item.get(key) or 0, reverse=reverse)
    payload = {"filters": filters.public(), "freshness": _freshness(data), "items": items, "total": len(items), "warnings": _warnings(data["cases"], data["unlinked_parse_rows"])}
    _assert_payload_safe(payload)
    return payload


async def station_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    stations = {station.id: station for station in data["stations"]}
    rows: dict[str, dict[str, Any]] = {}

    def row_for(station_id: Optional[str]) -> dict[str, Any]:
        key = station_id or "unassigned"
        if key not in rows:
            station = stations.get(station_id or "")
            rows[key] = {
                "police_station_id": station_id,
                "police_station_name": station.name if station else "Unassigned",
                "zone": getattr(station, "zone", None) if station else None,
                "cases_created": 0,
                "firs_registered": 0,
                "fir_drafts_created": 0,
                "documents_uploaded": 0,
                "generated_documents": 0,
                "ai_checks_performed": 0,
                "investigation_completed": 0,
                "court_progressed": 0,
                "median_complaint_to_fir_draft_minutes": None,
                "adoption_rate": None,
                "active_users": 0,
                "_active_users": set(),
            }
        return rows[key]

    case_station = {case.id: case.police_station_id for case in data["cases"]}
    for case in data["cases"]:
        row = row_for(case.police_station_id)
        row["cases_created"] += 1
        if _enum_value(case.status) in FIR_OR_LATER:
            row["firs_registered"] += 1
        if _enum_value(case.status) in INVESTIGATION_COMPLETED:
            row["investigation_completed"] += 1
        if _enum_value(case.status) in COURT_PROGRESSED:
            row["court_progressed"] += 1
        if case.created_by:
            row["_active_users"].add(case.created_by)
        if case.io_id:
            row["_active_users"].add(case.io_id)
    for doc in data["documents"]:
        row = row_for(case_station.get(doc.case_id))
        row["documents_uploaded"] += 1
        if doc.created_by:
            row["_active_users"].add(doc.created_by)
    for gen in data["generated"]:
        row = row_for(case_station.get(gen.case_id))
        row["generated_documents"] += 1
        if _is_fir_draft(gen):
            row["fir_drafts_created"] += 1
        if gen.created_by:
            row["_active_users"].add(gen.created_by)
    for analysis in data["analyses"]:
        row = row_for(case_station.get(analysis.case_id))
        row["ai_checks_performed"] += 1
        if analysis.created_by:
            row["_active_users"].add(analysis.created_by)
    items = []
    for row in rows.values():
        row["active_users"] = len(row.pop("_active_users"))
        station_id = row["police_station_id"]
        users_in_station = [
            item for item in data["users"]
            if getattr(item, "police_station_id", None) == station_id and getattr(item, "is_active", True)
        ]
        row["adoption_rate"] = round((row["active_users"] / len(users_in_station)) * 100, 2) if users_in_station else None
        station_cases = [case for case in data["cases"] if (case.police_station_id or "unassigned") == (station_id or "unassigned")]
        station_data = dict(data)
        station_data["cases"] = station_cases
        station_data["generated"] = [doc for doc in data["generated"] if doc.case_id in _case_scope_ids(station_cases)]
        station_data["documents"] = [doc for doc in data["documents"] if doc.case_id in _case_scope_ids(station_cases)]
        station_data["parse_rows"] = [row_ for row_ in data["parse_rows"] if row_.get("case_id") in _case_scope_ids(station_cases)]
        row["median_complaint_to_fir_draft_minutes"] = processing_time_summary_from_data(station_data, filters)["median_minutes"]
        items.append(row)
    items.sort(key=lambda item: item["cases_created"], reverse=True)
    if filters.sort:
        reverse = not filters.sort.startswith("-")
        key = filters.sort[1:] if filters.sort.startswith("-") else filters.sort
        items.sort(key=lambda item: item.get(key) or 0, reverse=reverse)
    payload = {"filters": filters.public(), "freshness": _freshness(data), "items": items, "total": len(items), "warnings": _warnings(data["cases"], data["unlinked_parse_rows"])}
    _assert_payload_safe(payload)
    return payload


def processing_time_summary_from_data(data: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    cases: list[Case] = data["cases"]
    generated: list[GeneratedDocument] = data["generated"]
    documents: list[CaseDocument] = data.get("documents", [])
    parse_rows: list[dict[str, Any]] = data.get("parse_rows", [])
    drafts_by_case: dict[str, list[GeneratedDocument]] = defaultdict(list)
    for doc in generated:
        if _is_fir_draft(doc):
            drafts_by_case[doc.case_id].append(doc)
    parser_draft_times: dict[str, list[datetime]] = defaultdict(list)
    for row in parse_rows:
        case_id = row.get("case_id")
        parsed_at = _dt(row.get("created_at"))
        if case_id and parsed_at and _parse_row_has_fir_draft(row):
            parser_draft_times[str(case_id)].append(parsed_at)
    durations: list[int] = []
    iteration_counts: list[int] = []
    negative_duration_count = 0
    items: list[dict[str, Any]] = []
    for case in cases:
        drafts = sorted(drafts_by_case.get(case.id, []), key=lambda doc: _dt(doc.created_at) or filters.date_to)
        parser_times = sorted(parser_draft_times.get(case.id, []))
        if not drafts and not parser_times:
            continue
        intake = _case_first_intake(case, documents, parse_rows)
        generated_times = [_dt(doc.created_at) for doc in drafts]
        generated_times = [value for value in generated_times if value]
        all_draft_times = sorted(generated_times + parser_times)
        first = all_draft_times[0] if all_draft_times else None
        last = all_draft_times[-1] if all_draft_times else None
        if not intake or not first:
            continue
        minutes = int((first - intake).total_seconds() // 60)
        if minutes < 0:
            negative_duration_count += 1
            continue
        durations.append(minutes)
        iteration_count = len(drafts) + len(parser_times)
        iteration_counts.append(iteration_count)
        items.append(
            {
                "case_id": case.id,
                "police_station_id": case.police_station_id,
                "io_id": case.io_id,
                "first_intake_at": intake.isoformat(),
                "first_fir_draft_at": first.isoformat(),
                "last_fir_draft_at": last.isoformat() if last else None,
                "draft_count": iteration_count,
                "generated_draft_count": len(drafts),
                "parser_draft_count": len(parser_times),
                "elapsed_minutes": minutes,
                "confidence": "high" if drafts else "medium",
            }
        )
    completed_case_ids = {item["case_id"] for item in items}
    pending = len([case for case in cases if case.id not in completed_case_ids])
    return {
        "median_minutes": median(durations) if durations else None,
        "average_minutes": round(sum(durations) / len(durations), 2) if durations else None,
        "p75_minutes": _percentile(durations, 75),
        "p95_minutes": _percentile(durations, 95),
        "average_draft_iterations": round(sum(iteration_counts) / len(iteration_counts), 2) if iteration_counts else 0,
        "median_draft_iterations": median(iteration_counts) if iteration_counts else 0,
        "completed_count": len(durations),
        "pending_draft_count": pending,
        "negative_duration_count": negative_duration_count,
        "items": items,
    }


def _percentile(values: list[int], percentile: int) -> Optional[int]:
    if not values:
        return None
    values = sorted(values)
    index = int(round((percentile / 100) * (len(values) - 1)))
    return values[index]


async def processing_time_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    summary = processing_time_summary_from_data(data, filters)
    extra = []
    if summary["negative_duration_count"]:
        extra.append(_warning("CLOCK_SKEW", f"{summary['negative_duration_count']} record(s) had negative processing duration and were excluded."))
    payload = {"filters": filters.public(), "freshness": _freshness(data), **summary, "warnings": _warnings(data["cases"], data["unlinked_parse_rows"], extra=extra)}
    _assert_payload_safe(payload)
    return payload


async def feature_adoption_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    modules = Counter()
    for event in data["events"]:
        modules[event.module or event.event_type] += 1
    modules["documents_uploaded"] += len(data["documents"])
    modules["generated_documents"] += len(data["generated"])
    modules["ai_checks"] += len(data["analyses"])
    modules["kis_indexed"] += len([row for row in data["parse_rows"] if row.get("kis_index_status") == "indexed"])
    reviewed = [row for row in data["analyses"] if row.io_reviewed or row.io_review_action]
    accepted = [row for row in reviewed if (row.io_review_action or "").lower() == "accepted"]
    rejected = [row for row in reviewed if (row.io_review_action or "").lower() == "rejected"]
    edited = [row for row in data["generated"] if row.io_edited]
    low_confidence = [row for row in data["analyses"] if row.has_uncertainty_flag or _enum_value(row.confidence_score) == "Low"]
    latency_values = [row.latency_ms for row in data["analyses"] if row.latency_ms is not None]
    kis_indexed = [row for row in data["all_parse_rows"] if row.get("kis_index_status") == "indexed"]
    kis_failed = [row for row in data["all_parse_rows"] if row.get("kis_index_status") == "failed"]
    graph_facts = sum(1 for row in data["all_parse_rows"] if row.get("kis_graph_status") in {"indexed", "ready"})
    wiki_articles = sum(1 for row in data["all_parse_rows"] if row.get("kis_wiki_status") in {"indexed", "ready"})
    payload = {
        "filters": filters.public(),
        "freshness": _freshness(data),
        "items": [{"module": key, "count": value} for key, value in sorted(modules.items())],
        "ai_effectiveness": {
            "reviewed_outputs": len(reviewed),
            "accepted_outputs": len(accepted),
            "rejected_outputs": len(rejected),
            "edited_outputs": len(edited),
            "rework_rate": round((len(rejected) / len(reviewed)) * 100, 2) if reviewed else None,
            "acceptance_rate": round((len(accepted) / len(reviewed)) * 100, 2) if reviewed else None,
            "low_confidence_outputs": len(low_confidence),
            "low_confidence_rate": round((len(low_confidence) / len(data["analyses"])) * 100, 2) if data["analyses"] else None,
            "median_latency_ms": median(latency_values) if latency_values else None,
            "citation_coverage_rate": None,
            "completeness_score": None,
        },
        "kis_quality": {
            "indexed_records": len(kis_indexed),
            "failed_records": len(kis_failed),
            "graph_facts_ready": graph_facts,
            "wiki_articles_ready": wiki_articles,
        },
        "warnings": _warnings(data["cases"], data["unlinked_parse_rows"]),
    }
    _assert_payload_safe(payload)
    return payload


async def record_dashboard_usage(db: AsyncSession, user: dict[str, Any], event_type: str, details: dict[str, Any]) -> None:
    safe_details = {key: value for key, value in details.items() if key not in FORBIDDEN_DASHBOARD_KEYS}
    safe_details.update(
        {
            "role": _role(user),
            "user_id": _user_id(user),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "details_hash": hashlib.sha256(json.dumps(details, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
        }
    )
    try:
        db.add(
            UsageEvent(
                user_id=_user_id(user),
                event_type=event_type,
                module="senior_dashboard",
                details=safe_details,
                created_by=_user_id(user),
            )
        )
        await db.flush()
    except Exception:
        pass
    try:
        from audit import log_audit_event

        action_type = "Export" if "export" in event_type else "Config_Change"
        await log_audit_event(
            _user_id(user),
            action_type,
            "senior_dashboard",
            event_type,
            safe_details,
            db=db,
        )
    except Exception:
        return


def _definition_to_payload(row: DashboardMetricDefinition | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, dict):
        return {
            "id": row.get("id") or row["metric_key"],
            "metric_key": row["metric_key"],
            "display_name": row["display_name"],
            "owner_role": row.get("owner_role"),
            "permitted_use": row["permitted_use"],
            "prohibited_use": row["prohibited_use"],
            "confidence": row.get("confidence") or row.get("confidence_tier"),
            "confidence_tier": row.get("confidence_tier") or row.get("confidence"),
            "minimum_sample_size": row.get("minimum_sample_size", 1),
            "source_tables": row.get("source_tables", []),
            "exclusions": row.get("exclusions", []),
            "version": row.get("version", 1),
            "is_active": row.get("is_active", True),
        }
    return {
        "id": row.id,
        "metric_key": row.metric_key,
        "display_name": row.display_name,
        "owner_role": row.owner_role,
        "permitted_use": row.permitted_use,
        "prohibited_use": row.prohibited_use,
        "confidence": row.confidence_tier,
        "confidence_tier": row.confidence_tier,
        "minimum_sample_size": row.minimum_sample_size,
        "source_tables": row.source_tables or [],
        "exclusions": row.exclusions or [],
        "version": row.version,
        "is_active": row.is_active,
    }


async def metric_definition_payloads(db: AsyncSession, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    persisted = await _all(db, DashboardMetricDefinition)
    by_key = {row.metric_key: _definition_to_payload(row) for row in persisted}
    for item in METRIC_DEFINITIONS:
        by_key.setdefault(item["metric_key"], _definition_to_payload(item))
    items = list(by_key.values())
    if not include_inactive:
        items = [item for item in items if item.get("is_active", True)]
    items.sort(key=lambda item: item["metric_key"])
    return items


async def source_map_payloads(db: AsyncSession) -> list[dict[str, Any]]:
    persisted = await _all(db, DashboardMetricSourceMap)
    by_key = {
        row.metric_key: {
            "id": row.id,
            "metric_key": row.metric_key,
            "primary_source": row.primary_source,
            "secondary_source": row.secondary_source,
            "confidence_rule": row.confidence_rule,
            "conflict_policy": row.conflict_policy,
        }
        for row in persisted
    }
    for item in SOURCE_MAPS:
        by_key.setdefault(item["metric_key"], dict(item))
    return sorted(by_key.values(), key=lambda item: item["metric_key"])


async def update_metric_definition(
    db: AsyncSession,
    user: dict[str, Any],
    metric_key: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    if _role(user) not in {"System_Admin", "AI_Admin"}:
        raise DashboardAuthorizationError("Only dashboard metric owners can update metric definitions.")
    definitions = await metric_definition_payloads(db, include_inactive=True)
    current = next((item for item in definitions if item["metric_key"] == metric_key), None)
    if not current:
        raise DashboardValidationError("Unknown dashboard metric key.", "metric_key")
    allowed = {"display_name", "owner_role", "permitted_use", "prohibited_use", "confidence_tier", "minimum_sample_size", "source_tables", "exclusions", "is_active"}
    payload = {key: value for key, value in patch.items() if key in allowed and value is not None}
    for value in payload.values():
        if isinstance(value, str) and PII_VALUE_PATTERN.search(value):
            raise DashboardValidationError("Metric definitions cannot contain PII.", "metric_definition")
    rows = await _all(db, DashboardMetricDefinition)
    row = next((item for item in rows if item.metric_key == metric_key), None)
    if row is None:
        row = DashboardMetricDefinition(
            metric_key=metric_key,
            display_name=current["display_name"],
            owner_role=current.get("owner_role"),
            permitted_use=current["permitted_use"],
            prohibited_use=current["prohibited_use"],
            confidence_tier=current.get("confidence_tier") or current.get("confidence") or "Medium",
            minimum_sample_size=int(current.get("minimum_sample_size") or 1),
            source_tables=current.get("source_tables") or [],
            exclusions=current.get("exclusions") or [],
            version=int(current.get("version") or 1),
            is_active=bool(current.get("is_active", True)),
            created_by=_user_id(user),
        )
        db.add(row)
    for key, value in payload.items():
        setattr(row, key, value)
    row.version = int(row.version or 1) + 1
    row.updated_by = _user_id(user)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.metric_definition.update", {"metric_key": metric_key, "version": row.version})
    return _definition_to_payload(row)


def _case_metadata(case: Case, station_by_id: dict[str, PoliceStation]) -> dict[str, Any]:
    station = station_by_id.get(case.police_station_id or "")
    return {
        "case_id": case.id,
        "case_type": _enum_value(case.case_type),
        "status": _enum_value(case.status),
        "crime_no": case.crime_no,
        "petition_no": case.petition_no,
        "police_station_id": case.police_station_id,
        "police_station_name": station.name if station else None,
        "io_id": case.io_id,
        "created_by": case.created_by,
        "created_at": _dt(case.created_at).isoformat() if _dt(case.created_at) else None,
        "age_days": _case_age_days(case, DashboardFilters("metadata", datetime.now(timezone.utc), datetime.now(timezone.utc))),
        "case_url": f"#case-detail:{case.id}",
    }


async def filter_options(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    station_by_id = data["station_by_id"]
    visible_stations = [
        station
        for station in data["stations"]
        if _station_allowed_for_user(user, station) or station.id in {case.police_station_id for case in data["visible_cases_all_dates"]}
    ]
    officers = []
    for item in data["users"]:
        if filters.police_station_id and item.police_station_id != filters.police_station_id:
            continue
        officers.append(
            {
                "user_id": item.id,
                "employee_id": item.employee_id,
                "full_name": item.full_name,
                "role": _enum_value(item.role),
                "police_station_id": item.police_station_id,
            }
        )
    return {
        "filters": filters.public(),
        "stations": [
            {
                "police_station_id": station.id,
                "name": station.name,
                "zone": _station_zone(station),
                "district": station.district,
            }
            for station in visible_stations
        ],
        "zones": sorted({zone for zone in (_station_zone(station) for station in visible_stations) if zone}),
        "officers": sorted(officers, key=lambda item: (item.get("full_name") or "", item["user_id"])),
        "roles": sorted({str(_enum_value(item.role)) for item in data["users"]}),
        "statuses": LIFECYCLE_ORDER,
        "case_types": sorted({str(_enum_value(case.case_type)) for case in data["visible_cases_all_dates"]}),
        "offence_categories": sorted({case.offence_type for case in data["visible_cases_all_dates"] if case.offence_type}),
        "station_names_by_id": {station.id: station.name for station in station_by_id.values()},
    }


async def officer_detail_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters, user_id: str) -> dict[str, Any]:
    filters = replace(filters, io_id=user_id)
    data = await dashboard_dataset(db, user, filters)
    officer_payload = await officer_metrics(db, user, filters)
    row = next((item for item in officer_payload["items"] if item["user_id"] == user_id), None)
    cases = [_case_metadata(case, data["station_by_id"]) for case in data["cases"]]
    await record_dashboard_usage(db, user, "dashboard.drilldown.officer", {"filters": data["filters"].public(), "officer_id": user_id})
    return {
        "filters": data["filters"].public(),
        "breadcrumb": ["Senior Dashboard", "Officers", user_id],
        "summary": row,
        "cases": cases,
        "total": len(cases),
        "warnings": _warnings(data["cases"], data["unlinked_parse_rows"]),
    }


async def station_detail_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters, station_id: str) -> dict[str, Any]:
    filters = replace(filters, police_station_id=station_id)
    data = await dashboard_dataset(db, user, filters)
    station_payload = await station_metrics(db, user, filters)
    row = next((item for item in station_payload["items"] if item["police_station_id"] == station_id), None)
    cases = [_case_metadata(case, data["station_by_id"]) for case in data["cases"]]
    await record_dashboard_usage(db, user, "dashboard.drilldown.station", {"filters": data["filters"].public(), "station_id": station_id})
    return {
        "filters": data["filters"].public(),
        "breadcrumb": ["Senior Dashboard", "Police Stations", station_id],
        "summary": row,
        "cases": cases,
        "total": len(cases),
        "warnings": _warnings(data["cases"], data["unlinked_parse_rows"]),
    }


async def lifecycle_stage_cases(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters, status: str) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, replace(filters, status=status))
    cases = [_case_metadata(case, data["station_by_id"]) for case in data["cases"]]
    await record_dashboard_usage(db, user, "dashboard.drilldown.lifecycle", {"filters": data["filters"].public(), "status": status})
    return {
        "filters": data["filters"].public(),
        "breadcrumb": ["Senior Dashboard", "Lifecycle", status],
        "status": status,
        "cases": cases,
        "total": len(cases),
        "warnings": _warnings(data["cases"], data["unlinked_parse_rows"]),
    }


async def document_analytics_metrics(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    data = await dashboard_dataset(db, user, filters)
    filters = data["filters"]
    subtype = Counter()
    export_formats = Counter()
    signature_status = Counter()
    templates = Counter()
    for doc in data["generated"]:
        subtype[doc.document_subtype or "unknown"] += 1
        export_formats[doc.export_format or "not_exported"] += 1
        signature_status[_enum_value(doc.digital_signature_status)] += 1
        if doc.template_id:
            templates[doc.template_id] += 1
    parser_drafts = len([row for row in data["parse_rows"] if _parse_row_has_fir_draft(row)])
    payload = {
        "filters": filters.public(),
        "freshness": _freshness(data),
        "totals": {
            "generated_documents": len(data["generated"]),
            "fir_drafts_created": len([doc for doc in data["generated"] if _is_fir_draft(doc)]) + parser_drafts,
            "parser_fir_drafts": parser_drafts,
            "exported_documents": sum(value for key, value in export_formats.items() if key != "not_exported"),
            "signature_failures": signature_status.get("Signature_Failed", 0),
        },
        "subtypes": [{"subtype": key, "count": value} for key, value in subtype.most_common()],
        "export_formats": [{"format": key, "count": value} for key, value in export_formats.most_common()],
        "signature_status": [{"status": key, "count": value} for key, value in signature_status.most_common()],
        "templates": [{"template_id": key, "count": value} for key, value in templates.most_common()],
        "warnings": _warnings(data["cases"], data["unlinked_parse_rows"]),
    }
    _assert_payload_safe(payload)
    return payload


def _metric_value_from_payload(metric_key: str, overview: dict[str, Any], processing: dict[str, Any], adoption: dict[str, Any]) -> tuple[Optional[float], int]:
    kpis = overview.get("kpis") or {}
    if metric_key in kpis and kpis[metric_key] is not None:
        return float(kpis[metric_key]), int(kpis.get("cases_created") or 0)
    if metric_key == "median_complaint_to_fir_draft_minutes":
        value = processing.get("median_minutes")
        return (float(value), int(processing.get("completed_count") or 0)) if value is not None else (None, 0)
    ai = adoption.get("ai_effectiveness") or {}
    if metric_key == "ai_acceptance_rate":
        value = ai.get("acceptance_rate")
        return (float(value), int(ai.get("reviewed_outputs") or 0)) if value is not None else (None, 0)
    if metric_key == "low_confidence_rate":
        value = ai.get("low_confidence_rate")
        return (float(value), int(ai.get("low_confidence_outputs") or 0)) if value is not None else (None, 0)
    return None, 0


def _threshold_breached(operator: str, observed: Optional[float], threshold: float) -> bool:
    if observed is None:
        return False
    return {
        ">": observed > threshold,
        ">=": observed >= threshold,
        "<": observed < threshold,
        "<=": observed <= threshold,
        "==": observed == threshold,
        "!=": observed != threshold,
    }.get(operator, False)


async def list_alert_rules(db: AsyncSession, user: dict[str, Any]) -> dict[str, Any]:
    ensure_dashboard_access(user, normalize_filters())
    rows = await _all(db, DashboardAlertRule)
    items = [
        {
            "id": row.id,
            "metric_key": row.metric_key,
            "scope_type": row.scope_type,
            "threshold_operator": row.threshold_operator,
            "threshold_value": row.threshold_value,
            "period": row.period,
            "severity": row.severity,
            "notification_channels": row.notification_channels or [],
            "minimum_sample_size": row.minimum_sample_size,
            "is_active": row.is_active,
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}


async def create_alert_rule(db: AsyncSession, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only supervisory users can manage dashboard alerts.")
    operator = payload.get("threshold_operator") or ">="
    if operator not in {">", ">=", "<", "<=", "==", "!="}:
        raise DashboardValidationError("Unsupported threshold operator.", "threshold_operator")
    metric_key = payload.get("metric_key")
    if metric_key not in {item["metric_key"] for item in await metric_definition_payloads(db, include_inactive=True)}:
        raise DashboardValidationError("Unknown dashboard metric key.", "metric_key")
    rule = DashboardAlertRule(
        metric_key=metric_key,
        scope_type=payload.get("scope_type") or "all",
        threshold_operator=operator,
        threshold_value=float(payload.get("threshold_value")),
        period=payload.get("period") or "weekly",
        severity=payload.get("severity") or "warning",
        notification_channels=payload.get("notification_channels") or ["in_app"],
        minimum_sample_size=int(payload.get("minimum_sample_size") or 5),
        is_active=bool(payload.get("is_active", True)),
        created_by=_user_id(user),
    )
    db.add(rule)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.alert_rule.create", {"rule_id": rule.id, "metric_key": rule.metric_key})
    return (await list_alert_rules(db, user))["items"][-1]


async def update_alert_rule(db: AsyncSession, user: dict[str, Any], rule_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only supervisory users can manage dashboard alerts.")
    row = await db.get(DashboardAlertRule, rule_id)
    if row is None:
        raise DashboardValidationError("Alert rule not found.", "rule_id")
    for key in ("threshold_operator", "threshold_value", "severity", "notification_channels", "minimum_sample_size", "is_active", "period"):
        if key in patch and patch[key] is not None:
            setattr(row, key, patch[key])
    row.updated_by = _user_id(user)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.alert_rule.update", {"rule_id": rule_id})
    return next(item for item in (await list_alert_rules(db, user))["items"] if item["id"] == rule_id)


async def list_alerts(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    overview = await overview_metrics(db, user, filters)
    processing = await processing_time_metrics(db, user, filters)
    adoption = await feature_adoption_metrics(db, user, filters)
    rules = [row for row in await _all(db, DashboardAlertRule) if row.is_active]
    existing = await _all(db, DashboardAlertInstance)
    open_keys = {(row.rule_id, row.period, row.scope_type, row.scope_id, row.status) for row in existing}
    for rule in rules:
        observed, sample_size = _metric_value_from_payload(rule.metric_key, overview, processing, adoption)
        if sample_size < int(rule.minimum_sample_size or 0):
            continue
        if not _threshold_breached(rule.threshold_operator, observed, float(rule.threshold_value)):
            continue
        scope = overview.get("scope") or {"type": "all", "id": None}
        key = (rule.id, rule.period, scope["type"], scope.get("id"), "open")
        if key in open_keys:
            continue
        alert = DashboardAlertInstance(
            rule_id=rule.id,
            metric_key=rule.metric_key,
            observed_value=observed,
            threshold_value=rule.threshold_value,
            period=rule.period,
            scope_type=scope["type"],
            scope_id=scope.get("id"),
            severity=rule.severity,
            status="open",
            recommended_action="Review the metric definition, sample size, and station/officer drill-down before operational action.",
            created_by=_user_id(user),
        )
        db.add(alert)
        if "in_app" in (rule.notification_channels or []):
            db.add(
                Notification(
                    user_id=_user_id(user) or getattr(rule, "created_by", None) or "admin",
                    type="dashboard_alert",
                    message=f"Dashboard alert: {rule.metric_key} {rule.threshold_operator} {rule.threshold_value}",
                    entity_type="dashboard_alert",
                    entity_id=alert.id,
                    created_by=_user_id(user),
                )
            )
    await db.flush()
    rows = await _all(db, DashboardAlertInstance)
    items = [
        {
            "id": row.id,
            "rule_id": row.rule_id,
            "metric_key": row.metric_key,
            "observed_value": row.observed_value,
            "threshold_value": row.threshold_value,
            "period": row.period,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "severity": row.severity,
            "status": row.status,
            "recommended_action": row.recommended_action,
            "acknowledged_by": row.acknowledged_by,
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        }
        for row in rows
        if row.status != "resolved"
    ]
    return {"items": items, "total": len(items), "warnings": overview.get("warnings", [])}


async def acknowledge_alert(db: AsyncSession, user: dict[str, Any], alert_id: str) -> dict[str, Any]:
    row = await db.get(DashboardAlertInstance, alert_id)
    if row is None:
        raise DashboardValidationError("Alert not found.", "alert_id")
    row.status = "acknowledged"
    row.acknowledged_by = _user_id(user)
    row.acknowledged_at = datetime.now(timezone.utc)
    row.updated_by = _user_id(user)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.alert.acknowledge", {"alert_id": alert_id})
    return {"id": row.id, "status": row.status, "acknowledged_by": row.acknowledged_by, "acknowledged_at": row.acknowledged_at.isoformat()}


def _rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO()
    if not rows:
        return b""
    writer = csv.DictWriter(stream, fieldnames=sorted({key for row in rows for key in row.keys()}))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in writer.fieldnames})
    return stream.getvalue().encode("utf-8")


async def _export_payload(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters, report_type: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if report_type == "officers":
        payload = await officer_metrics(db, user, filters)
        return payload, payload.get("items", [])
    if report_type == "stations":
        payload = await station_metrics(db, user, filters)
        return payload, payload.get("items", [])
    if report_type == "lifecycle":
        payload = await lifecycle_metrics(db, user, filters)
        return payload, payload.get("items", [])
    if report_type == "processing-times":
        payload = await processing_time_metrics(db, user, filters)
        return payload, payload.get("items", [])
    if report_type == "feature-adoption":
        payload = await feature_adoption_metrics(db, user, filters)
        return payload, payload.get("items", [])
    if report_type == "documents":
        payload = await document_analytics_metrics(db, user, filters)
        return payload, payload.get("subtypes", [])
    payload = await overview_metrics(db, user, filters)
    rows = [{"metric": key, "value": value} for key, value in (payload.get("kpis") or {}).items()]
    return payload, rows


def _build_export_content(
    *,
    payload: dict[str, Any],
    rows: list[dict[str, Any]],
    export_format: str,
    watermark: dict[str, Any],
) -> tuple[bytes, str, str]:
    export_format = export_format.lower()
    if export_format == "csv":
        content = _rows_to_csv(rows)
        mime = "text/csv"
    elif export_format == "pdf":
        content = ("IQW Senior Dashboard Export\n" + json.dumps(watermark, indent=2) + "\n" + json.dumps(rows, indent=2, default=str)).encode("utf-8")
        mime = "application/pdf"
    else:
        content = json.dumps({"watermark": watermark, "payload": payload}, default=str, indent=2).encode("utf-8")
        mime = "application/json"
        export_format = "json"
    digest = hashlib.sha256(content).hexdigest()
    file_uri = f"data:{mime};sha256={digest};base64,{base64.b64encode(content).decode('ascii')}"
    return content, digest, file_uri


async def create_export_job(
    db: AsyncSession,
    user: dict[str, Any],
    filters: DashboardFilters,
    *,
    report_type: str,
    export_format: str,
    purpose: str,
    schedule: Optional[str] = None,
) -> dict[str, Any]:
    if _role(user) in SELF_VIEW_ROLES:
        raise DashboardAuthorizationError("Self-view roles cannot export dashboard reports.")
    if not purpose or len(purpose.strip()) < 5:
        raise DashboardValidationError("Export purpose is required.", "purpose")
    if PII_VALUE_PATTERN.search(purpose):
        raise DashboardValidationError("Export purpose cannot include PII.", "purpose")
    stations = await _all(db, PoliceStation)
    effective_filters = resolve_dashboard_filters(user, filters, stations)
    watermark = {
        "purpose": purpose.strip()[:200],
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": _user_id(user),
        "role": _role(user),
        "scope": _scope_payload(stations, effective_filters, user),
        "personnel_safeguard": "For operational awareness only; not for standalone disciplinary use.",
        "schedule": schedule,
    }
    job = DashboardExportJob(
        requester_id=_user_id(user),
        report_type=report_type,
        export_format=export_format.lower(),
        status="queued",
        filters=effective_filters.public(),
        scope=watermark["scope"],
        file_uri=None,
        sha256_hash=None,
        watermark=json.dumps(watermark, sort_keys=True),
        completed_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=_user_id(user),
    )
    db.add(job)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.export.queue", {"job_id": job.id, "report_type": report_type, "format": export_format, "purpose": purpose, "scope": job.scope})
    wake_dashboard_worker()
    return export_job_payload(job)


def export_job_payload(job: DashboardExportJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "requester_id": job.requester_id,
        "report_type": job.report_type,
        "export_format": job.export_format,
        "status": job.status,
        "filters": job.filters,
        "scope": job.scope,
        "file_uri": job.file_uri,
        "sha256_hash": job.sha256_hash,
        "watermark": job.watermark,
        "requested_at": job.requested_at.isoformat() if job.requested_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "revoked_at": job.revoked_at.isoformat() if job.revoked_at else None,
        "error_code": job.error_code,
    }


async def list_export_jobs(db: AsyncSession, user: dict[str, Any]) -> dict[str, Any]:
    ensure_dashboard_access(user, normalize_filters())
    rows = await _all(db, DashboardExportJob)
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        rows = [row for row in rows if row.requester_id == _user_id(user)]
    items = [export_job_payload(row) for row in rows]
    return {"items": items, "total": len(items)}


async def get_export_job(db: AsyncSession, user: dict[str, Any], job_id: str) -> dict[str, Any]:
    job = await db.get(DashboardExportJob, job_id)
    if job is None:
        raise DashboardValidationError("Export job not found.", "job_id")
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES and job.requester_id != _user_id(user):
        raise DashboardAuthorizationError("Export job is outside dashboard scope.")
    return export_job_payload(job)


async def retry_export_job(db: AsyncSession, user: dict[str, Any], job_id: str) -> dict[str, Any]:
    job = await db.get(DashboardExportJob, job_id)
    if job is None:
        raise DashboardValidationError("Export job not found.", "job_id")
    job.status = "queued"
    job.error_code = None
    job.file_uri = None
    job.sha256_hash = None
    job.completed_at = None
    job.updated_by = _user_id(user)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.export.retry", {"job_id": job_id})
    wake_dashboard_worker()
    return export_job_payload(job)


async def process_dashboard_export_job(db: AsyncSession, job: DashboardExportJob) -> dict[str, Any]:
    if job.status not in {"queued", "running"}:
        return export_job_payload(job)
    job.status = "running"
    job.updated_by = "dashboard_worker"
    await db.flush()
    user_model = await db.get(User, job.requester_id) if job.requester_id else None
    user = _user_payload_from_model(user_model, job.requester_id)
    try:
        filters = _filters_from_public(job.filters or {})
        payload, rows = await _export_payload(db, user, filters, job.report_type)
        watermark = json.loads(job.watermark or "{}")
        watermark["generated_at"] = datetime.now(timezone.utc).isoformat()
        watermark["scope"] = payload.get("scope") or job.scope
        _content, digest, file_uri = _build_export_content(
            payload=payload,
            rows=rows,
            export_format=job.export_format,
            watermark=watermark,
        )
        job.status = "completed"
        job.file_uri = file_uri
        job.sha256_hash = digest
        job.watermark = json.dumps(watermark, sort_keys=True)
        job.scope = payload.get("scope") or job.scope
        job.filters = payload.get("filters") or job.filters
        job.completed_at = datetime.now(timezone.utc)
        job.error_code = None
        job.updated_by = "dashboard_worker"
        await db.flush()
        await record_dashboard_usage(db, user, "dashboard.export.complete", {"job_id": job.id, "report_type": job.report_type, "scope": job.scope})
    except Exception as exc:
        job.status = "failed"
        job.error_code = exc.__class__.__name__
        job.updated_by = "dashboard_worker"
        await db.flush()
    return export_job_payload(job)


async def process_next_dashboard_export_job(db: AsyncSession) -> bool:
    result = await db.execute(
        select(DashboardExportJob)
        .where(DashboardExportJob.status == "queued")
        .order_by(DashboardExportJob.requested_at.asc(), DashboardExportJob.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalars().first()
    if job is None:
        return False
    await process_dashboard_export_job(db, job)
    return True


async def revoke_export_job(db: AsyncSession, user: dict[str, Any], job_id: str) -> dict[str, Any]:
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only supervisory users can revoke exports.")
    job = await db.get(DashboardExportJob, job_id)
    if job is None:
        raise DashboardValidationError("Export job not found.", "job_id")
    job.status = "revoked"
    job.revoked_by = _user_id(user)
    job.revoked_at = datetime.now(timezone.utc)
    job.file_uri = None
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.export.revoke", {"job_id": job_id})
    return export_job_payload(job)


async def refresh_dashboard_snapshot(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters, metric_key: str = "overview") -> dict[str, Any]:
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only supervisory users can refresh dashboard snapshots.")
    stations = await _all(db, PoliceStation)
    filters = resolve_dashboard_filters(user, filters, stations)
    row = DashboardMetricSnapshot(
        metric_key=metric_key,
        period=filters.period,
        scope_type=_scope_payload(stations, filters, user).get("type", "filtered"),
        scope_id=_scope_payload(stations, filters, user).get("id"),
        filters_hash=_hash_filters(filters),
        filters=filters.public(),
        payload={},
        metric_definition_version=max([item.get("version", 1) for item in await metric_definition_payloads(db, include_inactive=True)] or [1]),
        source_watermark_at=None,
        status="Queued",
        created_by=_user_id(user),
    )
    db.add(row)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.snapshot.queue", {"snapshot_id": row.id, "metric_key": metric_key})
    wake_dashboard_worker()
    return {
        "id": row.id,
        "metric_key": row.metric_key,
        "status": row.status,
        "filters_hash": row.filters_hash,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        "source_watermark_at": row.source_watermark_at.isoformat() if row.source_watermark_at else None,
    }


async def process_dashboard_snapshot_job(db: AsyncSession, snapshot: DashboardMetricSnapshot) -> dict[str, Any]:
    if snapshot.status not in {"Queued", "Failed"}:
        return {
            "id": snapshot.id,
            "metric_key": snapshot.metric_key,
            "status": snapshot.status,
        }
    snapshot.status = "Running"
    snapshot.updated_by = "dashboard_worker"
    await db.flush()
    user_model = await db.get(User, snapshot.created_by) if snapshot.created_by else None
    user = _user_payload_from_model(user_model, snapshot.created_by)
    try:
        filters = _filters_from_public(snapshot.filters or {})
        payload = await overview_metrics(db, user, filters) if snapshot.metric_key == "overview" else await processing_time_metrics(db, user, filters)
        source = payload.get("freshness", {}).get("source_watermark_at")
        snapshot.payload = payload
        snapshot.filters = payload.get("filters") or snapshot.filters
        snapshot.filters_hash = _hash_filters(_filters_from_public(snapshot.filters))
        snapshot.scope_type = (payload.get("scope") or {}).get("type", snapshot.scope_type)
        snapshot.scope_id = (payload.get("scope") or {}).get("id", snapshot.scope_id)
        snapshot.source_watermark_at = _parse_date(source, field="source_watermark_at") if isinstance(source, str) else None
        snapshot.computed_at = datetime.now(timezone.utc)
        snapshot.status = "Current"
        snapshot.error_code = None
        snapshot.updated_by = "dashboard_worker"
        await db.flush()
        await record_dashboard_usage(db, user, "dashboard.snapshot.complete", {"snapshot_id": snapshot.id, "metric_key": snapshot.metric_key})
    except Exception as exc:
        snapshot.status = "Failed"
        snapshot.error_code = exc.__class__.__name__
        snapshot.updated_by = "dashboard_worker"
        await db.flush()
    return {
        "id": snapshot.id,
        "metric_key": snapshot.metric_key,
        "status": snapshot.status,
        "filters_hash": snapshot.filters_hash,
        "computed_at": snapshot.computed_at.isoformat() if snapshot.computed_at else None,
        "source_watermark_at": snapshot.source_watermark_at.isoformat() if snapshot.source_watermark_at else None,
    }


async def process_next_dashboard_snapshot_job(db: AsyncSession) -> bool:
    result = await db.execute(
        select(DashboardMetricSnapshot)
        .where(DashboardMetricSnapshot.status == "Queued")
        .order_by(DashboardMetricSnapshot.computed_at.asc(), DashboardMetricSnapshot.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    snapshot = result.scalars().first()
    if snapshot is None:
        return False
    await process_dashboard_snapshot_job(db, snapshot)
    return True


async def process_next_dashboard_background_job(db: AsyncSession) -> bool:
    if await process_next_dashboard_export_job(db):
        return True
    if await process_next_dashboard_snapshot_job(db):
        return True
    return False


async def list_metric_disputes(db: AsyncSession, user: dict[str, Any]) -> dict[str, Any]:
    ensure_dashboard_access(user, normalize_filters())
    rows = await _all(db, DashboardMetricDispute)
    items = [
        {
            "id": row.id,
            "metric_key": row.metric_key,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "reason_code": row.reason_code,
            "status": row.status,
            "disputed_by": row.disputed_by,
            "reviewer_id": row.reviewer_id,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }
        for row in rows
    ]
    return {"items": items, "total": len(items)}


async def create_metric_dispute(db: AsyncSession, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    ensure_dashboard_access(user, normalize_filters())
    explanation = _safe_explanation(payload.get("explanation"))
    metric_key = payload.get("metric_key")
    scope_type = payload.get("scope_type") or "filtered"
    scope_id = payload.get("scope_id")
    for row in await _all(db, DashboardMetricDispute):
        if row.metric_key == metric_key and row.scope_type == scope_type and row.scope_id == scope_id and row.status == "open":
            raise DashboardConflictError("An open dispute already exists for this metric and scope.", "metric_key")
    dispute = DashboardMetricDispute(
        metric_key=metric_key,
        scope_type=scope_type,
        scope_id=scope_id,
        disputed_by=_user_id(user),
        reason_code=payload.get("reason_code") or "data_quality",
        explanation=explanation,
        status="open",
        created_by=_user_id(user),
    )
    db.add(dispute)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.metric_dispute.create", {"dispute_id": dispute.id, "metric_key": metric_key})
    return (await list_metric_disputes(db, user))["items"][-1]


async def review_metric_dispute(db: AsyncSession, user: dict[str, Any], dispute_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only supervisory users can review metric disputes.")
    dispute = await db.get(DashboardMetricDispute, dispute_id)
    if dispute is None:
        raise DashboardValidationError("Metric dispute not found.", "dispute_id")
    status = payload.get("status") or "resolved"
    if status not in {"resolved", "rejected"}:
        raise DashboardValidationError("Unsupported dispute review status.", "status")
    dispute.status = status
    dispute.reviewer_id = _user_id(user)
    dispute.resolution_notes = _safe_explanation(payload.get("resolution_notes"))
    dispute.resolved_at = datetime.now(timezone.utc)
    if status == "resolved" and payload.get("corrected_value") is not None:
        db.add(
            DashboardMetricCorrection(
                dispute_id=dispute.id,
                metric_key=dispute.metric_key,
                original_value=payload.get("original_value"),
                corrected_value=payload.get("corrected_value"),
                approved_by=_user_id(user),
                created_by=_user_id(user),
            )
        )
        db.add(
            Notification(
                user_id=dispute.disputed_by or _user_id(user) or "admin",
                type="dashboard_metric_dispute",
                message=f"Metric dispute {dispute.metric_key} was resolved.",
                entity_type="dashboard_metric_dispute",
                entity_id=dispute.id,
                created_by=_user_id(user),
            )
        )
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.metric_dispute.review", {"dispute_id": dispute.id, "status": status})
    return next(item for item in (await list_metric_disputes(db, user))["items"] if item["id"] == dispute_id)


async def list_training_recommendations(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    ensure_dashboard_access(user, filters)
    rows = [row for row in await _all(db, DashboardTrainingRecommendation) if row.status == "open"]
    if not rows:
        adoption = await feature_adoption_metrics(db, user, filters)
        ai = adoption.get("ai_effectiveness") or {}
        if ai.get("low_confidence_rate") and ai["low_confidence_rate"] >= 30:
            row = DashboardTrainingRecommendation(
                scope_type="filtered",
                scope_id=None,
                metric_key="low_confidence_rate",
                evidence={"low_confidence_rate": ai["low_confidence_rate"], "sample": ai.get("low_confidence_outputs")},
                suggested_topic="Review AI confidence interpretation and knowledge-base feedback workflow",
                status="open",
                created_by=_user_id(user),
            )
            db.add(row)
            await db.flush()
            rows = [row]
    items = [
        {
            "id": row.id,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "metric_key": row.metric_key,
            "evidence": row.evidence,
            "suggested_topic": row.suggested_topic,
            "status": row.status,
            "dismissed_until": row.dismissed_until.isoformat() if row.dismissed_until else None,
        }
        for row in rows
    ]
    return {"items": items, "total": len(items), "disclaimer": "Training recommendations are non-disciplinary operational support signals."}


async def review_training_recommendation(db: AsyncSession, user: dict[str, Any], recommendation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if _role(user) not in SUPERVISORY_DASHBOARD_ROLES | ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only supervisory users can review training recommendations.")
    row = await db.get(DashboardTrainingRecommendation, recommendation_id)
    if row is None:
        raise DashboardValidationError("Training recommendation not found.", "recommendation_id")
    action = payload.get("status") or "reviewed"
    row.status = action
    row.reviewed_by = _user_id(user)
    row.reviewed_at = datetime.now(timezone.utc)
    if payload.get("dismiss_days"):
        row.dismissed_until = datetime.now(timezone.utc) + timedelta(days=int(payload["dismiss_days"]))
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.training_recommendation.review", {"recommendation_id": row.id, "status": row.status})
    return {"id": row.id, "status": row.status, "reviewed_by": row.reviewed_by, "reviewed_at": row.reviewed_at.isoformat()}


async def get_validation_state(db: AsyncSession, user: dict[str, Any], feature_key: str = "predictive_bottleneck_signals") -> dict[str, Any]:
    ensure_dashboard_access(user, normalize_filters())
    rows = await _all(db, DashboardValidationState)
    row = next((item for item in rows if item.feature_key == feature_key), None)
    if not row:
        return {"feature_key": feature_key, "state": "restricted", "findings": {"reason": "Feature requires validation approval before display."}}
    return {
        "id": row.id,
        "feature_key": row.feature_key,
        "state": row.state,
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "findings": row.findings or {},
    }


async def update_validation_state(db: AsyncSession, user: dict[str, Any], feature_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if _role(user) not in ADMIN_DASHBOARD_ROLES | AI_DASHBOARD_ROLES:
        raise DashboardAuthorizationError("Only AI or system admins can update dashboard validation gates.")
    rows = await _all(db, DashboardValidationState)
    row = next((item for item in rows if item.feature_key == feature_key), None)
    if row is None:
        row = DashboardValidationState(feature_key=feature_key, created_by=_user_id(user))
        db.add(row)
    row.state = payload.get("state") or row.state
    row.findings = payload.get("findings") or row.findings or {}
    row.approved_by = _user_id(user) if row.state == "approved" else row.approved_by
    row.approved_at = datetime.now(timezone.utc) if row.state == "approved" else row.approved_at
    row.updated_by = _user_id(user)
    await db.flush()
    await record_dashboard_usage(db, user, "dashboard.validation_state.update", {"feature_key": feature_key, "state": row.state})
    return await get_validation_state(db, user, feature_key)


async def predictive_signals(db: AsyncSession, user: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    state = await get_validation_state(db, user, "predictive_bottleneck_signals")
    if state["state"] != "approved":
        return {
            "enabled": False,
            "validation_state": state,
            "items": [],
            "disclaimer": "Predictive bottleneck signals are disabled until validation is approved; no case status or personnel score is mutated.",
        }
    lifecycle = await lifecycle_metrics(db, user, filters)
    items = []
    for stage in lifecycle["items"]:
        if stage["count"] and stage["p90_age_days"] >= 7:
            items.append(
                {
                    "signal": "possible_bottleneck",
                    "status": stage["status"],
                    "reason_codes": ["stage_age_p90_high", "aggregate_only"],
                    "confidence": "low",
                    "p90_age_days": stage["p90_age_days"],
                    "recommendation": "Review aggregate backlog and case mix before operational action.",
                }
            )
    return {"enabled": True, "validation_state": state, "items": items, "total": len(items)}


async def list_saved_views(db: AsyncSession, user: dict[str, Any]) -> dict[str, Any]:
    uid = _user_id(user)
    rows = [row for row in await _all(db, DashboardSavedView) if row.user_id == uid]
    items = [{"id": row.id, "name": row.name, "filters": row.filters, "is_default": row.is_default} for row in rows]
    return {"items": items, "total": len(items)}


async def save_dashboard_view(db: AsyncSession, user: dict[str, Any], name: str, filters: DashboardFilters, is_default: bool = False) -> dict[str, Any]:
    uid = _user_id(user)
    if not uid:
        raise DashboardAuthorizationError("Authenticated user id is required.")
    if not name.strip():
        raise DashboardValidationError("Saved view name is required.", "name")
    if is_default:
        for row in await _all(db, DashboardSavedView):
            if row.user_id == uid:
                row.is_default = False
    row = DashboardSavedView(user_id=uid, name=name.strip()[:100], filters=filters.public(), is_default=is_default, created_by=uid)
    db.add(row)
    await db.flush()
    return {"id": row.id, "name": row.name, "filters": row.filters, "is_default": row.is_default}
