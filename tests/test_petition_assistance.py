from __future__ import annotations

import unittest

from petition_assistance import (
    PetitionAssistanceError,
    build_assistance_packet,
    build_draft_translation_payload,
    create_placeholders,
    evaluate_checklist_questions,
    language_direction,
    merge_gap_sources,
    merge_final_petition_text,
    normalize_gap_findings,
    select_basis_text,
    summarize_pilot_metrics,
    validate_packet_body,
    validate_llm_rewrite_contract,
    validate_placeholder_tokens,
)


def _parsed_output(**overrides):
    payload = {
        "text": {
            "ocr_text": "తెలుగు మూల వచనం",
            "raw_english_translation": "Raw English complaint text.",
            "refined_english_translation": (
                "I, Ravi Kumar, submit that my mobile phone was stolen near the bus stop "
                "at around 8 PM. I request police action."
            ),
        },
        "language": {
            "detected": "te",
            "detected_name": "Telugu",
            "translation_refinement_status": "refined",
        },
        "gaps": {
            "missing_details": [
                "Name of accused person",
                "Name of accused person",
                "Exact incident location",
            ],
            "uncertain_details": ["CCTV or witness evidence"],
            "missing_fields": ["who.accused.name"],
            "uncertain_fields": ["when.time"],
            "requires_review": True,
            "completeness_score": 0.62,
        },
    }
    payload.update(overrides)
    return payload


