"""Tests for Phase 6: Document Generation Engine."""

from __future__ import annotations

import unittest

from document_generator import (
    _generated_documents,
    _templates,
    export_docx,
    export_pdf,
    extract_placeholders,
    generate_document,
    get_template,
    list_templates,
    seed_templates,
    update_generated_document,
)


class TestSeedTemplates(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        seed_templates()

    def test_templates_seeded(self):
        self.assertGreaterEqual(len(_templates), 10)

    def test_categories_present(self):
        categories = {t["category"] for t in _templates.values()}
        self.assertIn("FSL_Communication", categories)
        self.assertIn("Evidence_Certificate", categories)
        self.assertIn("Legal_Notice", categories)
        self.assertIn("Legal_Draft", categories)


class TestListTemplates(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        seed_templates()

    def test_list_all(self):
        result = list_templates()
        self.assertGreaterEqual(len(result), 10)

    def test_filter_by_category(self):
        result = list_templates("FSL_Communication")
        self.assertGreater(len(result), 0)
        for t in result:
            self.assertEqual(t["category"], "FSL_Communication")

    def test_filter_empty_category(self):
        result = list_templates("Nonexistent")
        self.assertEqual(len(result), 0)


class TestGetTemplate(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        seed_templates()

    def test_get_existing(self):
        first_id = next(iter(_templates))
        tpl = get_template(first_id)
        self.assertIsNotNone(tpl)
        self.assertIn("template_name", tpl)
        self.assertIn("template_body", tpl)

    def test_get_nonexistent(self):
        self.assertIsNone(get_template("nope"))


class TestExtractPlaceholders(unittest.TestCase):
    def test_extract(self):
        body = "Dear {{io_name}}, Case {{case_number}} at {{police_station}}."
        result = extract_placeholders(body)
        self.assertEqual(set(result), {"io_name", "case_number", "police_station"})

    def test_no_placeholders(self):
        result = extract_placeholders("Plain text with no tokens.")
        self.assertEqual(result, [])

    def test_duplicate_placeholders(self):
        body = "{{name}} and {{name}} again"
        result = extract_placeholders(body)
        self.assertEqual(len(result), 1)


class TestGenerateDocument(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        _generated_documents.clear()
        seed_templates()
        self.template_id = next(iter(_templates))

    def test_generate_basic(self):
        doc = generate_document(
            self.template_id,
            {"case_number": "0001/2026", "police_station": "Banjara Hills PS"},
            "u1",
        )
        self.assertIn("id", doc)
        self.assertIn("content", doc)
        self.assertIn("auto_filled_fields", doc)
        self.assertIn("case_number", doc["auto_filled_fields"])

    def test_missing_fields_detected(self):
        doc = generate_document(self.template_id, {}, "u1")
        self.assertGreater(len(doc["missing_fields"]), 0)

    def test_stored_in_memory(self):
        doc = generate_document(self.template_id, {}, "u1")
        self.assertIn(doc["id"], _generated_documents)


class TestUpdateGeneratedDocument(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        _generated_documents.clear()
        seed_templates()
        self.template_id = next(iter(_templates))
        self.doc = generate_document(self.template_id, {}, "u1")

    def test_update_content(self):
        updated = update_generated_document(self.doc["id"], "New content here", "u1")
        self.assertEqual(updated["content"], "New content here")
        self.assertTrue(updated["io_edited"])


class TestExportDocx(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        _generated_documents.clear()
        seed_templates()
        tid = next(iter(_templates))
        self.doc = generate_document(tid, {"case_number": "0001/2026"}, "u1")

    def test_export_returns_bytes(self):
        data = export_docx(self.doc["id"])
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 100)

    def test_docx_magic_bytes(self):
        data = export_docx(self.doc["id"])
        # DOCX is a ZIP file, starts with PK
        self.assertTrue(data[:2] == b"PK")


class TestExportPdf(unittest.TestCase):
    def setUp(self):
        _templates.clear()
        _generated_documents.clear()
        seed_templates()
        tid = next(iter(_templates))
        self.doc = generate_document(tid, {"case_number": "0001/2026"}, "u1")

    def test_export_returns_bytes(self):
        data = export_pdf(self.doc["id"])
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 100)

    def test_pdf_magic_bytes(self):
        data = export_pdf(self.doc["id"])
        self.assertTrue(data[:5] == b"%PDF-")


if __name__ == "__main__":
    unittest.main()
