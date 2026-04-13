"""Tests for Phase 5: Document Quality Engine."""

from __future__ import annotations

import unittest

from quality_engine import (
    DEFAULT_CHECKLISTS,
    classify_trial_risk,
    evaluate_checklist_item,
    generate_suggestion,
    run_quality_check,
    seed_checklists,
)


SAMPLE_FIR_TEXT = """
FIR No. 0123/2026 registered at Banjara Hills Police Station.
Complainant: Rajesh Kumar, son of Mohan Kumar, residing at Plot 45, Road No. 12, Banjara Hills, Hyderabad.
On 15th March 2026 at approximately 10:30 PM, the complainant was returning home from work.
Near SBI Bank, Road No. 12 junction, Banjara Hills, two unknown persons on a black motorcycle snatched
the complainant's mobile phone (Samsung Galaxy S24, IMEI: 123456789012345) worth approximately Rs. 80,000.
The accused were wearing helmets. One was of medium build, approximately 5'8" tall.
Witness: Srinivas Rao (auto driver), phone: 9876543210, was present at the scene.
Evidence: CCTV footage from nearby SBI ATM, broken phone case found at scene.
Investigating Officer: SI Venkat Reddy, Banjara Hills PS.
"""


class TestDefaultChecklists(unittest.TestCase):
    def test_generic_checklist_exists(self):
        self.assertIn("Generic", DEFAULT_CHECKLISTS)
        self.assertGreaterEqual(len(DEFAULT_CHECKLISTS["Generic"]), 10)

    def test_fir_checklist_exists(self):
        self.assertIn("FIR", DEFAULT_CHECKLISTS)

    def test_checklist_items_have_required_fields(self):
        for doc_type, items in DEFAULT_CHECKLISTS.items():
            for item in items:
                self.assertIn("item", item, f"Missing 'item' in {doc_type}")
                self.assertIn("severity", item, f"Missing 'severity' in {doc_type}")
                self.assertIn("category", item, f"Missing 'category' in {doc_type}")


class TestEvaluateChecklistItem(unittest.TestCase):
    def test_present_or_weak_item(self):
        result = evaluate_checklist_item(
            "Complainant full name and address", SAMPLE_FIR_TEXT
        )
        self.assertIn(result["status"], ("present", "weak"))
        self.assertIsNotNone(result["excerpt"])

    def test_missing_item(self):
        result = evaluate_checklist_item(
            "DNA forensic laboratory report", SAMPLE_FIR_TEXT
        )
        self.assertEqual(result["status"], "missing")

    def test_excerpt_has_offsets(self):
        result = evaluate_checklist_item(
            "Date and time of incident", SAMPLE_FIR_TEXT
        )
        if result["status"] in ("present", "weak"):
            self.assertIsNotNone(result["char_start"])
            self.assertIsNotNone(result["char_end"])


class TestClassifyTrialRisk(unittest.TestCase):
    def test_high_risk_from_missing_high_severity(self):
        findings = [
            {"status": "missing", "severity": "High", "item": "Accused name"},
        ]
        risks = classify_trial_risk(findings)
        high_risks = [r for r in risks if r["severity"] == "High"]
        self.assertGreater(len(high_risks), 0)

    def test_no_risk_when_all_present(self):
        findings = [
            {"status": "present", "severity": "High", "item": "Accused name"},
        ]
        risks = classify_trial_risk(findings)
        self.assertEqual(len(risks), 0)


class TestGenerateSuggestion(unittest.TestCase):
    def test_missing_suggestion(self):
        suggestion = generate_suggestion("Witness names and contact info", "missing")
        self.assertIsInstance(suggestion, str)
        self.assertGreater(len(suggestion), 0)

    def test_weak_suggestion(self):
        suggestion = generate_suggestion("Date and time of incident", "weak")
        self.assertIsInstance(suggestion, str)


class TestRunQualityCheck(unittest.TestCase):
    def test_generic_check_returns_structure(self):
        result = run_quality_check(SAMPLE_FIR_TEXT, "Generic")
        self.assertIn("analysis_id", result)
        self.assertIn("findings", result)
        self.assertIn("trial_risk_indicators", result)
        self.assertIn("completeness_score", result)
        self.assertIn("confidence_score", result)
        self.assertIsInstance(result["completeness_score"], float)

    def test_fir_check(self):
        result = run_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertGreater(result["total_items"], 0)
        self.assertGreater(result["present_count"], 0)

    def test_empty_document(self):
        result = run_quality_check("", "Generic")
        self.assertEqual(result["present_count"], 0)
        self.assertEqual(result["completeness_score"], 0.0)

    def test_completeness_score_range(self):
        result = run_quality_check(SAMPLE_FIR_TEXT, "Generic")
        self.assertGreaterEqual(result["completeness_score"], 0.0)
        self.assertLessEqual(result["completeness_score"], 1.0)

    def test_confidence_score_valid(self):
        result = run_quality_check(SAMPLE_FIR_TEXT, "Generic")
        self.assertIn(result["confidence_score"], ("High", "Medium", "Low"))

    def test_findings_have_excerpts(self):
        result = run_quality_check(SAMPLE_FIR_TEXT, "Generic")
        present_findings = [f for f in result["findings"] if f.get("status") == "present"]
        for f in present_findings:
            self.assertIsNotNone(f.get("excerpt"))


class TestSeedChecklists(unittest.TestCase):
    def test_seed_is_idempotent(self):
        seed_checklists()
        seed_checklists()  # should not raise


if __name__ == "__main__":
    unittest.main()
