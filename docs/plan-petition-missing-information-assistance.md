# Development Plan: Petition Missing Information Assistance

## Overview

Implement the council-updated BRD in `docs/petition-rewrite-assistance-brd.md` as a staged petitioner assistance workflow. The first release creates a source-grounded English missing-information packet from existing parse history, refined English text, and 5W+1H gaps, then later adds petitioner verification, multilingual semantic QA, checklist administration, and pilot reporting.

## Assumptions

- The first implementation uses the existing authenticated browser session and current documents page before adding a separate citizen portal.
- Phase 1 uses deterministic generation from refined English plus existing `gaps`; LLM drafting is deferred until the source-lineage and placeholder gates are stable.
- `parse_records.parsed_output.text.refined_english_translation` is the primary source. Raw English fallback is allowed only with a visible warning and stored lower-confidence basis type.
- Existing role maturity is mixed. The initial browser path can use current authentication, while Phase 2/3 should align API permissions with `Clerk`, `SHO`, `IO`, and `System_Admin` where available.
- The feature must preserve original OCR, raw English, and refined English. Accepted packet text must never overwrite existing parse output.
- Telugu/Hindi/Urdu translation is a later phase because the council identified semantic drift as a release risk.
- Existing dirty worktree changes are not part of this plan and should not be reverted during implementation.

## Codebase Findings

- `database.py` defines legacy `parse_records` as a SQLAlchemy Core table and `initialize_database()` runs `metadata.create_all` plus `migrations.apply_schema_migrations`.
- `models.py` contains SQLAlchemy ORM entities, shared enums, audit fields, and generated-document/template models, but no petition assistance entities yet.
- `migrations.py` uses lightweight idempotent migration helpers such as `_table_exists`, `_add_column_if_missing`, and direct DDL.
- `app.py` serves the current SPA and browser-session endpoints such as `/api/history`, `/api/history/{record_id}`, and `/api/history/{record_id}/file`.
- `api_v1.py` is mounted under `/api/v1` and provides standardized errors through `raise_api_error`, role dependencies, and routers for cases, templates, senior dashboard, and audit logs.
- `complaint_parsing.py` already stores `text.ocr_text`, `text.raw_english_translation`, `text.refined_english_translation`, `language.translation_refinement_status`, `gaps`, `summary.review_questions`, and `meta.text_used_for_extraction`.
- `index.html` already has the documents split pane with OCR, Raw English, and Refined English tabs, plus result rendering for gap summaries and 5W+1H detail.
- `tests/test_app.py` has mock-engine patterns for app-level history endpoint tests.
- `tests/test_document_generator.py` covers placeholder extraction and document generation helpers that can inform export behavior, but assistance packet placeholders use a different protected-token format.

## Architecture Decisions

- **Dedicated service module:** Create `petition_assistance.py` for packet generation, gap normalization, placeholder creation, source-lineage checks, contradiction heuristics, export text, and DTO assembly.
- **Core persistence in SQLAlchemy Core first:** Define minimal Phase 1 tables in `database.py` and idempotent DDL in `migrations.py` so browser endpoints can use the same pattern as `parse_records`.
- **Browser endpoints first, v1 parity second:** Add `/api/rewrite-requests` endpoints in `app.py` for the current SPA, then mirror stable contracts under `/api/v1/rewrite-requests` when role-scoped API access is ready.
- **Deterministic Phase 1 draft:** Produce a conservative English assistance draft with source narrative, missing details section, protected placeholders, disclosure, and signature block. Do not call an LLM until the exact JSON contract and lineage validators are implemented.
- **Lineage as a release gate:** Every factual paragraph and placeholder must have a `SourceLineageMap` equivalent record before approval/export.
- **No automatic legal conclusions:** The packet must not register FIRs, propose legal sections, resolve contradictions, or turn uncertain facts into definite statements.
- **UI stays operational, not decorative:** Extend the existing dense document review layout with an assistance packet action and review tabs; avoid a separate landing page or marketing flow.

## Dependency Graph

