"""Phase 8: Integration tests — end-to-end scenarios across all IQW modules."""

from __future__ import annotations

import unittest

# ---------------------------------------------------------------------------
# Module-level imports – every IQW subsystem
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
    _audit_log_store,
)
from cases import (
    _cases,
    _case_documents,
    _case_activities,
    _action_tracker_tasks,
    _notifications,
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
    seed_checklists,
    DEFAULT_CHECKLISTS,
)
from document_generator import (
    _templates,
    _generated_documents,
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


def _clear_all_stores():
    _cases.clear()
    _case_documents.clear()
    _case_activities.clear()
    _action_tracker_tasks.clear()
    _notifications.clear()
    _templates.clear()
    _generated_documents.clear()
    _audit_log_store.clear()
    _acknowledgements.clear()


class TestScenario1_FullCaseLifecycle(unittest.TestCase):
    """Scenario 1: Login -> Create case -> Upload doc -> Quality check ->
    Generate document -> Export DOCX -> Verify timeline & action tracker."""

    def setUp(self):
        _clear_all_stores()
        seed_police_stations()
        seed_offence_types()
        seed_checklists()
        seed_templates()

    def test_full_lifecycle(self):
        # 1. Authenticate (JWT)
        pw_hash = hash_password("testpass123")
        self.assertTrue(verify_password("testpass123", pw_hash))
        token = create_access_token("user-io-1", "IO")
        payload = decode_token(token)
        self.assertEqual(payload["sub"], "user-io-1")
        self.assertEqual(payload["role"], "IO")
        user_id = payload["sub"]

        # 2. Create a case with Crime No.
        case = create_case(
            data={
                "case_type": "Crime",
                "crime_no": "0001/2026",
                "police_station_id": "ps-1",
                "brief_facts": "Snatching near SBI Bank",
                "io_id": user_id,
            },
            user_id=user_id,
        )
        case_id = case["id"]
        self.assertIsNotNone(case_id)
        self.assertEqual(case["status"], "Open")
        self.assertEqual(case["case_type"], "Crime")

        # 3. Offence type seed data present
        offence_types = list_offence_types_data()
        self.assertGreater(len(offence_types), 0)

        # 4. Upload a complaint document
        file_content = SAMPLE_FIR_TEXT.encode("utf-8")
        doc = attach_document(
            case_id=case_id,
            file_name="complaint_0001.txt",
            document_type="FIR",
            file_bytes=file_content,
            user_id=user_id,
        )
        self.assertIsNotNone(doc["id"])
        self.assertIsNotNone(doc["sha256"])
        self.assertEqual(doc["document_type"], "FIR")

        # 5. Run quality check
        quality_result = run_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertIn("analysis_id", quality_result)
        self.assertGreater(quality_result["total_items"], 0)
        self.assertGreater(quality_result["present_count"], 0)
        self.assertGreaterEqual(quality_result["completeness_score"], 0.0)
        self.assertLessEqual(quality_result["completeness_score"], 1.0)

        # 6. Generate document from template
        fsl_templates = list_templates("FSL_Communication")
        self.assertGreater(len(fsl_templates), 0)
        template_id = fsl_templates[0]["id"]
        generated = generate_document(
            template_id,
            {"case_number": "0001/2026", "police_station": "Banjara Hills PS"},
            user_id,
        )
        self.assertIn("id", generated)
        self.assertIn("content", generated)

        # 7. Export as DOCX
        docx_bytes = export_docx(generated["id"])
        self.assertIsInstance(docx_bytes, bytes)
        self.assertTrue(docx_bytes[:2] == b"PK")

        # 8. Export as PDF
        pdf_bytes = export_pdf(generated["id"])
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes[:5] == b"%PDF-")

        # 9. Verify timeline shows activities
        timeline = get_timeline(case_id)
        self.assertGreaterEqual(len(timeline), 2)
        activity_types = [a["activity_type"] for a in timeline]
        self.assertIn("Case_Created", activity_types)
        self.assertIn("Document_Attached", activity_types)

        # 10. Verify action tracker
        auto_populate_statutory_deadlines(case_id, "Robbery")
        tasks = list_tasks(case_id)
        self.assertGreater(len(tasks), 0)
        statutory = [t for t in tasks if t.get("source") == "Statutory"]
        self.assertGreater(len(statutory), 0)

    def test_case_status_transitions(self):
        """Verify state machine: Open -> Under_Investigation -> Charge_Sheet_Filed -> Closed."""
        case = create_case(
            data={"case_type": "Crime", "crime_no": "0002/2026",
                  "police_station_id": "ps-1", "brief_facts": "Robbery"},
            user_id="io1",
        )
        cid = case["id"]

        updated = transition_case_status(cid, "Under_Investigation", "io1")
        self.assertEqual(updated["status"], "Under_Investigation")

        updated = transition_case_status(cid, "Charge_Sheet_Filed", "io1")
        self.assertEqual(updated["status"], "Charge_Sheet_Filed")

        updated = transition_case_status(cid, "Closed", "io1")
        self.assertEqual(updated["status"], "Closed")

    def test_invalid_status_transition_rejected(self):
        case = create_case(
            data={"case_type": "Crime", "crime_no": "0003/2026",
                  "police_station_id": "ps-1", "brief_facts": "Theft"},
            user_id="io1",
        )
        # Open -> Closed is not valid
        with self.assertRaises(Exception):
            transition_case_status(case["id"], "Closed", "io1")


