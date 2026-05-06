"""Tests for the FastAPI application endpoints."""

from __future__ import annotations

import os
import asyncio
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import sqlalchemy as sa
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
    row.kis_index_status = "indexed"
    row.kis_source_id = "src_1"
    row.kis_wiki_article_id = "wiki_1"
    row.kis_snapshot_id = None
    row.kis_quality_passed = True
    row.kis_fact_count = 3
    row.kis_graph_edge_count = 3
    row.kis_chunk_count = 2
    row.kis_idempotent_replay = False
    row.kis_privacy_summary = {"raw_pii_sent_to_llm": False}
    row.kis_index_summary = {"indexed": True}
    row.kis_error_code = None
    row.kis_error_detail = None
    row.kis_attempt_count = 1
    row.kis_next_attempt_at = None
    row.kis_worker_id = None
    row.kis_locked_at = None
    row.kis_locked_until = None
    row.kis_last_attempt_at = created_at
    row.kis_indexed_at = created_at
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
                "OPENAI_API_KEY",
                "OPENAI_TRANSLATION_API_KEY",
                "OPENAI_TRANSLATION_ENABLED",
                "TRANSLATION_REFINEMENT_ENABLED",
                "OPENAI_EXTRACTION_ENABLED",
                "OPENAI_EXTRACTION_MIN_CONFIDENCE",
                "OPENAI_EXTRACTION_REQUIRE_EVIDENCE",
                "CORS_ALLOWED_ORIGINS",
                "RATE_LIMIT_RPM",
                "DATABASE_URL",
                "IQW_KIS_ENABLED",
                "IQW_KIS_BASE_URL",
                "IQW_KIS_API_KEY",
                "IQW_KIS_DOMAIN",
                "IQW_KIS_KB",
                "IQW_KIS_FALLBACK_ON_ERROR",
                "IQW_KIS_AUTO_PUBLISH_SNAPSHOT",
                "IQW_KIS_BACKGROUND_INDEXING",
            )
        }
        os.environ["APP_ADMIN_USERNAME"] = "operator"
        os.environ["APP_ADMIN_PASSWORD"] = "correct horse battery staple"
        os.environ["APP_SESSION_SECRET"] = "test-session-secret"
        os.environ["DOC_AI_PROJECT_ID"] = "test-project"
        os.environ["DOC_AI_LOCATION"] = "eu"
        os.environ["DOC_AI_PROCESSOR_ID"] = "test-processor"
        os.environ["OPENAI_TRANSLATION_ENABLED"] = "false"
        os.environ["TRANSLATION_REFINEMENT_ENABLED"] = "false"
        os.environ["OPENAI_EXTRACTION_ENABLED"] = "false"
        os.environ["OPENAI_EXTRACTION_MIN_CONFIDENCE"] = "medium"
        os.environ["OPENAI_EXTRACTION_REQUIRE_EVIDENCE"] = "true"
        os.environ["IQW_KIS_ENABLED"] = "false"
        os.environ["IQW_KIS_BACKGROUND_INDEXING"] = "false"
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENAI_TRANSLATION_API_KEY", None)
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
        from app import _rate_limit_log, _support_request_store, app

        self._init_db_patch = patch("app.initialize_database", new=AsyncMock(return_value=None))
        self._db_health_patch = patch(
            "app.get_database_health",
            new=AsyncMock(return_value={"status": "ok", "table_ready": True, "detail": "ready"}),
        )
        self._get_engine_patch = patch(
            "app.get_engine",
            new=AsyncMock(side_effect=RuntimeError("Either DATABASE_URL or CLOUD_SQL_CONNECTION_NAME must be set.")),
        )
        self._init_db_patch.start()
        self._db_health_patch.start()
        self._get_engine_patch.start()
        _rate_limit_log.clear()
        _support_request_store.clear()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self._get_engine_patch.stop()
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

    def test_index_contains_assistance_packet_ui(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="assistanceGenerateBtn"', response.text)
        self.assertIn('id="assistancePacketPanel"', response.text)
        self.assertIn('data-assistance-tab="translation"', response.text)
        self.assertIn('data-assistance-tab="lineage"', response.text)
        self.assertIn("Generate Detailed Analysis", response.text)
        self.assertIn("Checklist Readiness", response.text)
        self.assertIn("Checklist Analysis", response.text)

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

    def test_auth_support_request_creates_ticket(self) -> None:
        response = self.client.post(
            "/api/auth/support-request",
            json={
                "request_type": "password_reset",
                "user_identifier": "operator",
                "message": "Forgot password from login page",
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["ticket_id"].startswith("SUP-"))
        self.assertEqual(data["request_type"], "password_reset")
        self.assertIn(data["persistence"], {"database", "memory_fallback"})

    def test_auth_support_requests_require_login_to_list(self) -> None:
        self.client.post(
            "/api/auth/support-request",
            json={"request_type": "access_request", "user_identifier": "operator"},
        )
        response = self.client.get("/api/auth/support-requests")
        self.assertEqual(response.status_code, 401)

        self._login()
        response = self.client.get("/api/auth/support-requests")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_auth_support_request_status_update_requires_login_and_updates_ticket(self) -> None:
        created = self.client.post(
            "/api/auth/support-request",
            json={"request_type": "access_request", "user_identifier": "operator"},
        )
        ticket_id = created.json()["ticket_id"]

        response = self.client.patch(
            f"/api/auth/support-requests/{ticket_id}",
            json={"status": "resolved"},
        )
        self.assertEqual(response.status_code, 401)

        self._login()
        response = self.client.patch(
            f"/api/auth/support-requests/{ticket_id}",
            json={"status": "resolved"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], ticket_id)
        self.assertEqual(data["status"], "resolved")
        self.assertEqual(data["resolved_by"], "operator")

    def test_parse_requires_authentication(self) -> None:
        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 401)

    def test_rewrite_request_requires_authentication(self) -> None:
        response = self.client.post(
            "/api/rewrite-requests",
            json={"parse_record_id": str(uuid.uuid4())},
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
        self.assertEqual(data["kis_indexing"]["indexed"], False)
        mock_process.assert_called_once()
        mock_save_parse_record.assert_awaited_once()

    @patch("app._index_parse_record_with_kis", new_callable=AsyncMock)
    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_success_triggers_kis_indexing(
        self,
        mock_process: MagicMock,
        mock_save_parse_record: AsyncMock,
        mock_index_kis: AsyncMock,
    ) -> None:
        self._login()
        os.environ["IQW_KIS_ENABLED"] = "true"
        os.environ["IQW_KIS_BASE_URL"] = "http://kis.local"
        os.environ["IQW_KIS_API_KEY"] = "secret-key"
        os.environ["IQW_KIS_DOMAIN"] = "police-iqw"
        os.environ["IQW_KIS_KB"] = "kb-1"
        os.environ["IQW_KIS_BACKGROUND_INDEXING"] = "false"
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Theft complaint\nVehicle KA01AB1234 was stolen."
        mock_process.return_value = mock_doc
        mock_save_parse_record.return_value = "record-123"
        mock_index_kis.return_value = {"enabled": True, "indexed": True, "source_id": "src_1"}

        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kis_indexing"]["source_id"], "src_1")
        mock_index_kis.assert_awaited_once()
        self.assertEqual(mock_index_kis.await_args.kwargs["record_id"], "record-123")

    @patch("app.enqueue_kis_indexing", new_callable=AsyncMock)
    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_parse_success_queues_kis_indexing(
        self,
        mock_process: MagicMock,
        mock_save_parse_record: AsyncMock,
        mock_enqueue: AsyncMock,
    ) -> None:
        self._login()
        os.environ["IQW_KIS_ENABLED"] = "true"
        os.environ["IQW_KIS_BASE_URL"] = "http://kis.local"
        os.environ["IQW_KIS_API_KEY"] = "secret-key"
        os.environ["IQW_KIS_DOMAIN"] = "police-iqw"
        os.environ["IQW_KIS_KB"] = "kb-1"
        os.environ["IQW_KIS_BACKGROUND_INDEXING"] = "true"
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Theft complaint\nVehicle KA01AB1234 was stolen."
        mock_process.return_value = mock_doc
        mock_save_parse_record.return_value = "record-123"

        response = self.client.post(
            "/api/parse",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["kis_indexing"]["queued"], True)
        self.assertEqual(data["kis_indexing"]["kis_index_status"], "pending")
        mock_enqueue.assert_awaited_once_with("record-123")

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
        self.assertEqual(data[0]["kis_index_status"], "indexed")
        self.assertEqual(data[0]["kis_source_id"], "src_1")

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
        self.assertEqual(data["kis_index_status"], "indexed")

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


class _FakeMappingResult:
    def __init__(self, rows: list[dict] | None = None, scalar_value=None, rowcount: int = 0):
        self._rows = rows or []
        self._scalar_value = scalar_value
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar_value


def _bound_value(value):
    if hasattr(value, "value"):
        return value.value
    return datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc)


def _insert_rows(statement) -> list[dict]:
    if getattr(statement, "_multi_values", None):
        return [dict(row) for row in statement._multi_values[0]]
    return {key: _bound_value(value) for key, value in statement._values.items()},


def _update_values(statement) -> dict:
    return {key: _bound_value(value) for key, value in statement._values.items()}


def _select_table_name(statement) -> str | None:
    froms = statement.get_final_froms()
    return froms[0].name if froms else None


def _selected_column_count(statement) -> int:
    try:
        return len(list(statement.selected_columns))
    except Exception:
        return 0


def _rewrite_parsed_output() -> dict:
    return {
        "text": {
            "ocr_text": "తెలుగు మూల వచనం",
            "raw_english_translation": "Raw English petition text.",
            "refined_english_translation": (
                "I, Ravi Kumar, submit that my mobile phone was stolen near the bus stop "
                "at around 8 PM. I request police action."
            ),
        },
        "language": {"detected": "te", "detected_name": "Telugu"},
        "gaps": {
            "missing_details": ["Name of accused person"],
            "uncertain_details": ["CCTV or witness evidence"],
            "missing_fields": ["where.exact_location"],
            "uncertain_fields": [],
        },
    }


class _RewriteFakeConnection:
    def __init__(self, parse_record_id: str):
        self.parse_record_id = parse_record_id
        self.rows = {
            "petition_rewrite_requests": [],
            "petition_placeholders": [],
            "generated_petition_drafts": [],
            "source_lineage_maps": [],
            "petitioner_packets": [],
            "petitioner_verification_records": [],
            "petition_draft_translations": [],
            "petition_checklist_questions": [],
            "petition_checklist_evaluations": [],
            "rewrite_audit_events": [],
        }

    async def execute(self, statement):
        if isinstance(statement, sa.sql.dml.Insert):
            table_name = statement.table.name
            rows = list(_insert_rows(statement))
            for row in rows:
                row.setdefault("created_at", datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc))
                if table_name == "petition_rewrite_requests":
                    row.setdefault("is_deleted", False)
                    row.setdefault("semantic_validation_status", "not_required")
                    row.setdefault("petitioner_consent_status", "not_presented")
                if table_name == "petition_placeholders":
                    row.setdefault("value_status", "blank")
                self.rows[table_name].append(row)
            return _FakeMappingResult(rowcount=len(rows))

        if isinstance(statement, sa.sql.dml.Update):
            table_name = statement.table.name
            values = _update_values(statement)
            updated = 0
            for row in self.rows.get(table_name, []):
                row.update(values)
                updated += 1
            return _FakeMappingResult(rowcount=updated)

        table_name = _select_table_name(statement)
        if table_name == "parse_records":
            return _FakeMappingResult(
                [
                    {
                        "id": self.parse_record_id,
                        "file_name": "telugu-petition.pdf",
                        "case_id": "CASE-1",
                        "parsed_output": _rewrite_parsed_output(),
                    }
                ]
            )
        if table_name == "petition_rewrite_requests":
            rows = self.rows["petition_rewrite_requests"]
            if _selected_column_count(statement) == 2:
                active = [
                    row for row in rows
                    if row.get("generation_status") not in {"printed", "shared", "accepted", "superseded", "failed", "cancelled"}
                    and not row.get("is_deleted")
                ]
                return _FakeMappingResult(active[:1])
            return _FakeMappingResult(rows[:1])
        if table_name == "petition_placeholders":
            rows = sorted(self.rows["petition_placeholders"], key=lambda row: row.get("display_order", 0))
            return _FakeMappingResult(rows)
        if table_name == "generated_petition_drafts":
            if "max" in str(statement).lower():
                max_version = max((row.get("draft_version", 0) for row in self.rows["generated_petition_drafts"]), default=0)
                return _FakeMappingResult(scalar_value=max_version + 1)
            rows = sorted(
                self.rows["generated_petition_drafts"],
                key=lambda row: row.get("draft_version", 0),
                reverse=True,
            )
            return _FakeMappingResult(rows)
        if table_name == "source_lineage_maps":
            rows = sorted(self.rows["source_lineage_maps"], key=lambda row: row.get("output_span_id", ""))
            return _FakeMappingResult(rows)
        if table_name == "petitioner_packets":
            return _FakeMappingResult(list(reversed(self.rows["petitioner_packets"])))
        if table_name == "petitioner_verification_records":
            return _FakeMappingResult(list(reversed(self.rows["petitioner_verification_records"])))
        if table_name == "petition_draft_translations":
            return _FakeMappingResult(list(reversed(self.rows["petition_draft_translations"])))
        if table_name == "petition_checklist_questions":
            return _FakeMappingResult(self.rows["petition_checklist_questions"])
        if table_name == "petition_checklist_evaluations":
            return _FakeMappingResult(list(reversed(self.rows["petition_checklist_evaluations"])))
        if table_name == "rewrite_audit_events":
            rows = list(reversed(self.rows["rewrite_audit_events"]))
            return _FakeMappingResult(rows)
        return _FakeMappingResult()


