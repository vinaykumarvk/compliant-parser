from __future__ import annotations

"""Lightweight versioned schema migrations for Cloud SQL/Postgres deployments."""

from collections.abc import Awaitable, Callable

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


Migration = Callable[[AsyncConnection], Awaitable[None]]


async def _table_exists(conn: AsyncConnection, table_name: str) -> bool:
    return bool(await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).has_table(table_name)))


async def _column_names(conn: AsyncConnection, table_name: str) -> set[str]:
    if not await _table_exists(conn, table_name):
        return set()
    return set(await conn.run_sync(lambda sync_conn: [c["name"] for c in sa.inspect(sync_conn).get_columns(table_name)]))


async def _add_column_if_missing(conn: AsyncConnection, table_name: str, column_name: str, ddl: str) -> None:
    columns = await _column_names(conn, table_name)
    if column_name not in columns:
        await conn.execute(sa.text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


async def _drop_not_null_if_supported(conn: AsyncConnection, table_name: str, column_name: str) -> None:
    if conn.dialect.name == "postgresql" and await _table_exists(conn, table_name):
        await conn.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP NOT NULL"))


async def _migration_parse_record_object_storage(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "parse_records"):
        return
    await _add_column_if_missing(conn, "parse_records", "file_storage_uri", "file_storage_uri TEXT")
    await _add_column_if_missing(conn, "parse_records", "file_storage_provider", "file_storage_provider TEXT")
    await _add_column_if_missing(conn, "parse_records", "file_sha256", "file_sha256 TEXT")
    await _drop_not_null_if_supported(conn, "parse_records", "file_bytes")


async def _migration_case_document_object_storage(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "case_documents"):
        return
    await _add_column_if_missing(conn, "case_documents", "file_storage_uri", "file_storage_uri TEXT")
    await _add_column_if_missing(conn, "case_documents", "file_storage_provider", "file_storage_provider VARCHAR(64)")
    await _add_column_if_missing(conn, "case_documents", "file_encryption_key_ref", "file_encryption_key_ref VARCHAR(255)")
    await _drop_not_null_if_supported(conn, "case_documents", "file_bytes")


async def _migration_generated_document_signature_details(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "generated_documents"):
        return
    await _add_column_if_missing(
        conn,
        "generated_documents",
        "signature_certificate_details",
        "signature_certificate_details JSON",
    )


async def _migration_generated_document_hash(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "generated_documents"):
        return
    await _add_column_if_missing(conn, "generated_documents", "sha256_hash", "sha256_hash VARCHAR(64)")


async def _migration_audit_hash_chain(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "audit_logs"):
        return
    await _add_column_if_missing(conn, "audit_logs", "previous_hash", "previous_hash VARCHAR(64)")
    await _add_column_if_missing(conn, "audit_logs", "entry_hash", "entry_hash VARCHAR(64)")


async def _migration_kb_validation_governance(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "knowledge_base_entries"):
        return
    await _add_column_if_missing(conn, "knowledge_base_entries", "validation_status", "validation_status VARCHAR(32)")
    await _add_column_if_missing(conn, "knowledge_base_entries", "validation_report", "validation_report JSON")
    await _add_column_if_missing(conn, "knowledge_base_entries", "validated_by", "validated_by VARCHAR(36)")
    await _add_column_if_missing(conn, "knowledge_base_entries", "validated_at", "validated_at TIMESTAMP WITH TIME ZONE")


async def _migration_parse_record_kis_indexing(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "parse_records"):
        return
    await _add_column_if_missing(
        conn,
        "parse_records",
        "kis_index_status",
        "kis_index_status TEXT DEFAULT 'not_started' NOT NULL",
    )
    await _add_column_if_missing(conn, "parse_records", "kis_source_id", "kis_source_id TEXT")
    await _add_column_if_missing(conn, "parse_records", "kis_wiki_article_id", "kis_wiki_article_id TEXT")
    await _add_column_if_missing(conn, "parse_records", "kis_snapshot_id", "kis_snapshot_id TEXT")
    await _add_column_if_missing(conn, "parse_records", "kis_quality_passed", "kis_quality_passed BOOLEAN")
    await _add_column_if_missing(conn, "parse_records", "kis_fact_count", "kis_fact_count INTEGER")
    await _add_column_if_missing(conn, "parse_records", "kis_graph_edge_count", "kis_graph_edge_count INTEGER")
    await _add_column_if_missing(conn, "parse_records", "kis_chunk_count", "kis_chunk_count INTEGER")
    await _add_column_if_missing(conn, "parse_records", "kis_idempotent_replay", "kis_idempotent_replay BOOLEAN")
    await _add_column_if_missing(conn, "parse_records", "kis_privacy_summary", "kis_privacy_summary JSON")
    await _add_column_if_missing(conn, "parse_records", "kis_index_summary", "kis_index_summary JSON")
    await _add_column_if_missing(conn, "parse_records", "kis_error_code", "kis_error_code TEXT")
    await _add_column_if_missing(conn, "parse_records", "kis_error_detail", "kis_error_detail TEXT")
    await _add_column_if_missing(
        conn,
        "parse_records",
        "kis_last_attempt_at",
        "kis_last_attempt_at TIMESTAMP WITH TIME ZONE",
    )
    await _add_column_if_missing(
        conn,
        "parse_records",
        "kis_indexed_at",
        "kis_indexed_at TIMESTAMP WITH TIME ZONE",
    )
    await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_parse_records_kis_index_status ON parse_records(kis_index_status)"))


async def _migration_parse_record_kis_retry_queue(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "parse_records"):
        return
    await _add_column_if_missing(conn, "parse_records", "kis_attempt_count", "kis_attempt_count INTEGER DEFAULT 0 NOT NULL")
    await _add_column_if_missing(
        conn,
        "parse_records",
        "kis_next_attempt_at",
        "kis_next_attempt_at TIMESTAMP WITH TIME ZONE",
    )
    await _add_column_if_missing(conn, "parse_records", "kis_worker_id", "kis_worker_id TEXT")
    await _add_column_if_missing(
        conn,
        "parse_records",
        "kis_locked_at",
        "kis_locked_at TIMESTAMP WITH TIME ZONE",
    )
    await _add_column_if_missing(
        conn,
        "parse_records",
        "kis_locked_until",
        "kis_locked_until TIMESTAMP WITH TIME ZONE",
    )
    await conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_parse_records_kis_queue "
            "ON parse_records(kis_index_status, kis_next_attempt_at, created_at)"
        )
    )


