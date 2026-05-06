from __future__ import annotations

"""Persistence helpers for complaint-parser to KIS indexing state."""

from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa

from database import get_engine, parse_records


KIS_INDEX_STATUSES = {"not_started", "pending", "running", "indexed", "failed", "disabled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_detail(value: str | None) -> str | None:
    if not value:
        return None
    return value[:300]


def retry_delay_seconds(attempt_count: int, *, base_seconds: int = 60, max_seconds: int = 3600) -> int:
    bounded_attempt = max(1, int(attempt_count or 1))
    return min(max_seconds, max(1, base_seconds) * (2 ** (bounded_attempt - 1)))


def normalize_kis_result_status(result: dict[str, Any]) -> str:
    if not result.get("enabled"):
        return "disabled"
    if result.get("indexed"):
        return "indexed"
    return "failed"


def summarize_kis_result(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "enabled",
        "indexed",
        "idempotent_replay",
        "source_id",
        "chunk_count",
        "fact_count",
        "graph_edge_count",
        "wiki_article_id",
        "quality_passed",
        "published_snapshot_id",
        "reason",
        "error",
    )
    return {key: result.get(key) for key in keys if key in result}


async def update_kis_index_status(
    record_id: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    if status not in KIS_INDEX_STATUSES:
        raise ValueError(f"Unsupported KIS index status: {status}")

    result = result or {}
    values: dict[str, Any] = {
        "kis_index_status": status,
        "kis_last_attempt_at": _now(),
        "kis_index_summary": summarize_kis_result(result) if result else None,
    }

    if status == "indexed":
        values.update(
            {
                "kis_source_id": result.get("source_id"),
                "kis_wiki_article_id": result.get("wiki_article_id"),
                "kis_snapshot_id": result.get("published_snapshot_id"),
                "kis_quality_passed": result.get("quality_passed"),
                "kis_fact_count": result.get("fact_count"),
                "kis_graph_edge_count": result.get("graph_edge_count"),
                "kis_chunk_count": result.get("chunk_count"),
                "kis_idempotent_replay": result.get("idempotent_replay"),
                "kis_privacy_summary": result.get("privacy_summary"),
                "kis_error_code": None,
                "kis_error_detail": None,
                "kis_indexed_at": _now(),
                "kis_next_attempt_at": None,
                "kis_worker_id": None,
                "kis_locked_at": None,
                "kis_locked_until": None,
            }
        )
    elif status == "failed":
        values.update(
            {
                "kis_error_code": error_code or result.get("reason") or result.get("error") or "kis_indexing_failed",
                "kis_error_detail": _safe_detail(error_detail or result.get("reason") or result.get("error")),
                "kis_worker_id": None,
                "kis_locked_at": None,
                "kis_locked_until": None,
            }
        )
    elif status == "disabled":
        values.update(
            {
                "kis_error_code": result.get("reason") or "kis_not_configured",
                "kis_error_detail": None,
                "kis_next_attempt_at": None,
                "kis_worker_id": None,
                "kis_locked_at": None,
                "kis_locked_until": None,
            }
        )
    elif status == "running":
        values.update(
            {
                "kis_error_code": None,
                "kis_error_detail": None,
            }
        )

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            parse_records.update()
            .where(parse_records.c.id == record_id)
            .values(**values)
        )


def kis_record_projection() -> tuple[Any, ...]:
    return (
        parse_records.c.kis_index_status,
        parse_records.c.kis_source_id,
        parse_records.c.kis_wiki_article_id,
        parse_records.c.kis_snapshot_id,
        parse_records.c.kis_quality_passed,
        parse_records.c.kis_fact_count,
        parse_records.c.kis_graph_edge_count,
        parse_records.c.kis_chunk_count,
        parse_records.c.kis_idempotent_replay,
        parse_records.c.kis_privacy_summary,
        parse_records.c.kis_index_summary,
        parse_records.c.kis_error_code,
        parse_records.c.kis_error_detail,
        parse_records.c.kis_attempt_count,
        parse_records.c.kis_next_attempt_at,
        parse_records.c.kis_worker_id,
        parse_records.c.kis_locked_at,
        parse_records.c.kis_locked_until,
        parse_records.c.kis_last_attempt_at,
        parse_records.c.kis_indexed_at,
    )


def kis_record_payload(row: Any) -> dict[str, Any]:
    def scalar(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool, dict, list)):
            return value
        return None

    def iso(value: Any) -> str | None:
        if not hasattr(value, "isoformat"):
            return None
        rendered = value.isoformat()
        return rendered if isinstance(rendered, str) else None

    return {
        "kis_index_status": scalar(getattr(row, "kis_index_status", None)) or "not_started",
        "kis_source_id": scalar(getattr(row, "kis_source_id", None)),
        "kis_wiki_article_id": scalar(getattr(row, "kis_wiki_article_id", None)),
        "kis_snapshot_id": scalar(getattr(row, "kis_snapshot_id", None)),
        "kis_quality_passed": scalar(getattr(row, "kis_quality_passed", None)),
        "kis_fact_count": scalar(getattr(row, "kis_fact_count", None)),
        "kis_graph_edge_count": scalar(getattr(row, "kis_graph_edge_count", None)),
        "kis_chunk_count": scalar(getattr(row, "kis_chunk_count", None)),
        "kis_idempotent_replay": scalar(getattr(row, "kis_idempotent_replay", None)),
        "kis_privacy_summary": scalar(getattr(row, "kis_privacy_summary", None)),
        "kis_index_summary": scalar(getattr(row, "kis_index_summary", None)),
        "kis_error_code": scalar(getattr(row, "kis_error_code", None)),
        "kis_error_detail": scalar(getattr(row, "kis_error_detail", None)),
        "kis_attempt_count": scalar(getattr(row, "kis_attempt_count", None)) or 0,
        "kis_next_attempt_at": iso(getattr(row, "kis_next_attempt_at", None)),
        "kis_worker_id": scalar(getattr(row, "kis_worker_id", None)),
        "kis_locked_at": iso(getattr(row, "kis_locked_at", None)),
        "kis_locked_until": iso(getattr(row, "kis_locked_until", None)),
        "kis_last_attempt_at": iso(getattr(row, "kis_last_attempt_at", None)),
        "kis_indexed_at": iso(getattr(row, "kis_indexed_at", None)),
    }


