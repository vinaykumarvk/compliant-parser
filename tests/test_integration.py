"""Phase 8: Integration tests -- end-to-end scenarios across all IQW modules (async ORM version)."""

from __future__ import annotations

import sys
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import AsyncTestCase

# ---------------------------------------------------------------------------
# Module-level imports -- every IQW subsystem
# ---------------------------------------------------------------------------
from auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
    PERMISSIONS,
)
from audit import (
    compute_sha256,
    log_audit_event,
    infer_action_type,
    search_audit_logs,
)
from cases import (
    create_case,
    get_case,
    transition_case_status,
    attach_document,
    get_timeline,
    create_task,
    list_tasks,
    auto_populate_statutory_deadlines,
    create_notification,
    mark_notification_read,
    list_notifications,
    list_police_stations_data,
    list_offence_types_data,
    seed_police_stations,
    seed_offence_types,
)
from quality_engine import (
    run_quality_check,
    run_llm_quality_check,
    seed_checklists,
    DEFAULT_CHECKLISTS,
)
from document_generator import (
    seed_templates,
    generate_document,
    export_docx,
    export_pdf,
    list_templates,
)
from ocr_enhancements import (
    _acknowledgements,
    detect_urdu,
    detect_language_enhanced,
    tag_segment_confidence,
    acknowledge_ocr,
    requires_acknowledgement,
)
from models import (
    Base,
    UserRole,
    CaseType,
    CaseStatus,
)


SAMPLE_FIR_TEXT = """\
FIR No. 0123/2026 registered at Banjara Hills Police Station.
Complainant: Rajesh Kumar, son of Mohan Kumar, residing at Plot 45, Road No. 12, Banjara Hills.
On 15th March 2026 at approximately 10:30 PM, the complainant was returning home from work.
Near SBI Bank, Road No. 12 junction, two unknown persons on a black motorcycle snatched
the complainant's mobile phone (Samsung Galaxy S24, IMEI: 123456789012345) worth Rs. 80,000.
Accused: two unknown persons, medium build, approximately 5'8\" tall.
Witness: Srinivas Rao (auto driver), phone: 9876543210.
Evidence: CCTV footage from SBI ATM, broken phone case.
IO: SI Venkat Reddy, Banjara Hills PS.
"""