async def _migration_dashboard_columns_and_indexes(conn: AsyncConnection) -> None:
    if await _table_exists(conn, "users"):
        await _add_column_if_missing(conn, "users", "jurisdiction_scope", "jurisdiction_scope VARCHAR(64)")
        await _add_column_if_missing(conn, "users", "jurisdiction_ids", "jurisdiction_ids JSON")
        await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_police_station_id ON users(police_station_id)"))
    if await _table_exists(conn, "police_stations"):
        await _add_column_if_missing(conn, "police_stations", "zone", "zone VARCHAR(128)")
        await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_police_stations_zone ON police_stations(zone)"))
    if await _table_exists(conn, "parse_records"):
        await _add_column_if_missing(conn, "parse_records", "case_id", "case_id TEXT")
        await _add_column_if_missing(conn, "parse_records", "created_by", "created_by TEXT")
        await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_parse_records_case_id ON parse_records(case_id)"))
        await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_parse_records_created_by ON parse_records(created_by)"))
    for table, statements in {
        "cases": [
            "CREATE INDEX IF NOT EXISTS ix_cases_created_at ON cases(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_cases_station_io_status ON cases(police_station_id, io_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_cases_case_type ON cases(case_type)",
        ],
        "case_documents": [
            "CREATE INDEX IF NOT EXISTS ix_case_documents_case_created ON case_documents(case_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_case_documents_created_by ON case_documents(created_by)",
        ],
        "generated_documents": [
            "CREATE INDEX IF NOT EXISTS ix_generated_documents_case_created ON generated_documents(case_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_generated_documents_subtype ON generated_documents(document_subtype)",
            "CREATE INDEX IF NOT EXISTS ix_generated_documents_created_by ON generated_documents(created_by)",
        ],
        "usage_events": [
            "CREATE INDEX IF NOT EXISTS ix_usage_events_user_timestamp ON usage_events(user_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS ix_usage_events_type_module ON usage_events(event_type, module)",
        ],
        "ai_analysis_results": [
            "CREATE INDEX IF NOT EXISTS ix_ai_analysis_case_created ON ai_analysis_results(case_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_ai_analysis_created_by ON ai_analysis_results(created_by)",
        ],
    }.items():
        if await _table_exists(conn, table):
            for statement in statements:
                await conn.execute(sa.text(statement))


