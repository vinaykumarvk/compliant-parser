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


if __name__ == "__main__":
    import unittest
    unittest.main()