```text
Phase 1 --> Phase 2 --> Phase 3 --> Phase 7
                     \-> Phase 4 --> Phase 7
Phase 5 ---------------------------> Phase 7
Phase 6 ---------------------------> Phase 7
```

## Conventions

- Use existing CSS custom properties and compact operational panels in `index.html`.
- Use protected placeholder tokens in the format `[[ADD_<CATEGORY>_<NNN>: <label>]]`.
- Store hashes for basis text and generated body using SHA-256.
- Return stable JSON error codes such as `MISSING_BASIS_TEXT`, `ACTIVE_REQUEST_EXISTS`, `SOURCE_LINEAGE_INCOMPLETE`, and `UNSUPPORTED_FACT_DETECTED`.
- Add focused tests in the same phase as the changed behavior.
- Keep generated packet text, petitioner values, and lineage separate from original parse history fields.
- For Phase 1, export can be HTML/plain text or browser print preview; PDF/DOCX hardening can follow after the review workflow is accepted.

---

## Phase 1: Deterministic Packet Core and Persistence

**Dependencies:** none

**Description:**
Build the backend foundation for a source-grounded English missing-information assistance packet from an existing `parse_records` row. This phase proves protected placeholders, gap normalization, source lineage, and unsupported-fact gates without adding LLM or multilingual complexity.

**Tasks:**
1. Create `petition_assistance.py` with pure functions for basis-text selection, gap normalization, deterministic placeholder generation, English packet body generation, source-lineage creation, contradiction/unsupported-fact validation, and response DTO formatting.
2. Add minimal Phase 1 tables in `database.py`: `petition_rewrite_requests`, `petition_placeholders`, `generated_petition_drafts`, `source_lineage_maps`, and `rewrite_audit_events`.
3. Add idempotent migration DDL in `migrations.py` for the Phase 1 tables and indexes.
4. Implement packet status values for `drafting`, `source_check_required`, `needs_review`, `approved`, `printed`, `shared`, `superseded`, and `failed`.
5. Add unit tests for gap normalization, duplicate placeholder merging, token formatting, lineage coverage, basis fallback warnings, and unsupported-fact detection.

**Files to create/modify:**
- `petition_assistance.py` - New service module.
- `database.py` - Core table definitions and indexes.
- `migrations.py` - Idempotent table/index creation.
- `tests/test_petition_assistance.py` - Service and validation tests.
- `tests/test_integration.py` - Table coexistence or migration smoke coverage.

**Acceptance criteria:**
- A parse record with refined English and missing/uncertain gaps can produce an English assistance packet DTO with placeholders and lineage.
- Placeholder tokens are deterministic, unique, and deduplicated by normalized category/field/label.
- Generated factual spans map to refined English or gap findings.
- Unsupported fact count is zero for deterministic output.
- Tests pass for empty gaps, missing refined English, raw English fallback, duplicate gaps, and Telugu/Hindi/Urdu source metadata.

---

## Phase 2: Browser API Endpoints and Review State

**Dependencies:** Phase 1

**Description:**
Expose the Phase 1 packet lifecycle to the current SPA through authenticated endpoints and persist review decisions/audit events.

**Tasks:**
1. Add browser-session endpoints in `app.py`: `POST /api/rewrite-requests`, `GET /api/rewrite-requests/{id}`, `PATCH /api/rewrite-requests/{id}/drafts/{draft_id}`, `POST /api/rewrite-requests/{id}/approve`, and `POST /api/rewrite-requests/{id}/export`.
2. Validate active request conflicts per parse record and allow new requests only when prior active request is final or superseded.
3. Persist officer edits with draft version increments and refreshed lineage status.
4. Block approval when placeholder integrity, source lineage, contradiction, or unsupported-fact checks fail.
5. Add audit events for generated, source-lineage checked, edited, approved, exported, superseded, and failed actions.
6. Add app endpoint tests using the existing mock-engine style in `tests/test_app.py`.

**Files to create/modify:**
- `app.py` - Browser endpoints and request/response models.
- `petition_assistance.py` - Persistence helpers and review transition functions.
- `tests/test_app.py` - Endpoint coverage for create/get/edit/approve/export.
- `tests/test_petition_assistance.py` - State transition tests.

