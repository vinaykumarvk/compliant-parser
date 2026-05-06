# Development Plan: KIS Next Hardening and Automation

## Overview

KIS is live, connected to compliant-parser, using real OpenAI reasoning, and populated with graph/wiki/vector artifacts for uploaded documents. The next work should convert the manual indexing and smoke process into a governed production workflow with stronger retrieval quality, admin controls, and operational evidence.

## Assumptions

- `knowledge-intelligence-service` remains a standalone reusable service.
- `police-iqw` remains the first production domain and `kb_0873ac3ae2b14e8d` remains the active knowledge base.
- Uploaded complaint documents should be indexed after successful parsing, but source text must be masked before it is stored or sent to LLM providers.

## Codebase Findings

- `app.py` - Upload parsing currently saves parse history but does not automatically push parsed document content into KIS.
- `kis_client.py` - Existing adapter supports KIS BNS reasoning and hybrid search, but not source ingestion/fact/wiki/snapshot APIs.
- `services/knowledge-intelligence-service/src/api/sources.py` - KIS already supports source text ingestion and vector chunk creation.
- `services/knowledge-intelligence-service/src/api/facts.py` and `src/api/graph.py` - Fact creation, review, and graph promotion exist.
- `services/knowledge-intelligence-service/src/api/wiki.py` - Source-targeted wiki article compilation exists.
- `services/knowledge-intelligence-service/src/reasoning/executor.py` - BNS reasoning now pins legal-reference context and uses structured LLM output.

## Architecture Decisions

- **Automate at the compliant-parser boundary**: Trigger KIS indexing after parse persistence so each uploaded document is indexed exactly once with the parse record ID as idempotency metadata.
- **Keep graph extraction conservative**: Start with deterministic non-PII facts from parsed fields, then add LLM-assisted fact extraction only after evaluation coverage exists.
- **Separate legal reference from uploaded complaints**: Keep BNS legal sources pinned as reference context so complaint uploads do not crowd out legal sections.
- **Publish snapshots behind quality gates**: Indexing may create draft state, but snapshot publication should remain gated.

## Dependency Graph

```text
Phase 1 --> Phase 2 --> Phase 4 --> Phase 5
Phase 3 -----------/       |
                           --> Phase 6
```

## Conventions

- Use `IQW_KIS_*` variables for compliant-parser integration and `KIS_*` variables for KIS service config.
- Do not store raw PII in KIS source text; mask before source ingestion.
- Add tests in the same phase as implementation.
- Verify with local tests and Cloud Run smoke checks after deployment.

---

## Phase 1: Automatic Upload Indexing
**Dependencies:** none

**Description:**
Automatically create KIS source/vector/wiki/graph artifacts whenever compliant-parser successfully parses and persists an uploaded document.

**Tasks:**
1. Extend `kis_client.py` with source ingestion, fact creation/review, graph promotion, wiki compile, quality gate, and snapshot APIs.
2. Add a post-parse indexing function that builds masked KIS source text from `parsed_output`.
3. Call the indexing function from `app.py` after `save_parse_record` succeeds for both normal and streaming parse paths.
4. Add idempotency metadata using complaint-parser record ID to avoid duplicate indexing.

**Files to create/modify:**
- `kis_client.py` - Add KIS write/admin API methods.
- `app.py` - Trigger KIS indexing after parse persistence.
- `tests/test_kis_client.py` and `tests/test_app.py` - Add success/failure/idempotency coverage.

**Acceptance criteria:**
- A newly uploaded document creates a KIS source and vector chunks automatically.
- KIS indexing failure does not break parse persistence when fallback is enabled.
- No raw phone, vehicle, Aadhaar, email, or detected person-name tokens are sent to KIS.

---

## Phase 2: Deterministic Graph and Wiki Enrichment
**Dependencies:** Phase 1

**Description:**
Make graph/wiki creation predictable and reviewable from parsed complaint fields.

**Tasks:**
1. Extract deterministic facts for document type, language, police station, offence category, proposed BNS sections, and parse confidence.
2. Promote approved facts into graph edges with source citations.
3. Compile one source-backed wiki article per uploaded document.
4. Add duplicate fact detection keyed by record ID, predicate, and object.

