"""Tests for Phase 3: Audit Logging & Document Integrity (async ORM)."""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import AsyncTestCase

from audit import (
    compute_sha256,
    get_audit_log,
    infer_action_type,
    log_audit_event,
    search_audit_logs,
)


# ---------------------------------------------------------------------------
# SHA-256 (pure functions — no DB needed, but we still use AsyncTestCase for
# consistency; they could also be plain unittest.TestCase).
# ---------------------------------------------------------------------------

class TestSHA256(AsyncTestCase):
    async def test_compute_sha256_known(self):
        result = compute_sha256(b"hello world")
        self.assertEqual(
            result,
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        )

    async def test_empty_bytes(self):
        result = compute_sha256(b"")
        self.assertEqual(
            result,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    async def test_deterministic(self):
        self.assertEqual(compute_sha256(b"abc"), compute_sha256(b"abc"))


# ---------------------------------------------------------------------------
# Core audit logging
# ---------------------------------------------------------------------------

class TestAuditLogging(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_log_creates_entry(self):
        entry = await log_audit_event(
            user_id="u1",
            action_type="Login",
            entity_type="User",
            entity_id="u1",
            db=self.db,
        )
        self.assertEqual(entry["user_id"], "u1")
        self.assertEqual(entry["action_type"], "Login")
        self.assertIn("id", entry)
        self.assertIn("timestamp", entry)

    async def test_log_stored_in_db(self):
        await log_audit_event("u1", "Upload", "CaseDocument", "doc-1", db=self.db)
        result = await search_audit_logs(db=self.db)
        self.assertEqual(result["total"], 1)

    async def test_log_with_details(self):
        entry = await log_audit_event(
            user_id="u2",
            action_type="Edit",
            entity_type="Case",
            entity_id="c-1",
            details={"field": "status", "old": "Open", "new": "Closed"},
            ip_address="10.0.0.1",
            session_id="sess-abc",
            db=self.db,
        )
        self.assertEqual(entry["ip_address"], "10.0.0.1")
        self.assertEqual(entry["action_details"]["field"], "status")


# ---------------------------------------------------------------------------
# Action-type inference (pure function — no DB)
# ---------------------------------------------------------------------------

class TestInferActionType(AsyncTestCase):
    async def test_post_auth_login(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/auth/login"), "Login")

    async def test_post_auth_logout(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/auth/logout"), "Logout")

    async def test_post_analysis(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/analysis/quality"), "AI_Analysis")

    async def test_post_document_generation(self):
        self.assertEqual(
            infer_action_type("POST", "/api/v1/documents/generate"),
            "Document_Generation",
        )

    async def test_post_generic(self):
        self.assertEqual(infer_action_type("POST", "/api/v1/cases"), "Upload")

    async def test_put(self):
        self.assertEqual(infer_action_type("PUT", "/api/v1/cases/123"), "Edit")

    async def test_patch(self):
        self.assertEqual(infer_action_type("PATCH", "/api/v1/users/123"), "Edit")

    async def test_delete(self):
        self.assertEqual(infer_action_type("DELETE", "/api/v1/cases/123"), "Delete")

    async def test_get_export(self):
        self.assertEqual(infer_action_type("GET", "/api/v1/cases/123/export"), "Export")

    async def test_get_normal_returns_none(self):
        self.assertIsNone(infer_action_type("GET", "/api/v1/cases"))


# ---------------------------------------------------------------------------
# Search / filter / pagination
# ---------------------------------------------------------------------------

class TestSearchAuditLogs(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await log_audit_event("u1", "Login", "User", "u1", db=self.db)
        await log_audit_event("u1", "Upload", "CaseDocument", "doc-1", db=self.db)
        await log_audit_event("u2", "Edit", "Case", "c-1", db=self.db)

    async def test_unfiltered_returns_all(self):
        result = await search_audit_logs(db=self.db)
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 3)

    async def test_filter_by_user_id(self):
        result = await search_audit_logs(filters={"user_id": "u1"}, db=self.db)
        self.assertEqual(result["total"], 2)

    async def test_filter_by_action_type(self):
        result = await search_audit_logs(filters={"action_type": "Login"}, db=self.db)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["action_type"], "Login")

    async def test_filter_by_entity_type(self):
        result = await search_audit_logs(filters={"entity_type": "Case"}, db=self.db)
        self.assertEqual(result["total"], 1)

    async def test_pagination(self):
        result = await search_audit_logs(page=1, page_size=2, db=self.db)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 2)


# ---------------------------------------------------------------------------
# Single-entry retrieval
# ---------------------------------------------------------------------------

class TestGetAuditLog(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_get_existing(self):
        entry = await log_audit_event("u1", "Login", "User", "u1", db=self.db)
        found = await get_audit_log(entry["id"], db=self.db)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], entry["id"])

    async def test_get_nonexistent(self):
        result = await get_audit_log("nonexistent-id", db=self.db)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Immutability contract
# ---------------------------------------------------------------------------

class TestAuditImmutability(AsyncTestCase):
    """Verify no update/delete operations exist for audit logs."""

    async def test_no_update_method(self):
        import audit
        public_funcs = [f for f in dir(audit) if not f.startswith("_")]
        for func_name in public_funcs:
            self.assertNotIn("update", func_name.lower())
            self.assertNotIn("delete", func_name.lower())


if __name__ == "__main__":
    import unittest
    unittest.main()