class TestScenario2_RBAC(unittest.TestCase):
    """Scenario 2: Role-based access control verification.

    PERMISSIONS maps permission_name -> list of allowed roles.
    """

    def test_io_can_create_cases(self):
        self.assertIn("IO", PERMISSIONS["create_case"])

    def test_io_can_upload_documents(self):
        self.assertIn("IO", PERMISSIONS["upload_document"])

    def test_io_can_run_quality_check(self):
        self.assertIn("IO", PERMISSIONS["run_quality_check"])

    def test_io_cannot_manage_users(self):
        self.assertNotIn("IO", PERMISSIONS["manage_users"])

    def test_clerk_can_upload_documents(self):
        self.assertIn("Clerk", PERMISSIONS["upload_document"])

    def test_clerk_cannot_create_cases(self):
        self.assertNotIn("Clerk", PERMISSIONS["create_case"])

    def test_system_admin_can_manage_users(self):
        self.assertIn("System_Admin", PERMISSIONS["manage_users"])

    def test_ai_admin_can_run_quality(self):
        self.assertIn("AI_Admin", PERMISSIONS["run_quality_check"])

    def test_ai_admin_can_manage_kb(self):
        self.assertIn("AI_Admin", PERMISSIONS["manage_kb"])

    def test_jwt_carries_role(self):
        for role in ["IO", "Clerk", "AI_Admin", "System_Admin"]:
            token = create_access_token(f"user-{role}", role)
            payload = decode_token(token)
            self.assertEqual(payload["role"], role)


class TestScenario3_AuditTrail(unittest.TestCase):
    """Scenario 3: Audit log completeness."""

    def setUp(self):
        _audit_log_store.clear()

    def test_audit_entries_created(self):
        log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="127.0.0.1",
        )
        log_audit_event(
            user_id="io1", action_type="document:upload", entity_type="CaseDocument",
            entity_id="doc-1", ip_address="127.0.0.1",
        )
        log_audit_event(
            user_id="io1", action_type="quality:run", entity_type="AIAnalysisResult",
            entity_id="analysis-1", ip_address="127.0.0.1",
        )
        self.assertEqual(len(_audit_log_store), 3)

    def test_audit_searchable_by_user(self):
        log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="10.0.0.1",
        )
        log_audit_event(
            user_id="admin1", action_type="user:create", entity_type="User",
            entity_id="user-1", ip_address="10.0.0.2",
        )
        results = search_audit_logs(filters={"user_id": "io1"})
        self.assertEqual(len(results["items"]), 1)
        self.assertEqual(results["items"][0]["user_id"], "io1")

    def test_audit_searchable_by_action_type(self):
        log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="10.0.0.1",
        )
        log_audit_event(
            user_id="io1", action_type="document:upload", entity_type="CaseDocument",
            entity_id="doc-1", ip_address="10.0.0.1",
        )
        results = search_audit_logs(filters={"action_type": "document:upload"})
        self.assertEqual(len(results["items"]), 1)

    def test_audit_action_inference(self):
        # infer_action_type takes (method, path)
        self.assertEqual(infer_action_type("POST", "/api/v1/cases"), "Upload")
        self.assertEqual(infer_action_type("PUT", "/api/v1/cases/1"), "Edit")
        self.assertEqual(infer_action_type("DELETE", "/api/v1/cases/1"), "Delete")
        # GET returns None (not logged)
        self.assertIsNone(infer_action_type("GET", "/api/v1/cases"))

    def test_audit_entry_structure(self):
        entry = log_audit_event(
            user_id="io1", action_type="case:create", entity_type="Case",
            entity_id="case-1", ip_address="127.0.0.1",
        )
        self.assertIn("id", entry)
        self.assertEqual(entry["action_type"], "case:create")
        self.assertEqual(entry["user_id"], "io1")
        self.assertIn("timestamp", entry)
        # Verify stored in the list
        stored = [e for e in _audit_log_store if e["id"] == entry["id"]]
        self.assertEqual(len(stored), 1)


class TestScenario4_BackwardCompatibility(unittest.TestCase):
    """Scenario 4: Verify existing functionality is preserved."""

    def test_models_coexist_with_parse_records(self):
        from database import parse_records
        self.assertIsNotNone(parse_records)
        self.assertEqual(parse_records.name, "parse_records")

    def test_base_metadata_has_all_tables(self):
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

    def test_existing_enums_intact(self):
        self.assertIn("IO", UserRole.__members__)
        self.assertIn("Clerk", UserRole.__members__)
        self.assertIn("AI_Admin", UserRole.__members__)
        self.assertIn("System_Admin", UserRole.__members__)
        self.assertIn("FIR", CaseType.__members__)
        self.assertIn("Petition", CaseType.__members__)
        self.assertIn("Open", CaseStatus.__members__)
        self.assertIn("Closed", CaseStatus.__members__)

    def test_app_module_importable(self):
        import app  # noqa: F401
        self.assertTrue(hasattr(app, "app"))


