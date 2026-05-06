# Petition Missing Information Assistance BRD

**Document status:** Draft for implementation planning; adversarial council observations incorporated  
**Product:** ADS Complaint Analyser  
**Confidentiality:** Confidential  
**Date:** 2026-05-06  
**Owner:** Police Complaint Parser Product Team  

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope & Boundaries](#2-scope--boundaries)
3. [User Roles & Permissions](#3-user-roles--permissions)
4. [Data Model](#4-data-model)
5. [Functional Requirements](#5-functional-requirements)
6. [User Interface Requirements](#6-user-interface-requirements)
7. [API & Integration Requirements](#7-api--integration-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Workflow & State Diagrams](#9-workflow--state-diagrams)
10. [Notification & Communication Requirements](#10-notification--communication-requirements)
11. [Reporting & Analytics](#11-reporting--analytics)
12. [Migration & Launch Plan](#12-migration--launch-plan)
13. [Glossary](#13-glossary)
14. [Appendices](#14-appendices)

# 1. Executive Summary

## 1.1 Project Name

**Petition Missing Information Assistance**

Former working title: Petition Rewrite Assistance.

## 1.2 Project Description

Petition Missing Information Assistance extends ADS Complaint Analyser by converting the refined English version of a petition, the 5W+1H gap analysis, and configurable checklist-question evaluations into a petitioner-facing missing-information packet. The packet preserves the petitioner's original factual narrative, inserts clear placeholders where required information is missing, explains what the petitioner may add, and generates an original-language rendering when the original language is supported. The feature supports English, Telugu, Hindi, and Urdu petition lifecycles and produces an auditable packet that a front-desk officer can review, print, share, and accept back only after petitioner verification.

The system must not become the author of the complaint. Generated text is assistance for collecting missing facts and organizing known facts; the final petition becomes operationally usable only after the petitioner verifies the text and supplies or confirms missing details. Every generated sentence and placeholder must be traceable to refined English text, original OCR/source text, or a named missing-information gap.

## 1.3 Business Objectives

- Reduce incomplete petition resubmissions by generating precise placeholders for missing facts such as accused identity, incident time, location, evidence, witnesses, and sequence of events.
- Improve citizen guidance at police-station intake by giving petitioners a readable draft that explains exactly what must be added.
- Standardize gap remediation using configurable 5W+1H and checklist-question requirements instead of free-form officer advice.
- Preserve multilingual accessibility by producing both refined English and original-language petitioner drafts for Telugu, Hindi, Urdu, and English submissions.
- Maintain a complete audit trail from original upload to generated assistance packet, officer edits, petitioner submission, petitioner verification, and final acceptance.
- Preserve petitioner authorship by requiring consent, refusal/correction rights, and final verification before the completed petition is accepted.
- Preserve evidentiary integrity through source lineage, contradiction checks, semantic translation review, and signed/witnessed packet metadata where required.

## 1.4 Target Users and Pain Points

| User | Pain Point | Feature Response |
|---|---|---|
| Front Desk Officer / Clerk | Must repeatedly explain missing details to petitioners and manually rewrite unclear petitions. | Generates a petitioner-ready missing-information packet with placeholders and instructions. |
| Station House Officer (SHO) | Needs complaints to contain sufficient facts before deciding on FIR registration or further inquiry. | Shows checklist pass/fail status and missing facts before packet approval. |
| Investigating Officer (IO) | Receives incomplete petitions that make follow-up slow. | Captures missing investigative facts early and records whether they were supplied. |
| Petitioner | May not know what factual details are legally or operationally required and may worry that police-authored language changes their complaint. | Receives a plain-language assistance packet with visible blanks, disclosure text, refusal/correction rights, and a verification block. |
| AI Admin / System Admin | Needs to tune checklist questions, translations, and prompt behavior. | Provides configurable question bank, versioning, and audit history. |
| Senior Command | Needs visibility into petition quality and recurring missing-information patterns. | Provides dashboards for gap frequency, rewrite volume, and completion rates. |

## 1.5 Success Metrics

| KPI | Target |
|---|---|
| Assistance packet generation success rate | At least 95% of parsed petitions with refined English text produce an assistance packet. |
| Placeholder precision | At least 90% of officer-reviewed placeholders are marked useful or accepted without deletion. |
| Petitioner completion rate | At least 70% of assistance packets returned by petitioners have all mandatory placeholders completed. |
| Intake cycle time | Median officer time to explain missing information decreases by 40% within 60 days of launch. |
| Multilingual availability | 100% of Telugu, Hindi, Urdu, and English petitions with successful translation produce an English draft; at least 95% produce original-language draft when translation provider is available. |
| Petitioner verification rate | 100% of accepted packets have recorded petitioner verification, language used, officer witness, and signature/copy metadata. |
| Unsupported fact rate | 0 accepted packets contain generated facts that cannot be traced to source text, petitioner-supplied values, or explicit officer-entered notes. |
| Semantic translation drift | Less than 2% of sampled Telugu/Hindi/Urdu packets contain material meaning drift after bilingual or back-translation QA. |
| Refusal/correction capture | 100% of petitioner refusals, corrections, or disputes are recorded with outcome and officer action. |

## 1.6 Adversarial Council Update

An adversarial review of this BRD returned a **GO WITH MODIFICATIONS** recommendation. The core observation is that the product must not appear to let the police or AI rewrite a citizen's complaint and then treat it as petitioner-authored text. This BRD therefore incorporates the following controls:

- Product language is reframed from "rewrite" to "missing-information assistance" for user-facing workflows.
- Petitioner consent, refusal/correction rights, final verification, and signature/witness metadata are mandatory before acceptance.
- Every generated sentence, placeholder, and translated sentence requires lineage to refined English, original OCR/source text, a named gap, an officer edit, or petitioner-supplied value.
- Telugu, Hindi, and Urdu output requires semantic translation validation, not only placeholder preservation.
- The launch plan is narrowed so Phase 1 proves a controlled English packet and source-lineage review before full multilingual return-capture and analytics.

# 2. Scope & Boundaries

## 2.1 In Scope

- Generate a petitioner-facing missing-information assistance packet from `text.refined_english_translation`.
- Use existing 5W+1H gap analysis and future configurable checklist-question evaluations to identify missing or weak information.
- Convert each missing required fact into an inline placeholder with a short petitioner instruction.
- Produce a clean English assistance draft with placeholders embedded in the document body.
- Translate the placeholder-bearing draft into the original petition language for Telugu, Hindi, Urdu, and English.
- Preserve placeholders as protected tokens during translation so placeholders remain visible and not paraphrased away.
- Allow officer review, edit, approve, export, print, and share of the assistance packet.
- Store generated drafts, placeholders, checklist evaluations, translations, reviewer decisions, and audit events.
- Store sentence-level source lineage for generated text, translated text, placeholders, officer edits, petitioner-supplied values, and final accepted petition text.
- Record petitioner consent, refusal/correction choices, verification language, signature/witness metadata, and copy-provided metadata.
- Run contradiction and semantic-drift checks before packet approval and before final acceptance.
- Support bilingual officer review or back-translation review for Telugu, Hindi, and Urdu packets.
- Support history records and case-linked documents.
- Provide dashboards and reports for assistance packet usage and missing-information patterns.
- Provide API endpoints for generation, review, translation, export, and petitioner return capture.

## 2.2 Out of Scope

- Direct citizen self-service portal login in version 1.
- Automatic FIR registration from assistance packets.
- Legal decision-making on whether an FIR must be registered.
- Digital signature of petitioner on generated assistance packet in version 1. Wet signature or offline verification metadata is required where the packet becomes the accepted petition.
- WhatsApp/SMS delivery in version 1 unless an approved messaging provider is configured.
- Automatic translation into languages other than English, Telugu, Hindi, and Urdu.
- Replacing officer review for sensitive categories such as POCSO, SC/ST Act, missing persons, custodial complaints, or offences requiring immediate escalation.
- Predicting accused identity, motive, witnesses, or evidence not present in the petition.
- Automated legal-section selection, contradiction resolution, FIR drafting, or conversion of an uncertain fact into a definite statement.
- Treating a generated or translated packet as petitioner-authored unless petitioner verification and signature/copy metadata are recorded.

## 2.3 Assumptions

- Every assistance packet is created after OCR and parser completion.
- `text.refined_english_translation` is available for the parse record; if unavailable, the system falls back to `text.raw_english_translation` only with a visible warning.
- Existing parser output includes `complaint`, `gaps`, `confidence`, `language`, and `meta` sections.
- Officers are authenticated users in the existing ADS Complaint Analyser workspace.
- The original uploaded file and parsed output are stored in PostgreSQL through `parse_records`.
- Supported original languages are `en`, `te`, `hi`, and `ur`.
- Translation providers can process protected placeholder tokens without altering them.
- Each generated packet remains read/write until officer approval; approved packets become read-only except for administrative supersession.
- The petitioner may refuse the generated packet, request correction, submit their own revised petition, or decline to answer a placeholder; the system must record that choice without blocking ordinary intake workflow.
- Officers responsible for bilingual approval are either language-capable or use an approved back-translation/semantic comparison workflow.

## 2.4 Constraints

- The feature must integrate with the current FastAPI monolith and vanilla JavaScript frontend unless a broader frontend migration is separately approved.
- All generated content must be auditable and reproducible from stored inputs, prompts, checklist versions, and model metadata.
- PII must be protected before LLM calls using the existing privacy controls.
- The system must not fabricate facts. Placeholders must be used whenever required information is absent or uncertain.
- English refined drafts must remain in Latin script; original-language drafts may use Telugu, Devanagari, or Arabic/Urdu script.
- All exports must clearly state that the petitioner must verify and complete placeholders before resubmission.
- Generated text must preserve uncertainty. For example, "around 8 PM" must not become "8:00 PM" unless the petitioner supplies that correction.
- Meaning preservation must be validated separately from placeholder integrity for Telugu, Hindi, and Urdu.
- Operational metrics must not reward faster acceptance at the expense of petitioner comprehension, refusal rights, or factual fidelity.

# 3. User Roles & Permissions

## 3.1 Role Descriptions

| Role | Description |
|---|---|
| Clerk | Front-desk user who receives petitions, generates assistance packets, prints packets, and records petitioner return. |
| SHO | Station-level approver who can review, approve, reject, or supersede assistance packets. |
| IO | Investigating officer who can view packet history and request additional placeholders but cannot approve station-facing packet policy. |
| AI Admin | User who maintains checklist questions, prompt templates, supported language configuration, and model settings. |
| System Admin | User who manages roles, stations, environment configuration, retention settings, and export permissions. |
| Senior Command | Read-only oversight user who reviews analytics and station-level quality metrics. |
| Petitioner | Non-authenticated external person who receives a printed or shared packet and completes missing details offline or through assisted intake. |

## 3.2 Permissions Matrix

| Capability | Clerk | SHO | IO | AI Admin | System Admin | Senior Command | Petitioner |
|---|---|---|---|---|---|---|---|
| View parsed petition and refined English | Yes, station-scoped | Yes, station-scoped | Yes, assigned case | Yes, redacted samples only | Yes | Aggregated or station-scoped | No system access |
| Generate assistance packet | Yes | Yes | Yes for assigned case | Test mode only | Yes | No | No |
| Edit generated English draft | Yes before approval | Yes before approval | Suggest edits only | No production edit | Yes | No | Handwrite on packet |
| Edit original-language draft | Yes before approval | Yes before approval | Suggest edits only | No production edit | Yes | No | Handwrite on packet |
| Approve packet for petitioner | No | Yes | No | No | Yes | No | No |
| Print/export packet | Yes after generation | Yes | Yes for assigned case | No | Yes | No | Receives copy |
| Configure checklist questions | No | Suggest only | Suggest only | Yes | Yes | No | No |
| Manage prompt templates | No | No | No | Yes | Yes | No | No |
| Record petitioner returned version | Yes | Yes | Yes for assigned case | No | Yes | No | Provides completed content |
| Mark rewrite accepted | No | Yes | Yes if delegated | No | Yes | No | No |
| Record petitioner consent/refusal/correction | Yes | Yes | Yes for assigned case | No | Yes | No | Provides decision offline |
| Verify petitioner-authored final text | No | Yes | Yes if delegated | No | Yes | No | Signs or confirms outside system |
| Approve semantic translation review | No | Yes if language-capable or using approved back-translation | Suggest only | No | Yes | No | Confirms readable copy if present |
| View source-lineage map | Yes, station-scoped | Yes, station-scoped | Yes, assigned case | Redacted samples only | Yes | Aggregated only | Receives readable change/verification page |
| Delete packet | No | Supersede only | No | No | Soft-delete with reason | No | No |
| View analytics | Station summary | Station summary | Assigned case summary | Prompt/config metrics | Full | Full | No |
| Explicit denials | Cannot approve, delete, or configure | Cannot change system prompts | Cannot configure or delete | Cannot view full PII outside approved samples | Cannot bypass audit logging | Cannot view petition PII unless assigned | Cannot access system UI |

# 4. Data Model

## 4.1 Entity Relationship Summary

- `ParseRecord` has many `GapFinding`, `ChecklistEvaluation`, and `PetitionRewriteRequest` records.
- `PetitionRewriteRequest` has many `PetitionPlaceholder`, many `GeneratedPetitionDraft`, many `PetitionDraftTranslation`, one `PetitionerPacket`, many `RewriteReviewTask`, and many `RewriteAuditEvent` records.
- `ChecklistQuestion` has many `ChecklistEvaluation` records.
- `GeneratedPetitionDraft` has many `PetitionDraftTranslation` records.
- `GeneratedPetitionDraft` and `PetitionDraftTranslation` have many `SourceLineageMap` records that map generated spans back to source facts, gaps, officer edits, translations, or petitioner-supplied values.
- `PetitionerPacket` references the approved English draft and approved original-language translation.
- `PetitionerPacket` has one or more `PetitionerVerificationRecord` records for consent, refusal/correction, signature, witness, and copy-provided metadata.
- `PetitionRewriteRequest` can have many `RewritePilotEvaluation` records for sampled quality and misuse monitoring.

## 4.2 E-001 ParseRecord

Existing persisted parse history record. New tables reference this entity; no destructive migration is required.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Must exist in `parse_records.id` | Generated |
| file_name | Text | Yes | 1-255 characters after safe filename normalization | None |
| case_id | Text | No | Must match existing case ID when linked | Null |
| parsed_output | JSONB | Yes | Must include `text`, `language`, `complaint`, `gaps`, `confidence`, `meta` | None |
| completeness_score | Float | No | 0.0-1.0 | Null |
| document_format | Text | No | MIME-derived label | Null |
| created_by | Text | No | Authenticated user ID | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |

Sample data:

| id | file_name | language | completeness_score | case_id |
|---|---|---|---:|---|
| `53edc479-9743-4fd0-ba6d-e00946ef125c` | `Wsg 05.pdf` | Telugu | 0.71 | `case-2026-0007` |
| `c7ea35b8-7388-4cee-8535-6583995b7377` | `complaint-1-hindi-handwritten.pdf` | Hindi | 0.83 | Null |

## 4.3 E-002 ChecklistQuestion

Configurable question evaluated against petition content.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| question_code | Text | Yes | Upper snake case, unique per version, e.g. `ACCUSED_NAME_KNOWN` | None |
| category | Enum | Yes | `who`, `what`, `when`, `where`, `why`, `how`, `evidence`, `legal`, `identity`, `contact` | None |
| question_text | Text | Yes | 20-500 characters | None |
| petitioner_instruction | Text | Yes | 20-300 characters; must be actionable | None |
| placeholder_label | Text | Yes | 3-80 characters | None |
| severity | Enum | Yes | `mandatory`, `recommended`, `optional` | `recommended` |
| applies_to_offence_types | JSON array | No | Empty means all offence types | `[]` |
| supported_languages | JSON array | Yes | Subset of `["en","te","hi","ur"]` | `["en","te","hi","ur"]` |
| active | Boolean | Yes | Inactive questions are not evaluated | `true` |
| version | Integer | Yes | Starts at 1; increment on material change | `1` |
| created_by | Text | Yes | User ID | None |
| updated_by | Text | No | User ID | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |
| is_deleted | Boolean | Yes | Soft delete only | `false` |

Sample data:

| id | question_code | category | severity | placeholder_label |
|---|---|---|---|---|
| `cq-001` | `ACCUSED_NAME_KNOWN` | who | mandatory | Accused name |
| `cq-002` | `INCIDENT_EXACT_LOCATION` | where | mandatory | Exact place of incident |
| `cq-003` | `SUPPORTING_EVIDENCE_AVAILABLE` | evidence | recommended | Supporting evidence |

## 4.4 E-003 ChecklistEvaluation

Result of evaluating a question against a parsed petition.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| parse_record_id | UUID string | Yes | FK to ParseRecord | None |
| checklist_question_id | UUID string | Yes | FK to ChecklistQuestion | None |
| rewrite_request_id | UUID string | No | FK to PetitionRewriteRequest after generation | Null |
| evaluation_status | Enum | Yes | `present`, `missing`, `uncertain`, `not_applicable` | None |
| evidence_text | Text | No | Source snippet up to 1,000 characters | Null |
| confidence_score | Float | Yes | 0.0-1.0 | `0.0` |
| rationale | Text | Yes | 20-1,000 characters | None |
| source | Enum | Yes | `5w1h`, `checklist_llm`, `officer_override` | None |
| model_name | Text | No | Required when source is `checklist_llm` | Null |
| evaluated_at | Timestamp | Yes | UTC timestamp | now() |
| created_by | Text | Yes | System or user ID | `system` |

Sample data:

| id | parse_record_id | question_code | evaluation_status | confidence_score |
|---|---|---|---|---:|
| `ce-001` | `53edc479-9743-4fd0-ba6d-e00946ef125c` | `ACCUSED_NAME_KNOWN` | present | 0.86 |
| `ce-002` | `53edc479-9743-4fd0-ba6d-e00946ef125c` | `SUPPORTING_EVIDENCE_AVAILABLE` | missing | 0.91 |

## 4.5 E-004 GapFinding

Normalized missing-information finding from 5W+1H and checklist evaluation.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| parse_record_id | UUID string | Yes | FK to ParseRecord | None |
| rewrite_request_id | UUID string | No | FK after rewrite generation | Null |
| source_type | Enum | Yes | `5w1h`, `checklist`, `officer_added` | None |
| category | Enum | Yes | `who`, `what`, `when`, `where`, `why`, `how`, `evidence`, `contact`, `identity` | None |
| field_key | Text | Yes | Dot path such as `who.accused.name` | None |
| gap_status | Enum | Yes | `missing`, `uncertain`, `weak`, `not_applicable`, `resolved` | None |
| severity | Enum | Yes | `mandatory`, `recommended`, `optional` | `recommended` |
| display_label | Text | Yes | 3-100 characters | None |
| petitioner_instruction | Text | Yes | 20-300 characters | None |
| evidence_text | Text | No | Source text supporting finding | Null |
| resolved_by_placeholder_id | UUID string | No | FK to PetitionPlaceholder | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |

Sample data:

| id | category | field_key | gap_status | display_label |
|---|---|---|---|---|
| `gf-001` | who | `who.accused.name` | missing | Name of accused person |
| `gf-002` | where | `where.exact_location` | uncertain | Exact incident location |
| `gf-003` | evidence | `evidence.cctv` | missing | CCTV or witness evidence |

## 4.6 E-005 PetitionRewriteRequest

Top-level request to generate petitioner-facing rewrite output.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| parse_record_id | UUID string | Yes | FK to ParseRecord | None |
| case_id | Text | No | FK to Case when linked | Null |
| source_language | Text | Yes | `en`, `te`, `hi`, `ur`, or `unknown` | None |
| source_language_name | Text | Yes | English display name | None |
| basis_text_type | Enum | Yes | `refined_english_translation`, `raw_english_translation` | `refined_english_translation` |
| basis_text_hash | Text | Yes | SHA-256 of basis English text | None |
| checklist_version | Integer | Yes | Active checklist version used | None |
| generation_status | Enum | Yes | `drafting`, `source_check_required`, `needs_review`, `petitioner_review`, `approved`, `printed`, `shared`, `returned`, `petitioner_verified`, `accepted`, `superseded`, `failed` | `drafting` |
| mandatory_gap_count | Integer | Yes | >= 0 | `0` |
| recommended_gap_count | Integer | Yes | >= 0 | `0` |
| source_lineage_status | Enum | Yes | `not_started`, `complete`, `incomplete`, `failed` | `not_started` |
| contradiction_check_status | Enum | Yes | `not_started`, `passed`, `needs_review`, `blocked` | `not_started` |
| semantic_validation_status | Enum | Yes | `not_required`, `not_started`, `passed`, `needs_review`, `failed` | `not_started` |
| petitioner_consent_status | Enum | Yes | `not_presented`, `consented`, `refused`, `correction_requested` | `not_presented` |
| pilot_review_required | Boolean | Yes | True when packet is in sampled pilot QA cohort or high-risk category | `false` |
| model_provider | Text | No | `openai`, `gemini`, `none` | Null |
| model_name | Text | No | e.g. `gpt-5.2` | Null |
| prompt_version | Text | Yes | e.g. `petition-rewrite-v1` | `petition-rewrite-v1` |
| error_code | Text | No | Machine-readable failure code | Null |
| error_message | Text | No | User-safe failure text | Null |
| created_by | Text | Yes | User ID | None |
| reviewed_by | Text | No | User ID | Null |
| approved_by | Text | No | User ID | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |
| approved_at | Timestamp | No | UTC timestamp | Null |
| is_deleted | Boolean | Yes | Soft delete only | `false` |

Sample data:

| id | parse_record_id | source_language | generation_status | mandatory_gap_count |
|---|---|---|---|---:|
| `prr-001` | `53edc479-9743-4fd0-ba6d-e00946ef125c` | te | source_check_required | 2 |
| `prr-002` | `c7ea35b8-7388-4cee-8535-6583995b7377` | hi | approved | 1 |

## 4.7 E-006 PetitionPlaceholder

Inline placeholder embedded in generated petition text.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| gap_finding_id | UUID string | Yes | FK to GapFinding | None |
| token | Text | Yes | Format `[[ADD_<CATEGORY>_<NNN>: <label>]]`; unique in request | None |
| label | Text | Yes | 3-100 characters | None |
| instruction | Text | Yes | 20-300 characters | None |
| example_hint | Text | No | Must not invent case facts; generic example only | Null |
| severity | Enum | Yes | `mandatory`, `recommended`, `optional` | None |
| inserted_after_anchor | Text | No | 0-500 character source sentence fragment | Null |
| source_lineage_id | UUID string | No | FK to SourceLineageMap for the gap or source sentence that caused placement | Null |
| display_order | Integer | Yes | Starts at 1 | None |
| petitioner_value | Text | No | Captured returned value | Null |
| value_status | Enum | Yes | `blank`, `filled`, `accepted_unknown`, `needs_follow_up`, `officer_rejected`, `accepted` | `blank` |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |

Sample data:

| id | token | label | severity | value_status |
|---|---|---|---|---|
| `ph-001` | `[[ADD_WHO_001: Name of accused person]]` | Name of accused person | mandatory | blank |
| `ph-002` | `[[ADD_WHERE_001: Exact incident location]]` | Exact incident location | mandatory | filled |
| `ph-003` | `[[ADD_EVIDENCE_001: CCTV or witnesses]]` | CCTV or witnesses | recommended | needs_follow_up |

## 4.8 E-007 GeneratedPetitionDraft

English rewrite draft generated from refined English and placeholders.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| draft_language | Text | Yes | Must be `en` for this entity | `en` |
| draft_version | Integer | Yes | Starts at 1; increments on regenerate/edit | `1` |
| title | Text | Yes | 5-150 characters | `Rewritten Petition with Required Additions` |
| body_markdown | Text | Yes | Contains placeholder tokens; 200-30,000 characters | None |
| body_plain_text | Text | Yes | Plain-text export form | None |
| placeholder_count | Integer | Yes | Must match PetitionPlaceholder count | `0` |
| mandatory_placeholder_count | Integer | Yes | >= 0 | `0` |
| generation_method | Enum | Yes | `llm`, `template`, `officer_edited` | None |
| quality_status | Enum | Yes | `passed`, `needs_review`, `failed` | `needs_review` |
| quality_notes | Text | No | Required when quality_status is not `passed` | Null |
| source_lineage_complete | Boolean | Yes | True only when every generated paragraph and placeholder has a lineage record | `false` |
| unsupported_fact_count | Integer | Yes | Must be 0 before approval | `0` |
| uncertainty_preservation_passed | Boolean | Yes | False when uncertain source language is converted into definite claims | `false` |
| contradiction_count | Integer | Yes | Number of detected contradictions requiring officer review | `0` |
| sha256_hash | Text | Yes | SHA-256 of body_plain_text | None |
| created_by | Text | Yes | User/system ID | None |
| updated_by | Text | No | User ID | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |

Sample data:

| id | rewrite_request_id | draft_version | placeholder_count | quality_status |
|---|---|---:|---:|---|
| `gpd-001` | `prr-001` | 1 | 3 | needs_review |
| `gpd-002` | `prr-002` | 2 | 1 | passed |

## 4.9 E-008 PetitionDraftTranslation

Original-language rendering of the English rewrite draft.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| generated_petition_draft_id | UUID string | Yes | FK to GeneratedPetitionDraft | None |
| target_language | Text | Yes | `en`, `te`, `hi`, `ur` | None |
| target_language_name | Text | Yes | English display name | None |
| translated_body | Text | Yes | Must preserve all placeholder tokens exactly | None |
| translation_status | Enum | Yes | `not_needed`, `translated`, `needs_review`, `failed` | None |
| provider | Text | No | `openai`, `google`, `gemini`, `identity` | Null |
| model_name | Text | No | Required for LLM provider | Null |
| placeholder_integrity_passed | Boolean | Yes | True only if all tokens preserved | `false` |
| semantic_validation_method | Enum | Yes | `not_required`, `bilingual_officer`, `back_translation`, `dual_model_review`, `manual_override` | `not_required` |
| semantic_validation_status | Enum | Yes | `not_required`, `passed`, `needs_review`, `failed` | `not_required` |
| back_translation_text | Text | No | Required when method is `back_translation` | Null |
| semantic_drift_notes | Text | No | Required when validation is not `passed` | Null |
| reviewed_by_language_capable_user | Text | No | User ID for bilingual reviewer | Null |
| rtl_display | Boolean | Yes | True for Urdu | `false` |
| error_code | Text | No | Machine-readable failure code | Null |
| error_message | Text | No | User-safe failure text | Null |
| sha256_hash | Text | Yes | SHA-256 of translated_body | None |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |

Sample data:

| id | rewrite_request_id | target_language | translation_status | placeholder_integrity_passed |
|---|---|---|---|---|
| `pdt-001` | `prr-001` | te | translated | true |
| `pdt-002` | `prr-002` | hi | translated | true |
| `pdt-003` | `prr-003` | ur | translated | true |

## 4.10 E-009 PetitionerPacket

Approved packet delivered to petitioner.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| english_draft_id | UUID string | Yes | FK to GeneratedPetitionDraft | None |
| original_language_translation_id | UUID string | No | FK to PetitionDraftTranslation | Null |
| packet_status | Enum | Yes | `draft`, `approved`, `printed`, `shared`, `returned`, `accepted`, `cancelled` | `draft` |
| delivery_method | Enum | No | `print`, `pdf_download`, `email`, `manual_handover` | Null |
| pdf_storage_uri | Text | No | Required after export | Null |
| packet_reference_number | Text | Yes | Station-scoped, human-readable | Generated |
| issued_to_name | Text | No | Petitioner name if known | Null |
| consent_disclosure_version | Text | Yes | Version of petitioner-facing disclosure included in packet | `petitioner-consent-v1` |
| petitioner_consent_status | Enum | Yes | `not_presented`, `consented`, `refused`, `correction_requested` | `not_presented` |
| verification_language | Text | No | Language in which verification was read or provided: `en`, `te`, `hi`, `ur` | Null |
| wet_signature_required | Boolean | Yes | True when packet is used as accepted petition record | `true` |
| signed_packet_storage_uri | Text | No | URI of scanned signed packet or signature attachment | Null |
| witnessed_by | Text | No | Officer user ID witnessing verification/signature | Null |
| signed_at | Timestamp | No | UTC timestamp when petitioner signed or verified final packet | Null |
| petitioner_copy_provided_at | Timestamp | No | UTC timestamp when copy was provided to petitioner | Null |
| refusal_or_correction_note | Text | No | Required when petitioner refuses packet or requests correction | Null |
| issued_at | Timestamp | No | UTC timestamp | Null |
| returned_at | Timestamp | No | UTC timestamp | Null |
| accepted_at | Timestamp | No | UTC timestamp | Null |
| created_by | Text | Yes | User ID | None |
| updated_by | Text | No | User ID | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |

Sample data:

| id | packet_reference_number | packet_status | delivery_method | issued_to_name |
|---|---|---|---|---|
| `pkt-001` | `WSG-RW-2026-00014` | printed | print | P. Naresh |
| `pkt-002` | `PNG-RW-2026-00003` | accepted | manual_handover | Ramesh Kumar |

## 4.11 E-010 RewriteReviewTask

Officer task for review, approval, or petitioner return.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| task_type | Enum | Yes | `source_lineage_check`, `review_generation`, `semantic_translation_review`, `petitioner_verification`, `approve_packet`, `capture_return`, `verify_returned_values`, `misuse_sample_review` | None |
| assigned_to | Text | No | User ID | Null |
| assigned_role | Enum | Yes | `Clerk`, `SHO`, `IO`, `System_Admin` | None |
| task_status | Enum | Yes | `pending`, `in_progress`, `completed`, `cancelled`, `overdue` | `pending` |
| due_at | Timestamp | No | Required for SLA reporting | Null |
| completed_by | Text | No | User ID | Null |
| completed_at | Timestamp | No | UTC timestamp | Null |
| notes | Text | No | 0-2,000 characters | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |
| updated_at | Timestamp | No | UTC timestamp | Null |

Sample data:

| id | task_type | assigned_role | task_status | due_at |
|---|---|---|---|---|
| `rrt-001` | approve_packet | SHO | pending | `2026-05-06T12:00:00Z` |
| `rrt-002` | capture_return | Clerk | completed | `2026-05-07T12:00:00Z` |

## 4.12 E-011 RewriteAuditEvent

Immutable audit trail for rewrite lifecycle actions.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| actor_id | Text | Yes | User ID or `system` | None |
| actor_role | Text | Yes | Role at time of action | None |
| action_type | Enum | Yes | `generated`, `source_lineage_checked`, `edited`, `translated`, `semantic_validated`, `consent_presented`, `petitioner_refused`, `correction_requested`, `approved`, `exported`, `printed`, `returned`, `petitioner_verified`, `accepted`, `rejected`, `superseded`, `pilot_reviewed`, `failed` | None |
| before_hash | Text | No | SHA-256 before change | Null |
| after_hash | Text | No | SHA-256 after change | Null |
| event_summary | Text | Yes | 10-500 characters | None |
| metadata | JSONB | No | Redacted structured event data | `{}` |
| created_at | Timestamp | Yes | UTC timestamp | now() |

Sample data:

| id | actor_role | action_type | event_summary |
|---|---|---|---|
| `rae-001` | Clerk | generated | Rewrite packet generated with 3 placeholders. |
| `rae-002` | SHO | approved | SHO approved petitioner packet for print. |
| `rae-003` | Clerk | returned | Petitioner returned packet with 2 completed values. |

## 4.13 E-012 SourceLineageMap

Traceability record proving why a generated or translated span exists.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| generated_petition_draft_id | UUID string | No | FK to GeneratedPetitionDraft | Null |
| petition_draft_translation_id | UUID string | No | FK to PetitionDraftTranslation | Null |
| output_span_id | Text | Yes | Stable span ID such as `en-p003-s002` | None |
| output_text | Text | Yes | Generated sentence, paragraph, placeholder, or translated span | None |
| source_type | Enum | Yes | `refined_english`, `original_ocr`, `raw_translation`, `gap_finding`, `checklist_evaluation`, `officer_edit`, `petitioner_value`, `translation`, `disclosure_template` | None |
| source_reference_id | Text | No | FK/ID/path to source record when available | Null |
| source_excerpt | Text | No | Source snippet up to 1,000 characters | Null |
| source_char_start | Integer | No | Character offset in source text | Null |
| source_char_end | Integer | No | Character offset in source text | Null |
| lineage_confidence | Float | Yes | 0.0-1.0 | `0.0` |
| reviewer_status | Enum | Yes | `pending`, `accepted`, `rejected`, `not_required` | `pending` |
| reviewer_note | Text | No | Required when rejected | Null |
| created_at | Timestamp | Yes | UTC timestamp | now() |

Sample data:

| id | output_span_id | source_type | reviewer_status |
|---|---|---|---|
| `slm-001` | `en-p002-s001` | refined_english | accepted |
| `slm-002` | `en-ph-who-001` | gap_finding | accepted |
| `slm-003` | `te-p002-s001` | translation | pending |

## 4.14 E-013 PetitionerVerificationRecord

Record that the petitioner received, understood, refused, corrected, or verified the generated packet.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| petitioner_packet_id | UUID string | Yes | FK to PetitionerPacket | None |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| verification_type | Enum | Yes | `consent`, `refusal`, `correction_request`, `final_verification`, `copy_provided` | None |
| verification_language | Text | Yes | `en`, `te`, `hi`, `ur`, or `other` | None |
| petitioner_name_recorded | Text | No | Name used for packet verification | Null |
| petitioner_response | Enum | Yes | `accepted_to_use_packet`, `refused_packet`, `requested_correction`, `verified_final_text`, `received_copy` | None |
| disclosure_version | Text | Yes | Disclosure text version shown or read to petitioner | `petitioner-consent-v1` |
| signature_mode | Enum | No | `wet_signature`, `thumb_impression`, `verbal_assisted`, `not_applicable` | Null |
| signed_packet_storage_uri | Text | No | Required for scanned signed packet when available | Null |
| witnessed_by | Text | No | Officer user ID | Null |
| witness_note | Text | No | Required for verbal assisted workflows | Null |
| created_by | Text | Yes | User ID | None |
| created_at | Timestamp | Yes | UTC timestamp | now() |

Sample data:

| id | verification_type | verification_language | petitioner_response |
|---|---|---|---|
| `pvr-001` | consent | te | accepted_to_use_packet |
| `pvr-002` | final_verification | te | verified_final_text |
| `pvr-003` | copy_provided | te | received_copy |

## 4.15 E-014 RewritePilotEvaluation

Sampled quality and governance review for pilot rollout and misuse monitoring.

| Field | Type | Required | Validation / Rules | Default |
|---|---|---:|---|---|
| id | UUID string | Yes | Unique | Generated |
| rewrite_request_id | UUID string | Yes | FK to PetitionRewriteRequest | None |
| station_id | Text | No | Station identifier | Null |
| sampled_reason | Enum | Yes | `random_sample`, `high_risk_category`, `language_qa`, `officer_override`, `petitioner_dispute`, `semantic_drift` | None |
| semantic_drift_found | Boolean | Yes | True if material meaning changed | `false` |
| unsupported_fact_found | Boolean | Yes | True if generated unsupported fact found | `false` |
| petitioner_comprehension_status | Enum | Yes | `not_measured`, `understood`, `partially_understood`, `did_not_understand` | `not_measured` |
| officer_oversteer_risk | Enum | Yes | `none`, `low`, `medium`, `high` | `none` |
| corrective_action | Text | No | Required when any risk is medium/high or fact drift is found | Null |
| reviewed_by | Text | Yes | User ID | None |
| reviewed_at | Timestamp | Yes | UTC timestamp | now() |

Sample data:

| id | sampled_reason | semantic_drift_found | officer_oversteer_risk |
|---|---|---|---|
| `rpe-001` | random_sample | false | none |
| `rpe-002` | language_qa | true | low |

# 5. Functional Requirements

## 5.1 Generation and Gap Mapping

### FR-001 Generate Missing-Information Assistance Request from Parsed Petition

**Description:** The system shall create a missing-information assistance request from an existing parse record using `text.refined_english_translation` as the primary source. If refined English is unavailable, the system shall require officer confirmation before using raw English and shall mark the request as lower confidence.

**User story:** As a Clerk, I want to generate a petitioner assistance request from a parsed petition so that the petitioner receives a clear document showing what information may be added or corrected.

**Acceptance criteria:**
1. Given a parse record with refined English, when the Clerk clicks "Generate Assistance Packet", the system creates a `PetitionRewriteRequest`.
2. The request stores `basis_text_type=refined_english_translation` and the SHA-256 hash of the basis text.
3. If neither refined nor raw English exists, generation fails with `MISSING_BASIS_TEXT`.
4. Generation status becomes `drafting` during processing and `source_check_required` after draft creation.
5. The request stores `source_lineage_status`, `contradiction_check_status`, and `petitioner_consent_status`.

**Business rules:**
- Refined English must be used when `language.translation_refinement_status=refined`.
- Raw English fallback requires `officer_confirmed_raw_basis=true`.
- One parse record may have multiple assistance requests, but only one request may be active unless the previous request is `superseded`, `accepted`, or `cancelled`.
- The UI and printed packet must describe the output as assistance for missing information, not as a police-authored replacement complaint.

**UI behavior notes:**
- The button is disabled until parsing is complete.
- A warning banner appears if refined English is unavailable.
- On success, the UI opens the Assistance Packet Review screen.

**Edge cases and error handling:**
- If parse record is missing, return `404 NOT_FOUND`.
- If generation is already running for the same parse record, return `409 ACTIVE_REQUEST_EXISTS`.
- If LLM provider times out, save failed status and allow retry.

### FR-002 Evaluate Checklist Questions

**Description:** The system shall evaluate active checklist questions against the refined English petition and original OCR text. Evaluation shall produce present, missing, uncertain, or not-applicable outcomes with evidence and rationale.

**User story:** As an SHO, I want checklist questions evaluated consistently so that every petitioner receives the same missing-information guidance for similar petition types.

**Acceptance criteria:**
1. Active `ChecklistQuestion` records are loaded by version before rewrite generation.
2. Each applicable question creates one `ChecklistEvaluation`.
3. Every evaluation includes status, confidence score, source, and rationale.
4. Evaluations with `missing` or `uncertain` status produce or link to a `GapFinding`.

**Business rules:**
- Mandatory questions with `missing` or `uncertain` status become mandatory placeholders.
- Questions whose `applies_to_offence_types` does not match detected offence type are marked `not_applicable`.
- Officer overrides require notes with at least 15 characters.

**UI behavior notes:**
- Results show as a checklist table grouped by 5W+1H category.
- Evidence snippets are expandable.
- Officer override opens a modal requiring status and note.

**Edge cases and error handling:**
- If checklist config is unavailable, generation continues using 5W+1H gaps and records warning `CHECKLIST_UNAVAILABLE`.
- If an LLM response lacks evidence for a present answer, status is downgraded to `uncertain`.

### FR-003 Normalize Gap Findings

**Description:** The system shall merge parser gaps and checklist gaps into one normalized gap list. Duplicate gaps shall be merged so that one missing accused name does not produce multiple placeholders.

**User story:** As a Clerk, I want duplicate missing facts merged so that the petitioner sees one clear blank for each required addition.

**Acceptance criteria:**
1. 5W+1H missing fields create `GapFinding` records.
2. Checklist missing fields create `GapFinding` records.
3. Duplicate gaps are merged by category, field key, and label.
4. The merged gap retains the highest severity among duplicates.

**Business rules:**
- `mandatory` outranks `recommended`, and `recommended` outranks `optional`.
- A gap with `not_applicable` status must not produce a placeholder.
- A gap with `resolved` status is excluded from newly generated drafts unless the officer manually includes it.

**UI behavior notes:**
- The Gap Review panel shows source badges: `5W+1H`, `Checklist`, or `Officer`.
- Merged gaps show all contributing sources.

**Edge cases and error handling:**
- If two sources provide conflicting statuses, show `uncertain` and require officer decision.
- If no gaps are found, generate a "No mandatory additions identified" packet with optional officer notes.

## 5.2 Placeholder and Draft Generation

### FR-004 Create Inline Placeholders

**Description:** The system shall transform each actionable gap into an inline placeholder token and instruction. Placeholders shall be embedded near the most relevant sentence in the assistance draft.

**User story:** As a Petitioner, I want missing information blanks placed inside the petition text so that I know exactly where to add the missing facts.

**Acceptance criteria:**
1. Every mandatory gap creates one mandatory placeholder.
2. Every placeholder token is unique within a rewrite request.
3. Placeholder tokens remain visible in English and original-language drafts.
4. Placeholder instructions are shown in a separate checklist table and as inline labels.
5. Every placeholder has a `SourceLineageMap` record pointing to the corresponding gap and any source sentence used for placement.

**Business rules:**
- Token format must be `[[ADD_<CATEGORY>_<NNN>: <label>]]`.
- Placeholder labels must not exceed 80 characters.
- Example hints must be generic and must not include invented facts.
- Deterministic placeholder deduplication must merge gaps with the same normalized category, field key, label, and source meaning before LLM drafting.

**UI behavior notes:**
- Mandatory placeholders are highlighted with red outline.
- Recommended placeholders are highlighted with amber outline.
- Hover or focus shows petitioner instruction.

**Edge cases and error handling:**
- If no relevant anchor sentence is found, insert the placeholder in a "Details to be added by petitioner" section before the prayer/request paragraph.
- If the LLM omits a placeholder token, deterministic validation reinserts it in the missing-details section.
- If two placeholders compete for the same source span, the system groups them in display order rather than letting the model choose an arbitrary location.

### FR-005 Generate Readable English Assistance Draft

**Description:** The system shall generate a logically readable English assistance draft from refined English and placeholders. The draft shall use standard petition structure: addressee, subject, petitioner identity, facts, missing details placeholders, requested action, petitioner verification note, and signature block.

**User story:** As an SHO, I want the generated draft to read like a coherent assistance document so that the petitioner can complete missing facts without the system changing the complaint's meaning.

**Acceptance criteria:**
1. The generated English draft includes all original facts that are clear in the refined English source.
2. The draft includes all mandatory placeholders.
3. The draft does not invent accused names, dates, evidence, injuries, witnesses, motive, or legal sections.
4. The draft quality validator confirms placeholder integrity before status becomes `needs_review`.
5. Every non-template sentence has a lineage record to source text, a named gap, an officer edit, or petitioner-supplied value.
6. The contradiction checker flags any sentence that softens, strengthens, omits uncertainty, changes chronology, or changes an allegation's meaning.

**Business rules:**
- The draft must preserve names, dates, times, addresses, amounts, phone numbers, vehicle numbers, and incident details from the basis text.
- The draft must not remove uncertainty markers unless officer edits them.
- The draft must include the statement: "This document is assistance for adding missing information. Please verify all facts and fill every mandatory placeholder before resubmission."
- The draft must not select legal sections, decide FIR eligibility, or convert "unknown" into a forced blank without officer review.
- Any unsupported fact count greater than zero blocks approval.

**UI behavior notes:**
- Draft appears in an editable rich text/plain text panel.
- Officer can toggle "Show source refined English" side-by-side.
- Validation errors are displayed above the draft with jump links to missing tokens.

**Edge cases and error handling:**
- If the source petition contains only administrative metadata, generation fails with `NO_COMPLAINT_BODY`.
- If the generated draft is shorter than 60% of the refined English source without officer approval, mark quality status `failed`.
- If lineage coverage is incomplete, status becomes `source_check_required` and export is blocked.

### FR-006 Translate Assistance Draft to Original Language

**Description:** The system shall translate the placeholder-bearing English assistance draft into the original petition language when the source language is Telugu, Hindi, or Urdu. English source petitions shall use identity translation with `translation_status=not_needed`.

**User story:** As a Petitioner, I want the rewritten draft in my original language so that I can understand and complete it accurately.

**Acceptance criteria:**
1. Telugu source petitions produce Telugu rewrite drafts.
2. Hindi source petitions produce Hindi rewrite drafts.
3. Urdu source petitions produce Urdu rewrite drafts with right-to-left display.
4. English source petitions show only English draft unless the officer explicitly requests another supported language.
5. Placeholder token integrity check passes before packet approval.
6. Semantic translation validation passes before a Telugu, Hindi, or Urdu packet can be marked bilingual-approved.
7. The packet stores the semantic validation method and reviewer or back-translation output.

**Business rules:**
- Placeholder tokens must be protected before translation and restored exactly after translation.
- Original-language translation must not translate token labels inside `[[...]]`.
- If translation fails, the packet can be reviewed in English but cannot be marked bilingual-approved.
- Placeholder integrity proves token preservation only; it does not prove meaning preservation.
- Telugu, Hindi, and Urdu approval requires one of: bilingual officer review, approved back-translation comparison, dual-model semantic review with officer acceptance, or documented SHO override.
- Urdu output must preserve right-to-left prose while keeping placeholder tokens and reference numbers readable.

**UI behavior notes:**
- Original-language tab appears next to English Draft.
- Urdu text panel uses `dir="rtl"` and right-aligned text.
- A warning banner appears if translation is unavailable.

**Edge cases and error handling:**
- If placeholder count after translation differs from English draft, status becomes `needs_review` and error code `PLACEHOLDER_INTEGRITY_FAILED`.
- If source language is `unknown`, system generates English only and asks officer to select a target language manually.
- If semantic validation finds drift in names, dates, chronology, uncertainty, allegations, or requested action, packet status becomes `source_check_required` and approval is blocked until corrected.

## 5.3 Officer Review and Petitioner Return

### FR-007 Officer Review and Approval

**Description:** The system shall require officer review before an assistance packet is issued to a petitioner. SHO or System Admin approval is required for packet status to move from `needs_review` to `approved`.

**User story:** As an SHO, I want to review generated assistance packets before they are issued so that petitioner guidance is accurate and legally neutral.

**Acceptance criteria:**
1. The review screen shows source refined English, original OCR/raw text where available, gaps, English draft, original-language draft, and source-lineage summary.
2. SHO can approve, reject, edit, or regenerate the packet.
3. Approval records `approved_by` and `approved_at`.
4. Approved packet becomes read-only except for supersession.
5. Review must show whether each paragraph is AI-suggested, officer-edited, petitioner-supplied, translated, or disclosure template text.

**Business rules:**
- Packet cannot be approved when mandatory placeholder integrity fails.
- Packet cannot be approved when source lineage is incomplete or unsupported facts are detected.
- Packet cannot be approved when contradiction check is `blocked`.
- Packet cannot be approved when original-language translation is failed and source language is Telugu, Hindi, or Urdu, unless SHO selects "English-only issue" with reason.
- Packet cannot be marked bilingual-approved unless semantic validation passes or a documented SHO override is recorded.
- Every edit after generation increments draft version.

**UI behavior notes:**
- Approve button is disabled until all validation checks are green or SHO override reason is entered.
- Reject requires reason with minimum 20 characters.

**Edge cases and error handling:**
- Concurrent edits use optimistic locking; stale save returns `409 VERSION_CONFLICT`.
- If user lacks approval permission, API returns `403 AUTHORIZATION_ERROR`.
- If officer edits introduce unsupported facts, approval remains blocked until those edits are linked to officer notes or petitioner-supplied values.

### FR-008 Export and Print Petitioner Packet

**Description:** The system shall export the approved packet as a printable PDF and optionally DOCX/text where supported. The packet shall include disclosure text, instructions, English draft, original-language draft, placeholder checklist, petitioner verification block, and officer footer.

**User story:** As a Clerk, I want to print the approved assistance packet so that the petitioner can fill missing information and resubmit it.

**Acceptance criteria:**
1. PDF export includes packet reference number and issue timestamp.
2. English and original-language sections are included when bilingual output is approved.
3. Placeholder checklist appears before the signature block.
4. Export action creates a `RewriteAuditEvent`.
5. Packet includes petitioner refusal/correction instructions and a readable change/verification page.

**Business rules:**
- Draft packets may be previewed but not exported with official footer.
- Printed packet must include "This document is a guidance draft. The petitioner must verify all facts before signing."
- Printed packet must also state that the petitioner may refuse the generated draft, request correction, provide their own revised petition, or decline to answer a placeholder.
- Urdu PDF must preserve right-to-left text direction.
- When the packet may be used as the accepted petition record, wet signature or thumb impression metadata must be captured after return.

**UI behavior notes:**
- Export button appears only after approval.
- Print opens browser print dialog after PDF generation succeeds.

**Edge cases and error handling:**
- If PDF rendering fails, return `EXPORT_FAILED` and provide DOCX/plain text fallback if available.
- If storage upload fails, allow direct browser download and log `EXPORT_STORAGE_FAILED`.

### FR-009 Capture Petitioner Returned Values

**Description:** The system shall allow officers to record petitioner-provided values for placeholders when the completed packet is returned. The officer can mark each placeholder as filled, rejected, or still blank.

**User story:** As a Clerk, I want to capture the petitioner's added details so that the corrected petition can be reviewed and accepted.

**Acceptance criteria:**
1. Returned packet form lists all placeholders with current values.
2. Officer can enter petitioner-provided text for each placeholder.
3. Mandatory blank placeholders block acceptance.
4. Each captured value updates `PetitionPlaceholder.value_status`.
5. Officer records whether the petitioner consented, refused, requested correction, or provided a separate revised petition.

**Business rules:**
- Values over 2,000 characters require SHO review.
- Phone number fields must accept Indian mobile numbers and landline formats.
- Date fields must accept `DD/MM/YYYY`, `DD-MM-YYYY`, and natural language dates that can be normalized.
- Petitioner-provided values must be stored as petitioner-supplied facts and must not be silently grammar-corrected in a way that changes meaning.
- The system must support `accepted_unknown` and `needs_follow_up` statuses when the petitioner says the information is unknown or cannot currently be supplied.

**UI behavior notes:**
- Mandatory blank fields show red validation text.
- "Save return draft" is allowed with blank values.
- "Submit for acceptance" requires all mandatory placeholders filled.

**Edge cases and error handling:**
- If a petitioner writes "unknown", officer must select `accepted_unknown` or `needs_follow_up`.
- If the returned value contradicts the original petition, show a warning and route to SHO review.
- If petitioner refuses the packet, status remains non-final and the refusal/correction event is preserved without deleting the original parse record.

### FR-010 Accept Final Completed Petition

**Description:** The system shall generate a final completed petition text by replacing placeholders with petitioner-provided values and marking the rewrite request accepted after officer review.

**User story:** As an IO, I want accepted placeholder values merged into a final petition so that downstream inquiry or FIR drafting uses the corrected facts.

**Acceptance criteria:**
1. Final text replaces every accepted placeholder with petitioner-provided value.
2. Accepted rewrite status becomes `accepted`.
3. Final accepted text is linked to the parse record and case document when available.
4. Audit event records before/after hashes.
5. The system stores a petitioner verification record with language used, signature mode, witnessed-by officer, signed timestamp, and scanned signed packet link when available.
6. Final accepted text includes lineage showing which parts came from original source, AI assistance, officer edits, and petitioner-supplied values.

**Business rules:**
- Only SHO, delegated IO, or System Admin may accept the final completed petition.
- Rejected placeholders remain visible in the final review and must be resolved before acceptance.
- Final accepted text must not overwrite original OCR or original refined translation.
- Acceptance requires recorded petitioner verification. Officer confirmation alone is insufficient.
- If a petitioner signs only the original-language packet, the English final text must remain marked as a translation/working copy unless separately verified.

**UI behavior notes:**
- Final preview shows inserted values highlighted once.
- Acceptance modal requires confirmation that petitioner verified the facts.

**Edge cases and error handling:**
- If final merge fails because a token is missing, return `FINAL_MERGE_FAILED`.
- If case document update fails, keep accepted packet and log `CASE_LINK_FAILED`.
- If signature or verification metadata is missing, return `PETITIONER_VERIFICATION_REQUIRED`.

## 5.4 Configuration, Audit, and Analytics

### FR-011 Manage Checklist Questions

**Description:** AI Admin and System Admin users shall create, edit, deactivate, and version checklist questions. Historical evaluations must remain tied to the version used at generation time.

**User story:** As an AI Admin, I want to manage checklist questions so that the system can evolve as department requirements change.

**Acceptance criteria:**
1. Admin can create question with category, severity, instruction, placeholder label, language support, and offence applicability.
2. Editing an active question creates a new version.
3. Deactivation prevents future evaluations but does not delete history.
4. Validation prevents duplicate active `question_code` values in same version set.

**Business rules:**
- Mandatory question deletion is prohibited; only deactivation is allowed.
- Question text must be reviewed by SHO or System Admin before activation.
- At least one active question must exist for each 5W+1H category.

**UI behavior notes:**
- Admin screen shows active/inactive tabs and version history.
- Save button remains disabled until validation passes.

**Edge cases and error handling:**
- If a question is referenced by an accepted packet, edits create new version and preserve old row.
- Invalid category returns `VALIDATION_ERROR`.

### FR-012 Audit Rewrite Lifecycle

**Description:** Every material action in the rewrite lifecycle shall create an immutable audit event with actor, role, action, timestamp, and content hash where content changed.

**User story:** As a System Admin, I want a complete audit trail so that petition rewrite activity can be reviewed during oversight or legal scrutiny.

**Acceptance criteria:**
1. Generation, edit, translation, approval, export, print, return, acceptance, rejection, supersession, and failure create audit events.
2. Audit events cannot be edited or deleted by application users.
3. Content-changing events include before and after hashes where both values exist.
4. Audit timeline is visible from the rewrite request detail screen.

**Business rules:**
- PII in metadata must be redacted unless required for evidentiary record and user is authorized.
- Failed events must include error code.

**UI behavior notes:**
- Timeline displays newest event first by default.
- Each event can expand to show metadata.

**Edge cases and error handling:**
- If audit logging fails, the primary action must fail for approval, acceptance, export, and deletion actions.
- Read-only view is returned for users without audit metadata permission.

### FR-013 Reporting Dashboard

**Description:** The system shall provide station and command dashboards showing rewrite volume, gap patterns, placeholder completion, translation success, and review SLA performance.

**User story:** As Senior Command, I want rewrite analytics so that I can identify stations, offence types, and petition categories with recurring missing information.

**Acceptance criteria:**
1. Dashboard filters by date range, station, language, offence type, and status.
2. Metrics include generated packets, approved packets, accepted packets, average mandatory gaps, top missing questions, and translation failure rate.
3. Data refreshes at least every 15 minutes.
4. CSV export is available for authorized users.

**Business rules:**
- Senior Command dashboard shows aggregates by default; row-level PII is hidden unless station-scoped access is granted.
- Metrics exclude soft-deleted records unless "include deleted" is selected by System Admin.

**UI behavior notes:**
- Use compact KPI cards, ranked tables, and trend lines.
- Empty state explains selected filters produced no records.

**Edge cases and error handling:**
- If aggregation query times out, return partial cached metrics with warning `REPORT_PARTIAL`.

### FR-014 Petitioner Consent, Refusal, and Authorship Controls

**Description:** The system shall require petitioner-facing disclosure and verification before a packet can be treated as accepted petition text.

**User story:** As a Petitioner, I want to know that the packet is AI/officer-assisted guidance and that I can refuse or correct it so that my complaint remains my own statement.

**Acceptance criteria:**
1. Every issued packet includes disclosure text in English and the original language when available.
2. The system records consent, refusal, correction request, or final verification as a `PetitionerVerificationRecord`.
3. Final acceptance is blocked unless petitioner verification is recorded.
4. The petitioner-facing packet includes a signature/thumb impression block and officer witness block where operationally required.

**Business rules:**
- Disclosure must state that the packet is not the petitioner's complaint unless the petitioner verifies and signs/confirms it.
- Petitioner refusal or correction request must not be treated as an error or deleted event.
- Officers must record the language in which the disclosure was provided.
- The petitioner must receive a copy or the reason for copy-not-provided must be recorded.

**UI behavior notes:**
- Return capture screen includes consent/refusal/correction controls before final merge.
- Acceptance modal shows missing verification fields and blocks submission until complete.

**Edge cases and error handling:**
- If petitioner is unable to sign, officer can select assisted verification mode with witness note.
- If petitioner disputes wording after approval, the packet is routed to correction rather than acceptance.

### FR-015 Source Lineage and Unsupported Fact Gate

**Description:** The system shall maintain source lineage for every generated sentence, translated sentence, placeholder, officer edit, and petitioner-supplied value.

**User story:** As an SHO, I want to see why every generated sentence exists so that I can approve only source-grounded assistance.

**Acceptance criteria:**
1. Every generated paragraph has one or more `SourceLineageMap` records.
2. Every placeholder maps to a `GapFinding`.
3. Officer edits either preserve previous lineage or create an `officer_edit` lineage record.
4. Approval is blocked when unsupported fact count is greater than zero.
5. Final accepted text preserves lineage to source text, officer edits, and petitioner values.

**Business rules:**
- Template disclosure/signature text may use `disclosure_template` lineage.
- AI-generated text may reorganize or clarify language but must not add factual content without a source.
- Source lineage must survive export and be viewable in the internal audit screen.

**UI behavior notes:**
- Review screen shows lineage badges such as Source, Gap, Officer Edit, Petitioner Value, Translation, and Disclosure.
- Officers can open source snippets from lineage badges.

**Edge cases and error handling:**
- If lineage generation fails, request status becomes `source_check_required`.
- If source text is too noisy to support a sentence, that sentence must be rewritten as a placeholder or officer note.

### FR-016 Semantic Translation and Contradiction Review

**Description:** The system shall validate meaning preservation for Telugu, Hindi, and Urdu drafts and detect contradictions before approval and final acceptance.

**User story:** As a bilingual reviewer, I want to ensure the original-language packet preserves meaning so that the petitioner is not asked to verify altered facts.

**Acceptance criteria:**
1. Translation validation checks names, dates, amounts, locations, chronology, uncertainty markers, allegations, requested action, and placeholders.
2. Urdu review verifies right-to-left rendering and readable placeholder placement.
3. Contradiction checks run after generation, officer edits, translation, and returned-value merge.
4. Material semantic drift or contradiction blocks approval unless corrected or explicitly overridden by SHO with reason.

**Business rules:**
- Placeholder preservation is necessary but not sufficient for bilingual approval.
- Back-translation or bilingual officer approval is mandatory for sampled pilot packets and high-risk categories.
- The system must not silently soften allegations or strengthen uncertain language.

**UI behavior notes:**
- Validation summary distinguishes placeholder integrity, semantic meaning, contradiction status, and rendering status.
- Failed checks include jump links to affected text spans.

**Edge cases and error handling:**
- If no bilingual reviewer is available, packet may be issued English-only only with recorded reason and petitioner language limitation warning.
- If semantic validation provider fails, packet remains `needs_review` and can be retried.

### FR-017 Pilot Evaluation, Misuse Monitoring, and Operational Accountability

**Description:** The system shall support pilot QA sampling and misuse monitoring to prove the feature improves factual completeness without coercion or distortion.

**User story:** As Senior Command, I want measurable guardrails for pilot rollout so that faster packet handling does not hide factual drift or petitioner pressure.

**Acceptance criteria:**
1. The system samples packets for `RewritePilotEvaluation` based on random selection, language QA, high-risk categories, officer overrides, semantic drift, and petitioner disputes.
2. Pilot reports include semantic drift rate, unsupported fact rate, petitioner comprehension status, refusal/correction frequency, officer override patterns, and legal acceptability review results.
3. High-risk pilot findings create corrective actions and block broader rollout until resolved.
4. Dashboard metrics separate speed metrics from quality, consent, and factual-fidelity metrics.

**Business rules:**
- Pilot exit requires zero accepted unsupported facts in sampled packets.
- Pilot exit requires documented language-specific QA for Telugu, Hindi, and Urdu before broad multilingual rollout.
- Officer productivity metrics must not rank users solely by acceptance speed or volume.

**UI behavior notes:**
- Senior dashboard shows pilot quality warnings before operational volume charts.
- Audit detail shows whether a packet was in the pilot sample and why.

**Edge cases and error handling:**
- If required pilot QA is overdue, new packets in the affected language or category require supervisor approval.
- If petitioner comprehension is repeatedly low for a station/language pair, the packet template is routed for review.

# 6. User Interface Requirements

## 6.1 Documents Page: Assistance Packet Entry Point

| Requirement | Description |
|---|---|
| Purpose | Let officers generate a missing-information packet after viewing OCR, raw English, refined English, and gap analysis. |
| Layout | Existing document split pane remains: original document on left, text tabs on right. Add "Generate Assistance Packet" action in result toolbar and gap analysis panel. |
| Components | Button, warning banner, gap count badges, generation progress step, toast notifications. |
| Navigation | From document detail or history record to Assistance Packet Review screen. |
| Responsive behavior | On mobile, action appears below tabs and opens full-screen rewrite review. |

## 6.2 Assistance Packet Review Screen

| Requirement | Description |
|---|---|
| Purpose | Review generated English assistance draft, original-language draft, placeholders, source facts, lineage, and petitioner disclosure before approval. |
| Layout | Five-pane tabbed workspace: Source, Gaps & Checklist, English Draft, Original Language Draft, Lineage & Validation. Right side shows validation summary and actions. |
| Components | Tabs, editable text area, placeholder table, validation checklist, lineage badges, semantic translation panel, regenerate button, approve/reject buttons, audit preview. |
| Design system | Use existing ADS Complaint Analyser CSS custom properties, restrained operational layout, compact panels, 8px or smaller radius, accessible focus rings. |
| Navigation | Back to document detail, forward to export/print, link to audit timeline. |
| Responsive behavior | Tabs become segmented control; validation panel collapses into top summary drawer. |

## 6.3 Petitioner Verification and Change Review Page

| Requirement | Description |
|---|---|
| Purpose | Provide a readable officer-facing and petitioner-facing page showing what was AI-suggested, officer-edited, petitioner-supplied, and finally verified. |
| Layout | Top disclosure/consent section, middle change summary grouped by source, bottom verification/signature/copy section. |
| Components | Consent selector, refusal/correction selector, language selector, signature mode selector, witness fields, copy-provided confirmation, source badges. |
| Navigation | From packet export and return capture; forward to final acceptance only when required fields are complete. |
| Responsive behavior | Verification controls stack above change summary on mobile. |

## 6.4 Checklist Configuration Screen

| Requirement | Description |
|---|---|
| Purpose | Allow AI Admin/System Admin to maintain checklist questions. |
| Layout | Left filter sidebar by category/severity/status; main table; right edit drawer. |
| Components | Data table, category filter, severity dropdown, language checkboxes, version history, validation errors. |
| Navigation | Admin section to question detail and audit history. |
| Responsive behavior | Edit drawer becomes full-screen modal on mobile. |

## 6.5 Petitioner Return Capture Screen

| Requirement | Description |
|---|---|
| Purpose | Capture values written or dictated by petitioner for each placeholder and record consent/refusal/correction/verification outcome. |
| Layout | Top packet summary and verification status, left final draft preview, right placeholder form grouped by category. |
| Components | Text inputs, date inputs, phone inputs, status selectors, contradiction warning, consent/refusal controls, signature metadata fields, save and submit buttons. |
| Navigation | From packet detail after status `printed` or `shared`; forward to final acceptance screen. |
| Responsive behavior | Placeholder form appears first on mobile; draft preview collapses behind "View draft". |

## 6.6 Reports Dashboard

| Requirement | Description |
|---|---|
| Purpose | Show rewrite usage, petition quality, consent/verification, semantic drift, and pilot accountability metrics. |
| Layout | Filter bar, pilot quality warning band, KPI band, trend chart, top missing question table, language/status breakdown. |
| Components | Date range picker, station selector, language filter, cards, tables, CSV export, pilot QA drill-down. |
| Navigation | Senior dashboard or admin analytics section. |
| Responsive behavior | KPI cards stack; tables horizontally scroll without text overlap. |

# 7. API & Integration Requirements

## 7.1 External Services

| Service | Purpose | Required Configuration |
|---|---|---|
| Google Document AI | Existing OCR source for petition text | Existing `DOC_AI_*` env vars |
| Google Cloud Translation | Translation fallback for draft localization | `TRANSLATION_PROJECT_ID`, target language |
| OpenAI Responses API | Rewrite generation, checklist evaluation, translation/refinement where configured | `OPENAI_API_KEY`, model `gpt-5.2` |
| Google Gemini API | Optional generation/translation fallback | `GEMINI_API_KEY` |
| PostgreSQL / Cloud SQL | Store rewrite lifecycle data | Existing `DATABASE_URL` or Cloud SQL connector |
| PDF/DOCX renderer | Export petitioner packet | Server-side renderer using existing document generation stack |

## 7.2 Authentication and Rate Limiting

- Authentication uses existing signed session cookies for browser endpoints and existing API authentication for versioned APIs.
- Write endpoints are rate limited to 30 requests per minute per authenticated user and 100 requests per minute per station.
- Generation endpoints are limited to 10 active rewrite generations per station.
- Admin checklist writes are limited to 20 writes per hour per AI Admin.

## 7.3 Standard Error Response

All new endpoints must return this shape for non-2xx responses:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Placeholder label is required.",
    "field": "placeholder_label",
    "details": {
      "request_id": "prr-001"
    }
  }
}
```

## 7.4 Endpoint Catalogue

| Method | Path | Purpose | Success Codes | Error Codes |
|---|---|---|---|---|
| POST | `/api/rewrite-requests` | Create rewrite request from parse record | 201 | 400, 401, 403, 404, 409, 503 |
| GET | `/api/rewrite-requests/{id}` | Retrieve rewrite request detail | 200 | 401, 403, 404 |
| POST | `/api/rewrite-requests/{id}/regenerate` | Regenerate draft using same or edited gaps | 200 | 400, 403, 409, 503 |
| PATCH | `/api/rewrite-requests/{id}/drafts/{draft_id}` | Save officer draft edits | 200 | 400, 403, 404, 409 |
| GET | `/api/rewrite-requests/{id}/lineage` | Retrieve source-lineage map and unsupported fact summary | 200 | 401, 403, 404 |
| POST | `/api/rewrite-requests/{id}/semantic-validation` | Run or record semantic translation validation | 200 | 400, 403, 409, 503 |
| POST | `/api/rewrite-requests/{id}/approve` | Approve packet for petitioner | 200 | 400, 403, 409 |
| POST | `/api/rewrite-requests/{id}/export` | Export PDF/DOCX packet | 200 | 400, 403, 409, 500 |
| POST | `/api/rewrite-requests/{id}/petitioner-verification` | Record petitioner consent/refusal/correction/final verification | 200 | 400, 403, 409 |
| POST | `/api/rewrite-requests/{id}/return-values` | Capture petitioner-provided placeholder values | 200 | 400, 403, 409 |
| POST | `/api/rewrite-requests/{id}/accept` | Accept final completed petition after petitioner verification | 200 | 400, 403, 409 |
| GET | `/api/checklist-questions` | List checklist questions | 200 | 401, 403 |
| POST | `/api/checklist-questions` | Create checklist question | 201 | 400, 403, 409 |
| PATCH | `/api/checklist-questions/{id}` | Version checklist question | 200 | 400, 403, 404, 409 |
| GET | `/api/rewrite-reports/summary` | Retrieve dashboard metrics | 200 | 400, 403, 504 |
| GET | `/api/rewrite-reports/pilot-quality` | Retrieve pilot QA and misuse monitoring metrics | 200 | 400, 403, 504 |

## 7.5 Request and Response Examples

### Create Rewrite Request

Request:

```json
{
  "parse_record_id": "53edc479-9743-4fd0-ba6d-e00946ef125c",
  "case_id": "case-2026-0007",
  "basis_text_type": "refined_english_translation",
  "include_original_language": true,
  "officer_added_gaps": [
    {
      "category": "evidence",
      "display_label": "CCTV footage availability",
      "petitioner_instruction": "Mention whether CCTV footage is available near the incident location.",
      "severity": "recommended"
    }
  ]
}
```

Response:

```json
{
  "id": "prr-001",
  "parse_record_id": "53edc479-9743-4fd0-ba6d-e00946ef125c",
  "generation_status": "source_check_required",
  "source_language": "te",
  "basis_text_type": "refined_english_translation",
  "mandatory_gap_count": 2,
  "recommended_gap_count": 1,
  "source_lineage_status": "complete",
  "contradiction_check_status": "passed",
  "semantic_validation_status": "needs_review",
  "english_draft_id": "gpd-001",
  "original_language_translation_id": "pdt-001",
  "placeholder_count": 3
}
```

### Approve Assistance Packet

Request:

```json
{
  "approval_note": "Reviewed. Mandatory placeholders are accurate and petitioner can complete them.",
  "allow_english_only_issue": false,
  "lineage_review_confirmed": true,
  "semantic_validation_confirmed": true
}
```

Response:

```json
{
  "id": "prr-001",
  "generation_status": "approved",
  "approved_by": "sho-war-001",
  "approved_at": "2026-05-06T08:30:00Z",
  "packet": {
    "id": "pkt-001",
    "packet_reference_number": "WSG-RW-2026-00014",
    "packet_status": "approved"
  }
}
```

### Record Petitioner Verification

Request:

```json
{
  "verification_type": "final_verification",
  "verification_language": "te",
  "petitioner_response": "verified_final_text",
  "signature_mode": "wet_signature",
  "signed_packet_storage_uri": "gs://complaint-parser/packets/pkt-001-signed.pdf",
  "witnessed_by": "clerk-war-002",
  "witness_note": "Disclosure read in Telugu and petitioner signed the completed packet.",
  "copy_provided": true
}
```

Response:

```json
{
  "id": "pvr-002",
  "rewrite_request_id": "prr-001",
  "verification_type": "final_verification",
  "verification_language": "te",
  "petitioner_response": "verified_final_text",
  "created_at": "2026-05-06T10:35:00Z"
}
```

### Retrieve Source Lineage

Response:

```json
{
  "rewrite_request_id": "prr-001",
  "source_lineage_status": "complete",
  "unsupported_fact_count": 0,
  "spans": [
    {
      "output_span_id": "en-p002-s001",
      "source_type": "refined_english",
      "source_excerpt": "The petitioner stated that the incident happened near Warasiguda bus stop.",
      "reviewer_status": "accepted"
    },
    {
      "output_span_id": "en-ph-who-001",
      "source_type": "gap_finding",
      "source_reference_id": "gf-001",
      "reviewer_status": "accepted"
    }
  ]
}
```

### Capture Return Values

Request:

```json
{
  "returned_at": "2026-05-06T10:15:00Z",
  "placeholder_values": [
    {
      "placeholder_id": "ph-001",
      "value": "Abhishek Reddy and two unknown persons",
      "value_status": "filled"
    },
    {
      "placeholder_id": "ph-003",
      "value": "CCTV camera installed in neighbouring shop may have recorded the incident",
      "value_status": "filled"
    }
  ],
  "officer_note": "Values captured from petitioner statement at counter."
}
```

Response:

```json
{
  "id": "prr-001",
  "generation_status": "returned",
  "filled_mandatory_count": 2,
  "remaining_mandatory_count": 0,
  "next_task": {
    "id": "rrt-003",
    "task_type": "verify_returned_values",
    "assigned_role": "SHO",
    "task_status": "pending"
  }
}
```

### Create Checklist Question

Request:

```json
{
  "question_code": "ACCUSED_PHONE_KNOWN",
  "category": "who",
  "question_text": "Does the petition provide a phone number or contact detail for the accused, if known?",
  "petitioner_instruction": "If you know the accused person's phone number or contact detail, write it here.",
  "placeholder_label": "Accused contact details",
  "severity": "recommended",
  "applies_to_offence_types": ["assault", "cheating", "money_dispute"],
  "supported_languages": ["en", "te", "hi", "ur"],
  "active": true
}
```

Response:

```json
{
  "id": "cq-004",
  "question_code": "ACCUSED_PHONE_KNOWN",
  "version": 1,
  "active": true,
  "created_at": "2026-05-06T08:45:00Z"
}
```

### Dashboard Summary

Response:

```json
{
  "date_from": "2026-05-01",
  "date_to": "2026-05-06",
  "station_id": "warasiguda",
  "generated_packets": 42,
  "approved_packets": 36,
  "accepted_packets": 21,
  "average_mandatory_gaps": 2.4,
  "translation_failure_rate": 0.03,
  "top_missing_questions": [
    {"question_code": "ACCUSED_NAME_KNOWN", "missing_count": 18},
    {"question_code": "INCIDENT_EXACT_LOCATION", "missing_count": 13}
  ]
}
```

# 8. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | Generate English draft within 20 seconds for petitions under 8,000 characters; original-language translation within 20 seconds; API read endpoints under 500 ms p95 excluding external provider time. |
| Capacity | Support 100 concurrent authenticated users and 20 concurrent rewrite generations across stations. |
| Security | Enforce existing authentication, role-based authorization, PII protection before LLM calls, audit logging, CSRF protections for browser writes, and OWASP Top 10 controls. |
| Procedural Integrity | Accepted packets must have petitioner verification, source lineage, contradiction status, and audit events before downstream use. |
| Authorship Protection | UI, exports, and APIs must distinguish AI-suggested, officer-edited, petitioner-supplied, translated, and final verified text. |
| Translation Safety | Telugu, Hindi, and Urdu output must pass placeholder integrity and semantic meaning validation before bilingual approval. |
| Encryption | Use HTTPS in transit and database/storage encryption at rest. |
| Scalability | Generation workers must be stateless and horizontally scalable under Cloud Run. |
| Availability | Target 99.5% for v1; generation may degrade to English-only when translation provider fails. |
| Backup & Recovery | Database backup daily; RPO 24 hours; RTO 4 hours for rewrite data. |
| Accessibility | WCAG 2.1 AA for screen reader labels, keyboard access, focus indicators, and contrast. |
| Browser Support | Latest Chrome, Edge, Safari; Android Chrome and iOS Safari for review and print preview. |
| Localization | English UI labels in v1; generated document content supports English, Telugu, Hindi, Urdu. |
| Observability | Log generation duration, provider status, placeholder counts, error codes, and audit event IDs. |
| Pilot Governance | Track semantic drift, unsupported facts, petitioner comprehension, refusal/correction rate, officer override patterns, and sampled QA outcomes. |

# 9. Workflow & State Diagrams

## 9.1 Rewrite Request State Transitions

| Current State | Action | Triggered By | Next State | Side Effects |
|---|---|---|---|---|
| None | Generate rewrite request | Clerk/IO/SHO | drafting | Create request, evaluate checklist, create audit event. |
| drafting | Draft generated | System | source_check_required | Save placeholders, English draft, translation, lineage, validation result. |
| drafting | Provider failure | System | failed | Save error code and retry option. |
| source_check_required | Lineage, placeholder, contradiction, and semantic checks pass | Clerk/SHO/System | needs_review | Mark validation complete and create source-lineage audit event. |
| source_check_required | Unsupported fact or semantic drift found | Clerk/SHO/System | source_check_required | Require edit, regeneration, or documented supervisor override. |
| needs_review | Officer edits draft | Clerk/SHO | needs_review | Increment draft version, audit edit. |
| needs_review | SHO approves | SHO/System Admin | approved | Create petitioner packet, lock approved draft. |
| needs_review | SHO rejects | SHO/System Admin | failed | Save rejection note and review task. |
| approved | Export/print | Clerk/SHO | printed | Generate PDF, mark issued when printed. |
| approved | Share/download | Clerk/SHO | shared | Save export URI and audit event. |
| printed/shared | Petitioner consents, refuses, or requests correction | Clerk/IO | petitioner_review | Save verification/refusal/correction record. |
| petitioner_review | Petitioner returns values | Clerk/IO | returned | Save placeholder values and review task. |
| returned | Petitioner verifies final packet | Clerk/IO | petitioner_verified | Save signature/witness/copy metadata. |
| petitioner_verified | Officer accepts values | SHO/Delegated IO | accepted | Generate final completed petition text with lineage. |
| any non-final | Supersede | SHO/System Admin | superseded | Create audit event; allow new request. |

## 9.2 Placeholder State Transitions

| Current State | Action | Triggered By | Next State | Side Effects |
|---|---|---|---|---|
| blank | Officer captures value | Clerk/IO | filled | Save petitioner value and timestamp. |
| filled | Reviewer rejects value | SHO/IO | officer_rejected | Require reason and new follow-up task. |
| filled | Reviewer accepts value | SHO/IO | accepted | Eligible for final merge. |
| officer_rejected | Petitioner supplies corrected value | Clerk/IO | filled | Append previous value to audit metadata. |

## 9.3 Petitioner Verification State Transitions

| Current State | Action | Triggered By | Next State | Side Effects |
|---|---|---|---|---|
| not_presented | Disclosure read or provided | Clerk/IO | consent_presented | Store disclosure version and language. |
| consent_presented | Petitioner agrees to use packet | Petitioner via Clerk/IO | consented | Allow placeholder return capture. |
| consent_presented | Petitioner refuses packet | Petitioner via Clerk/IO | refused | Record refusal and leave original petition unchanged. |
| consent_presented | Petitioner requests correction | Petitioner via Clerk/IO | correction_requested | Route packet back to review/edit. |
| consented | Petitioner verifies completed packet | Petitioner via Clerk/IO | verified | Store signature mode, witness, timestamp, and signed packet URI when available. |
| verified | Officer accepts final text | SHO/Delegated IO | accepted | Create final completed petition text and audit event. |

## 9.4 Checklist Question State Transitions

| Current State | Action | Triggered By | Next State | Side Effects |
|---|---|---|---|---|
| draft | Submit for activation | AI Admin | pending_review | Notify System Admin/SHO. |
| pending_review | Approve | System Admin/SHO | active | Available for future evaluations. |
| active | Edit material content | AI Admin | active_new_version | Previous version retained; new version created. |
| active | Deactivate | AI Admin/System Admin | inactive | Future evaluations skip question. |
| inactive | Reactivate | System Admin | active_new_version | New version required. |

# 10. Notification & Communication Requirements

| Event | Channel | Recipient | Trigger Condition | Message Template | Opt-out |
|---|---|---|---|---|---|
| Rewrite generation failed | In-app | Initiating user | `generation_status=failed` | `Rewrite generation failed for {file_name}: {error_message}.` | No |
| Packet needs approval | In-app | SHO | Request enters `needs_review` with mandatory gaps | `Rewrite packet {packet_reference_number} requires approval.` | No |
| Packet approved | In-app | Clerk/IO assigned | SHO approves packet | `Rewrite packet {packet_reference_number} is approved for issue.` | No |
| Source lineage blocked | In-app | Initiating user/SHO | Unsupported fact or incomplete lineage found | `Packet {packet_reference_number} requires source-lineage correction before approval.` | No |
| Semantic translation review required | In-app | SHO/Bilingual reviewer | Telugu/Hindi/Urdu packet needs semantic validation | `Packet {packet_reference_number} needs language meaning review.` | No |
| Petitioner refused or requested correction | In-app | SHO/assigned officer | Verification record status is refusal/correction | `Petitioner requested correction or refused packet {packet_reference_number}.` | No |
| Petitioner return pending review | In-app | SHO/IO | Clerk submits returned values | `Returned values for {packet_reference_number} require verification.` | No |
| Pilot QA corrective action | In-app | SHO/System Admin | Pilot evaluation records medium/high risk | `Pilot QA found an issue in packet {packet_reference_number}: {corrective_action}.` | No |
| Checklist question pending activation | In-app | System Admin/SHO | AI Admin submits new question | `Checklist question {question_code} is pending activation.` | No |
| Daily rewrite summary | Email or in-app | SHO/Senior Command | Scheduled 08:00 local time | `Yesterday: {generated} generated, {accepted} accepted, top missing field: {top_gap}.` | Yes for email, no for in-app summary |

# 11. Reporting & Analytics

| Report | Audience | Data Sources | Filters | Refresh | Metrics |
|---|---|---|---|---|---|
| Rewrite Operations Summary | SHO, Senior Command | PetitionRewriteRequest, PetitionerPacket | Date, station, status, language | 15 min | Generated, approved, printed, returned, accepted counts |
| Gap Frequency Report | SHO, AI Admin, Senior Command | GapFinding, ChecklistEvaluation | Date, category, offence type, severity | 15 min | Top missing fields, mandatory vs recommended rates |
| Placeholder Completion Report | SHO, IO | PetitionPlaceholder | Packet, station, category | Real-time | Filled, blank, rejected, accepted counts |
| Translation Quality Report | AI Admin, System Admin | PetitionDraftTranslation | Language, provider, model | 15 min | Success rate, placeholder integrity failures, semantic drift failures, provider failures |
| Source Lineage Report | SHO, System Admin | SourceLineageMap, GeneratedPetitionDraft | Station, language, status | 15 min | Lineage coverage, unsupported fact count, rejected spans |
| Petitioner Verification Report | SHO, Senior Command | PetitionerVerificationRecord, PetitionerPacket | Station, language, date | 15 min | Consent, refusal, correction, final verification, copy-provided counts |
| Pilot Quality Report | Senior Command, System Admin | RewritePilotEvaluation | Station, language, sample reason | 15 min | Semantic drift rate, unsupported fact rate, comprehension status, officer oversteer risk |
| Review SLA Report | SHO, Senior Command | RewriteReviewTask | Assigned role, station, date | 15 min | Pending, overdue, median approval time |
| Audit Export | System Admin | RewriteAuditEvent | Date, actor, action type, request ID | On demand | Full event list with hashes |

# 12. Migration & Launch Plan

## 12.1 Data Migration

- Add new tables for rewrite requests, checklist questions, evaluations, gaps, placeholders, drafts, translations, packets, source lineage, petitioner verification, pilot evaluation, review tasks, and audit events.
- Seed baseline checklist questions for 5W+1H categories and evidence/contact categories.
- Backfill no assistance packets automatically for old parse records in v1. Officers can generate packets on demand for old records.
- Existing `parse_records.parsed_output` remains unchanged except optional reference metadata to latest rewrite request.

## 12.2 Phased Rollout

| Phase | Scope | Exit Criteria |
|---|---|---|
| Phase 1 | English missing-information packet from existing `parse_records`, refined English, 5W+1H gaps, protected placeholders, officer review, source-lineage check, and export preview | 20 station test packets reviewed; 100% placeholder integrity; 100% lineage coverage; 0 unsupported facts in sampled packets. |
| Phase 2 | Petitioner disclosure, consent/refusal/correction capture, verification/signature metadata, and final acceptance gate | 20 returned packets processed; 100% accepted packets have verification records and no manual DB correction. |
| Phase 3 | Checklist-question evaluation and admin configuration | Active checklist version seeded; 10 admin edits tested with audit history; duplicate gap merge validated. |
| Phase 4 | Telugu, Hindi, Urdu original-language translations with semantic validation and Urdu RTL rendering | 30 multilingual packets verified; 95% placeholder preservation; semantic drift below pilot threshold. |
| Phase 5 | Pilot QA dashboards, misuse monitoring, station reporting, and broader rollout decision | SHO and Senior Command dashboards validated; pilot quality report meets exit thresholds. |

## 12.3 Go-Live Checklist

- Database migrations applied successfully.
- Baseline checklist questions seeded and approved.
- Rewrite prompt version locked as `petition-rewrite-v1`.
- Translation placeholder integrity tests passing for Telugu, Hindi, Urdu.
- Source-lineage tests passing for generated English, officer edits, translated spans, and final accepted text.
- Semantic translation QA rubric approved for Telugu, Hindi, and Urdu.
- Petitioner disclosure and refusal/correction language approved in English and supported original languages.
- Role permissions tested for Clerk, SHO, IO, AI Admin, System Admin, Senior Command.
- PDF export verified for English and Urdu right-to-left rendering.
- Audit events verified for generation, source-lineage check, semantic validation, consent/refusal/correction, edit, approval, export, return, verification, and acceptance.
- Training note prepared for front-desk officers explaining petitioner packet workflow, non-coercion expectations, refusal rights, and final verification requirements.

# 13. Glossary

| Term | Definition |
|---|---|
| Refined English Translation | Polished English rendering of OCR/translation text used as the source for analysis and rewrite generation. |
| 5W+1H | Structured analysis of Who, What, When, Where, Why, and How facts in a petition. |
| Checklist Question | Configurable question evaluated against petition content to identify required or recommended missing information. |
| Gap Finding | Normalized missing, weak, or uncertain information item derived from 5W+1H or checklist evaluation. |
| Placeholder | Inline token inserted in the assistance draft where petitioner must add missing information. |
| Missing-Information Assistance Packet | English and original-language petitioner-facing document containing source-grounded petition text, placeholders, disclosure, and completion instructions. |
| Rewrite Packet | Legacy/internal name for the Missing-Information Assistance Packet. User-facing screens should avoid this phrase where it implies police authorship. |
| Original-Language Draft | Translation of the placeholder-bearing English rewrite into the petitioner's original language. |
| Placeholder Integrity | Validation that every placeholder token in English draft appears exactly in translated draft. |
| Semantic Translation Validation | Review confirming translated text preserves names, dates, chronology, uncertainty, allegations, and requested action. |
| Source Lineage | Mapping from generated or translated text back to refined English, original OCR, gap finding, officer edit, petitioner value, or disclosure template. |
| Petitioner Verification | Recorded confirmation, refusal, correction request, or signature event proving whether the petitioner accepted the final wording. |
| Returned Values | Information added by petitioner after receiving the assistance packet. |
| Accepted Rewritten Petition | Final completed petition after officer review of petitioner-supplied placeholder values. |

# 14. Appendices

## 14.1 Baseline Placeholder Categories

| Category | Example Placeholder | Mandatory When |
|---|---|---|
| who | `[[ADD_WHO_001: Name of accused person]]` | Accused identity is required and absent or unclear. |
| what | `[[ADD_WHAT_001: Exact property or injury details]]` | Incident object, loss, or injury is absent. |
| when | `[[ADD_WHEN_001: Exact date and time]]` | Date/time is missing or too vague for inquiry. |
| where | `[[ADD_WHERE_001: Exact incident location]]` | Location cannot identify jurisdiction or scene. |
| why | `[[ADD_WHY_001: Reason or background, if known]]` | Motive/background is material to complaint type. |
| how | `[[ADD_HOW_001: How the incident happened]]` | Sequence or method is unclear. |
| evidence | `[[ADD_EVIDENCE_001: CCTV, witnesses, documents, or photos]]` | Complaint references proof vaguely or no proof detail is present. |
| contact | `[[ADD_CONTACT_001: Contact details of relevant person]]` | Follow-up contact is needed and not available. |

## 14.2 Placeholder Translation Rules

1. Before translation, replace each placeholder token with a protected marker such as `[[PH_001]]`.
2. Translate the surrounding prose into target language.
3. Restore the full placeholder token after translation.
4. Count tokens before and after restoration.
5. Reject translation if token sets differ.
6. For Urdu, render the prose right-to-left while keeping placeholder token text readable and unchanged.

## 14.3 Prompt Control Requirements

- System prompt must state that the model is creating a missing-information assistance packet for petitioner completion, not authoring a replacement complaint and not drafting an FIR.
- Prompt must instruct model to preserve all known facts from refined English.
- Prompt must instruct model to insert placeholders only from supplied `GapFinding` objects.
- Prompt must prohibit invented facts.
- Prompt must require a standard petition structure.
- Prompt must preserve uncertainty markers and avoid converting approximate or unknown facts into definite claims.
- Prompt must return structured JSON with `body_markdown`, `placeholder_insertions`, `lineage_map`, `contradiction_risks`, and `quality_notes`.

## 14.4 LLM Output JSON Schema

```json
{
  "body_markdown": "string",
  "body_plain_text": "string",
  "placeholder_insertions": [
    {
      "token": "[[ADD_WHO_001: Name of accused person]]",
      "gap_finding_id": "gf-001",
      "inserted_after_anchor": "string",
      "display_order": 1
    }
  ],
  "lineage_map": [
    {
      "output_span_id": "en-p002-s001",
      "output_text": "string",
      "source_type": "refined_english",
      "source_reference_id": "parse_record.text.refined_english_translation",
      "source_excerpt": "string",
      "source_char_start": 120,
      "source_char_end": 210,
      "lineage_confidence": 0.88
    }
  ],
  "contradiction_risks": [
    {
      "output_span_id": "en-p003-s001",
      "risk_type": "uncertainty_removed",
      "source_excerpt": "around 8 PM",
      "generated_excerpt": "at 8:00 PM",
      "severity": "blocking"
    }
  ],
  "quality_notes": [
    "All mandatory placeholders are present."
  ]
}
```

Validation rules:

1. `placeholder_insertions[*].token` must match the deterministic placeholder list exactly.
2. `lineage_map` must cover all generated factual spans and placeholders.
3. Blocking contradiction risks prevent approval.
4. Unknown fields are rejected unless explicitly versioned in the prompt contract.

## 14.5 Translation QA Rubric

| Area | Required Check |
|---|---|
| Names and identities | Names, relationships, roles, and "unknown person" language must preserve meaning. |
| Dates and times | Exact, approximate, and unknown dates/times must not be converted into different certainty levels. |
| Locations | Jurisdiction, address, landmark, and village/station names must remain recognizable. |
| Allegations | Alleged acts must not be softened, strengthened, or replaced with legal conclusions. |
| Requested action | The petitioner's requested action must remain a request, not an FIR decision or legal finding. |
| Placeholders | Tokens must remain exact, visible, and placed near corresponding missing fact context. |
| Urdu rendering | Right-to-left text, punctuation, numerals, and placeholder readability must be checked in PDF and browser view. |

## 14.6 Petitioner Disclosure Block

Minimum packet disclosure text:

> This document is generated to help you identify and add missing information. It is not your final complaint unless you verify it and sign or confirm it. You may refuse this document, ask for corrections, provide your own revised complaint, or state that you do not know a requested detail. Please read or ask an officer to read the full document in a language you understand before signing.

The same disclosure must be available in Telugu, Hindi, and Urdu before those languages are used for petitioner-facing packets.

## 14.7 Pilot Exit Thresholds

| Metric | Pilot Exit Threshold |
|---|---|
| Unsupported fact rate in sampled accepted packets | 0 |
| Placeholder integrity | 100% for accepted packets |
| Source-lineage coverage | 100% for generated factual spans and placeholders |
| Semantic translation drift | Less than 2% material drift in sampled Telugu/Hindi/Urdu packets |
| Petitioner verification completeness | 100% for accepted packets |
| Refusal/correction recording | 100% of known refusals and correction requests |
| Officer override review | 100% of high-risk overrides sampled by supervisor |

## 14.8 Quality Checklist Result

| Check | Result |
|---|---|
| Data model supports schema creation | Pass |
| Functional requirements are numbered and testable | Pass |
| UI screens are described with layout and components | Pass |
| Design system expectation is defined | Pass |
| Error handling is specific | Pass |
| Every functional entity is present in data model | Pass |
| Every entity has sample data | Pass |
| Complex API endpoints include JSON examples | Pass |
| Every FR includes user story and acceptance criteria | Pass |
| Glossary terms are used in document | Pass |
| Adversarial council observations are incorporated | Pass |
| Petitioner authorship and verification are explicitly protected | Pass |
| Source lineage and semantic translation QA are specified | Pass |