async def _migration_dashboard_worker_indexes(conn: AsyncConnection) -> None:
    for table, statements in {
        "dashboard_export_jobs": [
            "CREATE INDEX IF NOT EXISTS ix_dashboard_export_jobs_status_requested ON dashboard_export_jobs(status, requested_at)",
            "CREATE INDEX IF NOT EXISTS ix_dashboard_export_jobs_requester ON dashboard_export_jobs(requester_id)",
        ],
        "dashboard_metric_snapshots": [
            "CREATE INDEX IF NOT EXISTS ix_dashboard_snapshots_status_computed ON dashboard_metric_snapshots(status, computed_at)",
            "CREATE INDEX IF NOT EXISTS ix_dashboard_snapshots_filters_hash ON dashboard_metric_snapshots(filters_hash)",
        ],
    }.items():
        if await _table_exists(conn, table):
            for statement in statements:
                await conn.execute(sa.text(statement))


async def _migration_case_lifecycle_status_constraint(conn: AsyncConnection) -> None:
    if conn.dialect.name != "postgresql" or not await _table_exists(conn, "cases"):
        return
    await conn.execute(
        sa.text(
            "UPDATE cases SET status = CASE "
            "WHEN status = 'Open' THEN 'Complaint_Received' "
            "WHEN status = 'Closed' THEN 'Disposed' "
            "ELSE status END "
            "WHERE status IN ('Open', 'Closed')"
        )
    )
    await conn.execute(sa.text("ALTER TABLE cases DROP CONSTRAINT IF EXISTS casestatus"))
    await conn.execute(
        sa.text(
            "ALTER TABLE cases ADD CONSTRAINT casestatus CHECK ("
            "status IN ("
            "'Complaint_Received', 'FIR_Registered', 'Under_Investigation', "
            "'Charge_Sheet_Filed', 'Closure_Report_Filed', 'Court_Proceedings', "
            "'Transferred', 'Disposed', 'Closed_No_FIR'"
            "))"
        )
    )


async def _migration_auth_support_requests(conn: AsyncConnection) -> None:
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS auth_support_requests ("
            "id TEXT PRIMARY KEY, "
            "request_type TEXT NOT NULL, "
            "user_identifier TEXT NOT NULL, "
            "message TEXT, "
            "status TEXT DEFAULT 'open' NOT NULL, "
            "client_fingerprint TEXT, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "updated_at TIMESTAMP WITH TIME ZONE, "
            "resolved_at TIMESTAMP WITH TIME ZONE, "
            "resolved_by TEXT)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_auth_support_requests_status_created "
            "ON auth_support_requests(status, created_at DESC)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_auth_support_requests_type_created "
            "ON auth_support_requests(request_type, created_at DESC)"
        )
    )


