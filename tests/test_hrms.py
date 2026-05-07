"""Tests for HRMS authentication and user sync (AC-017-2 + AC-017-3)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

from tests.conftest import AsyncTestCase
from hrms import authenticate_hrms, HRMSProfile


class _FakeHTTPResponse:
    def __init__(self, data: dict, status: int = 200):
        self._data = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestHRMSAuthentication(AsyncTestCase):
    """AC-017-2: Auth sent to HRMS REST/LDAP."""

    async def test_returns_none_when_hrms_url_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            result = await authenticate_hrms("EMP001", "pass123")
        self.assertIsNone(result)

    async def test_successful_hrms_auth_returns_profile(self):
        response_data = {
            "authenticated": True,
            "employee_id": "EMP001",
            "full_name": "Rajesh Kumar",
            "rank": "Sub Inspector",
            "designation": "IO",
            "police_station_id": "PS_001",
            "role": "IO",
        }
        with patch.dict(os.environ, {"HRMS_AUTH_URL": "https://hrms.internal/auth"}, clear=False), \
             patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(response_data)):
            result = await authenticate_hrms("EMP001", "pass123")

        self.assertIsInstance(result, HRMSProfile)
        self.assertEqual(result.employee_id, "EMP001")
        self.assertEqual(result.full_name, "Rajesh Kumar")
        self.assertEqual(result.rank, "Sub Inspector")
        self.assertEqual(result.designation, "IO")
        self.assertEqual(result.police_station_id, "PS_001")
        self.assertEqual(result.role, "IO")

    async def test_hrms_auth_failure_returns_none(self):
        response_data = {"authenticated": False}
        with patch.dict(os.environ, {"HRMS_AUTH_URL": "https://hrms.internal/auth"}, clear=False), \
             patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(response_data)):
            result = await authenticate_hrms("EMP001", "wrong")
        self.assertIsNone(result)

    async def test_hrms_network_error_returns_none(self):
        from urllib.error import URLError

        with patch.dict(os.environ, {"HRMS_AUTH_URL": "https://hrms.internal/auth"}, clear=False), \
             patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
            result = await authenticate_hrms("EMP001", "pass123")
        self.assertIsNone(result)

    async def test_hrms_timeout_returns_none(self):
        with patch.dict(os.environ, {"HRMS_AUTH_URL": "https://hrms.internal/auth"}, clear=False), \
             patch("urllib.request.urlopen", side_effect=TimeoutError("Timed out")):
            result = await authenticate_hrms("EMP001", "pass123")
        self.assertIsNone(result)

    async def test_hrms_defaults_role_to_io(self):
        response_data = {
            "authenticated": True,
            "employee_id": "EMP002",
            "name": "Sita Devi",
        }
        with patch.dict(os.environ, {"HRMS_AUTH_URL": "https://hrms.internal/auth"}, clear=False), \
             patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(response_data)):
            result = await authenticate_hrms("EMP002", "pass123")

        self.assertIsInstance(result, HRMSProfile)
        self.assertEqual(result.role, "IO")
        self.assertEqual(result.full_name, "Sita Devi")


class TestSyncHRMSUser(AsyncTestCase):
    """AC-017-3: Successful auth syncs name/rank/posting/role."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        import api_v1
        self._sync_hrms_user = api_v1._sync_hrms_user

    async def test_new_user_created_from_hrms_profile(self):
        profile = HRMSProfile(
            employee_id="EMP100",
            full_name="New Officer",
            rank="Inspector",
            designation="SHO",
            police_station_id="PS_003",
            role="SHO",
        )
        result = await self._sync_hrms_user(profile, self.db)
        self.assertEqual(result["employee_id"], "EMP100")
        self.assertEqual(result["full_name"], "New Officer")
        self.assertEqual(result["rank"], "Inspector")
        self.assertEqual(result["designation"], "SHO")
        self.assertEqual(result["police_station_id"], "PS_003")

    async def test_existing_user_fields_updated(self):
        from models import User, UserRole

        user = User(
            employee_id="EMP101",
            full_name="Old Name",
            rank="Constable",
            role=UserRole.IO,
        )
        self.db.add(user)
        await self.db.flush()

        profile = HRMSProfile(
            employee_id="EMP101",
            full_name="Updated Name",
            rank="Sub Inspector",
            designation="IO",
            police_station_id="PS_005",
            role="IO",
        )
        result = await self._sync_hrms_user(profile, self.db)
        self.assertEqual(result["full_name"], "Updated Name")
        self.assertEqual(result["rank"], "Sub Inspector")
        self.assertEqual(result["police_station_id"], "PS_005")


if __name__ == "__main__":
    unittest.main()
