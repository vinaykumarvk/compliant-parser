from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import HTTPException

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

from api_v1 import senior_dashboard_metric_definitions_endpoint, senior_dashboard_overview_endpoint
from models import (
    AIAnalysisResult,
    AnalysisType,
    Case,
    CaseDocument,
    CaseStatus,
    CaseType,
    ConfidenceLevel,
    DocumentCategory,
    DocumentType,
    GeneratedDocument,
    DashboardMetricSnapshot,
    PoliceStation,
    UsageEvent,
    User,
    UserRole,
)
from senior_dashboard import (
    DashboardAuthorizationError,
    DashboardConflictError,
    DashboardValidationError,
    ensure_dashboard_access,
    acknowledge_alert,
    create_alert_rule,
    create_export_job,
    create_metric_dispute,
    document_analytics_metrics,
    feature_adoption_metrics,
    filter_options,
    get_validation_state,
    get_export_job,
    lifecycle_metrics,
    lifecycle_stage_cases,
    list_alerts,
    list_training_recommendations,
    normalize_filters,
    officer_metrics,
    officer_detail_metrics,
    overview_metrics,
    predictive_signals,
    process_next_dashboard_background_job,
    processing_time_metrics,
    refresh_dashboard_snapshot,
    review_metric_dispute,
    source_map_payloads,
    station_metrics,
    station_detail_metrics,
    update_metric_definition,
)
from tests.conftest import AsyncTestCase


