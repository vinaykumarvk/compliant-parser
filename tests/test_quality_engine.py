"""Tests for Phase 5: Document Quality Engine."""

from __future__ import annotations

import unittest

from quality_engine import (
    DEFAULT_CHECKLISTS,
    INVESTIGATION_QUESTIONS,
    classify_trial_risk,
    evaluate_checklist_item,
    generate_suggestion,
    run_quality_check,
    run_llm_quality_check,
    seed_checklists,
    _get_investigation_questions,
    _normalize_llm_quality_result,
    _derive_trial_risks_from_categories,
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


# ======================================================================
# Semantic / LLM quality engine tests
# ======================================================================


class TestInvestigationQuestions(unittest.TestCase):
    """Validate INVESTIGATION_QUESTIONS structure and merge logic."""

    def test_generic_has_required_categories(self):
        generic = INVESTIGATION_QUESTIONS["Generic"]
        ids = {cat["id"] for cat in generic}
        for expected in ("identity", "location", "timeline", "accused", "narrative"):
            self.assertIn(expected, ids)

    def test_each_category_has_required_keys(self):
        for doc_type, cats in INVESTIGATION_QUESTIONS.items():
            for cat in cats:
                self.assertIn("id", cat, f"Missing 'id' in {doc_type}")
                self.assertIn("label", cat, f"Missing 'label' in {doc_type}")
                self.assertIn("trial_impact", cat, f"Missing 'trial_impact' in {doc_type}")
                self.assertIn("questions", cat, f"Missing 'questions' in {doc_type}")
                self.assertIsInstance(cat["questions"], list)
                for q in cat["questions"]:
                    self.assertIn("q", q)
                    self.assertIn("severity", q)

    def test_merge_fir_with_generic(self):
        merged = _get_investigation_questions("FIR")
        ids = [cat["id"] for cat in merged]
        # FIR-specific should be first
        self.assertEqual(ids[0], "registration")
        # Generic categories should also be present
        self.assertIn("identity", ids)
        self.assertIn("location", ids)
        # No duplicates
        self.assertEqual(len(ids), len(set(ids)))

    def test_merge_unknown_type_returns_generic(self):
        merged = _get_investigation_questions("SomeUnknownType")
        generic = INVESTIGATION_QUESTIONS["Generic"]
        self.assertEqual(len(merged), len(generic))

    def test_charge_sheet_merge(self):
        merged = _get_investigation_questions("Charge_Sheet")
        ids = [cat["id"] for cat in merged]
        self.assertIn("cs_accused", ids)
        self.assertIn("cs_evidence", ids)
        self.assertIn("identity", ids)  # from Generic


class TestNormalizeLLMResult(unittest.TestCase):
    """Test _normalize_llm_quality_result with mock LLM output."""

    def _make_mock_llm_data(self):
        return {
            "categories": [
                {
                    "id": "identity",
                    "label": "Complainant / Victim Identity",
                    "status": "complete",
                    "summary": "Full name and address recorded.",
                    "findings": [
                        {
                            "question": "Is the complainant's full name recorded (including father's/spouse's name)?",
                            "answer": "Yes, Rajesh Kumar, son of Mohan Kumar.",
                            "excerpt": "Rajesh Kumar, son of Mohan Kumar",
                            "status": "complete",
                        },
                        {
                            "question": "Is the complainant's complete residential address provided?",
                            "answer": "Yes, Plot 45, Road No. 12.",
                            "excerpt": "Plot 45, Road No. 12, Banjara Hills, Hyderabad",
                            "status": "complete",
                        },
                    ],
                    "gaps": [],
                    "io_actions": [],
                    "trial_impact": "Identity is well-established.",
                },
                {
                    "id": "accused",
                    "label": "Accused / Suspect Details",
                    "status": "partial",
                    "summary": "Physical description but no name.",
                    "findings": [
                        {
                            "question": "Is the accused named, or is a physical description provided?",
                            "answer": "Physical description only.",
                            "excerpt": "two unknown persons on a black motorcycle",
                            "status": "partial",
                        },
                    ],
                    "gaps": ["Accused name not available"],
                    "io_actions": ["Collect CCTV to identify accused"],
                    "trial_impact": "Unidentified accused weakens prosecution.",
                },
                {
                    "id": "injuries",
                    "label": "Injuries / Medical",
                    "status": "not_found",
                    "summary": "No injury information found.",
                    "findings": [
                        {
                            "question": "Are injuries described or a medical report referenced?",
                            "answer": "Not mentioned.",
                            "excerpt": None,
                            "status": "not_found",
                        },
                    ],
                    "gaps": ["No injury report"],
                    "io_actions": ["Obtain medical report if applicable"],
                    "trial_impact": "Missing if assault charges apply.",
                },
            ],
            "overall_readiness": "Needs_Work",
            "investigation_readiness_score": 0.65,
            "priority_actions": ["Identify accused", "Obtain medical report"],
            "strengths": ["Complainant identity well-documented"],
        }

    def test_normalize_produces_required_fields(self):
        data = self._make_mock_llm_data()
        questions = _get_investigation_questions("Generic")
        result = _normalize_llm_quality_result(data, "Generic", questions, 1200, {"provider": "test"})

        self.assertIn("analysis_id", result)
        self.assertIn("categories", result)
        self.assertIn("findings", result)
        self.assertIn("completeness_score", result)
        self.assertIn("overall_readiness", result)
        self.assertIn("trial_risk_indicators", result)
        self.assertEqual(result["analysis_mode"], "semantic")

    def test_normalize_counts(self):
        data = self._make_mock_llm_data()
        questions = _get_investigation_questions("Generic")
        result = _normalize_llm_quality_result(data, "Generic", questions, 100, {})

        self.assertEqual(result["present_count"], 2)  # 2 complete
        self.assertEqual(result["weak_count"], 1)      # 1 partial
        self.assertEqual(result["missing_count"], 1)   # 1 not_found
        self.assertEqual(result["total_items"], 4)

    def test_normalize_flat_findings_backward_compat(self):
        data = self._make_mock_llm_data()
        questions = _get_investigation_questions("Generic")
        result = _normalize_llm_quality_result(data, "Generic", questions, 100, {})

        for f in result["findings"]:
            self.assertIn("item", f)
            self.assertIn("severity", f)
            self.assertIn("status", f)
            self.assertIn(f["status"], ("present", "weak", "missing"))
            self.assertIn("citation", f)


class TestDeriveTrialRisks(unittest.TestCase):
    """Test _derive_trial_risks_from_categories."""

    def test_complete_categories_produce_no_risks(self):
        cats = [{"id": "x", "label": "X", "status": "complete", "gaps": [], "trial_impact": ""}]
        risks = _derive_trial_risks_from_categories(cats)
        self.assertEqual(len(risks), 0)

    def test_partial_category_with_gaps(self):
        cats = [
            {
                "id": "accused",
                "label": "Accused Details",
                "status": "partial",
                "gaps": ["Name not recorded"],
                "trial_impact": "Weakens prosecution",
            }
        ]
        risks = _derive_trial_risks_from_categories(cats)
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0]["severity"], "Medium")
        self.assertIn("Name not recorded", risks[0]["risk"])

    def test_not_found_category_is_high_severity(self):
        cats = [
            {
                "id": "injuries",
                "label": "Injuries",
                "status": "not_found",
                "gaps": [],
                "trial_impact": "Assault charge unsupported",
            }
        ]
        risks = _derive_trial_risks_from_categories(cats)
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0]["severity"], "High")


