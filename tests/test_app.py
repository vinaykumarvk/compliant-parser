"""Tests for the FastAPI application endpoints."""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _minimal_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _make_fake_row(
    record_id: str | None = None,
    file_name: str = "test.pdf",
    file_size: int = 1024,
    file_bytes: bytes = b"%PDF-1.4\n%%EOF\n",
    parsed_output: dict | None = None,
    document_format: str = "POLICE_COMPLAINT",
    completeness_score: float = 0.75,
    created_at: datetime | None = None,
    gaps: dict | None = None,
) -> MagicMock:
    """Build a mock row that behaves like a SQLAlchemy Row."""
    if record_id is None:
        record_id = str(uuid.uuid4())
    if parsed_output is None:
        parsed_output = {"gaps": {"completeness_score": 0.75, "missing_fields": []}}
    if created_at is None:
        created_at = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
    if gaps is None:
        gaps = parsed_output.get("gaps")
    row = MagicMock()
    row.id = record_id
    row.file_name = file_name
    row.file_size = file_size
    row.file_bytes = file_bytes
    row.parsed_output = parsed_output
    row.document_format = document_format
    row.completeness_score = completeness_score
    row.created_at = created_at
    row.gaps = gaps
    row.police_station = None
    row.nature_of_offence = None
    row.language = None
    row.bns_sections = None
    row.occurrence_date = None
    return row