class SeniorDashboardTestCase(AsyncTestCase):
    def _seed_dashboard_data(self) -> tuple[dict, dict]:
        now = datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc)
        station = PoliceStation(
            id="ps_abids",
            station_code="ABIDS",
            name="Abids Police Station",
            district="Hyderabad",
            zone="central",
            city="Hyderabad",
            state="Telangana",
        )
        admin = User(
            id="admin",
            employee_id="ADM001",
            full_name="Admin Officer",
            role=UserRole.System_Admin,
            police_station_id="ps_abids",
        )
        io = User(
            id="io1",
            employee_id="HCP2088",
            full_name="S. Khan",
            rank="SI",
            role=UserRole.IO,
            police_station_id="ps_abids",
        )
        other_io = User(
            id="io2",
            employee_id="HCP2099",
            full_name="R. Devi",
            rank="CI",
            role=UserRole.IO,
            police_station_id="ps_abids",
        )
        fir_case = Case(
            id="case_fir",
            crime_no="24/2026",
            case_type=CaseType.FIR,
            police_station_id="ps_abids",
            io_id="io1",
            status=CaseStatus.FIR_Registered,
            brief_facts="Victim phone 9999999999 and home address should not leave metrics.",
            created_by="io1",
            created_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        )
        complaint_case = Case(
            id="case_complaint",
            petition_no="P/55/2026",
            case_type=CaseType.Petition,
            police_station_id="ps_abids",
            io_id="io1",
            status=CaseStatus.Complaint_Received,
            brief_facts="Complainant Aadhaar and mobile are intentionally seeded PII.",
            created_by="io1",
            created_at=datetime(2026, 5, 2, 11, 0, tzinfo=timezone.utc),
        )
        upload = CaseDocument(
            id="doc_fir",
            case_id="case_fir",
            document_type=DocumentType.FIR,
            file_name="fir.pdf",
            ocr_extracted_text="Sensitive OCR text 8888888888",
            created_by="io1",
            created_at=datetime(2026, 5, 1, 9, 5, tzinfo=timezone.utc),
        )
        first_draft = GeneratedDocument(
            id="draft_first",
            case_id="case_fir",
            document_category=DocumentCategory.Legal_Draft,
            document_subtype="FIR_Draft",
            generated_content="Full FIR draft with victim details",
            created_by="io1",
            created_at=datetime(2026, 5, 1, 9, 15, tzinfo=timezone.utc),
        )
        last_draft = GeneratedDocument(
            id="draft_last",
            case_id="case_fir",
            document_category=DocumentCategory.Legal_Draft,
            document_subtype="FIR_Draft",
            generated_content="Revised FIR draft with victim details",
            created_by="io1",
            created_at=datetime(2026, 5, 1, 9, 45, tzinfo=timezone.utc),
        )
        accepted_ai = AIAnalysisResult(
            id="ai_accepted",
            case_id="case_fir",
            document_id="doc_fir",
            analysis_type=AnalysisType.Quality_Check,
            confidence_score=ConfidenceLevel.High,
            io_reviewed=True,
            io_review_action="accepted",
            created_by="io1",
            created_at=datetime(2026, 5, 1, 9, 20, tzinfo=timezone.utc),
        )
        low_ai = AIAnalysisResult(
            id="ai_low",
            case_id="case_complaint",
            analysis_type=AnalysisType.Section_Recommendation,
            confidence_score=ConfidenceLevel.Low,
            has_uncertainty_flag=True,
            created_by="io1",
            created_at=datetime(2026, 5, 2, 11, 15, tzinfo=timezone.utc),
        )
        usage = UsageEvent(
            id="usage_case_create",
            user_id="io1",
            event_type="case.create",
            module="cases",
            created_by="io1",
            created_at=datetime(2026, 5, 1, 9, 1, tzinfo=timezone.utc),
            timestamp=datetime(2026, 5, 1, 9, 1, tzinfo=timezone.utc),
        )
        for item in (
            station,
            admin,
            io,
            other_io,
            fir_case,
            complaint_case,
            upload,
            first_draft,
            last_draft,
            accepted_ai,
            low_ai,
            usage,
        ):
            self.db.add(item)
        return {"sub": "admin", "role": "System_Admin"}, {"sub": "io1", "role": "IO"}

    def _filters(self):
        return normalize_filters(period="custom", date_from="2026-04-01", date_to="2026-05-05")

    async def test_overview_counts_and_omits_pii_payload_values(self):
        admin, _io = self._seed_dashboard_data()

        payload = await overview_metrics(self.db, admin, self._filters())

        self.assertEqual(payload["kpis"]["cases_created"], 2)
        self.assertEqual(payload["kpis"]["firs_registered"], 1)
        self.assertEqual(payload["kpis"]["fir_drafts_created"], 2)
        self.assertEqual(payload["kpis"]["documents_uploaded"], 1)
        self.assertEqual(payload["kpis"]["ai_checks_performed"], 2)
        self.assertEqual(payload["kpis"]["median_complaint_to_fir_draft_minutes"], 15)
        serialized = json.dumps(payload)
        self.assertNotIn("9999999999", serialized)
        self.assertNotIn("Sensitive OCR text", serialized)
        self.assertNotIn("Full FIR draft", serialized)

    async def test_officer_and_station_metrics_roll_up_required_counts(self):
        admin, _io = self._seed_dashboard_data()

        officer_payload = await officer_metrics(self.db, admin, self._filters())
        station_payload = await station_metrics(self.db, admin, self._filters())

        officer = officer_payload["items"][0]
        self.assertEqual(officer["user_id"], "io1")
        self.assertEqual(officer["cases_created"], 2)
        self.assertEqual(officer["firs_registered"], 1)
        self.assertEqual(officer["fir_drafts_created"], 2)
        self.assertEqual(officer["ai_checks_performed"], 2)
        station = station_payload["items"][0]
        self.assertEqual(station["police_station_id"], "ps_abids")
        self.assertEqual(station["cases_created"], 2)
        self.assertEqual(station["active_users"], 1)

    async def test_lifecycle_processing_and_feature_adoption_metrics(self):
        admin, _io = self._seed_dashboard_data()

        lifecycle_payload = await lifecycle_metrics(self.db, admin, self._filters())
        processing_payload = await processing_time_metrics(self.db, admin, self._filters())
        adoption_payload = await feature_adoption_metrics(self.db, admin, self._filters())

        lifecycle_counts = {item["status"]: item["count"] for item in lifecycle_payload["items"]}
        self.assertEqual(lifecycle_counts["Complaint_Received"], 1)
        self.assertEqual(lifecycle_counts["FIR_Registered"], 1)
        self.assertEqual(processing_payload["completed_count"], 1)
        self.assertEqual(processing_payload["pending_draft_count"], 1)
        self.assertEqual(processing_payload["items"][0]["draft_count"], 2)
        modules = {item["module"]: item["count"] for item in adoption_payload["items"]}
        self.assertEqual(modules["documents_uploaded"], 1)
        self.assertEqual(modules["generated_documents"], 2)
        self.assertEqual(modules["ai_checks"], 2)
        self.assertEqual(adoption_payload["ai_effectiveness"]["acceptance_rate"], 100.0)
        self.assertEqual(adoption_payload["ai_effectiveness"]["low_confidence_rate"], 50.0)

    async def test_io_scope_cannot_request_other_officer_or_station_metrics(self):
        _admin, io_user = self._seed_dashboard_data()
        other_officer_filters = normalize_filters(
            period="custom",
            date_from="2026-04-01",
            date_to="2026-05-05",
            io_id="io2",
        )
        station_filters = normalize_filters(
            period="custom",
            date_from="2026-04-01",
            date_to="2026-05-05",
            police_station_id="ps_abids",
        )

        with self.assertRaises(DashboardAuthorizationError):
            ensure_dashboard_access(io_user, other_officer_filters)
        with self.assertRaises(DashboardAuthorizationError):
            ensure_dashboard_access(io_user, station_filters)

    async def test_endpoint_mount_contract_and_validation_errors(self):
        admin, _io = self._seed_dashboard_data()

        payload = await senior_dashboard_overview_endpoint(
            period="custom",
            date_from="2026-04-01",
            date_to="2026-05-05",
            db=self.db,
            user=admin,
        )
        definitions = await senior_dashboard_metric_definitions_endpoint(db=self.db, user=admin)

        self.assertEqual(payload["kpis"]["cases_created"], 2)
        self.assertGreaterEqual(definitions["total"], 1)
        with self.assertRaises(HTTPException) as ctx:
            await senior_dashboard_overview_endpoint(
                period="custom",
                date_from="2026-05-05",
                date_to="2026-04-01",
                db=self.db,
                user=admin,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_senior_sho_zone_and_self_view_scopes(self):
        admin, io_user = self._seed_dashboard_data()
        sho = {"sub": "sho1", "role": "SHO", "police_station_id": "ps_abids"}
        zone = {"sub": "zone1", "role": "Zone_Officer", "jurisdiction_ids": ["central"]}

        self.assertEqual((await overview_metrics(self.db, admin, self._filters()))["kpis"]["cases_created"], 2)
        self.assertEqual((await overview_metrics(self.db, sho, self._filters()))["filters"]["police_station_id"], "ps_abids")
        self.assertEqual((await overview_metrics(self.db, zone, self._filters()))["filters"]["zone"], "central")
        self.assertEqual((await overview_metrics(self.db, io_user, self._filters()))["filters"]["io_id"], "io1")

        with self.assertRaises(DashboardAuthorizationError):
            await overview_metrics(
                self.db,
                sho,
                normalize_filters(period="custom", date_from="2026-04-01", date_to="2026-05-05", police_station_id="other"),
            )

    async def test_filters_drilldowns_and_document_analytics_are_metadata_only(self):
        admin, _io = self._seed_dashboard_data()

        options = await filter_options(self.db, admin, self._filters())
        docs = await document_analytics_metrics(self.db, admin, self._filters())
        officer = await officer_detail_metrics(self.db, admin, self._filters(), "io1")
        station = await station_detail_metrics(self.db, admin, self._filters(), "ps_abids")
        stage = await lifecycle_stage_cases(self.db, admin, self._filters(), "FIR_Registered")

        self.assertIn("central", options["zones"])
        self.assertEqual(docs["totals"]["fir_drafts_created"], 2)
        self.assertEqual(officer["total"], 2)
        self.assertEqual(station["total"], 2)
        self.assertEqual(stage["total"], 1)
        serialized = json.dumps({"officer": officer, "station": station, "stage": stage})
        self.assertNotIn("Victim phone", serialized)
        self.assertNotIn("Complainant Aadhaar", serialized)

    async def test_exports_alerts_snapshots_and_metric_registry_governance(self):
        admin, _io = self._seed_dashboard_data()

        definition = await update_metric_definition(
            self.db,
            admin,
            "cases_created",
            {"minimum_sample_size": 7, "owner_role": "System_Admin"},
        )
        source_maps = await source_map_payloads(self.db)
        export = await create_export_job(
            self.db,
            admin,
            self._filters(),
            report_type="overview",
            export_format="csv",
            purpose="Senior operational awareness review",
        )
        rule = await create_alert_rule(
            self.db,
            admin,
            {"metric_key": "cases_created", "threshold_operator": ">=", "threshold_value": 1, "minimum_sample_size": 1},
        )
        alerts = await list_alerts(self.db, admin, self._filters())
        ack = await acknowledge_alert(self.db, admin, alerts["items"][0]["id"])
        snapshot = await refresh_dashboard_snapshot(self.db, admin, self._filters())
        self.assertEqual(export["status"], "queued")
        self.assertEqual(snapshot["status"], "Queued")
        self.assertTrue(await process_next_dashboard_background_job(self.db))
        self.assertTrue(await process_next_dashboard_background_job(self.db))
        export = await get_export_job(self.db, admin, export["id"])
        snapshot_row = await self.db.get(DashboardMetricSnapshot, snapshot["id"])

        self.assertGreaterEqual(definition["version"], 2)
        self.assertTrue(source_maps)
        self.assertEqual(export["status"], "completed")
        self.assertEqual(len(export["sha256_hash"]), 64)
        self.assertIn("expires_at", export)
        self.assertNotIn("Full FIR draft", export["file_uri"])
        self.assertEqual(rule["metric_key"], "cases_created")
        self.assertEqual(alerts["total"], 1)
        self.assertEqual(ack["status"], "acknowledged")
        self.assertEqual(snapshot_row.status, "Current")

    async def test_metric_disputes_reject_pii_duplicates_and_create_corrections(self):
        admin, _io = self._seed_dashboard_data()

        dispute = await create_metric_dispute(
            self.db,
            admin,
            {"metric_key": "cases_created", "scope_type": "station", "scope_id": "ps_abids", "explanation": "Station count mismatch"},
        )
        with self.assertRaises(DashboardConflictError):
            await create_metric_dispute(
                self.db,
                admin,
                {"metric_key": "cases_created", "scope_type": "station", "scope_id": "ps_abids", "explanation": "Duplicate"},
            )
        with self.assertRaises(DashboardValidationError):
            await create_metric_dispute(
                self.db,
                admin,
                {"metric_key": "firs_registered", "scope_type": "station", "scope_id": "ps_abids", "explanation": "phone 9999999999"},
            )

        reviewed = await review_metric_dispute(
            self.db,
            admin,
            dispute["id"],
            {"status": "resolved", "resolution_notes": "Corrected station attribution", "corrected_value": {"cases_created": 2}},
        )
        self.assertEqual(reviewed["status"], "resolved")

    async def test_training_recommendations_and_predictive_signals_are_gated(self):
        admin, _io = self._seed_dashboard_data()

        recommendations = await list_training_recommendations(self.db, admin, self._filters())
        validation = await get_validation_state(self.db, admin)
        predictive = await predictive_signals(self.db, admin, self._filters())

        self.assertGreaterEqual(recommendations["total"], 1)
        self.assertEqual(validation["state"], "restricted")
        self.assertFalse(predictive["enabled"])
