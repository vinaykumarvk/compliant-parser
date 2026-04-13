"""Tests for Phase 4: Case Workbench (async + MockAsyncSession)."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.conftest import AsyncTestCase

from cases import (
    VALID_TRANSITIONS,
    attach_document,
    auto_populate_statutory_deadlines,
    create_case,
    create_notification,
    create_task,
    get_case,
    get_case_document,
    get_timeline,
    list_case_documents,
    list_cases,
    list_notifications,
    list_offence_types_data,
    list_police_stations_data,
    list_tasks,
    mark_notification_read,
    search_offence_types_data,
    seed_offence_types,
    seed_police_stations,
    transition_case_status,
    update_case,
    update_task,
    validate_crime_no,
    validate_petition_no,
)


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
        self.assertEqual(case["status"], "Open")
        self.assertIn("id", case)

    async def test_create_petition_case(self):
        case = await create_case(
            {"case_type": "Petition", "petition_no": "PET/BH/2026/0001"},
            "u1",
            self.db,
        )
        self.assertEqual(case["case_type"], "Petition")

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


class TestStatusTransitions(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()

    async def test_valid_transitions_defined(self):
        self.assertIn("Open", VALID_TRANSITIONS)
        self.assertIn("Under_Investigation", VALID_TRANSITIONS)

    async def test_open_to_under_investigation(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0010/2026"}, "u1", self.db
        )
        result = await transition_case_status(case["id"], "Under_Investigation", "u1", self.db)
        self.assertEqual(result["status"], "Under_Investigation")

    async def test_invalid_transition_raises(self):
        from fastapi import HTTPException

        case = await create_case(
            {"case_type": "FIR", "crime_no": "0011/2026"}, "u1", self.db
        )
        with self.assertRaises(HTTPException):
            await transition_case_status(case["id"], "Closed", "u1", self.db)

    async def test_full_lifecycle(self):
        case = await create_case(
            {"case_type": "FIR", "crime_no": "0012/2026"}, "u1", self.db
        )
        await transition_case_status(case["id"], "Under_Investigation", "u1", self.db)
        await transition_case_status(case["id"], "Charge_Sheet_Filed", "u1", self.db)
        result = await transition_case_status(case["id"], "Closed", "u1", self.db)
        self.assertEqual(result["status"], "Closed")


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
        await transition_case_status(self.case["id"], "Under_Investigation", "u1", self.db)
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


if __name__ == "__main__":
    import unittest

    unittest.main()