class TestLLMQualityFallback(unittest.TestCase):
    """Verify run_llm_quality_check falls back to keyword engine when LLM is unavailable."""

    def test_fallback_on_empty_text(self):
        result = run_llm_quality_check("", "Generic")
        # Should fall back to keyword engine — no categories
        self.assertNotIn("categories", result)
        self.assertIn("findings", result)

    def test_fallback_produces_valid_structure(self):
        # Without LLM configured, should fall back to keyword
        import os
        old = os.environ.get("IQW_ALLOW_LLM_STUBS")
        os.environ["IQW_ALLOW_LLM_STUBS"] = "true"
        try:
            result = run_llm_quality_check(SAMPLE_FIR_TEXT, "FIR")
            self.assertIn("findings", result)
            self.assertIn("completeness_score", result)
            self.assertGreater(result["total_items"], 0)
        finally:
            if old is None:
                os.environ.pop("IQW_ALLOW_LLM_STUBS", None)
            else:
                os.environ["IQW_ALLOW_LLM_STUBS"] = old


class TestCaseContextParam(unittest.TestCase):
    """Test that case_context parameter works for backward compatibility."""

    def test_run_quality_check_with_case_context_none(self):
        """run_quality_check still works when case_context=None (default)."""
        result = run_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertIn("findings", result)
        self.assertIn("completeness_score", result)

    def test_run_quality_check_with_case_context_dict(self):
        """run_quality_check accepts case_context dict without error."""
        ctx = {"brief_facts": "Theft at Banjara Hills", "offence_type": "Theft"}
        result = run_quality_check(SAMPLE_FIR_TEXT, "FIR", case_context=ctx)
        self.assertIn("findings", result)

    def test_run_llm_quality_check_with_case_context_none(self):
        """run_llm_quality_check falls back to keyword when no LLM, case_context=None."""
        result = run_llm_quality_check(SAMPLE_FIR_TEXT, "FIR")
        self.assertIn("findings", result)

    def test_run_llm_quality_check_with_case_context_dict(self):
        """run_llm_quality_check falls back to keyword when no LLM, case_context=dict."""
        ctx = {
            "brief_facts": "Mobile phone theft near SBI Bank",
            "offence_type": "Theft",
            "petition_analysis": {"risk_flags": ["night_incident"]},
        }
        result = run_llm_quality_check(SAMPLE_FIR_TEXT, "FIR", case_context=ctx)
        self.assertIn("findings", result)


class TestOffenceSpecificQuestions(unittest.TestCase):
    """Test offence-specific investigation questions merge."""

    def test_theft_questions_merged(self):
        from quality_engine import OFFENCE_SPECIFIC_QUESTIONS
        questions = _get_investigation_questions("Generic", offence_type="Theft")
        ids = {q["id"] for q in questions}
        self.assertIn("theft_specifics", ids)

    def test_robbery_questions_merged(self):
        questions = _get_investigation_questions("Generic", offence_type="Robbery")
        ids = {q["id"] for q in questions}
        self.assertIn("robbery_specifics", ids)

    def test_unknown_offence_no_extra_questions(self):
        base = _get_investigation_questions("Generic")
        with_unknown = _get_investigation_questions("Generic", offence_type="UnknownOffence")
        self.assertEqual(len(base), len(with_unknown))

    def test_no_offence_type_same_as_base(self):
        base = _get_investigation_questions("Generic")
        without = _get_investigation_questions("Generic", offence_type=None)
        self.assertEqual(len(base), len(without))


if __name__ == "__main__":
    unittest.main()
