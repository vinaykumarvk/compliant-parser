"""Tests for Phase 7: OCR Enhancements & PWA."""

from __future__ import annotations

import unittest

from ocr_enhancements import (
    _acknowledgements,
    acknowledge_ocr,
    classify_confidence,
    clean_urdu_noise,
    detect_language_enhanced,
    detect_urdu,
    get_acknowledgement_status,
    requires_acknowledgement,
    tag_segment_confidence,
)


class TestDetectUrdu(unittest.TestCase):
    def test_urdu_text_detected(self):
        urdu = "یہ ایک اردو متن ہے جو جانچ کے لیے استعمال ہوتا ہے"
        self.assertTrue(detect_urdu(urdu))

    def test_english_text_not_urdu(self):
        self.assertFalse(detect_urdu("This is plain English text."))

    def test_empty_string(self):
        self.assertFalse(detect_urdu(""))

    def test_whitespace_only(self):
        self.assertFalse(detect_urdu("   \n\t  "))

    def test_numbers_only(self):
        self.assertFalse(detect_urdu("12345"))

    def test_mixed_urdu_english(self):
        # Mostly Urdu with some English
        mixed = "یہ ایک test ہے جو Urdu اور English کے ساتھ ملا ہوا ہے"
        result = detect_urdu(mixed)
        self.assertIsInstance(result, bool)


class TestDetectLanguageEnhanced(unittest.TestCase):
    def test_english_detected(self):
        result = detect_language_enhanced("This is an English sentence.")
        self.assertEqual(result["language"], "en")
        self.assertEqual(result["script"], "Latin")
        self.assertGreater(result["confidence"], 0.5)

    def test_urdu_detected(self):
        result = detect_language_enhanced("یہ ایک اردو متن ہے جو جانچ کے لیے")
        self.assertEqual(result["language"], "ur")
        self.assertEqual(result["script"], "Arabic")

    def test_empty_returns_unknown(self):
        result = detect_language_enhanced("")
        self.assertEqual(result["language"], "unknown")
        self.assertEqual(result["confidence"], 0.0)

    def test_hindi_detected(self):
        result = detect_language_enhanced("यह एक हिंदी वाक्य है")
        self.assertEqual(result["language"], "hi")
        self.assertEqual(result["script"], "Devanagari")

    def test_telugu_detected(self):
        result = detect_language_enhanced("ఇది తెలుగు వాక్యం")
        self.assertEqual(result["language"], "te")
        self.assertEqual(result["script"], "Telugu")


class TestClassifyConfidence(unittest.TestCase):
    def test_high_confidence(self):
        self.assertEqual(classify_confidence("This is clean, readable text."), "High")

    def test_low_confidence_short(self):
        self.assertEqual(classify_confidence("ab"), "Low")

    def test_low_confidence_empty(self):
        self.assertEqual(classify_confidence(""), "Low")

    def test_low_confidence_repeated_punct(self):
        self.assertEqual(classify_confidence("Hello!!!!???...."), "Low")

    def test_low_confidence_mostly_punct(self):
        self.assertEqual(classify_confidence(".,;:!?."), "Low")


class TestTagSegmentConfidence(unittest.TestCase):
    def test_returns_segments(self):
        text = "First paragraph here.\n\nSecond paragraph here."
        segments = tag_segment_confidence(text)
        self.assertGreater(len(segments), 0)
        for seg in segments:
            self.assertIn("text", seg)
            self.assertIn("confidence", seg)
            self.assertIn("source", seg)
            self.assertIn("char_start", seg)
            self.assertIn("char_end", seg)

    def test_empty_text(self):
        self.assertEqual(tag_segment_confidence(""), [])

    def test_source_field(self):
        segments = tag_segment_confidence("Some text here.", source="manual")
        if segments:
            self.assertEqual(segments[0]["source"], "manual")

    def test_offsets_valid(self):
        text = "Hello world.\n\nGoodbye world."
        segments = tag_segment_confidence(text)
        for seg in segments:
            self.assertGreaterEqual(seg["char_start"], 0)
            self.assertGreater(seg["char_end"], seg["char_start"])
            self.assertEqual(text[seg["char_start"]:seg["char_end"]], seg["text"])


class TestAcknowledgement(unittest.TestCase):
    def setUp(self):
        _acknowledgements.clear()

    def test_acknowledge_specific_segments(self):
        result = acknowledge_ocr("doc1", "user1", segments=[0, 2])
        self.assertEqual(result["document_id"], "doc1")
        self.assertEqual(result["acknowledged_segments"], [0, 2])
        self.assertEqual(len(result["history"]), 1)

    def test_acknowledge_all_segments(self):
        result = acknowledge_ocr("doc2", "user1", segments=None)
        self.assertEqual(result["acknowledged_segments"], "all")

    def test_incremental_acknowledgement(self):
        acknowledge_ocr("doc3", "user1", segments=[0, 1])
        result = acknowledge_ocr("doc3", "user1", segments=[2, 3])
        self.assertEqual(result["acknowledged_segments"], [0, 1, 2, 3])
        self.assertEqual(len(result["history"]), 2)

    def test_get_status_existing(self):
        acknowledge_ocr("doc4", "user1", segments=[0])
        status = get_acknowledgement_status("doc4")
        self.assertIsNotNone(status)
        self.assertEqual(status["document_id"], "doc4")

    def test_get_status_nonexistent(self):
        self.assertIsNone(get_acknowledgement_status("nope"))


class TestRequiresAcknowledgement(unittest.TestCase):
    def test_low_confidence_requires(self):
        segments = [
            {"text": "Good", "confidence": "High"},
            {"text": "Bad", "confidence": "Low"},
        ]
        self.assertTrue(requires_acknowledgement(segments))

    def test_all_high_no_acknowledgement(self):
        segments = [
            {"text": "A", "confidence": "High"},
            {"text": "B", "confidence": "Medium"},
        ]
        self.assertFalse(requires_acknowledgement(segments))

    def test_empty_segments(self):
        self.assertFalse(requires_acknowledgement([]))


class TestCleanUrduNoise(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(clean_urdu_noise(""), "")

    def test_none(self):
        self.assertIsNone(clean_urdu_noise(None))

    def test_strips_diacritics(self):
        # FATHAH (U+064E) should be removed
        text = "بِسمِ"
        cleaned = clean_urdu_noise(text)
        self.assertNotIn("\u0650", cleaned)

    def test_removes_zero_width_joiners(self):
        text = "ا\u200Cب"
        cleaned = clean_urdu_noise(text)
        self.assertNotIn("\u200C", cleaned)

    def test_collapses_spaces_in_ligatures(self):
        # Two Arabic chars separated by multiple spaces
        text = "ا   ب"
        cleaned = clean_urdu_noise(text)
        # Should have fewer spaces
        self.assertTrue(len(cleaned) <= len(text))

    def test_clean_text_unchanged(self):
        text = "This is normal English text"
        self.assertEqual(clean_urdu_noise(text), text)


if __name__ == "__main__":
    unittest.main()
