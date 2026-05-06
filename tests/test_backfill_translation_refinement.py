import unittest

from scripts.backfill_translation_refinement import (
    _should_skip_existing_refinement,
    _source_is_english,
)


class BackfillTranslationRefinementTests(unittest.TestCase):
    def test_source_english_detection_includes_not_needed_translation_status(self) -> None:
        self.assertTrue(_source_is_english("en", "not_needed"))
        self.assertTrue(_source_is_english("", "not_needed"))
        self.assertFalse(_source_is_english("te", "translated"))

    def test_raw_identity_text_does_not_block_regeneration(self) -> None:
        self.assertFalse(
            _should_skip_existing_refinement(
                existing_refined="My phone was stolen.",
                raw_english="My phone was stolen.",
                refinement_status="not_needed",
                force=False,
            )
        )

    def test_existing_ai_refinement_is_skipped_without_force(self) -> None:
        self.assertTrue(
            _should_skip_existing_refinement(
                existing_refined="I submit that my phone was stolen.",
                raw_english="My phone stolen.",
                refinement_status="refined",
                force=False,
            )
        )

    def test_existing_officer_edit_is_skipped_without_force(self) -> None:
        self.assertTrue(
            _should_skip_existing_refinement(
                existing_refined="Officer corrected refined text.",
                raw_english="Raw English text.",
                refinement_status="edited",
                force=False,
            )
        )

    def test_force_regenerates_even_when_refined_exists(self) -> None:
        self.assertFalse(
            _should_skip_existing_refinement(
                existing_refined="I submit that my phone was stolen.",
                raw_english="My phone stolen.",
                refinement_status="refined",
                force=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