**Acceptance criteria:**
- Authenticated user can create and retrieve a packet from an existing parse record.
- Unauthenticated create/get/edit/approve/export requests return 401.
- Approval is blocked if lineage is incomplete or unsupported facts exist.
- Officer edits create a new draft version and audit event.
- Export returns a printable response with disclosure, placeholders, lineage reference, and signature block.

---

## Phase 3: Documents Page Assistance Packet UI

**Dependencies:** Phase 2

**Description:**
Add the officer-facing UI flow on the documents page: generate an assistance packet, review source/gaps/draft/lineage, approve, and preview export.

**Tasks:**
1. Add a "Generate Assistance Packet" action to the documents result toolbar and gap analysis area in `index.html`.
2. Add an Assistance Packet Review panel with tabs for Source, Gaps, English Draft, Lineage & Validation, and Export Preview.
3. Render placeholder table grouped by category/severity, lineage badges, validation state, and approval/export actions.
4. Add editable draft support with save, validation refresh, and version indicator.
5. Add loading, empty, error, validation-blocked, and approved states.
6. Verify responsive behavior for the existing split-pane layout and run JavaScript parse checks.

**Files to create/modify:**
- `index.html` - Markup, CSS, and JavaScript for packet generation/review/export.
- `tests/test_app.py` - Optional static HTML assertions for key IDs if existing test style supports it.

**Acceptance criteria:**
- Officer can generate a packet from a loaded document/history record without leaving the documents workflow.
- UI shows refined English source, missing gaps, generated English packet, placeholders, and lineage validation.
- Approval button is disabled until backend validation allows approval.
- Export preview includes disclosure and petitioner signature block.
- Inline JavaScript parses successfully.

---

## Phase 4: Petitioner Verification and Return Capture

**Dependencies:** Phase 2, Phase 3

**Description:**
Add consent/refusal/correction capture, petitioner-provided placeholder values, final verification metadata, and acceptance gates.

**Tasks:**
1. Add persistence for `petitioner_packets` and `petitioner_verification_records`.
2. Add endpoint support for `POST /api/rewrite-requests/{id}/petitioner-verification`, `POST /api/rewrite-requests/{id}/return-values`, and `POST /api/rewrite-requests/{id}/accept`.
3. Add placeholder value statuses: `blank`, `filled`, `accepted_unknown`, `needs_follow_up`, `officer_rejected`, and `accepted`.
4. Add final merge logic that replaces only accepted placeholders and preserves original parse output.
5. Add UI controls for consent, refusal, correction request, verification language, signature mode, witness note, signed packet URI, and copy-provided timestamp.
6. Add tests for refusal/correction paths, missing verification block, accepted unknown values, contradiction warnings, and final accepted packet lineage.

**Files to create/modify:**
- `database.py` - Petitioner packet and verification tables.
- `migrations.py` - Idempotent migration DDL.
- `petition_assistance.py` - Return capture, verification, final merge.
- `app.py` - Return/verification/accept endpoints.
- `index.html` - Return capture and verification UI.
- `tests/test_petition_assistance.py` - Merge and verification tests.
- `tests/test_app.py` - Endpoint tests.

**Acceptance criteria:**
- Final acceptance is impossible without petitioner verification metadata.
- Refusal and correction requests are recorded and do not overwrite or delete the original petition.
- Accepted final text shows source, AI assistance, officer edit, and petitioner value lineage.
- `accepted_unknown` and `needs_follow_up` are supported without forcing invented values.

---

## Phase 5: Multilingual Rendering and Semantic QA

**Dependencies:** Phase 1, Phase 2

**Description:**
Add Telugu, Hindi, and Urdu original-language assistance packet rendering with protected placeholders and semantic validation.

**Tasks:**
1. Reuse or extract existing translation provider helpers from `complaint_parsing.py` into a safe service boundary if needed.
2. Add `petition_draft_translations` persistence with placeholder integrity and semantic validation fields.
3. Implement placeholder protection/restoration for translation.
4. Add semantic validation through bilingual officer review fields first, then optional back-translation or model review behind configuration.
5. Add Urdu RTL browser and export rendering checks.
6. Add tests for Telugu/Hindi/Urdu placeholder preservation, semantic validation failure, English-only override reason, and Urdu direction metadata.

