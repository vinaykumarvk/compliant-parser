"""Tests for Phase 4: Case Workbench."""

from __future__ import annotations

import unittest

from cases import (
    VALID_TRANSITIONS,
    _action_tracker_tasks,
    _case_activities,
    _case_documents,
    _cases,
    _notifications,
    _offence_types,
    _police_stations,
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


def _clear_stores():
    _cases.clear()
    _case_documents.clear()
    _case_activities.clear()
    _action_tracker_tasks.clear()
    _notifications.clear()
    _police_stations.clear()
    _offence_types.clear()


class TestCrimeNoValidation(unittest.TestCase):
    def test_valid_crime_no(self):
        self.assertTrue(validate_crime_no("0001/2026"))
        self.assertTrue(validate_crime_no("9999/2025"))

    def test_invalid_crime_no(self):
        self.assertFalse(validate_crime_no("1/2026"))
        self.assertFalse(validate_crime_no("abcd/2026"))
        self.assertFalse(validate_crime_no("0001-2026"))
        self.assertFalse(validate_crime_no(""))

    def test_valid_petition_no(self):
        self.assertTrue(validate_petition_no("PET/BH/2026/0001"))

    def test_invalid_petition_no(self):
        self.assertFalse(validate_petition_no("PET/2026"))
        self.assertFalse(validate_petition_no("0001/2026"))


class TestCaseCRUD(unittest.TestCase):
    def setUp(self):
        _clear_stores()

    def test_create_fir_case(self):
        case = create_case(
            {"case_type": "FIR", "crime_no": "0001/2026"},
            user_id="u1",
        )
        self.assertEqual(case["case_type"], "FIR")
        self.assertEqual(case["status"], "Open")
        self.assertIn("id", case)

    def test_create_petition_case(self):
        case = create_case(
            {"case_type": "Petition", "petition_no": "PET/BH/2026/0001"},
            user_id="u1",
        )
        self.assertEqual(case["case_type"], "Petition")

    def test_create_case_invalid_crime_no(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            create_case({"case_type": "FIR", "crime_no": "bad"}, user_id="u1")

    def test_get_case(self):
        case = create_case({"case_type": "FIR", "crime_no": "0002/2026"}, "u1")
        found = get_case(case["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], case["id"])

    def test_get_nonexistent_case(self):
        self.assertIsNone(get_case("nonexistent"))

    def test_list_cases_io_own(self):
        create_case({"case_type": "FIR", "crime_no": "0003/2026"}, "u1")
        create_case({"case_type": "FIR", "crime_no": "0004/2026"}, "u2")
        result = list_cases("u1", "IO")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["total"], 1)

    def test_list_cases_admin_all(self):
        create_case({"case_type": "FIR", "crime_no": "0005/2026"}, "u1")
        create_case({"case_type": "FIR", "crime_no": "0006/2026"}, "u2")
        result = list_cases("u1", "System_Admin")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["total"], 2)

    def test_update_case(self):
        case = create_case({"case_type": "FIR", "crime_no": "0007/2026"}, "u1")
        updated = update_case(case["id"], {"brief_facts": "Updated facts"}, "u1")
        self.assertEqual(updated["brief_facts"], "Updated facts")


class TestStatusTransitions(unittest.TestCase):
    def setUp(self):
        _clear_stores()

    def test_valid_transitions_defined(self):
        self.assertIn("Open", VALID_TRANSITIONS)
        self.assertIn("Under_Investigation", VALID_TRANSITIONS)

    def test_open_to_under_investigation(self):
        case = create_case({"case_type": "FIR", "crime_no": "0010/2026"}, "u1")
        result = transition_case_status(case["id"], "Under_Investigation", "u1")
        self.assertEqual(result["status"], "Under_Investigation")

    def test_invalid_transition_raises(self):
        from fastapi import HTTPException
        case = create_case({"case_type": "FIR", "crime_no": "0011/2026"}, "u1")
        with self.assertRaises(HTTPException):
            transition_case_status(case["id"], "Closed", "u1")

    def test_full_lifecycle(self):
        case = create_case({"case_type": "FIR", "crime_no": "0012/2026"}, "u1")
        transition_case_status(case["id"], "Under_Investigation", "u1")
        transition_case_status(case["id"], "Charge_Sheet_Filed", "u1")
        result = transition_case_status(case["id"], "Closed", "u1")
        self.assertEqual(result["status"], "Closed")


class TestDocumentManagement(unittest.TestCase):
    def setUp(self):
        _clear_stores()
        self.case = create_case({"case_type": "FIR", "crime_no": "0020/2026"}, "u1")

    def test_attach_document(self):
        doc = attach_document(
            self.case["id"], "test.pdf", "FIR", b"file content", "u1"
        )
        self.assertEqual(doc["file_name"], "test.pdf")
        self.assertIn("sha256", doc)
        self.assertIsNotNone(doc["sha256"])

    def test_list_case_documents(self):
        attach_document(self.case["id"], "a.pdf", "FIR", b"a", "u1")
        attach_document(self.case["id"], "b.pdf", "Witness_Statement", b"b", "u1")
        docs = list_case_documents(self.case["id"])
        self.assertEqual(len(docs), 2)

    def test_get_case_document(self):
        doc = attach_document(self.case["id"], "c.pdf", "FIR", b"c", "u1")
        found = get_case_document(self.case["id"], doc["id"])
        self.assertIsNotNone(found)

    def test_get_nonexistent_document(self):
        self.assertIsNone(get_case_document(self.case["id"], "nope"))

    def test_attach_creates_activity(self):
        attach_document(self.case["id"], "d.pdf", "FIR", b"d", "u1")
        timeline = get_timeline(self.case["id"])
        doc_activities = [a for a in timeline if a["activity_type"] == "Document_Attached"]
        self.assertGreater(len(doc_activities), 0)


class TestTimeline(unittest.TestCase):
    def setUp(self):
        _clear_stores()
        self.case = create_case({"case_type": "FIR", "crime_no": "0030/2026"}, "u1")

    def test_case_creation_creates_activity(self):
        timeline = get_timeline(self.case["id"])
        self.assertGreater(len(timeline), 0)

    def test_sort_asc(self):
        transition_case_status(self.case["id"], "Under_Investigation", "u1")
        timeline = get_timeline(self.case["id"], sort_asc=True)
        self.assertGreaterEqual(len(timeline), 2)
        # First should be oldest (case creation)
        self.assertLessEqual(timeline[0]["created_at"], timeline[-1]["created_at"])


class TestActionTracker(unittest.TestCase):
    def setUp(self):
        _clear_stores()
        self.case = create_case({"case_type": "FIR", "crime_no": "0040/2026"}, "u1")

    def test_create_task(self):
        task = create_task(self.case["id"], {"task_name": "File charge sheet"}, "u1")
        self.assertEqual(task["task_name"], "File charge sheet")
        self.assertEqual(task["status"], "Pending")

    def test_list_tasks(self):
        create_task(self.case["id"], {"task_name": "Task 1"}, "u1")
        create_task(self.case["id"], {"task_name": "Task 2"}, "u1")
        tasks = list_tasks(self.case["id"])
        self.assertEqual(len(tasks), 2)

    def test_update_task_status(self):
        task = create_task(self.case["id"], {"task_name": "Task X"}, "u1")
        updated = update_task(self.case["id"], task["id"], {"status": "Completed"}, "u1")
        self.assertEqual(updated["status"], "Completed")

    def test_auto_populate_deadlines(self):
        tasks = auto_populate_statutory_deadlines(self.case["id"], "Theft")
        self.assertGreater(len(tasks), 0)
        names = [t["task_name"] for t in tasks]
        self.assertTrue(any("charge" in n.lower() for n in names))


class TestNotifications(unittest.TestCase):
    def setUp(self):
        _clear_stores()

    def test_create_notification(self):
        note = create_notification("u1", "info", "Test message")
        self.assertEqual(note["message"], "Test message")
        self.assertFalse(note["is_read"])

    def test_list_unread(self):
        create_notification("u1", "info", "Msg 1")
        create_notification("u1", "warning", "Msg 2")
        create_notification("u2", "info", "Msg 3")  # different user
        result = list_notifications("u1")
        self.assertEqual(len(result), 2)

    def test_mark_read(self):
        note = create_notification("u1", "info", "Msg")
        updated = mark_notification_read(note["id"])
        self.assertTrue(updated["is_read"])

    def test_mark_read_nonexistent(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            mark_notification_read("nope")


class TestSeedData(unittest.TestCase):
    def setUp(self):
        _clear_stores()

    def test_seed_police_stations(self):
        seed_police_stations()
        result = list_police_stations_data()
        self.assertEqual(len(result), 5)
        names = [s["name"] for s in result]
        self.assertTrue(any("Banjara" in n for n in names))

    def test_seed_offence_types(self):
        seed_offence_types()
        result = list_offence_types_data()
        self.assertEqual(len(result), 10)

    def test_search_offence_types(self):
        seed_offence_types()
        result = search_offence_types_data("theft")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Theft")

    def test_search_offence_types_no_match(self):
        seed_offence_types()
        result = search_offence_types_data("zzz")
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
