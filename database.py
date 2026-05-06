"""Cloud SQL persistence layer for parse history."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

metadata = sa.MetaData()

parse_records = sa.Table(
    "parse_records",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("file_name", sa.Text, nullable=False),
    sa.Column("file_size", sa.Integer, nullable=False),
    sa.Column("file_bytes", BYTEA, nullable=True),
    sa.Column("file_storage_uri", sa.Text, nullable=True),
    sa.Column("file_storage_provider", sa.Text, nullable=True),
    sa.Column("file_sha256", sa.Text, nullable=True),
    sa.Column("case_id", sa.Text, nullable=True),
    sa.Column("created_by", sa.Text, nullable=True),
    sa.Column("parsed_output", JSONB, nullable=False),
    sa.Column("document_format", sa.Text, nullable=True),
    sa.Column("completeness_score", sa.Float, nullable=True),
    sa.Column("kis_index_status", sa.Text, nullable=False, server_default=sa.text("'not_started'")),
    sa.Column("kis_source_id", sa.Text, nullable=True),
    sa.Column("kis_wiki_article_id", sa.Text, nullable=True),
    sa.Column("kis_snapshot_id", sa.Text, nullable=True),
    sa.Column("kis_quality_passed", sa.Boolean, nullable=True),
    sa.Column("kis_fact_count", sa.Integer, nullable=True),
    sa.Column("kis_graph_edge_count", sa.Integer, nullable=True),
    sa.Column("kis_chunk_count", sa.Integer, nullable=True),
    sa.Column("kis_idempotent_replay", sa.Boolean, nullable=True),
    sa.Column("kis_privacy_summary", JSONB, nullable=True),
    sa.Column("kis_index_summary", JSONB, nullable=True),
    sa.Column("kis_error_code", sa.Text, nullable=True),
    sa.Column("kis_error_detail", sa.Text, nullable=True),
    sa.Column("kis_attempt_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("kis_next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("kis_worker_id", sa.Text, nullable=True),
    sa.Column("kis_locked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("kis_locked_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column("kis_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("kis_indexed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    ),
)

auth_support_requests = sa.Table(
    "auth_support_requests",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("request_type", sa.Text, nullable=False),
    sa.Column("user_identifier", sa.Text, nullable=False),
    sa.Column("message", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'open'")),
    sa.Column("client_fingerprint", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("resolved_by", sa.Text, nullable=True),
)

petition_rewrite_requests = sa.Table(
    "petition_rewrite_requests",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("parse_record_id", UUID(as_uuid=False), sa.ForeignKey("parse_records.id", ondelete="CASCADE"), nullable=False),
    sa.Column("case_id", sa.Text, nullable=True),
    sa.Column("source_language", sa.Text, nullable=False),
    sa.Column("source_language_name", sa.Text, nullable=True),
    sa.Column("basis_text_type", sa.Text, nullable=False),
    sa.Column("basis_text_hash", sa.Text, nullable=False),
    sa.Column("checklist_version", sa.Integer, nullable=True),
    sa.Column("generation_status", sa.Text, nullable=False, server_default=sa.text("'drafting'")),
    sa.Column("mandatory_gap_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("recommended_gap_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("source_lineage_status", sa.Text, nullable=False, server_default=sa.text("'not_started'")),
    sa.Column("contradiction_check_status", sa.Text, nullable=False, server_default=sa.text("'not_started'")),
    sa.Column("semantic_validation_status", sa.Text, nullable=False, server_default=sa.text("'not_required'")),
    sa.Column("petitioner_consent_status", sa.Text, nullable=False, server_default=sa.text("'not_presented'")),
    sa.Column("unsupported_fact_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("model_provider", sa.Text, nullable=True),
    sa.Column("model_name", sa.Text, nullable=True),
    sa.Column("prompt_version", sa.Text, nullable=False, server_default=sa.text("'deterministic-packet-v1'")),
    sa.Column("error_code", sa.Text, nullable=True),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("reviewed_by", sa.Text, nullable=True),
    sa.Column("approved_by", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
)

petition_placeholders = sa.Table(
    "petition_placeholders",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("gap_finding_id", sa.Text, nullable=False),
    sa.Column("token", sa.Text, nullable=False),
    sa.Column("category", sa.Text, nullable=False),
    sa.Column("label", sa.Text, nullable=False),
    sa.Column("instruction", sa.Text, nullable=False),
    sa.Column("severity", sa.Text, nullable=False),
    sa.Column("inserted_after_anchor", sa.Text, nullable=True),
    sa.Column("display_order", sa.Integer, nullable=False),
    sa.Column("petitioner_value", sa.Text, nullable=True),
    sa.Column("value_status", sa.Text, nullable=False, server_default=sa.text("'blank'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
)

generated_petition_drafts = sa.Table(
    "generated_petition_drafts",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("draft_language", sa.Text, nullable=False, server_default=sa.text("'en'")),
    sa.Column("draft_version", sa.Integer, nullable=False, server_default=sa.text("1")),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("body_markdown", sa.Text, nullable=False),
    sa.Column("body_plain_text", sa.Text, nullable=False),
    sa.Column("placeholder_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("mandatory_placeholder_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("generation_method", sa.Text, nullable=False),
    sa.Column("quality_status", sa.Text, nullable=False, server_default=sa.text("'needs_review'")),
    sa.Column("quality_notes", JSONB, nullable=True),
    sa.Column("source_lineage_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("unsupported_fact_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("contradiction_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("sha256_hash", sa.Text, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("updated_by", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
)

source_lineage_maps = sa.Table(
    "source_lineage_maps",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("generated_petition_draft_id", UUID(as_uuid=False), sa.ForeignKey("generated_petition_drafts.id", ondelete="CASCADE"), nullable=True),
    sa.Column("output_span_id", sa.Text, nullable=False),
    sa.Column("output_text", sa.Text, nullable=False),
    sa.Column("source_type", sa.Text, nullable=False),
    sa.Column("source_reference_id", sa.Text, nullable=True),
    sa.Column("source_excerpt", sa.Text, nullable=True),
    sa.Column("source_char_start", sa.Integer, nullable=True),
    sa.Column("source_char_end", sa.Integer, nullable=True),
    sa.Column("lineage_confidence", sa.Float, nullable=False, server_default=sa.text("0")),
    sa.Column("reviewer_status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("reviewer_note", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

petitioner_packets = sa.Table(
    "petitioner_packets",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("generated_petition_draft_id", UUID(as_uuid=False), sa.ForeignKey("generated_petition_drafts.id", ondelete="SET NULL"), nullable=True),
    sa.Column("presentation_language", sa.Text, nullable=False, server_default=sa.text("'en'")),
    sa.Column("packet_body_markdown", sa.Text, nullable=False),
    sa.Column("packet_hash", sa.Text, nullable=False),
    sa.Column("delivery_mode", sa.Text, nullable=False, server_default=sa.text("'in_person'")),
    sa.Column("delivery_status", sa.Text, nullable=False, server_default=sa.text("'prepared'")),
    sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

petitioner_verification_records = sa.Table(
    "petitioner_verification_records",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("petitioner_packet_id", UUID(as_uuid=False), sa.ForeignKey("petitioner_packets.id", ondelete="SET NULL"), nullable=True),
    sa.Column("consent_status", sa.Text, nullable=False),
    sa.Column("petitioner_name", sa.Text, nullable=True),
    sa.Column("verification_language", sa.Text, nullable=True),
    sa.Column("signature_mode", sa.Text, nullable=True),
    sa.Column("witness_note", sa.Text, nullable=True),
    sa.Column("signed_packet_uri", sa.Text, nullable=True),
    sa.Column("copy_provided_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("correction_note", sa.Text, nullable=True),
    sa.Column("verified_by", sa.Text, nullable=False),
    sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

petition_draft_translations = sa.Table(
    "petition_draft_translations",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("generated_petition_draft_id", UUID(as_uuid=False), sa.ForeignKey("generated_petition_drafts.id", ondelete="CASCADE"), nullable=False),
    sa.Column("target_language", sa.Text, nullable=False),
    sa.Column("target_language_name", sa.Text, nullable=True),
    sa.Column("direction", sa.Text, nullable=False, server_default=sa.text("'ltr'")),
    sa.Column("translated_body_markdown", sa.Text, nullable=False),
    sa.Column("placeholder_integrity_passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("semantic_validation_status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
    sa.Column("semantic_validation_notes", JSONB, nullable=True),
    sa.Column("english_only_reason", sa.Text, nullable=True),
    sa.Column("sho_override_reason", sa.Text, nullable=True),
    sa.Column("sha256_hash", sa.Text, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("reviewed_by", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
)

petition_checklist_questions = sa.Table(
    "petition_checklist_questions",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("checklist_version", sa.Integer, nullable=False),
    sa.Column("category", sa.Text, nullable=False),
    sa.Column("purpose", sa.Text, nullable=False, server_default=sa.text("'petition'")),
    sa.Column("offence_type", sa.Text, nullable=True),
    sa.Column("question_text", sa.Text, nullable=False),
    sa.Column("expected_field_key", sa.Text, nullable=True),
    sa.Column("severity", sa.Text, nullable=False, server_default=sa.text("'recommended'")),
    sa.Column("source_section", sa.Text, nullable=True),
    sa.Column("guidance", sa.Text, nullable=True),
    sa.Column("display_order", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("updated_by", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
)

petition_checklist_evaluations = sa.Table(
    "petition_checklist_evaluations",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("question_id", UUID(as_uuid=False), sa.ForeignKey("petition_checklist_questions.id", ondelete="CASCADE"), nullable=False),
    sa.Column("checklist_version", sa.Integer, nullable=False),
    sa.Column("evaluation_status", sa.Text, nullable=False),
    sa.Column("evidence_excerpt", sa.Text, nullable=True),
    sa.Column("question_text", sa.Text, nullable=True),
    sa.Column("category", sa.Text, nullable=True),
    sa.Column("purpose", sa.Text, nullable=True),
    sa.Column("severity", sa.Text, nullable=True),
    sa.Column("missing_detail", sa.Text, nullable=True),
    sa.Column("follow_up_action", sa.Text, nullable=True),
    sa.Column("guidance", sa.Text, nullable=True),
    sa.Column("evaluation_reason", sa.Text, nullable=True),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

petition_pilot_evaluations = sa.Table(
    "petition_pilot_evaluations",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("semantic_drift_flag", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("unsupported_fact_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("petitioner_comprehension_status", sa.Text, nullable=True),
    sa.Column("refusal_or_correction", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("officer_override_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.Column("quality_notes", JSONB, nullable=True),
    sa.Column("created_by", sa.Text, nullable=False, server_default=sa.text("'system'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

rewrite_audit_events = sa.Table(
    "rewrite_audit_events",
    metadata,
    sa.Column("id", UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), primary_key=True),
    sa.Column("rewrite_request_id", UUID(as_uuid=False), sa.ForeignKey("petition_rewrite_requests.id", ondelete="CASCADE"), nullable=False),
    sa.Column("actor_id", sa.Text, nullable=False),
    sa.Column("actor_role", sa.Text, nullable=False),
    sa.Column("action_type", sa.Text, nullable=False),
    sa.Column("before_hash", sa.Text, nullable=True),
    sa.Column("after_hash", sa.Text, nullable=True),
    sa.Column("event_summary", sa.Text, nullable=False),
    sa.Column("metadata", JSONB, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

_idx_created = sa.Index("ix_parse_records_created_at", parse_records.c.created_at.desc())
_idx_kis_status = sa.Index("ix_parse_records_kis_index_status", parse_records.c.kis_index_status)
_idx_kis_queue = sa.Index("ix_parse_records_kis_queue", parse_records.c.kis_index_status, parse_records.c.kis_next_attempt_at, parse_records.c.created_at)
_idx_support_status = sa.Index("ix_auth_support_requests_status_created", auth_support_requests.c.status, auth_support_requests.c.created_at.desc())
_idx_support_type = sa.Index("ix_auth_support_requests_type_created", auth_support_requests.c.request_type, auth_support_requests.c.created_at.desc())
_idx_rewrite_parse_status = sa.Index("ix_petition_rewrite_parse_status", petition_rewrite_requests.c.parse_record_id, petition_rewrite_requests.c.generation_status)
_idx_rewrite_created = sa.Index("ix_petition_rewrite_created_at", petition_rewrite_requests.c.created_at.desc())
_idx_placeholder_request_order = sa.Index("ix_petition_placeholders_request_order", petition_placeholders.c.rewrite_request_id, petition_placeholders.c.display_order)
_idx_draft_request_version = sa.Index("ix_generated_petition_drafts_request_version", generated_petition_drafts.c.rewrite_request_id, generated_petition_drafts.c.draft_version.desc())
_idx_lineage_request_span = sa.Index("ix_source_lineage_request_span", source_lineage_maps.c.rewrite_request_id, source_lineage_maps.c.output_span_id)
_idx_petitioner_packets_request = sa.Index("ix_petitioner_packets_request_created", petitioner_packets.c.rewrite_request_id, petitioner_packets.c.created_at.desc())
_idx_petitioner_verification_request = sa.Index("ix_petitioner_verification_request_verified", petitioner_verification_records.c.rewrite_request_id, petitioner_verification_records.c.verified_at.desc())
_idx_petition_translations_request = sa.Index("ix_petition_translations_request_created", petition_draft_translations.c.rewrite_request_id, petition_draft_translations.c.created_at.desc())
_idx_petition_checklist_active = sa.Index("ix_petition_checklist_active_version", petition_checklist_questions.c.is_active, petition_checklist_questions.c.checklist_version)
_idx_petition_checklist_eval_request = sa.Index("ix_petition_checklist_eval_request", petition_checklist_evaluations.c.rewrite_request_id, petition_checklist_evaluations.c.checklist_version)
_idx_petition_pilot_eval_created = sa.Index("ix_petition_pilot_eval_created", petition_pilot_evaluations.c.created_at.desc())
_idx_rewrite_audit_request_created = sa.Index("ix_rewrite_audit_request_created", rewrite_audit_events.c.rewrite_request_id, rewrite_audit_events.c.created_at.desc())

_engine: AsyncEngine | None = None
_connector: Any | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

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


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (and lazily create) the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False,
        )
    return _session_factory


async def get_db():
    """FastAPI dependency that yields an async DB session with auto-commit."""
    factory = await get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def initialize_database() -> None:
    """Create the required schema before the app starts serving traffic."""
    from migrations import apply_schema_migrations

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    await apply_schema_migrations(engine)


async def initialize_all_tables() -> None:
    """Create all IQW ORM tables (models.py) alongside legacy parse_records."""
    from migrations import apply_schema_migrations
    from models import Base  # noqa: F811 — ORM declarative base

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_schema_migrations(engine)


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
    global _session_factory

    _session_factory = None

    if _engine is not None:
        await _engine.dispose()
        _engine = None

    if _connector is not None:
        if hasattr(_connector, "close_async"):
            await _connector.close_async()
        elif hasattr(_connector, "close"):
            _connector.close()
        _connector = None