**Files to create/modify:**
- `kis_client.py` - Add higher-level document indexing helper.
- `tests/test_kis_client.py` - Validate fact/wiki payloads and duplicate avoidance.
- `docs/operations/kis-local-deployment.md` - Document automatic indexing behavior.

**Acceptance criteria:**
- Each uploaded document has a source-backed wiki article.
- Each uploaded document has graph facts with source citations.
- Re-indexing the same parse record is idempotent.

---

## Phase 3: Retrieval Quality Evaluation
**Dependencies:** none

**Description:**
Create measurable retrieval quality checks before adding more LLM-assisted enrichment.

**Tasks:**
1. Add golden queries for uploaded complaint retrieval and BNS legal section retrieval.
2. Add regression checks that BNS legal references remain retrievable after uploaded complaint ingestion.
3. Add an evaluation summary endpoint or report for source counts and recall.

**Files to create/modify:**
- `services/knowledge-intelligence-service/tests/golden_sets/` - Add uploaded-document and BNS reference cases.
- `services/knowledge-intelligence-service/tests/test_evaluation.py` - Extend recall tests.
- `docs/reviews/` - Add retrieval quality evidence report.

**Acceptance criteria:**
- BNS legal queries return legal-reference chunks.
- Uploaded complaint queries return uploaded document source/wiki/fact results.
- Evaluation output is repeatable locally and usable before deployment.

---

## Phase 4: Admin Operations Surface
**Dependencies:** Phase 2, Phase 3

**Description:**
Expose KIS indexing and knowledge health to admins without requiring scripts.

**Tasks:**
1. Add admin status for latest KIS snapshot, source count, chunk count, graph count, wiki count, and quality gate status.
2. Add an admin action to re-index a parse record.
3. Add an admin action to publish a KIS snapshot after quality gates pass.

**Files to create/modify:**
- `api_v1.py` - Extend admin external/KIS status endpoints.
- `index.html` and related static files - Add compact admin status/action UI if needed.
- `tests/test_external_interfaces.py` - Add non-secret KIS status coverage.

**Acceptance criteria:**
- System Admin can see KIS index health without secrets.
- System Admin can re-index one document and publish a passing snapshot.
- Failed quality gates are visible with failed check names.

---

## Phase 5: LLM-Assisted Fact Extraction
**Dependencies:** Phase 4

**Description:**
Use governed LLM calls to suggest richer graph facts only after deterministic indexing and retrieval evaluation are stable.

**Tasks:**
1. Define a strict JSON schema for fact extraction.
2. Run LLM fact extraction with masked text only.
3. Mark LLM facts as candidate until AI Admin approval.
4. Add uncertainty and review queue integration.

**Files to create/modify:**
- `services/knowledge-intelligence-service/src/reasoning/` - Add fact extraction pattern/schema.
- `services/knowledge-intelligence-service/src/api/` - Add review endpoints if missing.
- `tests/` - Add schema rejection and PII masking tests.

**Acceptance criteria:**
- LLM fact extraction never stores unreviewed facts as approved graph edges.
- Invalid LLM fact JSON is rejected.
- PII masking evidence is captured in usage logs.

---

## Phase 6: Release Verification
**Dependencies:** Phase 1, Phase 2, Phase 3, Phase 4, Phase 5

**Description:**
Validate the full production workflow end to end.

**Tasks:**
1. Run KIS, compliant-parser adapter, app, privacy, and external interface tests.
2. Deploy to Cloud Run.
3. Upload one representative complaint and confirm automatic KIS indexing.
4. Verify hybrid retrieval returns vector, fact, and wiki results.
5. Verify BNS reasoning returns live LLM output with canonical BNS section code.
6. Update deployment/readiness docs.

**Files to create/modify:**
- `docs/reviews/deploy-readiness-knowledge-intelligence-service-2026-05-05.md` - Append final automated-indexing evidence.

**Acceptance criteria:**
- Tests pass.
- Cloud Run health checks pass.
- New upload automatically appears in KIS as source/vector/fact/wiki artifacts.
- Snapshot quality gates pass and snapshot is published.