async def _migration_petition_assistance_phase1(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "parse_records"):
        return
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petition_rewrite_requests ("
            "id UUID PRIMARY KEY, "
            "parse_record_id UUID NOT NULL REFERENCES parse_records(id) ON DELETE CASCADE, "
            "case_id TEXT, "
            "source_language TEXT NOT NULL, "
            "source_language_name TEXT, "
            "basis_text_type TEXT NOT NULL, "
            "basis_text_hash TEXT NOT NULL, "
            "checklist_version INTEGER, "
            "generation_status TEXT DEFAULT 'drafting' NOT NULL, "
            "mandatory_gap_count INTEGER DEFAULT 0 NOT NULL, "
            "recommended_gap_count INTEGER DEFAULT 0 NOT NULL, "
            "source_lineage_status TEXT DEFAULT 'not_started' NOT NULL, "
            "contradiction_check_status TEXT DEFAULT 'not_started' NOT NULL, "
            "semantic_validation_status TEXT DEFAULT 'not_required' NOT NULL, "
            "petitioner_consent_status TEXT DEFAULT 'not_presented' NOT NULL, "
            "unsupported_fact_count INTEGER DEFAULT 0 NOT NULL, "
            "model_provider TEXT, "
            "model_name TEXT, "
            "prompt_version TEXT DEFAULT 'deterministic-packet-v1' NOT NULL, "
            "error_code TEXT, "
            "error_message TEXT, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "reviewed_by TEXT, "
            "approved_by TEXT, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "updated_at TIMESTAMP WITH TIME ZONE, "
            "approved_at TIMESTAMP WITH TIME ZONE, "
            "is_deleted BOOLEAN DEFAULT false NOT NULL)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petition_placeholders ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "gap_finding_id TEXT NOT NULL, "
            "token TEXT NOT NULL, "
            "category TEXT NOT NULL, "
            "label TEXT NOT NULL, "
            "instruction TEXT NOT NULL, "
            "severity TEXT NOT NULL, "
            "inserted_after_anchor TEXT, "
            "display_order INTEGER NOT NULL, "
            "petitioner_value TEXT, "
            "value_status TEXT DEFAULT 'blank' NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "updated_at TIMESTAMP WITH TIME ZONE)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS generated_petition_drafts ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "draft_language TEXT DEFAULT 'en' NOT NULL, "
            "draft_version INTEGER DEFAULT 1 NOT NULL, "
            "title TEXT NOT NULL, "
            "body_markdown TEXT NOT NULL, "
            "body_plain_text TEXT NOT NULL, "
            "placeholder_count INTEGER DEFAULT 0 NOT NULL, "
            "mandatory_placeholder_count INTEGER DEFAULT 0 NOT NULL, "
            "generation_method TEXT NOT NULL, "
            "quality_status TEXT DEFAULT 'needs_review' NOT NULL, "
            "quality_notes JSON, "
            "source_lineage_complete BOOLEAN DEFAULT false NOT NULL, "
            "unsupported_fact_count INTEGER DEFAULT 0 NOT NULL, "
            "contradiction_count INTEGER DEFAULT 0 NOT NULL, "
            "sha256_hash TEXT NOT NULL, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "updated_by TEXT, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "updated_at TIMESTAMP WITH TIME ZONE)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS source_lineage_maps ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "generated_petition_draft_id UUID REFERENCES generated_petition_drafts(id) ON DELETE CASCADE, "
            "output_span_id TEXT NOT NULL, "
            "output_text TEXT NOT NULL, "
            "source_type TEXT NOT NULL, "
            "source_reference_id TEXT, "
            "source_excerpt TEXT, "
            "source_char_start INTEGER, "
            "source_char_end INTEGER, "
            "lineage_confidence DOUBLE PRECISION DEFAULT 0 NOT NULL, "
            "reviewer_status TEXT DEFAULT 'pending' NOT NULL, "
            "reviewer_note TEXT, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS rewrite_audit_events ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "actor_id TEXT NOT NULL, "
            "actor_role TEXT NOT NULL, "
            "action_type TEXT NOT NULL, "
            "before_hash TEXT, "
            "after_hash TEXT, "
            "event_summary TEXT NOT NULL, "
            "metadata JSON, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_petition_rewrite_parse_status ON petition_rewrite_requests(parse_record_id, generation_status)",
        "CREATE INDEX IF NOT EXISTS ix_petition_rewrite_created_at ON petition_rewrite_requests(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_petition_placeholders_request_order ON petition_placeholders(rewrite_request_id, display_order)",
        "CREATE INDEX IF NOT EXISTS ix_generated_petition_drafts_request_version ON generated_petition_drafts(rewrite_request_id, draft_version DESC)",
        "CREATE INDEX IF NOT EXISTS ix_source_lineage_request_span ON source_lineage_maps(rewrite_request_id, output_span_id)",
        "CREATE INDEX IF NOT EXISTS ix_rewrite_audit_request_created ON rewrite_audit_events(rewrite_request_id, created_at DESC)",
    ]:
        await conn.execute(sa.text(statement))