class TestScenario1_FullCaseLifecycle(AsyncTestCase):
    """Scenario 1: Login -> Create case -> Upload doc -> Quality check ->
    Generate document -> Export DOCX -> Verify timeline & action tracker."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_police_stations(self.db)
        await seed_offence_types(self.db)
        seed_checklists()
        await seed_templates(self.db)

    async def test_full_lifecycle(self):
        # 1. Authenticate (JWT) -- sync, no db
        pw_hash = hash_password("testpass123")
        self.assertTrue(verify_password("testpass123", pw_hash))
        token = create_access_token("user-io-1", "IO")
        payload = decode_token(token)
        self.assertEqual(payload["sub"], "user-io-1")
        self.assertEqual(payload["role"], "IO")
        user_id = payload["sub"]

        # 2. Create a case with Crime No.
        case = await create_case(
            data={
                "case_type": "Crime",
                "crime_no": "0001/2026",
                "police_station_id": "ps-001",
                "brief_facts": "Snatching near SBI Bank",
                "io_id": user_id,
            },
            user_id=user_id,
            db=self.db,
        )
        case_id = case["id"]
        self.assertIsNotNone(case_id)
        self.assertEqual(case["status"], "Complaint_Received")
        self.assertEqual(case["case_type"], "Crime")

        # 3. Offence type seed data present
        offence_types = await list_offence_types_data(self.db)
        self.assertGreater(len(offence_types), 0)

        # 4. Upload a complaint document
        file_content = SAMPLE_FIR_TEXT.encode("utf-8")
        doc = await attach_document(
            case_id=case_id,
            file_name="complaint_0001.txt",
            document_type="FIR",
            file_bytes=file_content,
            user_id=user_id,
            db=self.db,
        )
        self.assertIsNotNone(doc["id"])
        self.assertIsNotNone(doc["sha256"])
        self.assertEqual(doc["document_type"], "FIR")

        # 5. Run quality check -- sync, no db
        quality_result = run_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertIn("analysis_id", quality_result)
        self.assertGreater(quality_result["total_items"], 0)
        self.assertGreater(quality_result["present_count"], 0)
        self.assertGreaterEqual(quality_result["completeness_score"], 0.0)
        self.assertLessEqual(quality_result["completeness_score"], 1.0)

        # 6. Generate document from template
        fsl_templates = await list_templates("FSL_Communication", db=self.db)
        self.assertGreater(len(fsl_templates), 0)
        template_id = fsl_templates[0]["id"]
        generated = await generate_document(
            template_id,
            {"case_number": "0001/2026", "police_station": "Banjara Hills PS"},
            user_id,
            db=self.db,
        )
        self.assertIn("id", generated)
        self.assertIn("content", generated)

        # 7. Export as DOCX
        docx_bytes = await export_docx(generated["id"], db=self.db)
        self.assertIsInstance(docx_bytes, bytes)
        self.assertTrue(docx_bytes[:2] == b"PK")

        # 8. Export as PDF
        pdf_bytes = await export_pdf(generated["id"], db=self.db)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes[:5] == b"%PDF-")

        # 9. Verify timeline shows activities
        timeline = await get_timeline(case_id, db=self.db)
        self.assertGreaterEqual(len(timeline), 2)
        activity_types = [a["activity_type"] for a in timeline]
        self.assertIn("Case_Created", activity_types)
        self.assertIn("Document_Attached", activity_types)

        # 10. Verify action tracker
        await auto_populate_statutory_deadlines(case_id, "Robbery", self.db)
        tasks = await list_tasks(case_id, self.db)
        self.assertGreater(len(tasks), 0)
        statutory = [t for t in tasks if t.get("source") == "Statutory"]
        self.assertGreater(len(statutory), 0)

    async def test_case_status_transitions(self):
        """Verify state machine: Complaint_Received -> FIR_Registered -> Under_Investigation -> Charge_Sheet_Filed -> Court_Proceedings -> Disposed."""
        case = await create_case(
            data={"case_type": "Crime", "crime_no": "0002/2026",
                  "police_station_id": "ps-001", "brief_facts": "Robbery"},
            user_id="io1",
            db=self.db,
        )
        cid = case["id"]

        updated = await transition_case_status(cid, "FIR_Registered", "io1", self.db)
        self.assertEqual(updated["status"], "FIR_Registered")

        updated = await transition_case_status(cid, "Under_Investigation", "io1", self.db)
        self.assertEqual(updated["status"], "Under_Investigation")

        updated = await transition_case_status(cid, "Charge_Sheet_Filed", "io1", self.db)
        self.assertEqual(updated["status"], "Charge_Sheet_Filed")

        updated = await transition_case_status(cid, "Court_Proceedings", "io1", self.db)
        self.assertEqual(updated["status"], "Court_Proceedings")

        updated = await transition_case_status(cid, "Disposed", "io1", self.db)
        self.assertEqual(updated["status"], "Disposed")

    async def test_invalid_status_transition_rejected(self):
        case = await create_case(
            data={"case_type": "Crime", "crime_no": "0003/2026",
                  "police_station_id": "ps-001", "brief_facts": "Theft"},
            user_id="io1",
            db=self.db,
        )
        # Complaint_Received -> Under_Investigation is not valid (must go through FIR first)
        with self.assertRaises(Exception):
            await transition_case_status(case["id"], "Under_Investigation", "io1", self.db)


class TestScenario2_RBAC(AsyncTestCase):
    """Scenario 2: Role-based access control verification.

    PERMISSIONS maps permission_name -> list of allowed roles.
    These tests are sync (no db) but use AsyncTestCase for consistency.
    """

    async def test_io_can_create_cases(self):
        self.assertIn("IO", PERMISSIONS["create_case"])

    async def test_io_can_upload_documents(self):
        self.assertIn("IO", PERMISSIONS["upload_document"])

    async def test_io_can_run_quality_check(self):
        self.assertIn("IO", PERMISSIONS["run_quality_check"])

    async def test_io_cannot_manage_users(self):
        self.assertNotIn("IO", PERMISSIONS["manage_users"])

    async def test_clerk_can_upload_documents(self):
        self.assertIn("Clerk", PERMISSIONS["upload_document"])

    async def test_clerk_can_create_cases(self):
        self.assertIn("Clerk", PERMISSIONS["create_case"])

    async def test_system_admin_can_manage_users(self):
        self.assertIn("System_Admin", PERMISSIONS["manage_users"])

    async def test_ai_admin_can_run_quality(self):
        self.assertIn("AI_Admin", PERMISSIONS["run_quality_check"])

    async def test_ai_admin_can_manage_kb(self):
        self.assertIn("AI_Admin", PERMISSIONS["manage_kb"])

    async def test_jwt_carries_role(self):
        for role in ["IO", "Clerk", "AI_Admin", "System_Admin"]:
            token = create_access_token(f"user-{role}", role)
            payload = decode_token(token)
            self.assertEqual(payload["role"], role)


class TestScenario3_AuditTrail(AsyncTestCase):
    """Scenario 3: Audit log completeness."""

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_audit_entries_created(self):
        await log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="127.0.0.1", db=self.db,
        )
        await log_audit_event(
            user_id="io1", action_type="document:upload", entity_type="CaseDocument",
            entity_id="doc-1", ip_address="127.0.0.1", db=self.db,
        )
        await log_audit_event(
            user_id="io1", action_type="quality:run", entity_type="AIAnalysisResult",
            entity_id="analysis-1", ip_address="127.0.0.1", db=self.db,
        )
        results = await search_audit_logs(db=self.db)
        self.assertEqual(results["total"], 3)

    async def test_audit_searchable_by_user(self):
        await log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="10.0.0.1", db=self.db,
        )
        await log_audit_event(
            user_id="admin1", action_type="user:create", entity_type="User",
            entity_id="user-1", ip_address="10.0.0.2", db=self.db,
        )
        results = await search_audit_logs(filters={"user_id": "io1"}, db=self.db)
        self.assertEqual(len(results["items"]), 1)
        self.assertEqual(results["items"][0]["user_id"], "io1")

    async def test_audit_searchable_by_action_type(self):
        await log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="10.0.0.1", db=self.db,
        )
        await log_audit_event(
            user_id="io1", action_type="document:upload", entity_type="CaseDocument",
            entity_id="doc-1", ip_address="10.0.0.1", db=self.db,
        )
        results = await search_audit_logs(filters={"action_type": "document:upload"}, db=self.db)
        self.assertEqual(len(results["items"]), 1)

    async def test_audit_action_inference(self):
        # infer_action_type is sync (no db)
        self.assertEqual(infer_action_type("POST", "/api/v1/cases"), "Upload")
        self.assertEqual(infer_action_type("PUT", "/api/v1/cases/1"), "Edit")
        self.assertEqual(infer_action_type("DELETE", "/api/v1/cases/1"), "Delete")
        # GET returns None (not logged)
        self.assertIsNone(infer_action_type("GET", "/api/v1/cases"))

    async def test_audit_entry_structure(self):
        entry = await log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="127.0.0.1", db=self.db,
        )
        self.assertIn("id", entry)
        self.assertEqual(entry["action_type"], "case:create")
        self.assertEqual(entry["user_id"], "io1")
        self.assertIn("timestamp", entry)

        # Verify stored in the DB via search
        results = await search_audit_logs(filters={"user_id": "io1"}, db=self.db)
        stored = [e for e in results["items"] if e["id"] == entry["id"]]
        self.assertEqual(len(stored), 1)


class TestScenario4_BackwardCompatibility(AsyncTestCase):
    """Scenario 4: Verify existing functionality is preserved."""

    async def test_models_coexist_with_parse_records(self):
        from database import parse_records
        self.assertIsNotNone(parse_records)
        self.assertEqual(parse_records.name, "parse_records")

    async def test_base_metadata_has_all_tables(self):
        table_names = set(Base.metadata.tables.keys())
        required = {
            "users", "cases", "case_documents", "case_activities",
            "ai_analysis_results", "citations", "congruence_alerts",
            "section_recommendations", "generated_documents", "document_templates",
            "investigation_plans", "judgment_analyses", "knowledge_base_entries",
            "audit_logs", "notifications", "action_tracker_tasks",
            "usage_events", "police_stations", "offence_types",
        }
        for tbl in required:
            self.assertIn(tbl, table_names, f"Missing table: {tbl}")

    async def test_existing_enums_intact(self):
        self.assertIn("IO", UserRole.__members__)
        self.assertIn("Clerk", UserRole.__members__)
        self.assertIn("AI_Admin", UserRole.__members__)
        self.assertIn("System_Admin", UserRole.__members__)
        self.assertIn("FIR", CaseType.__members__)
        self.assertIn("Petition", CaseType.__members__)
        self.assertIn("Complaint_Received", CaseStatus.__members__)
        self.assertIn("Disposed", CaseStatus.__members__)

    async def test_app_module_importable(self):
        import app  # noqa: F401
        self.assertTrue(hasattr(app, "app"))


class TestScenario5_DocumentIntegrity(AsyncTestCase):
    """Scenario 5: SHA-256 hash verification for uploaded documents."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_police_stations(self.db)
        await seed_offence_types(self.db)

    async def test_sha256_computed_on_upload(self):
        case = await create_case(
            data={"case_type": "Crime", "crime_no": "0010/2026",
                  "police_station_id": "ps-001", "brief_facts": "Test"},
            user_id="io1",
            db=self.db,
        )
        file_bytes = b"This is test content for hashing."
        doc = await attach_document(
            case_id=case["id"], file_name="test.txt",
            document_type="FIR", file_bytes=file_bytes,
            user_id="io1", db=self.db,
        )
        expected_hash = compute_sha256(file_bytes)
        self.assertEqual(doc["sha256"], expected_hash)

    async def test_sha256_deterministic(self):
        data = b"Deterministic content check"
        h1 = compute_sha256(data)
        h2 = compute_sha256(data)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    async def test_sha256_different_content(self):
        h1 = compute_sha256(b"content A")
        h2 = compute_sha256(b"content B")
        self.assertNotEqual(h1, h2)

    async def test_integrity_check_pass(self):
        case = await create_case(
            data={"case_type": "Crime", "crime_no": "0011/2026",
                  "police_station_id": "ps-001", "brief_facts": "Integrity test"},
            user_id="io1",
            db=self.db,
        )
        original_bytes = b"Important evidence document content."
        doc = await attach_document(
            case_id=case["id"], file_name="evidence.pdf",
            document_type="Evidence", file_bytes=original_bytes,
            user_id="io1", db=self.db,
        )
        recomputed = compute_sha256(original_bytes)
        self.assertEqual(doc["sha256"], recomputed)

    async def test_integrity_check_tampered(self):
        original = b"Original untampered content"
        tampered = b"Original tampered content!!"
        self.assertNotEqual(compute_sha256(original), compute_sha256(tampered))


