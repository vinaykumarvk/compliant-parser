"""Cloud SQL persistence layer for parse history."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

metadata = sa.MetaData()

parse_records = sa.Table(
    "parse_records",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("file_name", sa.Text, nullable=False),
    sa.Column("file_size", sa.Integer, nullable=False),
    sa.Column("file_bytes", BYTEA, nullable=False),
    sa.Column("parsed_output", JSONB, nullable=False),
    sa.Column("document_format", sa.Text, nullable=True),
    sa.Column("completeness_score", sa.Float, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    ),
)

_idx_created = sa.Index("ix_parse_records_created_at", parse_records.c.created_at.desc())

_engine: AsyncEngine | None = None
_connector: Any | None = None

_POOL_KWARGS = dict(pool_size=5, max_overflow=2, pool_recycle=1800)


async def get_engine() -> AsyncEngine:
    """Return (and lazily create) the async engine.

    Two connection paths:
      1. DATABASE_URL env var  → direct asyncpg (local dev / Cloud SQL proxy)
      2. CLOUD_SQL_CONNECTION_NAME → Cloud SQL Python Connector with IAM auth
    """
    global _connector
    global _engine

    if _engine is not None:
        return _engine

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        _engine = create_async_engine(database_url, **_POOL_KWARGS)
        return _engine

    connection_name = os.getenv("CLOUD_SQL_CONNECTION_NAME")
    if not connection_name:
        raise RuntimeError("Either DATABASE_URL or CLOUD_SQL_CONNECTION_NAME must be set.")

    from google.cloud.sql.connector import Connector

    _connector = Connector()
    db_user = os.getenv("DB_USER", "postgres")
    db_name = os.getenv("DB_NAME", "police_complaints")
    db_password = os.getenv("DB_PASSWORD", "")
    use_iam = not db_password

    async def get_connection():
        kwargs: dict = dict(
            user=db_user,
            db=db_name,
        )
        if use_iam:
            kwargs["enable_iam_auth"] = True
        else:
            kwargs["password"] = db_password
        return await _connector.connect_async(
            connection_name,
            "asyncpg",
            **kwargs,
        )

    _engine = create_async_engine(
        "postgresql+asyncpg://",
        async_creator=get_connection,
        **_POOL_KWARGS,
    )
    return _engine


async def initialize_database() -> None:
    """Create the required schema before the app starts serving traffic."""
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def get_database_health() -> dict[str, bool | str]:
    """Check basic database reachability and table readiness."""
    try:
        engine = await get_engine()
    except RuntimeError as exc:
        logger.warning("Database configuration missing: %s", exc)
        return {
            "status": "error",
            "table_ready": False,
            "detail": "configuration_missing",
        }

    try:
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
            table_ready = await conn.run_sync(
                lambda sync_conn: sa.inspect(sync_conn).has_table(parse_records.name)
            )
        return {
            "status": "ok" if table_ready else "error",
            "table_ready": table_ready,
            "detail": "ready" if table_ready else "table_missing",
        }
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return {
            "status": "error",
            "table_ready": False,
            "detail": "unreachable",
        }


async def dispose_engine() -> None:
    """Dispose of the engine and close the Cloud SQL connector on shutdown."""
    global _connector
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None

    if _connector is not None:
        if hasattr(_connector, "close_async"):
            await _connector.close_async()
        elif hasattr(_connector, "close"):
            _connector.close()
        _connector = None
