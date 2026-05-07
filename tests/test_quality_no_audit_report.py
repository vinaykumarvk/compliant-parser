"""Test AC-006-6: Quality check returns inline results with no separate audit report."""

from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quality_engine import run_quality_check, seed_checklists


class TestQualityCheckNoAuditReport(unittest.TestCase):
    """AC-006-6: Quality check produces inline findings only, no separate audit report."""

    def setUp(self):
        seed_checklists()

    def test_no_audit_report_field_in_result(self):
        result = run_quality_check("Sample FIR text with complainant details.", "FIR")
        self.assertNotIn("audit_report", result)
        self.assertNotIn("audit_report_path", result)
        self.assertNotIn("report_file", result)

    def test_result_has_inline_findings(self):
        result = run_quality_check("Sample FIR text with complainant details.", "FIR")
        self.assertIn("findings", result)
        self.assertIn("analysis_id", result)
        self.assertIn("completeness_score", result)

    def test_suppressed_uncited_findings_empty(self):
        result = run_quality_check("Sample FIR text.", "FIR")
        self.assertEqual(result["suppressed_uncited_findings"], [])

    def test_checklist_note_is_none_for_semantic(self):
        result = run_quality_check("Sample FIR text.", "FIR")
        if result.get("analysis_mode") == "semantic":
            self.assertIsNone(result.get("checklist_note"))


if __name__ == "__main__":
    unittest.main()