async def _migration_petition_assistance_phase4(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "petition_rewrite_requests"):
        return
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petitioner_packets ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "generated_petition_draft_id UUID REFERENCES generated_petition_drafts(id) ON DELETE SET NULL, "
            "presentation_language TEXT DEFAULT 'en' NOT NULL, "
            "packet_body_markdown TEXT NOT NULL, "
            "packet_hash TEXT NOT NULL, "
            "delivery_mode TEXT DEFAULT 'in_person' NOT NULL, "
            "delivery_status TEXT DEFAULT 'prepared' NOT NULL, "
            "presented_at TIMESTAMP WITH TIME ZONE, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petitioner_verification_records ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "petitioner_packet_id UUID REFERENCES petitioner_packets(id) ON DELETE SET NULL, "
            "consent_status TEXT NOT NULL, "
            "petitioner_name TEXT, "
            "verification_language TEXT, "
            "signature_mode TEXT, "
            "witness_note TEXT, "
            "signed_packet_uri TEXT, "
            "copy_provided_at TIMESTAMP WITH TIME ZONE, "
            "correction_note TEXT, "
            "verified_by TEXT NOT NULL, "
            "verified_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_petitioner_packets_request_created ON petitioner_packets(rewrite_request_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_petitioner_verification_request_verified ON petitioner_verification_records(rewrite_request_id, verified_at DESC)",
    ]:
        await conn.execute(sa.text(statement))


async def _migration_petition_assistance_phase5(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "petition_rewrite_requests"):
        return
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petition_draft_translations ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "generated_petition_draft_id UUID NOT NULL REFERENCES generated_petition_drafts(id) ON DELETE CASCADE, "
            "target_language TEXT NOT NULL, "
            "target_language_name TEXT, "
            "direction TEXT DEFAULT 'ltr' NOT NULL, "
            "translated_body_markdown TEXT NOT NULL, "
            "placeholder_integrity_passed BOOLEAN DEFAULT false NOT NULL, "
            "semantic_validation_status TEXT DEFAULT 'pending' NOT NULL, "
            "semantic_validation_notes JSON, "
            "english_only_reason TEXT, "
            "sho_override_reason TEXT, "
            "sha256_hash TEXT NOT NULL, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "reviewed_by TEXT, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
            "updated_at TIMESTAMP WITH TIME ZONE)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_petition_translations_request_created "
            "ON petition_draft_translations(rewrite_request_id, created_at DESC)"
        )
    )


async def _migration_petition_assistance_phase6(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "petition_rewrite_requests"):
        return
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petition_checklist_questions ("
            "id UUID PRIMARY KEY, "
            "checklist_version INTEGER NOT NULL, "
            "category TEXT NOT NULL, "
            "question_text TEXT NOT NULL, "
            "expected_field_key TEXT, "
            "severity TEXT DEFAULT 'recommended' NOT NULL, "
            "is_active BOOLEAN DEFAULT true NOT NULL, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petition_checklist_evaluations ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "question_id UUID NOT NULL REFERENCES petition_checklist_questions(id) ON DELETE CASCADE, "
            "checklist_version INTEGER NOT NULL, "
            "evaluation_status TEXT NOT NULL, "
            "evidence_excerpt TEXT, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    await conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS petition_pilot_evaluations ("
            "id UUID PRIMARY KEY, "
            "rewrite_request_id UUID NOT NULL REFERENCES petition_rewrite_requests(id) ON DELETE CASCADE, "
            "semantic_drift_flag BOOLEAN DEFAULT false NOT NULL, "
            "unsupported_fact_count INTEGER DEFAULT 0 NOT NULL, "
            "petitioner_comprehension_status TEXT, "
            "refusal_or_correction BOOLEAN DEFAULT false NOT NULL, "
            "officer_override_used BOOLEAN DEFAULT false NOT NULL, "
            "quality_notes JSON, "
            "created_by TEXT DEFAULT 'system' NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL)"
        )
    )
    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_petition_checklist_active_version ON petition_checklist_questions(is_active, checklist_version)",
        "CREATE INDEX IF NOT EXISTS ix_petition_checklist_eval_request ON petition_checklist_evaluations(rewrite_request_id, checklist_version)",
        "CREATE INDEX IF NOT EXISTS ix_petition_pilot_eval_created ON petition_pilot_evaluations(created_at DESC)",
    ]:
        await conn.execute(sa.text(statement))