**Files to create/modify:**
- `petition_assistance.py` - Translation orchestration and semantic validation DTOs.
- `database.py` - Translation table.
- `migrations.py` - Translation migration DDL.
- `app.py` - Translation validation endpoints or fields on existing detail response.
- `index.html` - Original-language draft tab, semantic QA panel, Urdu RTL handling.
- `tests/test_petition_assistance.py` - Translation placeholder and validation tests.

**Acceptance criteria:**
- Telugu, Hindi, and Urdu packets preserve all placeholder tokens exactly.
- Bilingual approval is blocked until semantic validation passes or an SHO override reason is recorded.
- Urdu displays right-to-left prose while keeping placeholder tokens readable.
- Translation failure degrades to English-only with a visible reason and no false bilingual approval.

---

## Phase 6: Checklist Questions, LLM Contract, and Pilot Reporting

**Dependencies:** Phase 1, Phase 2, Phase 4, Phase 5

**Description:**
Add configurable checklist evaluations, optional LLM drafting under a strict JSON schema, and pilot accountability reporting.

**Tasks:**
1. Add checklist question/evaluation persistence and admin endpoints after baseline packet workflow is proven.
2. Implement duplicate gap merge across 5W+1H, checklist, and officer-added gaps.
3. Add the `petition-rewrite-v1` prompt contract only after JSON schema validation, placeholder validation, source-lineage validation, and contradiction gates are in place.
4. Add pilot evaluation persistence and reports for semantic drift, unsupported facts, petitioner comprehension, refusal/correction frequency, and officer override patterns.
5. Add senior/admin dashboard widgets for pilot quality warnings before volume metrics.
6. Add tests for checklist versioning, LLM JSON rejection, unsupported fact blocking, and pilot exit thresholds.

**Files to create/modify:**
- `petition_assistance.py` - Checklist evaluation adapter, LLM contract validation, pilot metrics.
- `database.py` - Checklist and pilot evaluation tables.
- `migrations.py` - Checklist/pilot migration DDL.
- `app.py` and/or `api_v1.py` - Admin/checklist/report endpoints.
- `index.html` - Checklist admin and pilot reporting UI.
- `tests/test_petition_assistance.py` - Contract and reporting tests.

**Acceptance criteria:**
- Checklist questions can be versioned without changing historical evaluations.
- LLM output is rejected if it omits placeholders, invents facts, lacks lineage, or includes blocking contradiction risks.
- Pilot reports show quality metrics separately from speed/volume metrics.
- Broader rollout can be blocked by pilot QA thresholds.

---

## Phase 7: Integration, Regression, and Local Deployment Verification

**Dependencies:** Phase 3, Phase 4, Phase 5, Phase 6

**Description:**
Validate the full lifecycle, regression surface, database migrations, UI behavior, and local deployment readiness.

**Tasks:**
1. Run Python compile checks for changed modules.
2. Run focused tests for `petition_assistance.py`, app endpoints, migrations, and UI static checks.
3. Run existing parser/history/document-generator regression tests.
4. Run JavaScript parse checks for `index.html`.
5. Start the local app and smoke-test login, history load, packet generation, review, export, return capture, and acceptance.
6. Save a validation report under `docs/test-validation-petition-missing-information-assistance-2026-05-06.md`.

**Files to create/modify:**
- `docs/test-validation-petition-missing-information-assistance-2026-05-06.md` - Validation evidence and any residual risks.
- Optional `PROJECT_SUMMARY.md` update after implementation is complete.

**Acceptance criteria:**
- Focused feature tests pass.
- Relevant existing regression tests pass or documented blockers are isolated and explained.
- Database migrations are idempotent against an empty database and an existing database.
- Browser workflow is manually smoke-tested locally.
- Validation report links BRD, council report, plan, implementation, tests, and remaining rollout risks.
