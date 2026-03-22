import os
import unittest

from complaint_parsing import parse_document


class ComplaintParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in (
                "TRANSLATION_ENABLED",
                "TRANSLATION_PROJECT_ID",
                "TRANSLATION_LOCATION",
                "TRANSLATION_TARGET_LANGUAGE",
                "DOC_AI_PROJECT_ID",
            )
        }

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_extracts_complete_english_complaint(self) -> None:
        sample = """
        Subject: Complaint regarding theft of mobile phone
        My name is Ram Kumar.
        I want to report that my mobile phone was stolen on 15 March 2026 at around 8 PM near XYZ Market bus stand.
        The unknown accused took the phone from my pocket in a crowded bus.
        The theft appears to be opportunistic.
        """

        result = parse_document(sample)

        self.assertEqual(result["document_type"], "police_complaint")
        self.assertEqual(result["language"]["detected"], "en")
        self.assertEqual(result["language"]["translation_status"], "not_needed")
        self.assertEqual(result["complaint"]["who"]["status"], "present")
        self.assertEqual(result["complaint"]["what"]["status"], "present")
        self.assertEqual(result["complaint"]["when"]["status"], "present")
        self.assertEqual(result["complaint"]["where"]["status"], "present")
        self.assertEqual(result["complaint"]["why"]["status"], "present")
        self.assertEqual(result["complaint"]["how"]["status"], "present")
        self.assertEqual(result["gaps"]["missing_fields"], [])
        self.assertFalse(result["gaps"]["requires_review"])

    def test_detects_hindi_and_flags_translation_gap_when_disabled(self) -> None:
        os.environ["TRANSLATION_ENABLED"] = "false"
        sample = (
            "मेरी शिकायत यह है कि मेरा मोबाइल 15/03/2026 को शाम 8 बजे बस स्टैंड के पास चोरी हो गया। "
            "अज्ञात आरोपी ने भीड़ वाली बस में मेरी जेब से मोबाइल निकाला।"
        )

        result = parse_document(sample)

        self.assertEqual(result["language"]["detected"], "hi")
        self.assertEqual(result["language"]["translation_status"], "disabled")
        self.assertIn("translation_to_english_unavailable", result["gaps"]["pipeline_flags"])
        self.assertTrue(result["gaps"]["requires_review"])


if __name__ == "__main__":
    unittest.main()
