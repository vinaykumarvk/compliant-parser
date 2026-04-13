"""Tests for Phase 3: Audit Logging & Document Integrity."""

from __future__ import annotations

import unittest

from audit import (
    _audit_log_store,
    compute_sha256,
    get_audit_log,
    infer_action_type,
    log_audit_event,
    search_audit_logs,
)


class TestSHA256(unittest.TestCase):
    def test_compute_sha256_known(self):
        result = compute_sha256(b"hello world")
        self.assertEqual(
            result,
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        )

    def test_empty_bytes(self):
        result = compute_sha256(b"")
        self.assertEqual(
            result,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_deterministic(self):
        self.assertEqual(compute_sha256(b"abc"), compute_sha256(b"abc"))


class TestAuditLogging(unittest.TestCase):
    def setUp(self):
        _audit_log_store.clear()

    def test_log_creates_entry(self):
        entry = log_audit_event(
            user_id="u1",
            action_type="Login",
            entity_type="User",
            entity_id="u1",
        )
        self.assertEqual(entry["user_id"], "u1")
        self.assertEqual(entry["action_type"], "Login")
        self.assertIn("id", entry)
        self.assertIn("timestamp", entry)

    def test_log_stored_in_memory(self):
        log_audit_event("u1", "Upload", "CaseDocument", "doc-1")
        self.assertEqual(len(_audit_log_store), 1)

    def test_log_with_details(self):
        entry = log_audit_event(
            user_id="u2",
            action_type="Edit",
            entity_type="Case",
            entity_id="c-1",
            details={"field": "status", "old": "Open", "new": "Closed"},
            ip_address="10.0.0.1",
            session_id="sess-abc",
        )
        self.assertEqual(entry["ip_address"], "10.0.0.1")
        self.assertEqual(entry["action_details"]["field"], "status")


class TestInferActionType(unittest.TestCase):
    def test_post_auth_login(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/auth/login"), "Login")

    def test_post_auth_logout(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/auth/logout"), "Logout")

    def test_post_analysis(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/analysis/quality"), "AI_Analysis")

    def test_post_document_generation(self):
        self.assertEqual(
            infer_action_type("POST", "/api/v1/documents/generate"),
            "Document_Generation",
        )

    def test_post_generic(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/cases"), "Upload")

    def test_put(self):
        self.assertEqual(infer_action_type("PUT", "/api/v1/cases/123"), "Edit")

    def test_patch(self):
        self.assertEqual(infer_action_type("PATCH", "/api/v1/users/123"), "Edit")

    def test_delete(self):
        self.assertEqual(infer_action_type("DELETE", "/api/v1/cases/123"), "Delete")

    def test_get_export(self):
        self.assertEqual(infer_action_type("GET", "/api/v1/cases/123/export"), "Export")

    def test_get_normal_returns_none(self):
        self.assertIsNone(infer_action_type("GET", "/api/v1/cases"))


class TestSearchAuditLogs(unittest.TestCase):
    def setUp(self):
        _audit_log_store.clear()
        log_audit_event("u1", "Login", "User", "u1")
        log_audit_event("u1", "Upload", "CaseDocument", "doc-1")
        log_audit_event("u2", "Edit", "Case", "c-1")

    def test_unfiltered_returns_all(self):
        result = search_audit_logs()
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 3)

    def test_filter_by_user_id(self):
        result = search_audit_logs(filters={"user_id": "u1"})
        self.assertEqual(result["total"], 2)

    def test_filter_by_action_type(self):
        result = search_audit_logs(filters={"action_type": "Login"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["action_type"], "Login")

    def test_filter_by_entity_type(self):
        result = search_audit_logs(filters={"entity_type": "Case"})
        self.assertEqual(result["total"], 1)

    def test_pagination(self):
        result = search_audit_logs(page=1, page_size=2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 2)


class TestGetAuditLog(unittest.TestCase):
    def setUp(self):
        _audit_log_store.clear()

    def test_get_existing(self):
        entry = log_audit_event("u1", "Login", "User", "u1")
        found = get_audit_log(entry["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], entry["id"])

    def test_get_nonexistent(self):
        self.assertIsNone(get_audit_log("nonexistent-id"))


class TestAuditImmutability(unittest.TestCase):
    """Verify no update/delete operations exist for audit logs."""

    def test_no_update_method(self):
        import audit
        public_funcs = [f for f in dir(audit) if not f.startswith("_")]
        for func_name in public_funcs:
            self.assertNotIn("update", func_name.lower())
            self.assertNotIn("delete", func_name.lower())


if __name__ == "__main__":
    unittest.main()