async def _migration_petition_checklist_intelligence(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "petition_checklist_questions"):
        return
    await _add_column_if_missing(
        conn,
        "petition_checklist_questions",
        "purpose",
        "purpose TEXT DEFAULT 'petition' NOT NULL",
    )
    await _add_column_if_missing(conn, "petition_checklist_questions", "offence_type", "offence_type TEXT")
    await _add_column_if_missing(conn, "petition_checklist_questions", "source_section", "source_section TEXT")
    await _add_column_if_missing(conn, "petition_checklist_questions", "guidance", "guidance TEXT")
    await _add_column_if_missing(
        conn,
        "petition_checklist_questions",
        "display_order",
        "display_order INTEGER DEFAULT 0 NOT NULL",
    )
    await _add_column_if_missing(conn, "petition_checklist_questions", "updated_by", "updated_by TEXT")
    await _add_column_if_missing(
        conn,
        "petition_checklist_questions",
        "updated_at",
        "updated_at TIMESTAMP WITH TIME ZONE",
    )

    if await _table_exists(conn, "petition_checklist_evaluations"):
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "question_text", "question_text TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "category", "category TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "purpose", "purpose TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "severity", "severity TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "missing_detail", "missing_detail TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "follow_up_action", "follow_up_action TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "guidance", "guidance TEXT")
        await _add_column_if_missing(conn, "petition_checklist_evaluations", "evaluation_reason", "evaluation_reason TEXT")

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_petition_checklist_purpose_active ON petition_checklist_questions(purpose, is_active, checklist_version)",
        "CREATE INDEX IF NOT EXISTS ix_petition_checklist_offence ON petition_checklist_questions(offence_type)",
    ]:
        await conn.execute(sa.text(statement))


async def _migration_case_petition_analysis(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "cases"):
        return
    await _add_column_if_missing(conn, "cases", "petition_analysis", "petition_analysis JSON")


async def _migration_section_recommendation_enhanced_fields(conn: AsyncConnection) -> None:
    if not await _table_exists(conn, "section_recommendations"):
        return
    await _add_column_if_missing(conn, "section_recommendations", "applicability_rank", "applicability_rank INTEGER")
    await _add_column_if_missing(conn, "section_recommendations", "statutory_text", "statutory_text TEXT")
    await _add_column_if_missing(conn, "section_recommendations", "ingredient_mapping", "ingredient_mapping JSON")


MIGRATIONS: list[tuple[str, Migration]] = [
    ("20260504_001_parse_record_object_storage", _migration_parse_record_object_storage),
    ("20260504_002_case_document_object_storage", _migration_case_document_object_storage),
    ("20260504_003_generated_document_signature_details", _migration_generated_document_signature_details),
    ("20260504_004_generated_document_hash", _migration_generated_document_hash),
    ("20260504_005_audit_hash_chain", _migration_audit_hash_chain),
    ("20260504_006_kb_validation_governance", _migration_kb_validation_governance),
    ("20260505_001_parse_record_kis_indexing", _migration_parse_record_kis_indexing),
    ("20260505_002_parse_record_kis_retry_queue", _migration_parse_record_kis_retry_queue),
    ("20260505_003_dashboard_columns_and_indexes", _migration_dashboard_columns_and_indexes),
    ("20260505_004_dashboard_worker_indexes", _migration_dashboard_worker_indexes),
    ("20260505_005_case_lifecycle_status_constraint", _migration_case_lifecycle_status_constraint),
    ("20260505_006_auth_support_requests", _migration_auth_support_requests),
    ("20260506_001_petition_assistance_phase1", _migration_petition_assistance_phase1),
    ("20260506_002_petition_assistance_phase4", _migration_petition_assistance_phase4),
    ("20260506_003_petition_assistance_phase5", _migration_petition_assistance_phase5),
    ("20260506_004_petition_assistance_phase6", _migration_petition_assistance_phase6),
    ("20260506_005_petition_checklist_intelligence", _migration_petition_checklist_intelligence),
    ("20260506_006_case_petition_analysis", _migration_case_petition_analysis),
    ("20260507_001_section_recommendation_enhanced_fields", _migration_section_recommendation_enhanced_fields),
]


async def apply_schema_migrations(engine: AsyncEngine) -> None:
    """Apply idempotent schema migrations and record completed versions."""
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, "
                "applied_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL)"
            )
        )
        result = await conn.execute(sa.text("SELECT version FROM schema_migrations"))
        applied = {row[0] for row in result}
        for version, migration in MIGRATIONS:
            if version in applied:
                continue
            await migration(conn)
            await conn.execute(
                sa.text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )
