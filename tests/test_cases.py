"""Tests for Phase 4: Case Workbench (async + MockAsyncSession)."""

from __future__ import annotations

import sys
import os
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.conftest import AsyncTestCase

from cases import (
    VALID_TRANSITIONS,
    attach_document,
    auto_populate_statutory_deadlines,
    create_case,
    create_notification,
    create_task,
    ensure_case_access,
    generate_case_identifiers,
    get_case,
    get_case_document,
    get_lifecycle_map,
    get_stage_guidance,
    get_timeline,
    list_case_documents,
    list_cases,
    list_notifications,
    list_offence_types_data,
    list_police_stations_data,
    list_tasks,
    mark_notification_read,
    purge_old_document_versions,
    search_offence_types_data,
    seed_demo_case,
    seed_offence_types,
    seed_police_stations,
    suggest_case_intake_from_petition,
    transition_case_status,
    update_case,
    update_case_offence_type,
    update_task,
    validate_crime_no,
    validate_petition_no,
)
from external_interfaces import LLMResult, OCRResult


class TestCrimeNoValidation(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_valid_crime_no(self):
        self.assertTrue(validate_crime_no("0001/2026"))
        self.assertTrue(validate_crime_no("9999/2025"))

    async def test_invalid_crime_no(self):
        self.assertFalse(validate_crime_no("1/2026"))
        self.assertFalse(validate_crime_no("abcd/2026"))
        self.assertFalse(validate_crime_no("0001-2026"))
        self.assertFalse(validate_crime_no(""))

    async def test_valid_petition_no(self):
        self.assertTrue(validate_petition_no("PET/BH/2026/0001"))

    async def test_invalid_petition_no(self):
        self.assertFalse(validate_petition_no("PET/2026"))
        self.assertFalse(validate_petition_no("0001/2026"))


class TestCaseCRUD(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_create_fir_case(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0001/2026"},
            "u1",
            self.db,
        )
        self.assertEqual(case["case_type"], "FIR")
        self.assertEqual(case["status"], "Complaint_Received")
        self.assertIn("id", case)

    async def test_create_petition_case(self):
        case = await create_case(
            {"case_type": "Petition", "petition_no": "PET/BH/2026/0001"},
            "u1",
            self.db,
        )
        self.assertEqual(case["case_type"], "Petition")

    async def test_station_selection_generates_petition_number(self):
        await seed_police_stations(self.db)
        preview = await generate_case_identifiers(
            police_station_id="ps-001",
            case_type="Petition",
            registration_datetime="2026-05-05",
            db=self.db,
        )
        self.assertEqual(preview["petition_no"], "PET/BH/2026/0001")

        first = await create_case(
            {
                "case_type": "Petition",
                "police_station_id": "ps-001",
                "date_of_registration": "2026-05-05",
            },
            "u1",
            self.db,
        )
        second = await create_case(
            {
                "case_type": "Petition",
                "police_station_id": "ps-001",
                "date_of_registration": "2026-05-05",
            },
            "u1",
            self.db,
        )
        self.assertEqual(first["petition_no"], "PET/BH/2026/0001")
        self.assertEqual(second["petition_no"], "PET/BH/2026/0002")

    async def test_station_selection_generates_fir_crime_number(self):
        await seed_police_stations(self.db)
        case = await create_case(
            {
                "case_type": "FIR",
                "police_station_id": "ps-001",
                "date_of_registration": "2026-05-05",
            },
            "u1",
            self.db,
        )
        self.assertEqual(case["crime_no"], "0001/2026")

    async def test_create_case_invalid_crime_no(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            await create_case({"case_type": "FIR", "crime_no": "bad"}, "u1", self.db)

    async def test_get_case(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0002/2026"}, "u1", self.db
        )
        found = await get_case(case["id"], self.db)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], case["id"])

    async def test_get_case_includes_offence_type_name(self):
        """AC-002-3: offence type name must be in case dict for dashboard header display."""
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0015/2026"}, "u1", self.db
        )
        found = await get_case(case["id"], self.db)
        self.assertIn("primary_offence_type_name", found)

    async def test_get_nonexistent_case(self):
        self.assertIsNone(await get_case("nonexistent", self.db))

    async def test_list_cases_io_own(self):
        await create_case({"case_type": "FIR", "crime_no": "0003/2026"}, "u1", self.db)
        await create_case({"case_type": "FIR", "crime_no": "0004/2026"}, "u2", self.db)
        result = await list_cases("u1", "IO", db=self.db)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["total"], 1)

    async def test_list_cases_admin_all(self):
        await create_case({"case_type": "FIR", "crime_no": "0005/2026"}, "u1", self.db)
        await create_case({"case_type": "FIR", "crime_no": "0006/2026"}, "u2", self.db)
        result = await list_cases("u1", "System_Admin", db=self.db)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["total"], 2)

    async def test_update_case(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0007/2026"}, "u1", self.db
        )
        updated = await update_case(case["id"], {"brief_facts": "Updated facts"}, "u1", self.db)
        self.assertEqual(updated["brief_facts"], "Updated facts")

    async def test_update_case_offence_type(self):
        """AC-002-4: IO can modify offence type during investigation."""
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0016/2026"}, "u1", self.db
        )
        updated = await update_case_offence_type(
            case["id"],
            primary_offence_type_id="ot-theft",
            user_id="u1",
            db=self.db,
        )
        self.assertEqual(updated["primary_offence_type_id"], "ot-theft")

    async def test_ai_suggested_field_edit_is_audited(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0014/2026"}, "u1", self.db
        )
        await update_case(
            case["id"],
            {
                "brief_facts": "Officer edited summary",
                "ai_suggestion_context": {
                    "suggestion_id": "sug-1",
                    "suggested_brief_facts": "AI suggested summary",
                    "suggested_offence_type": "Theft",
                    "suggested_primary_offence_type_id": "off-001",
                },
            },
            "u1",
            self.db,
        )
        timeline = await get_timeline(case["id"], db=self.db)
        self.assertTrue(any(row["activity_type"] == "AI_Suggestion_Edited" for row in timeline))

    async def test_petition_ai_intake_uses_ocr_and_llm(self):
        await seed_offence_types(self.db)
        with patch("cases.run_configured_ocr") as mock_ocr, patch("cases.LiveLLMClient.generate_json") as mock_llm:
            mock_ocr.return_value = OCRResult(
                text="A mobile phone was snatched near the market.",
                provider="google_document_ai",
                page_count=1,
            )
            mock_llm.return_value = LLMResult(
                data={
                    "brief_facts": "An unknown person snatched a mobile phone near the market.",
                    "offence_type": "Theft",
                    "offence_confidence": "High",
                    "case_type": "Petition",
                    "risk_flags": [],
                    "rationale": "Property was dishonestly taken.",
                },
                provider="openai",
                model="gpt-5.2",
                privacy={"raw_pii_sent_to_llm": False},
            )
            suggestion = await suggest_case_intake_from_petition(
                file_name="petition.pdf",
                file_bytes=b"%PDF-1.4 test",
                mime_type="application/pdf",
                user_id="u1",
                db=self.db,
            )
        self.assertEqual(suggestion["offence_type"], "Theft")
        self.assertEqual(suggestion["primary_offence_type_id"], "off-001")
        self.assertIn("mobile phone", suggestion["brief_facts"])
        self.assertEqual(suggestion["ocr"]["provider"], "google_document_ai")
        self.assertEqual(suggestion["llm"]["provider"], "openai")

    async def test_case_access_allows_owner_and_admin(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0008/2026"}, "u1", self.db
        )
        owner = await ensure_case_access(case["id"], {"sub": "u1", "role": "IO"}, self.db)
        admin = await ensure_case_access(case["id"], {"sub": "admin", "role": "System_Admin"}, self.db)
        self.assertEqual(owner.id, case["id"])
        self.assertEqual(admin.id, case["id"])

    async def test_case_access_denies_other_io(self):
        from fastapi import HTTPException

        case = await create_case(
            {"case_type": "FIR", "crime_no": "0009/2026"}, "u1", self.db
        )
        with self.assertRaises(HTTPException) as ctx:
            await ensure_case_access(case["id"], {"sub": "u2", "role": "IO"}, self.db)
        self.assertEqual(ctx.exception.status_code, 403)


