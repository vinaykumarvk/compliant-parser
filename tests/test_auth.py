"""Tests for Phase 2: Authentication & RBAC."""

from __future__ import annotations

import time
import unittest
import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

from auth import (
    PERMISSIONS,
    _failed_attempts,
    blacklist_token,
    blacklisted_tokens,
    check_lockout,
    clear_failed_attempts,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_blacklisted,
    record_failed_attempt,
    require_permission,
    verify_password,
)


class TestPasswordHashing(unittest.TestCase):
    def test_hash_and_verify(self):
        hashed = hash_password("MyP@ss123")
        self.assertTrue(verify_password("MyP@ss123", hashed))

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        self.assertFalse(verify_password("wrong", hashed))

    def test_different_hashes_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        self.assertNotEqual(h1, h2)  # bcrypt salting


class TestJWT(unittest.TestCase):
    def test_create_and_decode_access_token(self):
        token = create_access_token("user-123", "IO")
        payload = decode_token(token)
        self.assertEqual(payload["sub"], "user-123")
        self.assertEqual(payload["role"], "IO")
        self.assertEqual(payload["type"], "access")

    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token("user-456")
        payload = decode_token(token)
        self.assertEqual(payload["sub"], "user-456")
        self.assertEqual(payload["type"], "refresh")

    def test_expired_token_raises(self):
        from fastapi import HTTPException
        token = create_access_token("user-1", "IO", expires_delta=timedelta(seconds=-1))
        with self.assertRaises(HTTPException) as ctx:
            decode_token(token)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_invalid_token_raises(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            decode_token("not.a.valid.token")


class TestTokenBlacklist(unittest.TestCase):
    def setUp(self):
        blacklisted_tokens.clear()

    def test_blacklist_and_check(self):
        self.assertFalse(is_blacklisted("tok-abc"))
        blacklist_token("tok-abc")
        self.assertTrue(is_blacklisted("tok-abc"))

    def test_non_blacklisted(self):
        self.assertFalse(is_blacklisted("tok-xyz"))


class TestAccountLockout(unittest.TestCase):
    def setUp(self):
        _failed_attempts.clear()

    def test_no_lockout_initially(self):
        check_lockout("emp-001")  # should not raise

    def test_lockout_after_5_attempts(self):
        from fastapi import HTTPException
        for _ in range(5):
            record_failed_attempt("emp-001")
        with self.assertRaises(HTTPException) as ctx:
            check_lockout("emp-001")
        self.assertEqual(ctx.exception.status_code, 423)

    def test_clear_resets_count(self):
        for _ in range(4):
            record_failed_attempt("emp-002")
        clear_failed_attempts("emp-002")
        check_lockout("emp-002")  # should not raise

    def test_lockout_expires(self):
        for _ in range(5):
            record_failed_attempt("emp-003")
        # Simulate expired lock
        _failed_attempts["emp-003"]["locked_until"] = time.time() - 1
        check_lockout("emp-003")  # should not raise (expired)


class TestPermissions(unittest.TestCase):
    def test_all_permissions_have_roles(self):
        for perm, roles in PERMISSIONS.items():
            self.assertIsInstance(roles, list)
            self.assertGreater(len(roles), 0, f"{perm} has no roles")

    def test_io_can_create_case(self):
        self.assertIn("IO", PERMISSIONS["create_case"])

    def test_clerk_can_create_case(self):
        self.assertIn("Clerk", PERMISSIONS["create_case"])

    def test_system_admin_can_manage_users(self):
        self.assertIn("System_Admin", PERMISSIONS["manage_users"])

    def test_io_cannot_manage_users(self):
        self.assertNotIn("IO", PERMISSIONS["manage_users"])

    def test_require_permission_unknown_raises(self):
        with self.assertRaises(ValueError):
            require_permission("nonexistent_permission")


class TestRBAC(unittest.TestCase):
    """Test role-based access via require_role and require_permission."""

    def test_role_dependency_returns_callable(self):
        from auth import require_role
        dep = require_role("IO", "Clerk")
        self.assertTrue(callable(dep))

    def test_permission_dependency_returns_callable(self):
        dep = require_permission("create_case")
        self.assertTrue(callable(dep))


if __name__ == "__main__":
    unittest.main()