class TestCrossModuleIntegration(AsyncTestCase):
    """Cross-cutting integration between modules."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_police_stations(self.db)
        await seed_offence_types(self.db)
        await seed_templates(self.db)
        seed_checklists()
        _acknowledgements.clear()

    async def test_quality_check_on_uploaded_document(self):
        case = await create_case(
            data={"case_type": "Crime", "crime_no": "0020/2026",
                  "police_station_id": "ps-001", "brief_facts": "Cross-module test"},
            user_id="io1",
            db=self.db,
        )
        await attach_document(
            case_id=case["id"], file_name="fir.txt",
            document_type="FIR", file_bytes=SAMPLE_FIR_TEXT.encode(),
            user_id="io1", db=self.db,
        )
        # run_quality_check is sync, no db
        result = run_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertGreater(result["completeness_score"], 0.0)

    async def test_generate_document_for_case(self):
        case = await create_case(
            data={"case_type": "Crime", "crime_no": "0021/2026",
                  "police_station_id": "ps-001", "brief_facts": "Doc gen test"},
            user_id="io1",
            db=self.db,
        )
        templates = await list_templates(db=self.db)
        template_id = templates[0]["id"]
        doc = await generate_document(
            template_id,
            {"case_number": case["crime_no"], "police_station": "Banjara Hills PS"},
            "io1",
            db=self.db,
        )
        self.assertIn("content", doc)

    async def test_ocr_confidence_on_urdu_text(self):
        # OCR functions are sync, no db
        urdu_text = "\u06cc\u06c1 \u0627\u06cc\u06a9 \u0627\u0631\u062f\u0648 \u0645\u062a\u0646 \u06c1\u06d2 \u062c\u0648 \u062c\u0627\u0646\u0686 \u06a9\u06d2 \u0644\u06cc\u06d2 \u0627\u0633\u062a\u0639\u0645\u0627\u0644 \u06c1\u0648\u062a\u0627 \u06c1\u06d2"
        self.assertTrue(detect_urdu(urdu_text))
        lang = detect_language_enhanced(urdu_text)
        self.assertEqual(lang["language"], "ur")
        segments = tag_segment_confidence(urdu_text)
        self.assertGreater(len(segments), 0)

    async def test_notification_flow(self):
        notif = await create_notification("io1", "assignment", "Case assigned", db=self.db)
        self.assertFalse(notif["is_read"])

        unread = await list_notifications("io1", db=self.db)
        self.assertGreater(len(unread), 0)

        await mark_notification_read(notif["id"], self.db)
        all_notifs = await list_notifications("io1", unread_only=False, db=self.db)
        updated = [n for n in all_notifs if n["id"] == notif["id"]]
        self.assertTrue(updated[0]["is_read"])

    async def test_seed_data_loaded(self):
        stations = await list_police_stations_data(self.db)
        self.assertGreaterEqual(len(stations), 5)

        offences = await list_offence_types_data(self.db)
        self.assertGreaterEqual(len(offences), 10)

        self.assertIn("Generic", DEFAULT_CHECKLISTS)
        self.assertIn("FIR", DEFAULT_CHECKLISTS)

        templates = await list_templates(db=self.db)
        self.assertGreaterEqual(len(templates), 10)


class TestPetitionAnalysisPipeline(AsyncTestCase):
    """Integration: petition intake → case creation → context-aware quality check."""

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_create_case_with_petition_and_run_quality_check(self):
        """Create case with ai_suggestion_context, attach petition doc, run QC with context."""
        # 1. Create case with AI suggestion context
        case = await create_case(
            {
                "case_type": "FIR",
                "crime_no": "0001/2026",
                "brief_facts": "Theft of mobile phone at Road No. 12, Banjara Hills",
                "offence_type": "Theft",
                "ai_suggestion_context": {
                    "suggestion_id": "sug-int-001",
                    "brief_facts": "Theft of mobile phone at Road No. 12, Banjara Hills",
                    "offence_type": "Theft",
                    "offence_confidence": 0.95,
                    "case_type": "FIR",
                    "date_of_occurrence": "2026-03-15",
                    "risk_flags": ["night_incident", "repeat_location"],
                    "rationale": "Petition text analysis identified theft pattern",
                },
            },
            "u1",
            self.db,
        )
        case_id = case["id"]
        self.assertIsNotNone(case["petition_analysis"])
        self.assertEqual(case["petition_analysis"]["offence_type"], "Theft")

        # 2. Attach a petition document
        doc = await attach_document(
            case_id,
            "petition.txt",
            "Petition",
            b"Theft of mobile phone Samsung Galaxy S24 at Banjara Hills on 15 March 2026",
            "u1",
            self.db,
        )
        self.assertIsNotNone(doc["id"])

        # 3. Build case context from the case data
        from models import Case as CaseModel
        case_obj = await self.db.get(CaseModel, case_id)
        case_context = {
            "brief_facts": case_obj.brief_facts,
            "offence_type": case_obj.offence_type,
            "petition_analysis": case_obj.petition_analysis,
        }

        # 4. Run quality check with case context (falls back to keyword in test env)
        petition_text = "Theft of mobile phone Samsung Galaxy S24 at Banjara Hills on 15 March 2026"
        result = run_llm_quality_check(
            petition_text, "Petition", offence_type="Theft", case_context=case_context,
        )
        self.assertIn("findings", result)
        self.assertIn("completeness_score", result)
        self.assertGreater(result["total_items"], 0)

    async def test_case_without_ai_context_still_works(self):
        """Case created without AI context — quality check still works (backward compat)."""
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0002/2026"},
            "u1",
            self.db,
        )
        self.assertIsNone(case.get("petition_analysis"))

        # Run quality check without case context
        result = run_quality_check("Some document text for quality check.", "Generic")
        self.assertIn("findings", result)


if __name__ == "__main__":
    import unittest
    unittest.main()