class TestStatusTransitions(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_valid_transitions_defined(self):
        self.assertIn("Complaint_Received", VALID_TRANSITIONS)
        self.assertIn("Under_Investigation", VALID_TRANSITIONS)

    async def test_complaint_to_fir_registered(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0010/2026"}, "u1", self.db
        )
        result = await transition_case_status(case["id"], "FIR_Registered", "u1", self.db)
        self.assertEqual(result["status"], "FIR_Registered")

    async def test_invalid_transition_raises(self):
        from fastapi import HTTPException

        case = await create_case(
            {"case_type": "FIR", "crime_no": "0011/2026"}, "u1", self.db
        )
        with self.assertRaises(HTTPException):
            await transition_case_status(case["id"], "Under_Investigation", "u1", self.db)

    async def test_full_lifecycle(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0012/2026"}, "u1", self.db
        )
        await transition_case_status(case["id"], "FIR_Registered", "u1", self.db)
        await transition_case_status(case["id"], "Under_Investigation", "u1", self.db)
        await transition_case_status(case["id"], "Charge_Sheet_Filed", "u1", self.db)
        await transition_case_status(case["id"], "Court_Proceedings", "u1", self.db)
        result = await transition_case_status(case["id"], "Disposed", "u1", self.db)
        self.assertEqual(result["status"], "Disposed")

    async def test_fir_registered_requires_crime_no(self):
        from fastapi import HTTPException

        case = await create_case(
            {"case_type": "Petition", "petition_no": "PET/MH/2026/0001"}, "u1", self.db
        )
        with self.assertRaises(HTTPException):
            await transition_case_status(case["id"], "FIR_Registered", "u1", self.db)

    async def test_closure_report_lifecycle(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0013/2026"}, "u1", self.db
        )
        await transition_case_status(case["id"], "FIR_Registered", "u1", self.db)
        await transition_case_status(case["id"], "Under_Investigation", "u1", self.db)
        await transition_case_status(case["id"], "Closure_Report_Filed", "u1", self.db)
        result = await transition_case_status(case["id"], "Disposed", "u1", self.db)
        self.assertEqual(result["status"], "Disposed")


class TestLifecycleHelpers(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_get_stage_guidance_valid(self):
        g = get_stage_guidance("Under_Investigation")
        self.assertEqual(g["label"], "Under Investigation")
        self.assertIn("expected_documents", g)
        self.assertIn("expected_actions", g)

    async def test_get_stage_guidance_invalid(self):
        g = get_stage_guidance("NonExistent")
        self.assertEqual(g, {})

    async def test_get_lifecycle_map(self):
        lmap = get_lifecycle_map()
        self.assertIn("transitions", lmap)
        self.assertIn("guidance", lmap)
        self.assertIn("Complaint_Received", lmap["transitions"])

    async def test_seed_demo_case(self):
        case = await seed_demo_case("u1", self.db)
        self.assertEqual(case["status"], "Complaint_Received")
        self.assertEqual(case["case_type"], "Petition")
        self.assertIn("id", case)


class TestDocumentManagement(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        self.case = await create_case(
            {"case_type": "FIR", "crime_no": "0020/2026"}, "u1", self.db
        )

    async def test_attach_document(self):
        doc = await attach_document(
            self.case["id"], "test.pdf", "FIR", b"file content", "u1", self.db
        )
        self.assertEqual(doc["file_name"], "test.pdf")
        self.assertIn("sha256", doc)
        self.assertIsNotNone(doc["sha256"])

    async def test_list_case_documents(self):
        await attach_document(self.case["id"], "a.pdf", "FIR", b"a", "u1", self.db)
        await attach_document(
            self.case["id"], "b.pdf", "Witness_Statement", b"b", "u1", self.db
        )
        docs = await list_case_documents(self.case["id"], self.db)
        self.assertEqual(len(docs), 2)

    async def test_get_case_document(self):
        doc = await attach_document(
            self.case["id"], "c.pdf", "FIR", b"c", "u1", self.db
        )
        found = await get_case_document(self.case["id"], doc["id"], self.db)
        self.assertIsNotNone(found)

    async def test_get_nonexistent_document(self):
        self.assertIsNone(await get_case_document(self.case["id"], "nope", self.db))

    async def test_attach_creates_activity(self):
        await attach_document(self.case["id"], "d.pdf", "FIR", b"d", "u1", self.db)
        timeline = await get_timeline(self.case["id"], db=self.db)
        doc_activities = [a for a in timeline if a["activity_type"] == "Document_Attached"]
        self.assertGreater(len(doc_activities), 0)

    async def test_purge_old_versions_removes_superseded(self):
        # Upload v1 then v2 of the same file
        await attach_document(self.case["id"], "report.pdf", "FIR", b"v1 content", "u1", self.db)
        await attach_document(self.case["id"], "report.pdf", "FIR", b"v2 content", "u1", self.db)
        # Both should be in the DB (v1 is_latest=False, v2 is_latest=True)
        all_docs = await list_case_documents(self.case["id"], self.db)
        # list_case_documents may only return latest; count all via purge
        result = await purge_old_document_versions(self.case["id"], "u1", self.db)
        self.assertEqual(result["purged_count"], 1)
        self.assertEqual(result["purged_documents"][0]["file_name"], "report.pdf")
        self.assertEqual(result["purged_documents"][0]["version"], 1)
        self.assertGreater(result["freed_bytes"], 0)

    async def test_purge_no_old_versions(self):
        await attach_document(self.case["id"], "single.pdf", "FIR", b"only version", "u1", self.db)
        result = await purge_old_document_versions(self.case["id"], "u1", self.db)
        self.assertEqual(result["purged_count"], 0)
        self.assertEqual(result["freed_bytes"], 0)

    async def test_purge_multiple_files_multiple_versions(self):
        # Upload 3 versions of file A and 2 versions of file B
        await attach_document(self.case["id"], "a.pdf", "FIR", b"a-v1", "u1", self.db)
        await attach_document(self.case["id"], "a.pdf", "FIR", b"a-v2", "u1", self.db)
        await attach_document(self.case["id"], "a.pdf", "FIR", b"a-v3", "u1", self.db)
        await attach_document(self.case["id"], "b.pdf", "FIR", b"b-v1", "u1", self.db)
        await attach_document(self.case["id"], "b.pdf", "FIR", b"b-v2", "u1", self.db)
        result = await purge_old_document_versions(self.case["id"], "u1", self.db)
        # Should purge a-v1, a-v2, b-v1 = 3 documents
        self.assertEqual(result["purged_count"], 3)


class TestTimeline(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        self.case = await create_case(
            {"case_type": "FIR", "crime_no": "0030/2026"}, "u1", self.db
        )

    async def test_case_creation_creates_activity(self):
        timeline = await get_timeline(self.case["id"], db=self.db)
        self.assertGreater(len(timeline), 0)

    async def test_sort_asc(self):
        await transition_case_status(self.case["id"], "FIR_Registered", "u1", self.db)
        timeline = await get_timeline(self.case["id"], sort_asc=True, db=self.db)
        self.assertGreaterEqual(len(timeline), 2)
        # First should be oldest (case creation)
        self.assertLessEqual(timeline[0]["created_at"], timeline[-1]["created_at"])


class TestActionTracker(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        self.case = await create_case(
            {"case_type": "FIR", "crime_no": "0040/2026"}, "u1", self.db
        )

    async def test_create_task(self):
        task = await create_task(
            self.case["id"], {"task_name": "File charge sheet"}, "u1", self.db
        )
        self.assertEqual(task["task_name"], "File charge sheet")
        self.assertEqual(task["status"], "Pending")

    async def test_list_tasks(self):
        await create_task(self.case["id"], {"task_name": "Task 1"}, "u1", self.db)
        await create_task(self.case["id"], {"task_name": "Task 2"}, "u1", self.db)
        tasks = await list_tasks(self.case["id"], self.db)
        self.assertEqual(len(tasks), 2)

    async def test_update_task_status(self):
        task = await create_task(
            self.case["id"], {"task_name": "Task X"}, "u1", self.db
        )
        updated = await update_task(
            self.case["id"], task["id"], {"status": "Completed"}, "u1", self.db
        )
        self.assertEqual(updated["status"], "Completed")

    async def test_auto_populate_deadlines(self):
        tasks = await auto_populate_statutory_deadlines(
            self.case["id"], "Theft", self.db
        )
        self.assertGreater(len(tasks), 0)
        names = [t["task_name"] for t in tasks]
        self.assertTrue(any("charge" in n.lower() for n in names))


class TestNotifications(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_create_notification(self):
        note = await create_notification("u1", "info", "Test message", db=self.db)
        self.assertEqual(note["message"], "Test message")
        self.assertFalse(note["is_read"])

    async def test_list_unread(self):
        await create_notification("u1", "info", "Msg 1", db=self.db)
        await create_notification("u1", "warning", "Msg 2", db=self.db)
        await create_notification("u2", "info", "Msg 3", db=self.db)  # different user
        result = await list_notifications("u1", db=self.db)
        self.assertEqual(len(result), 2)

    async def test_mark_read(self):
        note = await create_notification("u1", "info", "Msg", db=self.db)
        updated = await mark_notification_read(note["id"], self.db)
        self.assertTrue(updated["is_read"])

    async def test_mark_read_nonexistent(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            await mark_notification_read("nope", self.db)


class TestSeedData(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_seed_police_stations(self):
        await seed_police_stations(self.db)
        result = await list_police_stations_data(self.db)
        self.assertEqual(len(result), 5)
        names = [s["name"] for s in result]
        self.assertTrue(any("Banjara" in n for n in names))

    async def test_seed_offence_types(self):
        await seed_offence_types(self.db)
        result = await list_offence_types_data(self.db)
        self.assertEqual(len(result), 10)

    async def test_search_offence_types(self):
        await seed_offence_types(self.db)
        result = await search_offence_types_data("theft", self.db)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Theft")

    async def test_search_offence_types_no_match(self):
        await seed_offence_types(self.db)
        result = await search_offence_types_data("zzz", self.db)
        self.assertEqual(len(result), 0)


class TestRBACPermissions(AsyncTestCase):
    """Verify PERMISSIONS dict gates the correct roles for case operations."""

    async def test_create_case_allowed_roles(self):
        from auth import PERMISSIONS
        allowed = PERMISSIONS["create_case"]
        self.assertIn("IO", allowed)
        self.assertIn("Clerk", allowed)
        self.assertIn("SHO", allowed)
        self.assertIn("System_Admin", allowed)
        self.assertNotIn("AI_Admin", allowed)

    async def test_transition_case_status_allowed_roles(self):
        from auth import PERMISSIONS
        allowed = PERMISSIONS["transition_case_status"]
        self.assertIn("IO", allowed)
        self.assertIn("SHO", allowed)
        self.assertIn("System_Admin", allowed)
        self.assertNotIn("Clerk", allowed)
        self.assertNotIn("AI_Admin", allowed)

    async def test_upload_document_allowed_roles(self):
        from auth import PERMISSIONS
        allowed = PERMISSIONS["upload_document"]
        self.assertIn("IO", allowed)
        self.assertIn("Clerk", allowed)
        self.assertIn("SHO", allowed)
        self.assertIn("System_Admin", allowed)
        self.assertNotIn("AI_Admin", allowed)


class TestClerkPoliceStationFilter(AsyncTestCase):
    """Clerk and SHO should see cases from their police station, not just own."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        # Create a user with police_station_id
        from models import User, UserRole
        self.clerk_user = User(
            employee_id="CLERK01",
            full_name="Test Clerk",
            role=UserRole.Clerk,
            police_station_id="PS_001",
        )
        self.db.add(self.clerk_user)

    async def test_clerk_sees_station_cases(self):
        # Create cases at the clerk's station by different IOs
        c1 = await create_case(
            {"case_type": "FIR", "crime_no": "0070/2026", "police_station_id": "PS_001"},
            "io_user_1", self.db,
        )
        c2 = await create_case(
            {"case_type": "FIR", "crime_no": "0071/2026", "police_station_id": "PS_001"},
            "io_user_2", self.db,
        )
        # Case at a different station
        await create_case(
            {"case_type": "FIR", "crime_no": "0072/2026", "police_station_id": "PS_002"},
            "io_user_3", self.db,
        )
        result = await list_cases(self.clerk_user.id, "Clerk", db=self.db)
        # Clerk should see both cases at PS_001, not the one at PS_002
        self.assertEqual(result["total"], 2)
        ids = {item["id"] for item in result["items"]}
        self.assertIn(c1["id"], ids)
        self.assertIn(c2["id"], ids)

    async def test_clerk_no_station_sees_own_only(self):
        from models import User, UserRole
        clerk_no_ps = User(
            employee_id="CLERK02",
            full_name="Clerk No Station",
            role=UserRole.Clerk,
        )
        self.db.add(clerk_no_ps)
        await create_case(
            {"case_type": "FIR", "crime_no": "0073/2026"}, "other_io", self.db,
        )
        result = await list_cases(clerk_no_ps.id, "Clerk", db=self.db)
        self.assertEqual(result["total"], 0)


class TestStatutoryDeadlines(AsyncTestCase):
    """Verify all 5 deadline templates and FIR-date-based computation."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        self.case = await create_case(
            {"case_type": "FIR", "crime_no": "0080/2026"}, "u1", self.db,
        )

    async def test_all_five_deadline_templates(self):
        tasks = await auto_populate_statutory_deadlines(
            self.case["id"], "Theft", self.db,
        )
        self.assertEqual(len(tasks), 5)
        names = [t["task_name"] for t in tasks]
        self.assertIn("Submit progress report", names)
        self.assertIn("Serve summons to accused", names)
        self.assertIn("Witness examination completion", names)
        self.assertIn("File charge sheet", names)
        self.assertIn("FSL report follow-up", names)

    async def test_summons_deadline_is_60_days(self):
        from datetime import timedelta
        tasks = await auto_populate_statutory_deadlines(
            self.case["id"], "Theft", self.db,
        )
        summons = [t for t in tasks if t["task_name"] == "Serve summons to accused"][0]
        self.assertEqual(summons["priority"], "High")
        # Verify due date is 60 days from base date
        from models import Case
        case_obj = await self.db.get(Case, self.case["id"])
        raw_date = case_obj.date_of_registration or case_obj.created_at
        expected_due = (raw_date + timedelta(days=60)).date().isoformat()
        self.assertEqual(summons["due_date"], expected_due)

    async def test_deadlines_use_fir_registration_date(self):
        from datetime import datetime, timedelta, timezone
        from models import Case
        # Set date_of_registration on the case
        case_obj = await self.db.get(Case, self.case["id"])
        fir_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
        case_obj.date_of_registration = fir_date

        tasks = await auto_populate_statutory_deadlines(
            self.case["id"], "Theft", self.db,
        )
        # Charge sheet should be 90 days from FIR date, not created_at
        cs_task = [t for t in tasks if t["task_name"] == "File charge sheet"][0]
        expected_due = (fir_date + timedelta(days=90)).date().isoformat()
        self.assertEqual(cs_task["due_date"], expected_due)


class TestAllStageGuidance(AsyncTestCase):
    """Verify all 9 stage guidance entries exist and have required fields."""

    async def test_all_nine_statuses_have_guidance(self):
        statuses = [
            "Complaint_Received", "FIR_Registered", "Under_Investigation",
            "Charge_Sheet_Filed", "Closure_Report_Filed", "Court_Proceedings",
            "Transferred", "Disposed", "Closed_No_FIR",
        ]
        for status in statuses:
            g = get_stage_guidance(status)
            self.assertNotEqual(g, {}, f"No guidance for {status}")
            self.assertIn("label", g, f"Missing 'label' for {status}")
            self.assertIn("description", g, f"Missing 'description' for {status}")
            self.assertIn("expected_documents", g, f"Missing 'expected_documents' for {status}")
            self.assertIn("expected_actions", g, f"Missing 'expected_actions' for {status}")
            self.assertIn("next_hint", g, f"Missing 'next_hint' for {status}")

    async def test_under_investigation_has_rich_guidance(self):
        g = get_stage_guidance("Under_Investigation")
        # Under Investigation should have the most expected documents/actions
        self.assertGreater(len(g["expected_documents"]), 3)
        self.assertGreater(len(g["expected_actions"]), 3)

    async def test_terminal_states_have_closeout_actions(self):
        for status in ("Disposed", "Transferred"):
            g = get_stage_guidance(status)
            self.assertIsInstance(g["expected_documents"], list)
            self.assertGreaterEqual(len(g["expected_actions"]), 1)
            self.assertIn("Terminal", g["next_hint"])


class TestCrimeNoUniqueness(AsyncTestCase):
    """BR-001-1: Crime number unique within police station/year.
    EC-001-1: Duplicate crime number exact error."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_duplicate_crime_no_same_station_raises(self):
        """BR-001-1: Duplicate crime_no at same police station raises 409."""
        from fastapi import HTTPException

        await create_case(
            {"case_type": "FIR", "crime_no": "0090/2026", "police_station_id": "PS_001"},
            "u1", self.db,
        )
        with self.assertRaises(HTTPException) as ctx:
            await create_case(
                {"case_type": "FIR", "crime_no": "0090/2026", "police_station_id": "PS_001"},
                "u2", self.db,
            )
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_duplicate_crime_no_exact_error_message(self):
        """EC-001-1: Exact CONFLICT error message with crime number."""
        from fastapi import HTTPException

        await create_case(
            {"case_type": "FIR", "crime_no": "0091/2026", "police_station_id": "PS_001"},
            "u1", self.db,
        )
        with self.assertRaises(HTTPException) as ctx:
            await create_case(
                {"case_type": "FIR", "crime_no": "0091/2026", "police_station_id": "PS_001"},
                "u2", self.db,
            )
        self.assertIn("already exists", str(ctx.exception.detail))
        self.assertIn("0091/2026", str(ctx.exception.detail))

    async def test_same_crime_no_different_station_allowed(self):
        """BR-001-1: Same crime_no at different police stations is allowed."""
        c1 = await create_case(
            {"case_type": "FIR", "crime_no": "0092/2026", "police_station_id": "PS_001"},
            "u1", self.db,
        )
        c2 = await create_case(
            {"case_type": "FIR", "crime_no": "0092/2026", "police_station_id": "PS_002"},
            "u1", self.db,
        )
        self.assertNotEqual(c1["id"], c2["id"])

    async def test_same_crime_no_different_year_allowed(self):
        """BR-001-1: Same crime_no sequence in different years is allowed."""
        c1 = await create_case(
            {"case_type": "FIR", "crime_no": "0093/2025", "police_station_id": "PS_001"},
            "u1", self.db,
        )
        c2 = await create_case(
            {"case_type": "FIR", "crime_no": "0093/2026", "police_station_id": "PS_001"},
            "u1", self.db,
        )
        self.assertNotEqual(c1["id"], c2["id"])


class TestPetitionAnalysisPersistence(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_create_case_with_ai_suggestion_persists_petition_analysis(self):
        case = await create_case(
            {
                "case_type": "FIR",
                "crime_no": "0001/2026",
                "ai_suggestion_context": {
                    "suggestion_id": "sug-123",
                    "brief_facts": "Theft of mobile phone at Banjara Hills",
                    "offence_type": "Theft",
                    "offence_confidence": 0.92,
                    "case_type": "FIR",
                    "date_of_occurrence": "2026-03-15",
                    "risk_flags": ["night_incident"],
                    "rationale": "Based on petition text analysis",
                },
            },
            "u1",
            self.db,
        )
        self.assertIsNotNone(case.get("petition_analysis"))
        pa = case["petition_analysis"]
        self.assertEqual(pa["suggestion_id"], "sug-123")
        self.assertEqual(pa["brief_facts"], "Theft of mobile phone at Banjara Hills")
        self.assertEqual(pa["offence_type"], "Theft")
        self.assertEqual(pa["offence_confidence"], 0.92)
        self.assertEqual(pa["risk_flags"], ["night_incident"])
        self.assertIn("extracted_at", pa)

    async def test_create_case_without_ai_suggestion_no_petition_analysis(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0002/2026"},
            "u1",
            self.db,
        )
        self.assertIsNone(case.get("petition_analysis"))


if __name__ == "__main__":
    import unittest

    unittest.main()
