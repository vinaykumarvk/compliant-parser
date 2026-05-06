from __future__ import annotations

import unittest

from privacy import PIIProtectionContext, detect_high_risk_pii, detect_pii


class TestPIIProtection(unittest.TestCase):
    def test_masks_and_restores_common_pii(self) -> None:
        ctx = PIIProtectionContext()
        source = (
            "I, Rajesh Kumar resident of 12 MG Road, phone 9876543210, "
            "email rajesh@example.com, Aadhaar 1234 5678 9012, vehicle TS09AB1234."
        )

        protected = ctx.protect_text(source)

        self.assertNotIn("Rajesh Kumar", protected)
        self.assertNotIn("9876543210", protected)
        self.assertNotIn("rajesh@example.com", protected)
        self.assertNotIn("1234 5678 9012", protected)
        self.assertIn("[[PII_PERSON_NAME_0001]]", protected)
        self.assertIn("[[PII_PHONE_0001]]", protected)
        self.assertIn("[[PII_EMAIL_0001]]", protected)
        self.assertEqual(ctx.restore_text(protected), source)

    def test_reuses_same_token_for_repeated_value(self) -> None:
        ctx = PIIProtectionContext()
        protected = ctx.protect_text("Rajesh Kumar saw Rajesh Kumar near the shop.")

        self.assertEqual(protected.count("[[PII_PERSON_NAME_0001]]"), 2)
        self.assertEqual(ctx.metadata()["redaction_count"], 1)

    def test_high_risk_detector_finds_structured_identifiers(self) -> None:
        findings = detect_high_risk_pii("Contact 9876543210 and PAN ABCDE1234F")
        self.assertEqual({item.pii_type for item in findings}, {"phone", "pan"})

    def test_detects_indic_names(self) -> None:
        findings = detect_pii("मैं राजेश कुमार निवासी नया बाजार से प्रार्थना करता हूँ")
        self.assertIn("person_name", {item.pii_type for item in findings})


if __name__ == "__main__":
    unittest.main()