class PetitionAssistanceServiceTests(unittest.TestCase):
    def test_select_basis_text_prefers_refined_english(self) -> None:
        basis = select_basis_text(_parsed_output())

        self.assertEqual(basis.basis_text_type, "refined_english_translation")
        self.assertIn("Ravi Kumar", basis.text)
        self.assertEqual(basis.warnings, [])
        self.assertEqual(len(basis.basis_text_hash), 64)

    def test_select_basis_text_falls_back_to_raw_with_warning(self) -> None:
        payload = _parsed_output(
            text={
                "ocr_text": "हिंदी पाठ",
                "raw_english_translation": "Raw translated complaint.",
                "refined_english_translation": "",
            }
        )

        basis = select_basis_text(payload)

        self.assertEqual(basis.basis_text_type, "raw_english_translation")
        self.assertEqual(basis.warnings, ["RAW_ENGLISH_FALLBACK"])

    def test_select_basis_text_raises_when_missing(self) -> None:
        with self.assertRaises(PetitionAssistanceError) as ctx:
            select_basis_text({"text": {}})

        self.assertEqual(ctx.exception.code, "MISSING_BASIS_TEXT")

    def test_normalize_gap_findings_deduplicates_and_orders(self) -> None:
        findings = normalize_gap_findings(_parsed_output())
        labels = [finding.display_label for finding in findings]

        self.assertEqual(labels.count("Name of accused person"), 1)
        self.assertIn("Exact incident location", labels)
        self.assertEqual(findings[0].severity, "mandatory")
        self.assertTrue(all(finding.field_key for finding in findings))

    def test_create_placeholders_uses_protected_tokens(self) -> None:
        findings = normalize_gap_findings(_parsed_output())
        placeholders = create_placeholders(findings)

        self.assertTrue(placeholders)
        self.assertTrue(placeholders[0].token.startswith("[[ADD_"))
        self.assertTrue(placeholders[0].token.endswith("]]"))
        self.assertEqual(len({p.token for p in placeholders}), len(placeholders))

    def test_build_assistance_packet_has_lineage_and_zero_unsupported_facts(self) -> None:
        packet = build_assistance_packet(
            parse_record_id="53edc479-9743-4fd0-ba6d-e00946ef125c",
            parsed_output=_parsed_output(),
            file_name="petition.pdf",
            created_by="operator",
        )

        self.assertEqual(packet["request"]["generation_status"], "needs_review")
        self.assertEqual(packet["request"]["source_lineage_status"], "complete")
        self.assertEqual(packet["request"]["unsupported_fact_count"], 0)
        self.assertIn("Missing Information Assistance Packet", packet["draft"]["body_markdown"])
        self.assertIn("Petitioner Verification", packet["draft"]["body_markdown"])
        self.assertTrue(packet["validation"]["placeholder_integrity_passed"])
        self.assertTrue(any(item["source_type"] == "gap_finding" for item in packet["lineage"]))
        self.assertTrue(
            any(item["source_type"] == "refined_english_translation" for item in packet["lineage"])
        )

    def test_build_assistance_packet_handles_no_gaps(self) -> None:
        packet = build_assistance_packet(
            parse_record_id="record-1",
            parsed_output=_parsed_output(gaps={"missing_fields": [], "requires_review": False}),
        )

        self.assertEqual(packet["draft"]["placeholder_count"], 0)
        self.assertIn("No mandatory missing details", packet["draft"]["body_plain_text"])
        self.assertTrue(packet["validation"]["source_lineage_complete"])

    def test_checklist_evaluation_asks_specific_missing_details_only(self) -> None:
        parsed = _parsed_output(
            complaint={
                "who": {
                    "status": "present",
                    "components": {
                        "complainant": {"status": "present", "values": ["Ravi Kumar"]},
                        "victim": {"status": "present", "values": ["Ravi Kumar"]},
                        "accused": {"status": "missing", "values": []},
                        "witnesses": {"status": "missing", "values": []},
                    },
                },
                "what": {"status": "present", "value": "mobile phone was stolen"},
                "when": {"status": "uncertain", "components": {"date": {"status": "missing"}, "time": {"status": "present", "value": "8 PM"}}},
                "where": {"status": "present", "value": "near the bus stop"},
                "how": {"status": "missing"},
            },
        )
        questions = [
            {"id": "q-what", "checklist_version": 1, "category": "incident", "purpose": "petition", "question_text": "What loss, injury, death, assault, fear, property damage, humiliation, or financial harm occurred?", "severity": "mandatory", "is_active": True},
            {"id": "q-date", "checklist_version": 1, "category": "incident", "purpose": "petition", "question_text": "Exact date and time of occurrence, or best-known time window?", "severity": "mandatory", "is_active": True},
            {"id": "q-accused", "checklist_version": 1, "category": "accused", "purpose": "petition", "question_text": "Is the accused known, unknown, partly known, or suspected?", "severity": "mandatory", "is_active": True},
            {"id": "q-witness", "checklist_version": 1, "category": "witnesses", "purpose": "petition", "question_text": "Direct eyewitnesses: names, addresses, phone numbers, what each saw/heard.", "severity": "mandatory", "is_active": True},
        ]

        evaluations = evaluate_checklist_questions(parsed, questions)
        by_id = {item["id"]: item for item in evaluations}

        self.assertEqual(by_id["q-what"]["evaluation_status"], "present")
        self.assertEqual(by_id["q-date"]["evaluation_status"], "missing")
        self.assertIn("exact incident date", by_id["q-date"]["missing_detail"])
        self.assertEqual(by_id["q-accused"]["evaluation_status"], "missing")
        self.assertIn("accused identity", by_id["q-accused"]["missing_detail"])
        self.assertIn("names/contact", by_id["q-witness"]["missing_detail"])

    def test_packet_uses_checklist_guidance_instead_of_generic_what_where(self) -> None:
        checklist_evaluations = [
            {
                "id": "q-date",
                "checklist_version": 1,
                "category": "incident",
                "purpose": "petition",
                "question_text": "Exact date and time of occurrence, or best-known time window?",
                "severity": "mandatory",
                "evaluation_status": "missing",
                "missing_detail": "exact incident date",
                "follow_up_action": "Add the exact incident date or best-known date range.",
                "guidance": "Needed for FIR chronology, CCTV and alibi checks.",
            }
        ]

        packet = build_assistance_packet(
            parse_record_id="record-1",
            parsed_output=_parsed_output(gaps={"missing_fields": [], "requires_review": False}),
            checklist_evaluations=checklist_evaluations,
        )

        body = packet["draft"]["body_markdown"]
        self.assertIn("Checklist Validation And Foolproofing Guidance", body)
        self.assertIn("Add the exact incident date", body)
        self.assertNotIn("Confirm or correct the what", body)
        self.assertNotIn("Confirm or correct the where", body)

    def test_validate_packet_body_fails_missing_placeholder(self) -> None:
        findings = normalize_gap_findings(_parsed_output())
        placeholders = create_placeholders(findings)
        packet = build_assistance_packet(parse_record_id="record-1", parsed_output=_parsed_output())
        body = packet["draft"]["body_plain_text"].replace(placeholders[0].token, "")

        validation = validate_packet_body(
            body_plain_text=body,
            placeholders=placeholders,
            lineage=[],
        )

        self.assertFalse(validation.placeholder_integrity_passed)
        self.assertEqual(validation.quality_status, "failed")

    def test_merge_final_petition_text_replaces_only_finalized_values(self) -> None:
        placeholders = [
            {
                "id": "p1",
                "token": "[[ADD_WHO_001: Name of accused person]]",
                "label": "Name of accused person",
                "petitioner_value": "Suresh",
                "value_status": "accepted",
            },
            {
                "id": "p2",
                "token": "[[ADD_WHERE_001: Exact incident location]]",
                "label": "Exact incident location",
                "petitioner_value": "",
                "value_status": "accepted_unknown",
            },
            {
                "id": "p3",
                "token": "[[ADD_EVIDENCE_001: CCTV or witness evidence]]",
                "label": "CCTV or witness evidence",
                "petitioner_value": "",
                "value_status": "filled",
            },
        ]
        body = "Accused: [[ADD_WHO_001: Name of accused person]]\nPlace: [[ADD_WHERE_001: Exact incident location]]\nEvidence: [[ADD_EVIDENCE_001: CCTV or witness evidence]]"

        merged = merge_final_petition_text(body_markdown=body, placeholders=placeholders)

        self.assertIn("Suresh", merged["body_markdown"])
        self.assertIn("unknown", merged["body_markdown"])
        self.assertIn("[[ADD_EVIDENCE_001", merged["body_markdown"])
        self.assertEqual(len(merged["unresolved"]), 1)

    def test_translation_payload_preserves_placeholders_with_translator(self) -> None:
        body = "Add name here: [[ADD_WHO_001: Name of accused person]]"

        payload = build_draft_translation_payload(
            rewrite_request_id="req-1",
            draft_id="draft-1",
            body_markdown=body,
            target_language="te",
            target_language_name="Telugu",
            translator=lambda protected, _lang: "తెలుగు ముసాయిదా " + protected,
        )

        self.assertIn("[[ADD_WHO_001: Name of accused person]]", payload["translated_body_markdown"])
        self.assertTrue(payload["placeholder_integrity_passed"])
        self.assertEqual(payload["semantic_validation_status"], "pending")

    def test_translation_payload_flags_english_only_without_provider(self) -> None:
        payload = build_draft_translation_payload(
            rewrite_request_id="req-1",
            draft_id="draft-1",
            body_markdown="Draft [[ADD_WHAT_001: Detail]]",
            target_language="ur",
            target_language_name="Urdu",
        )

        self.assertEqual(payload["direction"], "rtl")
        self.assertEqual(payload["semantic_validation_status"], "english_only_issue")
        self.assertTrue(payload["placeholder_integrity_passed"])
        self.assertEqual(language_direction("ur"), "rtl")
        self.assertTrue(validate_placeholder_tokens("A [[ADD_WHAT_001: Detail]]", payload["translated_body_markdown"])["placeholder_integrity_passed"])

    def test_merge_gap_sources_deduplicates_checklist_and_parser_gaps(self) -> None:
        merged = merge_gap_sources(
            [{"category": "who", "display_label": "Name of accused person", "severity": "mandatory", "sources": ["5w1h"]}],
            [{"category": "who", "question_text": "Name of accused person", "severity": "recommended", "sources": ["checklist"]}],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(sorted(merged[0]["sources"]), ["5w1h", "checklist"])

    def test_llm_contract_rejects_missing_placeholder_and_unsupported_fact(self) -> None:
        result = validate_llm_rewrite_contract(
            {
                "body_markdown": "Draft without token",
                "lineage": [],
                "unsupported_facts": ["invented accused name"],
            },
            ["[[ADD_WHO_001: Name of accused person]]"],
        )

        self.assertFalse(result["valid"])
        self.assertIn("missing_placeholders", result["errors"])
        self.assertEqual(result["unsupported_fact_count"], 1)

    def test_summarize_pilot_metrics_reports_quality_rates(self) -> None:
        summary = summarize_pilot_metrics(
            [
                {"semantic_drift_flag": True, "unsupported_fact_count": 1, "refusal_or_correction": False, "officer_override_used": True},
                {"semantic_drift_flag": False, "unsupported_fact_count": 0, "refusal_or_correction": True, "officer_override_used": False},
            ]
        )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["semantic_drift_rate"], 0.5)
        self.assertEqual(summary["override_rate"], 0.5)


class PetitionAssistanceDatabaseTests(unittest.TestCase):
    def test_phase1_tables_registered_in_core_metadata(self) -> None:
        from database import metadata

        table_names = set(metadata.tables)
        for name in {
            "petition_rewrite_requests",
            "petition_placeholders",
            "generated_petition_drafts",
            "source_lineage_maps",
            "rewrite_audit_events",
            "petitioner_packets",
            "petitioner_verification_records",
            "petition_draft_translations",
            "petition_checklist_questions",
            "petition_checklist_evaluations",
            "petition_pilot_evaluations",
        }:
            self.assertIn(name, table_names)


if __name__ == "__main__":
    unittest.main()