class _RewriteFakeEngine:
    def __init__(self, conn: _RewriteFakeConnection):
        self.conn = conn

    def connect(self):
        return _AsyncCM(self.conn)

    def begin(self):
        return _AsyncCM(self.conn)


class RewriteRequestEndpointTests(_BaseAppTestCase):
    def setUp(self) -> None:
        super().setUp()
        from app import _rate_limit_log, app

        self.parse_record_id = str(uuid.uuid4())
        self.conn = _RewriteFakeConnection(self.parse_record_id)
        self.engine = _RewriteFakeEngine(self.conn)

        async def fake_get_engine():
            return self.engine

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
            json={"username": "operator", "password": "correct horse battery staple"},
        )
        self.assertEqual(login_response.status_code, 200)

    def tearDown(self) -> None:
        self._engine_patch.stop()
        self._db_health_patch.stop()
        self._init_db_patch.stop()
        super().tearDown()

    def _create_packet(self) -> dict:
        response = self.client.post(
            "/api/rewrite-requests",
            json={"parse_record_id": self.parse_record_id},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_and_get_rewrite_request(self) -> None:
        created = self._create_packet()

        self.assertEqual(created["request"]["parse_record_id"], self.parse_record_id)
        self.assertEqual(created["request"]["source_language"], "te")
        self.assertEqual(created["request"]["generation_status"], "needs_review")
        self.assertTrue(created["placeholders"])
        self.assertIn("Petitioner Verification", created["draft"]["body_markdown"])
        self.assertTrue(created["validation"]["source_lineage_complete"])

        response = self.client.get(f"/api/rewrite-requests/{created['request']['id']}")
        self.assertEqual(response.status_code, 200)
        fetched = response.json()
        self.assertEqual(fetched["request"]["id"], created["request"]["id"])
        self.assertGreaterEqual(len(fetched["audit_events"]), 2)

    def test_admin_can_create_and_update_checklist_question(self) -> None:
        response = self.client.post(
            "/api/rewrite-checklist/questions",
            json={
                "question_text": "Exact date and time of occurrence, or best-known time window?",
                "category": "incident",
                "purpose": "petition",
                "offence_type": "",
                "severity": "mandatory",
                "guidance": "Needed for chronology and CCTV checks.",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        self.assertEqual(created["purpose"], "petition")
        self.assertEqual(created["category"], "incident")

        response = self.client.patch(
            f"/api/rewrite-checklist/questions/{created['id']}",
            json={"guidance": "Updated guidance.", "is_active": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()
        self.assertFalse(updated["is_active"])
        self.assertEqual(updated["guidance"], "Updated guidance.")

        response = self.client.get("/api/rewrite-checklist/questions?include_inactive=true")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_create_packet_persists_checklist_evaluations(self) -> None:
        question_id = str(uuid.uuid4())
        self.conn.rows["petition_checklist_questions"].append(
            {
                "id": question_id,
                "checklist_version": 1,
                "category": "incident",
                "purpose": "petition",
                "offence_type": None,
                "question_text": "Exact date and time of occurrence, or best-known time window?",
                "expected_field_key": None,
                "severity": "mandatory",
                "source_section": "Incident essentials",
                "guidance": "Needed for chronology.",
                "display_order": 1,
                "is_active": True,
            }
        )

        created = self._create_packet()

        self.assertTrue(created["checklist_evaluations"])
        self.assertEqual(created["checklist_evaluations"][0]["question_id"], question_id)
        self.assertIn("Checklist Validation And Foolproofing Guidance", created["draft"]["body_markdown"])

    def test_edit_creates_new_version_and_blocks_approval_until_lineage_review(self) -> None:
        created = self._create_packet()
        draft = created["draft"]
        edited_body = draft["body_markdown"] + "\nOfficer-added unsupported fact for test.\n"

        response = self.client.patch(
            f"/api/rewrite-requests/{created['request']['id']}/drafts/{draft['id']}",
            json={"body_markdown": edited_body, "update_note": "test edit"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()
        self.assertEqual(updated["draft"]["draft_version"], 2)
        self.assertEqual(updated["request"]["generation_status"], "source_check_required")
        self.assertFalse(updated["draft"]["source_lineage_complete"])

        response = self.client.post(
            f"/api/rewrite-requests/{created['request']['id']}/approve",
            json={"approval_note": "Reviewed source lineage", "lineage_review_confirmed": True, "allow_english_only_issue": True},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["error"]["code"], "SOURCE_LINEAGE_INCOMPLETE")

    def test_translation_semantic_validation_allows_multilingual_approval(self) -> None:
        created = self._create_packet()
        request_id = created["request"]["id"]

        response = self.client.post(
            f"/api/rewrite-requests/{request_id}/translations",
            json={"target_language": "te", "target_language_name": "Telugu"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        translated = response.json()
        self.assertEqual(translated["latest_translation"]["semantic_validation_status"], "english_only_issue")
        self.assertTrue(translated["latest_translation"]["placeholder_integrity_passed"])

        translation_id = translated["latest_translation"]["id"]
        response = self.client.post(
            f"/api/rewrite-requests/{request_id}/translations/{translation_id}/semantic-validation",
            json={"semantic_validation_status": "passed", "reviewer_note": "Bilingual officer reviewed."},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["request"]["semantic_validation_status"], "passed")

        response = self.client.post(
            f"/api/rewrite-requests/{request_id}/approve",
            json={"approval_note": "Reviewed source lineage", "lineage_review_confirmed": True},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_approve_and_export_rewrite_request(self) -> None:
        created = self._create_packet()

        response = self.client.post(
            f"/api/rewrite-requests/{created['request']['id']}/approve",
            json={"approval_note": "Reviewed source lineage", "lineage_review_confirmed": True, "allow_english_only_issue": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        approved = response.json()
        self.assertEqual(approved["request"]["generation_status"], "approved")

        response = self.client.post(f"/api/rewrite-requests/{created['request']['id']}/export")
        self.assertEqual(response.status_code, 200, response.text)
        exported = response.json()
        self.assertEqual(exported["content_type"], "text/markdown; charset=utf-8")
        self.assertIn("Disclosure", exported["content"])
        self.assertIn("Signature or thumb impression", exported["content"])

    def test_petitioner_return_verification_and_acceptance(self) -> None:
        created = self._create_packet()
        request_id = created["request"]["id"]
        approve_response = self.client.post(
            f"/api/rewrite-requests/{request_id}/approve",
            json={"approval_note": "Reviewed source lineage", "lineage_review_confirmed": True, "allow_english_only_issue": True},
        )
        self.assertEqual(approve_response.status_code, 200, approve_response.text)

        values = [
            {
                "placeholder_id": item["id"],
                "petitioner_value": "",
                "value_status": "accepted_unknown",
            }
            for item in created["placeholders"]
        ]
        response = self.client.post(
            f"/api/rewrite-requests/{request_id}/return-values",
            json={"values": values, "update_note": "petitioner reviewed"},
        )
        self.assertEqual(response.status_code, 200, response.text)

        response = self.client.post(
            f"/api/rewrite-requests/{request_id}/petitioner-verification",
            json={
                "consent_status": "verified",
                "petitioner_name": "Ravi Kumar",
                "verification_language": "te",
                "signature_mode": "signature",
                "witness_note": "Verified in person",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["latest_verification"]["consent_status"], "verified")

        response = self.client.post(
            f"/api/rewrite-requests/{request_id}/accept",
            json={"acceptance_note": "Accepted after petitioner verification"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        accepted = response.json()
        self.assertEqual(accepted["request"]["generation_status"], "accepted")
        self.assertEqual(accepted["draft"]["generation_method"], "petitioner_return_merge")
        self.assertIn("unknown", accepted["draft"]["body_markdown"])


class OpenAIPetitionTranslationTests(_BaseAppTestCase):
    def test_openai_petition_translation_preserves_placeholder_tokens(self) -> None:
        from app import _translate_petition_packet_via_openai

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return b'{"output_text":"\\u0c24\\u0c46\\u0c32\\u0c41\\u0c17\\u0c41 __PETITION_PLACEHOLDER_000__"}'

        config = {
            "enabled": True,
            "openai_enabled": True,
            "openai_api_key": "test-key",
            "openai_base_url": "https://api.openai.test/v1",
            "openai_model": "gpt-5.2",
            "openai_reasoning_effort": "none",
        }
        with patch("app.get_translation_config", return_value=config), \
             patch("app.urllib.request.urlopen", return_value=FakeResponse()) as mock_urlopen:
            translated = _translate_petition_packet_via_openai(
                "English __PETITION_PLACEHOLDER_000__",
                "te",
                "Telugu",
            )

        self.assertEqual(translated, "తెలుగు __PETITION_PLACEHOLDER_000__")
        request_obj = mock_urlopen.call_args.args[0]
        self.assertEqual(request_obj.full_url, "https://api.openai.test/v1/responses")
        self.assertIn(b"__PETITION_PLACEHOLDER_000__", request_obj.data)


class KISBackgroundWorkerTests(_BaseAppTestCase):
    def test_worker_processes_claimed_record(self) -> None:
        from app import _process_next_kis_queue_item

        claimed = {
            "id": "record-123",
            "file_name": "complaint.pdf",
            "document_format": "POLICE_COMPLAINT",
            "parsed_output": {"summary": "Theft complaint"},
            "kis_attempt_count": 1,
        }
        with patch("app.claim_next_kis_index_record", new=AsyncMock(return_value=claimed)) as mock_claim, \
             patch("app._run_kis_indexing", new=AsyncMock(return_value={"enabled": True, "indexed": True, "source_id": "src_1"})) as mock_run, \
             patch("app._record_kis_index_status", new=AsyncMock(return_value=None)) as mock_status:
            processed = asyncio.run(_process_next_kis_queue_item("worker-1"))

        self.assertTrue(processed)
        mock_claim.assert_awaited_once()
        mock_run.assert_awaited_once()
        mock_status.assert_awaited_once()
        self.assertEqual(mock_status.await_args.kwargs["status"], "indexed")

    def test_worker_schedules_retry_on_error(self) -> None:
        from app import _process_next_kis_queue_item

        claimed = {
            "id": "record-123",
            "file_name": "complaint.pdf",
            "document_format": "POLICE_COMPLAINT",
            "parsed_output": {"summary": "Theft complaint"},
            "kis_attempt_count": 2,
        }
        with patch("app.claim_next_kis_index_record", new=AsyncMock(return_value=claimed)), \
             patch("app._run_kis_indexing", new=AsyncMock(side_effect=RuntimeError("kis down"))), \
             patch("app.mark_kis_index_failure", new=AsyncMock(return_value={"retryable": True})) as mock_failure:
            processed = asyncio.run(_process_next_kis_queue_item("worker-1"))

        self.assertTrue(processed)
        mock_failure.assert_awaited_once()
        self.assertEqual(mock_failure.await_args.kwargs["attempt_count"], 2)


class ChecklistAnalysisPayloadTests(unittest.TestCase):
    def test_checklist_analysis_counts_actionable_items(self) -> None:
        from app import _build_checklist_analysis_payload

        parsed_output = {
            "text": {"refined_english_translation": "My mobile phone was stolen near the bus stand."},
            "fir_draft": {"occurrence": {"nature_of_offence": "theft"}},
        }
        analysis = _build_checklist_analysis_payload(
            parsed_output,
            [
                {
                    "id": "q1",
                    "checklist_version": 3,
                    "category": "identity",
                    "purpose": "petition",
                    "question_text": "Is the accused identified?",
                    "severity": "mandatory",
                    "evaluation_status": "missing",
                    "missing_detail": "Accused name is not stated.",
                    "follow_up_action": "Add the accused name or state that it is unknown.",
                    "display_order": 1,
                },
                {
                    "id": "q2",
                    "checklist_version": 3,
                    "category": "incident",
                    "purpose": "petition",
                    "question_text": "Is the place stated?",
                    "severity": "recommended",
                    "evaluation_status": "present",
                    "evidence_excerpt": "near the bus stand",
                    "display_order": 2,
                },
                {
                    "id": "q3",
                    "checklist_version": 2,
                    "category": "medical",
                    "purpose": "petition",
                    "question_text": "Is medical examination required?",
                    "severity": "optional",
                    "evaluation_status": "not_applicable",
                    "display_order": 3,
                },
            ],
        )

        self.assertEqual(analysis["status"], "ready")
        self.assertEqual(analysis["offence_type"], "theft")
        self.assertEqual(analysis["checklist_version"], 3)
        self.assertEqual(analysis["counts"]["missing"], 1)
        self.assertEqual(analysis["counts"]["present"], 1)
        self.assertEqual(analysis["counts"]["not_applicable"], 1)
        self.assertEqual(analysis["applicable_questions"], 2)
        self.assertEqual(analysis["readiness_score"], 0.5)
        self.assertEqual(analysis["mandatory_action_count"], 1)
        self.assertEqual(analysis["top_findings"][0]["missing_detail"], "Accused name is not stated.")


class ParseDocumentEdgeCaseTests(unittest.TestCase):
    """Edge-case tests for the parse_document function."""

    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in (
                "OPENAI_EXTRACTION_ENABLED",
                "TRANSLATION_REFINEMENT_ENABLED",
                "OPENAI_EXTRACTION_MIN_CONFIDENCE",
                "OPENAI_EXTRACTION_REQUIRE_EVIDENCE",
            )
        }
        os.environ["TRANSLATION_REFINEMENT_ENABLED"] = "false"
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


class StreamEndpointTests(_BaseAppTestCase):
    """Tests for the SSE streaming parse endpoint."""

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

    def _login(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "correct horse battery staple"},
        )
        self.assertEqual(response.status_code, 200)

    def test_stream_requires_auth(self) -> None:
        response = self.client.post(
            "/api/parse/stream",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 401)

    @patch("app.save_parse_record", new_callable=AsyncMock)
    @patch("app.process_document_bytes")
    def test_stream_endpoint_returns_sse_events(
        self,
        mock_process: MagicMock,
        mock_save: AsyncMock,
    ) -> None:
        self._login()
        mock_doc = MagicMock()
        mock_doc.document.text = "Subject: Test complaint about theft on 10 March 2026"
        mock_process.return_value = mock_doc
        mock_save.return_value = str(uuid.uuid4())

        response = self.client.post(
            "/api/parse/stream",
            files={"file": ("complaint.pdf", _minimal_pdf_bytes(), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))

        import json
        events = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        # Must have at least one progress event and a done event
        self.assertTrue(len(events) >= 2, f"Expected >=2 events, got {len(events)}")
        done_events = [e for e in events if e.get("step") == "done"]
        self.assertEqual(len(done_events), 1)
        self.assertIn("result", done_events[0])
        self.assertIn("parsed_output", done_events[0]["result"])


if __name__ == "__main__":
    unittest.main()
