"""Tests for Phase 6: Document Generation Engine (async ORM version)."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import AsyncTestCase

from document_generator import (
    export_docx,
    export_pdf,
    extract_placeholders,
    generate_document,
    get_template,
    list_templates,
    seed_templates,
    update_generated_document,
)
from models import DocumentTemplate


class TestSeedTemplates(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)

    async def test_templates_seeded(self):
        templates = await list_templates(db=self.db)
        self.assertGreaterEqual(len(templates), 10)

    async def test_categories_present(self):
        templates = await list_templates(db=self.db)
        categories = {t["category"] for t in templates}
        self.assertIn("FSL_Communication", categories)
        self.assertIn("Evidence_Certificate", categories)
        self.assertIn("Legal_Notice", categories)
        self.assertIn("Legal_Draft", categories)


class TestListTemplates(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)

    async def test_list_all(self):
        result = await list_templates(db=self.db)
        self.assertGreaterEqual(len(result), 10)

    async def test_filter_by_category(self):
        result = await list_templates("FSL_Communication", db=self.db)
        self.assertGreater(len(result), 0)
        for t in result:
            self.assertEqual(t["category"], "FSL_Communication")

    async def test_filter_empty_category(self):
        result = await list_templates("Nonexistent", db=self.db)
        self.assertEqual(len(result), 0)


class TestGetTemplate(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)

    async def test_get_existing(self):
        templates = await list_templates(db=self.db)
        first_id = templates[0]["id"]
        tpl = await get_template(first_id, db=self.db)
        self.assertIsNotNone(tpl)
        self.assertIn("template_name", tpl)
        self.assertIn("template_body", tpl)

    async def test_get_nonexistent(self):
        tpl = await get_template("nope", db=self.db)
        self.assertIsNone(tpl)


class TestExtractPlaceholders(AsyncTestCase):
    """extract_placeholders is a pure function -- no db needed."""

    async def test_extract(self):
        body = "Dear {{io_name}}, Case {{case_number}} at {{police_station}}."
        result = extract_placeholders(body)
        self.assertEqual(set(result), {"io_name", "case_number", "police_station"})

    async def test_no_placeholders(self):
        result = extract_placeholders("Plain text with no tokens.")
        self.assertEqual(result, [])

    async def test_duplicate_placeholders(self):
        body = "{{name}} and {{name}} again"
        result = extract_placeholders(body)
        self.assertEqual(len(result), 1)


class TestGenerateDocument(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)
        templates = await list_templates(db=self.db)
        self.template_id = templates[0]["id"]

    async def test_generate_basic(self):
        doc = await generate_document(
            self.template_id,
            {"case_number": "0001/2026", "police_station": "Banjara Hills PS"},
            "u1",
            db=self.db,
        )
        self.assertIn("id", doc)
        self.assertIn("content", doc)
        self.assertRegex(doc["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("auto_filled_fields", doc)
        self.assertIn("case_number", doc["auto_filled_fields"])

    async def test_missing_fields_detected(self):
        doc = await generate_document(self.template_id, {}, "u1", db=self.db)
        self.assertGreater(len(doc["missing_fields"]), 0)

    async def test_stored_in_db(self):
        doc = await generate_document(self.template_id, {}, "u1", db=self.db)
        from models import GeneratedDocument
        stored = await self.db.get(GeneratedDocument, doc["id"])
        self.assertIsNotNone(stored)


class TestUpdateGeneratedDocument(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)
        templates = await list_templates(db=self.db)
        self.template_id = templates[0]["id"]
        self.doc = await generate_document(self.template_id, {}, "u1", db=self.db)

    async def test_update_content(self):
        previous_hash = self.doc["sha256"]
        updated = await update_generated_document(
            self.doc["id"], "New content here", "u1", db=self.db,
        )
        self.assertEqual(updated["content"], "New content here")
        self.assertRegex(updated["sha256"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(updated["sha256"], previous_hash)
        self.assertTrue(updated["io_edited"])


class TestExportDocx(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)
        templates = await list_templates(db=self.db)
        tid = templates[0]["id"]
        self.doc = await generate_document(
            tid, {"case_number": "0001/2026"}, "u1", db=self.db,
        )

    async def test_export_returns_bytes(self):
        data = await export_docx(self.doc["id"], db=self.db)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 100)

    async def test_docx_magic_bytes(self):
        data = await export_docx(self.doc["id"], db=self.db)
        # DOCX is a ZIP file, starts with PK
        self.assertTrue(data[:2] == b"PK")


class TestExportPdf(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)
        templates = await list_templates(db=self.db)
        tid = templates[0]["id"]
        self.doc = await generate_document(
            tid, {"case_number": "0001/2026"}, "u1", db=self.db,
        )

    async def test_export_returns_bytes(self):
        data = await export_pdf(self.doc["id"], db=self.db)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 100)

    async def test_pdf_magic_bytes(self):
        data = await export_pdf(self.doc["id"], db=self.db)
        self.assertTrue(data[:5] == b"%PDF-")


class TestSignGeneratedDocument(AsyncTestCase):
    """AC-018-2: DSC token detection, AC-018-3: signed status records, AC-018-4: missing DSC error."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_templates(self.db)
        templates = await list_templates(db=self.db)
        tid = templates[0]["id"]
        self.doc = await generate_document(tid, {"case_number": "0001/2026"}, "u1", db=self.db)

    async def test_missing_dsc_token_raises_exact_error(self):
        """AC-018-4: Missing DSC token exact error message."""
        from document_generator import sign_generated_document
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(os.environ, {"DSC_TOKEN_PRESENT": ""}, clear=False):
            with self.assertRaises(RuntimeError) as ctx:
                await sign_generated_document(self.doc["id"], "u1", "1234", db=self.db)
            self.assertIn("Digital Signature Certificate not detected", str(ctx.exception))
            self.assertIn("insert your DSC token", str(ctx.exception))

    async def test_sign_requires_pin(self):
        """AC-018-2: DSC PIN is required."""
        from document_generator import sign_generated_document
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(os.environ, {"DSC_TOKEN_PRESENT": "true"}, clear=False):
            with self.assertRaises(ValueError) as ctx:
                await sign_generated_document(self.doc["id"], "u1", None, db=self.db)
            self.assertIn("PIN is required", str(ctx.exception))

    async def test_sign_records_signer_timestamp_certificate(self):
        """AC-018-3: Signed status records signer, timestamp, and certificate details."""
        from document_generator import sign_generated_document
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(os.environ, {
            "DSC_TOKEN_PRESENT": "true",
            "DSC_CERT_SUBJECT": "CN=Test Officer",
            "DSC_CERT_SERIAL": "SN-12345",
            "DSC_PROVIDER": "Test DSC Bridge",
        }, clear=False):
            result = await sign_generated_document(self.doc["id"], "u1", "9999", db=self.db)

        self.assertEqual(result["digital_signature_status"], "Signed")
        self.assertEqual(result["signed_by"], "u1")
        self.assertIsNotNone(result.get("signed_at"))
        cert = result.get("signature_certificate_details", {})
        self.assertEqual(cert["certificate_subject"], "CN=Test Officer")
        self.assertEqual(cert["certificate_serial"], "SN-12345")
        self.assertEqual(cert["provider"], "Test DSC Bridge")
        self.assertIn("document_sha256", cert)

    async def test_signed_doc_is_read_only(self):
        """AC-018-5 (re-verify): Signed documents cannot be edited."""
        from document_generator import sign_generated_document
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(os.environ, {"DSC_TOKEN_PRESENT": "true"}, clear=False):
            await sign_generated_document(self.doc["id"], "u1", "1234", db=self.db)

        with self.assertRaises(ValueError) as ctx:
            await update_generated_document(self.doc["id"], "Modified content", "u1", db=self.db)
        self.assertIn("read-only", str(ctx.exception))


if __name__ == "__main__":
    import unittest
    unittest.main()
