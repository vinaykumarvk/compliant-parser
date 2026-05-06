from __future__ import annotations

import unittest

from governance import validate_kb_entry, validate_kb_promotion


class TestKBGovernance(unittest.TestCase):
    def test_checklist_validation_requires_items_and_change_description(self):
        failed = validate_kb_entry("Checklist", "Evidence checklist", {"items": []})
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["validation_status"], "Failed")

        passed = validate_kb_entry(
            "Checklist",
            "Evidence checklist",
            {"items": [{"label": "Collect CCTV"}], "change_description": "BRD validated update"},
        )
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["validation_status"], "Passed")

    def test_production_requires_staging_and_passed_validation(self):
        with self.assertRaises(ValueError):
            validate_kb_promotion("Draft", "Production", "Passed")
        with self.assertRaises(ValueError):
            validate_kb_promotion("Staging", "Production", "Failed")

        validate_kb_promotion("Draft", "Staging", None)
        validate_kb_promotion("Staging", "Production", "Passed")


if __name__ == "__main__":
    unittest.main()