class TestScenario5_DocumentIntegrity(unittest.TestCase):
    """Scenario 5: SHA-256 hash verification for uploaded documents."""

    def setUp(self):
        _cases.clear()
        _case_documents.clear()
        _case_activities.clear()
        seed_police_stations()
        seed_offence_types()

    def test_sha256_computed_on_upload(self):
        case = create_case(
            data={"case_type": "Crime", "crime_no": "0010/2026",
                  "police_station_id": "ps-1", "brief_facts": "Test"},
            user_id="io1",
        )
        file_bytes = b"This is test content for hashing."
        doc = attach_document(
            case_id=case["id"], file_name="test.txt",
            document_type="FIR", file_bytes=file_bytes,
            user_id="io1",
        )
        expected_hash = compute_sha256(file_bytes)
        self.assertEqual(doc["sha256"], expected_hash)

    def test_sha256_deterministic(self):
        data = b"Deterministic content check"
        h1 = compute_sha256(data)
        h2 = compute_sha256(data)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_sha256_different_content(self):
        h1 = compute_sha256(b"content A")
        h2 = compute_sha256(b"content B")
        self.assertNotEqual(h1, h2)

    def test_integrity_check_pass(self):
        case = create_case(
            data={"case_type": "Crime", "crime_no": "0011/2026",
                  "police_station_id": "ps-1", "brief_facts": "Integrity test"},
            user_id="io1",
        )
        original_bytes = b"Important evidence document content."
        doc = attach_document(
            case_id=case["id"], file_name="evidence.pdf",
            document_type="Evidence", file_bytes=original_bytes,
            user_id="io1",
        )
        recomputed = compute_sha256(original_bytes)
        self.assertEqual(doc["sha256"], recomputed)

    def test_integrity_check_tampered(self):
        original = b"Original untampered content"
        tampered = b"Original tampered content!!"
        self.assertNotEqual(compute_sha256(original), compute_sha256(tampered))


class TestCrossModuleIntegration(unittest.TestCase):
    """Cross-cutting integration between modules."""

    def setUp(self):
        _clear_all_stores()
        seed_police_stations()
        seed_offence_types()
        seed_templates()
        seed_checklists()

    def test_quality_check_on_uploaded_document(self):
        case = create_case(
            data={"case_type": "Crime", "crime_no": "0020/2026",
                  "police_station_id": "ps-1", "brief_facts": "Cross-module test"},
            user_id="io1",
        )
        attach_document(
            case_id=case["id"], file_name="fir.txt",
            document_type="FIR", file_bytes=SAMPLE_FIR_TEXT.encode(),
            user_id="io1",
        )
        result = run_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertGreater(result["completeness_score"], 0.0)

    def test_generate_document_for_case(self):
        case = create_case(
            data={"case_type": "Crime", "crime_no": "0021/2026",
                  "police_station_id": "ps-1", "brief_facts": "Doc gen test"},
            user_id="io1",
        )
        template_id = next(iter(_templates))
        doc = generate_document(
            template_id,
            {"case_number": case["crime_no"], "police_station": "Banjara Hills PS"},
            "io1",
        )
        self.assertIn("content", doc)

    def test_ocr_confidence_on_urdu_text(self):
        urdu_text = "یہ ایک اردو متن ہے جو جانچ کے لیے استعمال ہوتا ہے"
        self.assertTrue(detect_urdu(urdu_text))
        lang = detect_language_enhanced(urdu_text)
        self.assertEqual(lang["language"], "ur")
        segments = tag_segment_confidence(urdu_text)
        self.assertGreater(len(segments), 0)

    def test_notification_flow(self):
        notif = create_notification("io1", "assignment", "Case assigned")
        self.assertFalse(notif["is_read"])

        unread = list_notifications("io1")
        self.assertGreater(len(unread), 0)

        mark_notification_read(notif["id"])
        all_notifs = list_notifications("io1", unread_only=False)
        updated = [n for n in all_notifs if n["id"] == notif["id"]]
        self.assertTrue(updated[0]["is_read"])

    def test_seed_data_loaded(self):
        stations = list_police_stations_data()
        self.assertGreaterEqual(len(stations), 5)

        offences = list_offence_types_data()
        self.assertGreaterEqual(len(offences), 10)

        self.assertIn("Generic", DEFAULT_CHECKLISTS)
        self.assertIn("FIR", DEFAULT_CHECKLISTS)

        templates = list_templates()
        self.assertGreaterEqual(len(templates), 10)


if __name__ == "__main__":
    unittest.main()