class _AsyncCM:
    """Async context manager that yields a fixed value."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        return None


def _mock_engine():
    """Create a mock async engine with context-managed connect/begin."""
    conn = AsyncMock()
    engine = MagicMock()
    engine.connect.side_effect = lambda: _AsyncCM(conn)
    engine.begin.side_effect = lambda: _AsyncCM(conn)
    return engine, conn


class _BaseAppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in (
                "APP_ADMIN_USERNAME",
                "APP_ADMIN_PASSWORD",
                "APP_SESSION_SECRET",
                "DOC_AI_PROJECT_ID",
                "DOC_AI_LOCATION",
                "DOC_AI_PROCESSOR_ID",
                "GOOGLE_APPLICATION_CREDENTIALS",
                "OPENAI_EXTRACTION_ENABLED",
                "OPENAI_EXTRACTION_MIN_CONFIDENCE",
                "OPENAI_EXTRACTION_REQUIRE_EVIDENCE",
                "CORS_ALLOWED_ORIGINS",
                "RATE_LIMIT_RPM",
                "DATABASE_URL",
            )
        }
        os.environ["APP_ADMIN_USERNAME"] = "operator"
        os.environ["APP_ADMIN_PASSWORD"] = "correct horse battery staple"
        os.environ["APP_SESSION_SECRET"] = "test-session-secret"
        os.environ["DOC_AI_PROJECT_ID"] = "test-project"
        os.environ["DOC_AI_LOCATION"] = "eu"
        os.environ["DOC_AI_PROCESSOR_ID"] = "test-processor"
        os.environ["OPENAI_EXTRACTION_ENABLED"] = "false"
        os.environ["OPENAI_EXTRACTION_MIN_CONFIDENCE"] = "medium"
        os.environ["OPENAI_EXTRACTION_REQUIRE_EVIDENCE"] = "true"
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class AppEndpointTests(_BaseAppTestCase):
    """Test API endpoints without hitting real cloud services."""

    def setUp(self) -> None:
        super().setUp()
        from app import _rate_limit_log, app

        self._init_db_patch = patch("app.initialize_database", new=AsyncMock(return_value=None))
        self._db_health_patch = patch(
            "app.get_database_health",
            new=AsyncMock(return_value={"status": "ok", "table_ready": True, "detail": "ready"}),
        )
        self._init_db_patch.start()
        self._db_health_patch.start()
        _rate_limit_log.clear()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._db_health_patch.stop()
        self._init_db_patch.stop()
        super().tearDown()

    def _login(self, password: str | None = None) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={
                "username": "operator",
                "password": password or "correct horse battery staple",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_index_returns_html(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("<!doctype html>", response.text.lower())

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["parser_mode"], "police_complaint")
        self.assertTrue(data["auth_required"])
        self.assertEqual(data["database_status"], "ok")
        self.assertTrue(data["database_table_ready"])

    def test_api_health_returns_ok(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_login_rejects_invalid_credentials(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_session_endpoint_reflects_login_state(self) -> None:
        response = self.client.get("/api/auth/session")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["authenticated"])

        self._login()

        response = self.client.get("/api/auth/session")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertEqual(response.json()["user"], "operator")

    def test_parse_requires_authentication(self) -> None:
        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 401)

    def test_parse_rejects_unsupported_type(self) -> None:
        self._login()
        response = self.client.post(
            "/api/parse",
            files={"file": ("test.xyz", b"hello world", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported", response.json()["detail"])

    def test_parse_rejects_empty_file(self) -> None:
        self._login()
        response = self.client.post(
            "/api/parse",
            files={"file": ("test.pdf", b"", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    @patch("app.MAX_PARSE_UPLOAD_BYTES", 10)
    def test_parse_rejects_oversized_file(self) -> None:
        self._login()
        response = self.client.post(
            "/api/parse",
            files={"file": ("test.pdf", b"x" * 20, "application/pdf")},
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("size limit", response.json()["detail"].lower())

    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_success(self, mock_process: MagicMock, mock_save_parse_record: AsyncMock) -> None:
        self._login()
        mock_doc = MagicMock()
        mock_doc.document.text = (
            "Subject: Theft complaint\n"
            "My mobile phone was stolen on 15 March 2026 near the bus stand."
        )
        mock_process.return_value = mock_doc
        mock_save_parse_record.return_value = "record-123"

        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "record-123")
        self.assertEqual(data["document_format"], "POLICE_COMPLAINT")
        self.assertIn("parsed_output", data)
        mock_process.assert_called_once()
        mock_save_parse_record.assert_awaited_once()

    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_persistence_failure_is_explicit(
        self,
        mock_process: MagicMock,
        mock_save_parse_record: AsyncMock,
    ) -> None:
        self._login()
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Theft complaint"
        mock_process.return_value = mock_doc
        mock_save_parse_record.side_effect = RuntimeError("db unavailable")

        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("saved to history", response.json()["detail"].lower())

    @patch("app.process_document_bytes", side_effect=Exception("Cloud error"))
    def test_parse_internal_error_sanitized(self, mock_process: MagicMock) -> None:
        self._login()
        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 500)
        detail = response.json()["detail"]
        self.assertNotIn("Cloud error", detail)
        self.assertIn("Check server logs", detail)

    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_accepts_jpeg(self, mock_process: MagicMock, mock_save: AsyncMock) -> None:
        self._login()
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Photo evidence of damage"
        mock_process.return_value = mock_doc
        mock_save.return_value = "record-img-1"

        response = self.client.post(
            "/api/parse",
            files={"file": ("photo.jpg", b"\xff\xd8\xff\xe0fake-jpeg", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "record-img-1")
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args
        self.assertEqual(call_kwargs.kwargs.get("mime_type") or call_kwargs[1].get("mime_type", ""), "image/jpeg")

    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_accepts_docx(self, mock_process: MagicMock, mock_save: AsyncMock) -> None:
        self._login()
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Written complaint document"
        mock_process.return_value = mock_doc
        mock_save.return_value = "record-docx-1"

        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.docx", b"PK\x03\x04fake-docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "record-docx-1")

    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_accepts_png(self, mock_process: MagicMock, mock_save: AsyncMock) -> None:
        self._login()
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Screenshot"
        mock_process.return_value = mock_doc
        mock_save.return_value = "record-png-1"

        response = self.client.post(
            "/api/parse",
            files={"file": ("screenshot.png", b"\x89PNGfake-png", "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "record-png-1")


class HistoryEndpointTests(_BaseAppTestCase):
    """Test the history API endpoints with a mocked database."""

    def setUp(self) -> None:
        super().setUp()
        self.engine, self.conn = _mock_engine()

        async def fake_get_engine():
            return self.engine

        from app import _rate_limit_log, app

        self._init_db_patch = patch("app.initialize_database", new=AsyncMock(return_value=None))
        self._db_health_patch = patch(
            "app.get_database_health",
            new=AsyncMock(return_value={"status": "ok", "table_ready": True, "detail": "ready"}),
        )
        self._engine_patch = patch("app.get_engine", side_effect=fake_get_engine)
        self._init_db_patch.start()
        self._db_health_patch.start()
        self._engine_patch.start()

        _rate_limit_log.clear()
        self.client = TestClient(app, raise_server_exceptions=False)
        login_response = self.client.post(
            "/api/auth/login",
            json={
                "username": "operator",
                "password": "correct horse battery staple",
            },
        )
        self.assertEqual(login_response.status_code, 200)

    def tearDown(self) -> None:
        self._engine_patch.stop()
        self._db_health_patch.stop()
        self._init_db_patch.stop()
        super().tearDown()

    def test_history_requires_authentication(self) -> None:
        self.client.cookies.clear()
        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 401)

    def test_list_history_empty(self) -> None:
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([]))
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_history_with_records(self) -> None:
        row = _make_fake_row()
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([row]))
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["file_name"], "test.pdf")
        self.assertIn("gaps", data[0])

    def test_get_history_record(self) -> None:
        row = _make_fake_row()
        result_mock = MagicMock()
        result_mock.first.return_value = row
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.get(f"/api/history/{row.id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["file_name"], "test.pdf")
        self.assertIn("parsed_output", data)

    def test_get_history_record_not_found(self) -> None:
        result_mock = MagicMock()
        result_mock.first.return_value = None
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.get(f"/api/history/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 404)

    def test_get_history_pdf(self) -> None:
        pdf_bytes = _minimal_pdf_bytes()
        row = _make_fake_row(file_bytes=pdf_bytes)
        result_mock = MagicMock()
        result_mock.first.return_value = row
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.get(f"/api/history/{row.id}/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, pdf_bytes)
        self.assertIn("application/pdf", response.headers["content-type"])

    def test_get_history_pdf_not_found(self) -> None:
        result_mock = MagicMock()
        result_mock.first.return_value = None
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.get(f"/api/history/{uuid.uuid4()}/pdf")
        self.assertEqual(response.status_code, 404)

    def test_delete_history_record(self) -> None:
        result_mock = MagicMock()
        result_mock.rowcount = 1
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.delete(f"/api/history/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

    def test_delete_history_record_not_found(self) -> None:
        result_mock = MagicMock()
        result_mock.rowcount = 0
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.delete(f"/api/history/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 404)

    def test_clear_history(self) -> None:
        result_mock = MagicMock()
        result_mock.rowcount = 5
        self.conn.execute = AsyncMock(return_value=result_mock)

        response = self.client.delete("/api/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_count"], 5)


class ParseDocumentEdgeCaseTests(unittest.TestCase):
    """Edge-case tests for the parse_document function."""

    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in (
                "OPENAI_EXTRACTION_ENABLED",
                "OPENAI_EXTRACTION_MIN_CONFIDENCE",
                "OPENAI_EXTRACTION_REQUIRE_EVIDENCE",
            )
        }
        os.environ["OPENAI_EXTRACTION_ENABLED"] = "false"
        os.environ["OPENAI_EXTRACTION_MIN_CONFIDENCE"] = "medium"
        os.environ["OPENAI_EXTRACTION_REQUIRE_EVIDENCE"] = "true"

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_empty_input(self) -> None:
        from complaint_parsing import parse_document

        result = parse_document("")
        self.assertEqual(result["document_type"], "police_complaint")
        self.assertEqual(result["language"]["detected"], "unknown")
        self.assertEqual(result["gaps"]["completeness_score"], 0.0)

    def test_whitespace_only_input(self) -> None:
        from complaint_parsing import parse_document

        result = parse_document("   \n\n\t  ")
        self.assertEqual(result["document_type"], "police_complaint")
        self.assertEqual(result["meta"]["line_count"], 0)

    def test_non_complaint_text(self) -> None:
        from complaint_parsing import parse_document

        result = parse_document("The quick brown fox jumps over the lazy dog.")
        self.assertEqual(result["language"]["detected"], "en")
        self.assertFalse(result["meta"]["complaint_assessment"]["likely_police_complaint"])

    def test_schema_version_present(self) -> None:
        from complaint_parsing import parse_document

        result = parse_document("Subject: Test complaint")
        self.assertEqual(result["schema_version"], "3.0")

    def test_all_fields_exist_in_complaint(self) -> None:
        from complaint_parsing import parse_document

        result = parse_document("Subject: Test complaint about theft")
        for field in ("who", "what", "when", "where", "why", "how"):
            self.assertIn(field, result["complaint"])
            self.assertIn("status", result["complaint"][field])
        self.assertIn("complaint_brief", result["summary"])
        self.assertIn("review_questions", result["summary"])
        self.assertIn("fir_draft", result)
        self.assertIn("proposed_bns_sections", result["fir_draft"])
        self.assertIn("formatted_text", result["fir_draft"])
        self.assertIn("extraction", result["meta"])


if __name__ == "__main__":
    unittest.main()