async def enqueue_kis_indexing(record_id: str, *, reset_attempts: bool = False) -> None:
    values: dict[str, Any] = {
        "kis_index_status": "pending",
        "kis_next_attempt_at": _now(),
        "kis_error_code": None,
        "kis_error_detail": None,
        "kis_worker_id": None,
        "kis_locked_at": None,
        "kis_locked_until": None,
    }
    if reset_attempts:
        values["kis_attempt_count"] = 0
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            parse_records.update()
            .where(parse_records.c.id == record_id)
            .values(**values)
        )


async def claim_next_kis_index_record(
    *,
    worker_id: str,
    lock_seconds: int = 900,
    max_attempts: int = 5,
) -> dict[str, Any] | None:
    engine = await get_engine()
    lock_seconds = max(60, int(lock_seconds or 900))
    max_attempts = max(1, int(max_attempts or 5))
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            result = await conn.execute(
                sa.text(
                    """
                    WITH candidate AS (
                        SELECT id
                        FROM parse_records
                        WHERE (
                            kis_index_status = 'pending'
                            OR (
                                kis_index_status = 'failed'
                                AND COALESCE(kis_attempt_count, 0) < :max_attempts
                            )
                            OR (
                                kis_index_status = 'running'
                                AND kis_locked_until IS NOT NULL
                                AND kis_locked_until < now()
                            )
                        )
                        AND (kis_next_attempt_at IS NULL OR kis_next_attempt_at <= now())
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE parse_records
                    SET kis_index_status = 'running',
                        kis_attempt_count = COALESCE(kis_attempt_count, 0) + 1,
                        kis_worker_id = :worker_id,
                        kis_locked_at = now(),
                        kis_locked_until = now() + (:lock_seconds * interval '1 second'),
                        kis_last_attempt_at = now(),
                        kis_error_code = NULL,
                        kis_error_detail = NULL
                    FROM candidate
                    WHERE parse_records.id = candidate.id
                    RETURNING
                        parse_records.id,
                        parse_records.file_name,
                        parse_records.document_format,
                        parse_records.parsed_output,
                        parse_records.kis_attempt_count
                    """
                ),
                {
                    "worker_id": worker_id,
                    "lock_seconds": lock_seconds,
                    "max_attempts": max_attempts,
                },
            )
            row = result.first()
            if row is None:
                return None
            return {
                "id": str(row.id),
                "file_name": row.file_name,
                "document_format": row.document_format,
                "parsed_output": row.parsed_output,
                "kis_attempt_count": row.kis_attempt_count,
            }

        now = _now()
        result = await conn.execute(
            sa.select(
                parse_records.c.id,
                parse_records.c.file_name,
                parse_records.c.document_format,
                parse_records.c.parsed_output,
                parse_records.c.kis_attempt_count,
            )
            .where(
                sa.and_(
                    sa.or_(
                        parse_records.c.kis_index_status == "pending",
                        sa.and_(
                            parse_records.c.kis_index_status == "failed",
                            parse_records.c.kis_attempt_count < max_attempts,
                        ),
                        sa.and_(
                            parse_records.c.kis_index_status == "running",
                            parse_records.c.kis_locked_until.is_not(None),
                            parse_records.c.kis_locked_until < now,
                        ),
                    ),
                    sa.or_(
                        parse_records.c.kis_next_attempt_at.is_(None),
                        parse_records.c.kis_next_attempt_at <= now,
                    ),
                )
            )
            .order_by(parse_records.c.created_at.asc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        next_attempt_count = int(row.kis_attempt_count or 0) + 1
        await conn.execute(
            parse_records.update()
            .where(parse_records.c.id == row.id)
            .values(
                kis_index_status="running",
                kis_attempt_count=next_attempt_count,
                kis_worker_id=worker_id,
                kis_locked_at=now,
                kis_locked_until=now + timedelta(seconds=lock_seconds),
                kis_last_attempt_at=now,
                kis_error_code=None,
                kis_error_detail=None,
            )
        )
        return {
            "id": str(row.id),
            "file_name": row.file_name,
            "document_format": row.document_format,
            "parsed_output": row.parsed_output,
            "kis_attempt_count": next_attempt_count,
        }


async def mark_kis_index_failure(
    record_id: str,
    *,
    error_code: str,
    error_detail: str,
    attempt_count: int,
    max_attempts: int = 5,
    retry_base_seconds: int = 60,
    retry_max_seconds: int = 3600,
) -> dict[str, Any]:
    max_attempts = max(1, int(max_attempts or 5))
    attempt_count = max(1, int(attempt_count or 1))
    retryable = attempt_count < max_attempts
    next_attempt = None
    if retryable:
        next_attempt = _now() + timedelta(
            seconds=retry_delay_seconds(
                attempt_count,
                base_seconds=retry_base_seconds,
                max_seconds=retry_max_seconds,
            )
        )
    values = {
        "kis_index_status": "failed",
        "kis_error_code": error_code or "kis_indexing_failed",
        "kis_error_detail": _safe_detail(error_detail),
        "kis_next_attempt_at": next_attempt,
        "kis_worker_id": None,
        "kis_locked_at": None,
        "kis_locked_until": None,
        "kis_last_attempt_at": _now(),
    }
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            parse_records.update()
            .where(parse_records.c.id == record_id)
            .values(**values)
        )
    return {
        "status": "failed",
        "retryable": retryable,
        "next_attempt_at": next_attempt.isoformat() if next_attempt else None,
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
    }


async def requeue_failed_kis_indexing(limit: int = 100) -> int:
    bounded_limit = max(1, min(int(limit or 100), 500))
    engine = await get_engine()
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            result = await conn.execute(
                sa.text(
                    """
                    WITH candidates AS (
                        SELECT id
                        FROM parse_records
                        WHERE kis_index_status = 'failed'
                        ORDER BY kis_last_attempt_at ASC NULLS FIRST, created_at ASC
                        LIMIT :limit
                    )
                    UPDATE parse_records
                    SET kis_index_status = 'pending',
                        kis_attempt_count = 0,
                        kis_next_attempt_at = now(),
                        kis_error_code = NULL,
                        kis_error_detail = NULL,
                        kis_worker_id = NULL,
                        kis_locked_at = NULL,
                        kis_locked_until = NULL
                    FROM candidates
                    WHERE parse_records.id = candidates.id
                    RETURNING parse_records.id
                    """
                ),
                {"limit": bounded_limit},
            )
            return len(result.fetchall())
        result = await conn.execute(
            sa.select(parse_records.c.id)
            .where(parse_records.c.kis_index_status == "failed")
            .order_by(parse_records.c.created_at.asc())
            .limit(bounded_limit)
        )
        ids = [row.id for row in result]
        if not ids:
            return 0
        update_result = await conn.execute(
            parse_records.update()
            .where(parse_records.c.id.in_(ids))
            .values(
                kis_index_status="pending",
                kis_attempt_count=0,
                kis_next_attempt_at=_now(),
                kis_error_code=None,
                kis_error_detail=None,
                kis_worker_id=None,
                kis_locked_at=None,
                kis_locked_until=None,
            )
        )
        return int(update_result.rowcount or 0)


async def list_kis_indexing_records(limit: int = 50) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit or 50), 200))
    engine = await get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            sa.select(
                parse_records.c.id,
                parse_records.c.file_name,
                parse_records.c.document_format,
                parse_records.c.created_at,
                *kis_record_projection(),
            )
            .order_by(parse_records.c.created_at.desc())
            .limit(bounded_limit)
        )
        return [
            {
                "id": str(row.id),
                "file_name": row.file_name,
                "document_format": row.document_format,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                **kis_record_payload(row),
            }
            for row in rows
        ]


async def kis_index_status_counts() -> dict[str, int]:
    engine = await get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            sa.select(
                parse_records.c.kis_index_status,
                sa.func.count().label("record_count"),
            ).group_by(parse_records.c.kis_index_status)
        )
        counts = {status: 0 for status in sorted(KIS_INDEX_STATUSES)}
        for row in rows:
            counts[getattr(row, "kis_index_status", None) or "not_started"] = int(row.record_count or 0)
        return counts
