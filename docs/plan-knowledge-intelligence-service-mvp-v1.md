# Development Plan: Knowledge Intelligence Service MVP v1

## Overview

Build the Knowledge Intelligence Service (KIS) MVP v1 from the revised BRD in `docs/knowledge-intelligence-service-brd.md`. MVP v1 delivers a standalone, reusable FastAPI service with domain-scoped knowledge bases, templates, ingestion, masked embeddings, vector and hybrid retrieval, graph/fact/wiki support, published snapshots, LLM provider governance, BNS mapping reasoning, auditability, and a compliant-parser integration adapter.

This plan intentionally implements the BRD's MVP v1 service boundary first. Advanced target-state features such as broad connector catalogs, full A/B testing UI, output fatigue routing, and real-time collaborative wiki editing remain deferred until the reusable core is stable.

## Assumptions

- KIS will be created inside this repository under `services/knowledge-intelligence-service/` for the first implementation cycle, while remaining deployable as an independent service.
- The existing `compliant-parser` app will integrate with KIS through an HTTP adapter rather than importing KIS internals.
- PostgreSQL with pgvector is the v1 vector store; tests may use mocks or skip true pgvector similarity when PostgreSQL is unavailable.
- The existing `privacy.py` PII boundary is the baseline for LLM and embedding privacy and should be reused or ported into KIS rather than rewritten.
- MVP v1 focuses on the `police-iqw` / BNS use case for compliant-parser while preserving domain-neutral models and APIs.
- PS-WMS migration is planned and tested through compatibility adapters and golden-set comparisons, but production PS-WMS cutover is not part of MVP implementation unless explicitly requested later.

## Codebase Findings

- `docs/knowledge-intelligence-service-brd.md` - Revised BRD v0.2 with MVP v1 scope, entities, APIs, privacy constraints, quality gates, snapshots, and migration requirements.
- `app.py` - Current FastAPI monolith serves the complaint parser, initializes tables, includes `api_v1.v1_router`, and exposes `/health`, `/api/parse`, history, and auth endpoints.
- `api_v1.py` - Existing API routing pattern uses `APIRouter`, Pydantic request models, `require_auth`, standardized error shape, per-endpoint rate limiting, and routers included under `/api/v1`.
- `models.py` - Existing SQLAlchemy ORM uses one `Base`, `AuditMixin`, enum classes, UUID primary keys, relationships, and soft delete fields. It already has `KnowledgeBaseEntry`, `AIAnalysisResult`, and BNS/section recommendation entities that the KIS adapter must not break.
- `database.py` and `migrations.py` - Current persistence uses async SQLAlchemy, programmatic table creation, and lightweight idempotent migrations. KIS should use its own metadata/models and migration module under the new service directory.
- `external_interfaces.py` - Existing external boundary contains OCR, object storage, and `LiveLLMClient`; LLM calls already flow through `privacy.protect_for_llm`.
- `privacy.py` - Existing PII detection, tokenization, encrypted token map, restoration, and strict high-risk leakage guard. KIS should extend this to embedding calls.
- `ai_workflows.py` - Existing BNS/section recommendation workflow calls live LLM JSON and persists section recommendations. This is the compliant-parser integration target for KIS-backed BNS mapping.
- `tests/conftest.py` - Test suite uses an in-memory `MockAsyncSession`; new KIS unit tests can follow this style for service-layer behavior and add FastAPI TestClient tests for API contracts.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/main.py` - Reference standalone FastAPI service with routers, auth middleware, metrics middleware, lifespan, and `/api/v1` prefix.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/db/models.py` - Reference document/chunk/vector model, pgvector type, document status lifecycle, and app isolation.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/db/kg_models.py` - Reference graph nodes, graph edges, extracted facts, sentiment, and policy rules.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/retrieval/hybrid_retriever.py` - Reference hybrid retrieval shape combining vector, graph, fact, and wiki sources with source counts and elapsed time.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/pipeline/processor.py` - Reference ingestion pipeline: status updates, chunking, embedding, NLP extraction, persistence, metrics, and Redis event publishing.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/pipeline/wiki_compiler.py` - Reference wiki compilation with concept extraction, article generation, wikilink resolution, change detection, and DB sync.
- `/Users/n15318/PS-WMS/services/intelligence-service/src/reasoning/executor.py` - Reference reasoning execution chain with context assembly, PII redaction, rules/analytics/LLM steps, cost budgets, result persistence, and hallucination guard.

## Architecture Decisions

- **Standalone service in-repo first**: Create `services/knowledge-intelligence-service/` as an independent FastAPI service so MVP work is isolated from the complaint-parser monolith while remaining easy to develop in the current workspace.
- **Domain-first schema**: Every persisted KIS business row includes `domain_id`; knowledge-specific rows also include `knowledge_base_id`. This replaces PS-WMS `app_id` filtering with explicit domain and service principal scopes.
- **Control plane and data plane separation**: Use separate modules for control-plane APIs/models such as domains, templates, providers, credentials, prompts, policies, snapshots, quality gates, audit, and data-plane APIs/models such as sources, chunks, embeddings, graph, facts, wiki, retrieval, and reasoning.
- **HTTP adapter for compliant-parser**: Add a small client module in the existing app that calls KIS endpoints for BNS mapping and hybrid legal retrieval; keep existing local LLM flow as fallback only when explicitly configured.
- **Privacy before provider calls**: Apply PII masking before both LLM prompts and external embedding calls. Store only redaction summaries and hashes in logs/usage events.
- **Published snapshot reads by default**: Production retrieval and reasoning use the latest published snapshot unless a specific snapshot version is requested.
- **Idempotency on side-effecting endpoints**: Mutating endpoints acquire idempotency records before writes or external provider calls.
- **Tests travel with implementation**: Each phase includes unit/API tests and, where possible, cross-domain negative tests and privacy tests.

## Dependency Graph

```text
Phase 1 --> Phase 2 --> Phase 4 --> Phase 6 --> Phase 8
             |           |           |
             |           |           --> Phase 7 --> Phase 8
             |           |
             --> Phase 3 --> Phase 5 --> Phase 6
                         \-----------> Phase 7
```

Phase summary:

- Phase 1: Create standalone KIS service scaffold and development harness.
- Phase 2: Build secure control-plane foundation.
- Phase 3: Build privacy-safe embedding, ingestion, chunks, and vector search.
- Phase 4: Build ontology, facts, graph, wiki, snapshots, and quality gates.
- Phase 5: Build hybrid retrieval and evaluation sets.
- Phase 6: Build LLM provider governance, prompts, reasoning, and BNS mapping.
- Phase 7: Build compliant-parser and PS-WMS integration adapters.
- Phase 8: Run integration, security, migration, and deployment readiness verification.

## Conventions

- Follow FastAPI router structure from `/Users/n15318/PS-WMS/services/intelligence-service/src/main.py` for KIS service layout, but use explicit domain IDs rather than `app_id`.
- Follow existing `api_v1.py` error response shape for KIS API errors:
  `{ "error": { "code": "...", "message": "...", "field": "...", "request_id": "..." } }`.
- Follow existing `models.py` audit and soft-delete conventions for ORM models.
- Keep KIS service files under `services/knowledge-intelligence-service/`; keep compliant-parser adapter files in the existing root app.
- Use `pytest` with unit tests under `services/knowledge-intelligence-service/tests/` for KIS and existing `tests/` for compliant-parser adapter behavior.
- Use environment variables with `KIS_` prefix for KIS service configuration and `IQW_KIS_` prefix for compliant-parser integration configuration.
- Never persist plaintext provider credentials, prompt token maps, or raw high-risk PII in KIS logs, audit records, usage events, or retrieval logs.

---

## Phase 1: Standalone KIS Service Scaffold
**Dependencies:** none

**Description:**
Create the standalone service boundary and local development harness. This phase gives later work a dedicated app, configuration model, database session, health endpoint, and test setup without touching complaint-parser behavior.

**Tasks:**
1. Create `services/knowledge-intelligence-service/` with FastAPI app entry point, settings, database session, logging, health router, and package metadata.
2. Add KIS development configuration with `.env.example`, service README, Dockerfile or compose entry if needed, and `KIS_API_PREFIX=/api/v1`.
3. Add baseline auth middleware for service API keys and domain resolution, initially backed by static settings for local tests.
4. Add health and readiness endpoints reporting database configured/unconfigured state without requiring external providers.
5. Add initial pytest setup and health/auth middleware tests.

**Files to create/modify:**
- `services/knowledge-intelligence-service/pyproject.toml` - Service package dependencies and pytest config.
- `services/knowledge-intelligence-service/src/main.py` - FastAPI app, lifespan, middleware, router inclusion.
- `services/knowledge-intelligence-service/src/config.py` - Pydantic settings for DB, Redis, providers, auth, CORS, privacy, and API prefix.
- `services/knowledge-intelligence-service/src/db/session.py` - Async SQLAlchemy engine/session lifecycle.
- `services/knowledge-intelligence-service/src/api/health.py` - Health/readiness endpoints.
- `services/knowledge-intelligence-service/src/middleware/auth.py` - API-key auth, scopes, service principal, domain resolution.
- `services/knowledge-intelligence-service/tests/test_health.py` - Health and startup-safe tests.
- `services/knowledge-intelligence-service/tests/test_auth_middleware.py` - Auth and domain resolution tests.
- `services/knowledge-intelligence-service/.env.example` - Local environment template.
- `services/knowledge-intelligence-service/README.md` - Local startup and API notes.

**Acceptance criteria:**
- `pytest services/knowledge-intelligence-service/tests/test_health.py services/knowledge-intelligence-service/tests/test_auth_middleware.py -q` passes.
- KIS can start locally without configured LLM providers.
- Auth middleware rejects missing/invalid API keys when auth is enabled and sets `request.state.domain_id`, `request.state.principal_id`, and scopes for valid keys.
- Health endpoint returns no secrets and distinguishes liveness from readiness.

---

## Phase 2: Control Plane Models, Migrations, RBAC, Audit, and Idempotency
**Dependencies:** Phase 1

**Description:**
Implement the BRD's control-plane foundation: domains, memberships, knowledge bases, templates, providers, encrypted credentials metadata, prompts, policies, audit events, legal holds, deletion requests, and idempotency. This phase establishes secure governance before data-plane ingestion and retrieval exist.

**Tasks:**
1. Create SQLAlchemy models and idempotent migrations for BRD control-plane entities: Domain, User or ServicePrincipal, DomainMembership, KnowledgeBase, DomainTemplate, LLMProviderConfig, LLMCredential, PromptTemplate, PolicyRule, AuditEvent, ReviewTask, LegalHold, DeletionRequest, and IdempotencyRecord.
2. Implement service-layer functions for domain access checks, scope checks, audit writes, legal-hold checks, idempotency acquire/replay/conflict handling, and secret fingerprinting.
3. Implement admin APIs for domains, memberships, knowledge bases, template listing/application, provider configs, credentials metadata, audit search, legal holds, and deletion requests.
4. Add seed templates for `police_iqw_bns` and `ps_wms_advisory` with policies, ontology seeds, retrieval defaults, prompt seeds, and evaluation seeds.
5. Add tests for control-plane CRUD, forbidden cross-domain access, credential no-plaintext responses, idempotency replay/conflict, legal hold blocking, and audit event creation.

**Files to create/modify:**
- `services/knowledge-intelligence-service/src/db/models.py` - Control-plane ORM models and common mixins.
- `services/knowledge-intelligence-service/src/db/migrations.py` - Idempotent KIS schema migrations.
- `services/knowledge-intelligence-service/src/core/errors.py` - Standard error response helpers.
- `services/knowledge-intelligence-service/src/core/security.py` - Scope checks, credential hashing/fingerprints, encryption hooks.
- `services/knowledge-intelligence-service/src/core/audit.py` - Audit event creation and search helpers.
- `services/knowledge-intelligence-service/src/core/idempotency.py` - Idempotency acquire/replay/conflict logic.
- `services/knowledge-intelligence-service/src/core/legal_hold.py` - Legal hold and deletion guards.
- `services/knowledge-intelligence-service/src/templates/seeds.py` - Police IQW and PS-WMS template seed payloads.
- `services/knowledge-intelligence-service/src/api/domains.py` - Domain and membership endpoints.
- `services/knowledge-intelligence-service/src/api/knowledge_bases.py` - Knowledge base endpoints.
- `services/knowledge-intelligence-service/src/api/templates.py` - Domain template endpoints.
- `services/knowledge-intelligence-service/src/api/providers.py` - Provider and credential metadata endpoints.
- `services/knowledge-intelligence-service/src/api/audit.py` - Audit search/export endpoints.
- `services/knowledge-intelligence-service/src/api/retention.py` - Legal hold and deletion request endpoints.
- `services/knowledge-intelligence-service/tests/test_control_plane.py` - Domain, KB, template, provider, credential, and audit tests.
- `services/knowledge-intelligence-service/tests/test_domain_isolation.py` - Cross-domain negative tests.
- `services/knowledge-intelligence-service/tests/test_idempotency.py` - Idempotency behavior tests.
- `services/knowledge-intelligence-service/tests/test_retention.py` - Legal hold and deletion request tests.

**Acceptance criteria:**
- Control-plane tests pass.
- Every control-plane model includes `domain_id` where applicable and audit/soft-delete fields.
- Cross-domain reads and writes return `403 DOMAIN_ACCESS_DENIED` or equivalent standard error.
- Credential APIs never return plaintext or encrypted secret values, only metadata and fingerprint.
- Idempotent retry with the same key and same body returns the original response; same key with a different body returns conflict.

---

## Phase 3: Source Ingestion, Chunking, Masked Embeddings, and Vector Search
**Dependencies:** Phase 2

**Description:**
Implement the first data-plane slice. Domain admins or service principals can ingest source text or object references, chunk content, apply PII policy before external embeddings, store chunks and vector metadata, and query vector search with citations.

**Tasks:**
1. Add data-plane models and migrations for SourceConnector, SourceDocument, DocumentChunk, VectorNamespace, RetrievalQuery, RetrievalResult, LLMUsageEvent, and IngestionJob.
2. Implement ingestion service with source hash/versioning, idempotency, document status transitions, review-required state, and object URI/raw text handling.
3. Implement chunking and embedding pipeline with configurable chunk size/overlap, embedding provider abstraction, privacy masking before external embedding calls, LLMUsageEvent recording for embeddings, and local deterministic test embedding fallback.
4. Implement vector namespace management and vector search endpoint returning ranked chunks, source metadata, citation payloads, privacy summary, and retrieval logs.
5. Add tests for ingestion lifecycle, duplicate content versioning, chunking, masked embedding payloads, vector search filtering, citation presence, and cross-domain isolation.

**Files to create/modify:**
- `services/knowledge-intelligence-service/src/db/data_models.py` - Source, chunk, vector, retrieval, usage, and ingestion job ORM models.
- `services/knowledge-intelligence-service/src/pipeline/chunker.py` - Token-aware chunking with overlap.
- `services/knowledge-intelligence-service/src/privacy/pii.py` - Port or wrap root `privacy.py` for KIS text/value masking.
- `services/knowledge-intelligence-service/src/llm/providers.py` - Provider clients for embeddings and later LLM calls.
- `services/knowledge-intelligence-service/src/llm/router.py` - Provider/model routing and usage summary.
- `services/knowledge-intelligence-service/src/pipeline/embeddings.py` - Masked embedding generation and vector formatting.
- `services/knowledge-intelligence-service/src/pipeline/ingestion.py` - Source ingestion orchestration and status updates.
- `services/knowledge-intelligence-service/src/retrieval/vector_search.py` - Vector search implementation and test fallback.
- `services/knowledge-intelligence-service/src/api/sources.py` - Source ingestion and source detail endpoints.
- `services/knowledge-intelligence-service/src/api/search.py` - Vector search endpoint.
- `services/knowledge-intelligence-service/tests/test_ingestion.py` - Source lifecycle and duplicate/version tests.
- `services/knowledge-intelligence-service/tests/test_embeddings_privacy.py` - PII masking before embedding calls.
- `services/knowledge-intelligence-service/tests/test_vector_search.py` - Search contract, filters, citations, and isolation tests.

**Acceptance criteria:**
- Ingestion can create a source document, chunks, and embedding metadata for a domain-scoped knowledge base.
- External embedding calls receive masked/generalized text when policy requires it.
- RetrievalQuery logs store redacted query text/hash and never raw high-risk PII.
- Vector search responses include citations and do not return results from other domains or inactive knowledge bases.
- Tests for ingestion, embedding privacy, and vector search pass.

---

## Phase 4: Ontology, Facts, Graph, Wiki, Snapshots, and Quality Gates
**Dependencies:** Phase 2, Phase 3

**Description:**
Add the remaining knowledge data structures that make KIS more than vector search: ontology, extracted facts, graph, wiki, immutable published snapshots, and release quality gates. This enables hybrid retrieval and stable production reads.

**Tasks:**
1. Add models/migrations and APIs for OntologyType, ExtractedFact, GraphNode, GraphEdge, WikiArticle, EvaluationSet, EvaluationRun, FeedbackItem, and KnowledgeSnapshot.
2. Implement ontology validation, fact candidate creation/review, graph node/edge upsert, graph traversal/search/stats, and source provenance.
3. Implement wiki compilation for MVP using approved source text and deterministic/LLM-assisted article draft generation behind provider governance; include wikilink resolution, review status, and citations.
4. Implement snapshot creation, quality gate execution, publish, rollback, retired snapshot handling, and latest-published snapshot resolution.
5. Add quality gates for citation coverage, broken wiki links, orphan articles, low-confidence graph edges, active fact contradictions, and required evaluation-set presence.

**Files to create/modify:**
- `services/knowledge-intelligence-service/src/db/knowledge_models.py` - Ontology, fact, graph, wiki, evaluation, feedback, and snapshot ORM models.
- `services/knowledge-intelligence-service/src/ontology/service.py` - Ontology validation and seed application.
- `services/knowledge-intelligence-service/src/facts/service.py` - Fact extraction/review service.
- `services/knowledge-intelligence-service/src/graph/builder.py` - Graph upsert from verified facts.
- `services/knowledge-intelligence-service/src/graph/query.py` - Graph search, traversal, and stats.
- `services/knowledge-intelligence-service/src/wiki/compiler.py` - Wiki draft compilation and wikilink report.
- `services/knowledge-intelligence-service/src/snapshots/service.py` - Snapshot create/publish/rollback and resolver.
- `services/knowledge-intelligence-service/src/quality/gates.py` - Release gate checks and ReviewTask creation.
- `services/knowledge-intelligence-service/src/api/ontology.py` - Ontology endpoints.
- `services/knowledge-intelligence-service/src/api/facts.py` - Fact review endpoints.
- `services/knowledge-intelligence-service/src/api/graph.py` - Graph endpoints.
- `services/knowledge-intelligence-service/src/api/wiki.py` - Wiki endpoints.
- `services/knowledge-intelligence-service/src/api/snapshots.py` - Snapshot and quality gate endpoints.
- `services/knowledge-intelligence-service/tests/test_ontology.py` - Ontology validation and template seed tests.
- `services/knowledge-intelligence-service/tests/test_graph.py` - Graph upsert/traversal/isolation tests.
- `services/knowledge-intelligence-service/tests/test_wiki.py` - Wiki compile/link/citation tests.
- `services/knowledge-intelligence-service/tests/test_snapshots.py` - Publish/rollback/retired snapshot tests.
- `services/knowledge-intelligence-service/tests/test_quality_gates.py` - Gate pass/fail tests.

**Acceptance criteria:**
- Facts can be reviewed and promoted into graph nodes/edges with source provenance.
- Wiki draft articles preserve citations and expose broken wikilink reports.
- Snapshot publication is blocked when mandatory quality gates fail.
- Retrieval and reasoning services can resolve the latest published snapshot.
- Graph, wiki, snapshot, and quality gate tests pass, including cross-domain negative cases.

---

## Phase 5: Hybrid Retrieval and Evaluation Sets
**Dependencies:** Phase 3, Phase 4

**Description:**
Implement KIS hybrid retrieval across vector, graph, facts, and wiki, plus evaluation sets that compare hybrid retrieval against vector-only retrieval. This phase proves the core knowledge advantage from the BRD.

**Tasks:**
1. Implement hybrid retrieval service with source fan-out, per-source include flags, source failure/degraded handling, ranking weights from retrieval profile, deduplication, citations, and elapsed/source counts.
2. Add APIs for hybrid search, retrieval trace inspection, feedback submission, evaluation set CRUD, and evaluation run execution.
3. Seed a BNS legal smoke evaluation set from the `police_iqw_bns` domain template.
4. Add evaluation metrics: recall, precision where expected sources are available, MRR, citation coverage, source failure count, and latency.
5. Add tests for hybrid source merging, degraded source behavior, snapshot scoping, quality metrics, feedback routing, and vector-only baseline comparison.

**Files to create/modify:**
- `services/knowledge-intelligence-service/src/retrieval/hybrid.py` - Hybrid retrieval orchestration.
- `services/knowledge-intelligence-service/src/retrieval/wiki_query.py` - Wiki query helper.
- `services/knowledge-intelligence-service/src/retrieval/graph_query.py` - Graph/fact retrieval helper.
- `services/knowledge-intelligence-service/src/retrieval/ranking.py` - Weighted reranking and deduplication.
- `services/knowledge-intelligence-service/src/evaluation/service.py` - Evaluation set/run execution and metrics.
- `services/knowledge-intelligence-service/src/feedback/service.py` - Feedback capture and ReviewTask creation.
- `services/knowledge-intelligence-service/src/api/search.py` - Extend with `/search/hybrid` and retrieval trace support.
- `services/knowledge-intelligence-service/src/api/evaluations.py` - Evaluation endpoints.
- `services/knowledge-intelligence-service/src/api/feedback.py` - Feedback endpoint.
- `services/knowledge-intelligence-service/tests/test_hybrid_retrieval.py` - Hybrid retrieval contract and degraded tests.
- `services/knowledge-intelligence-service/tests/test_evaluation.py` - Evaluation metrics and release gate tests.
- `services/knowledge-intelligence-service/tests/test_feedback.py` - Feedback routing tests.

**Acceptance criteria:**
- Hybrid search returns vector, graph, fact, and wiki source counts plus ranked cited results.
- Non-required source failure returns `degraded=true`; required source failure returns a standard error.
- Evaluation run can compare vector-only and hybrid retrieval and report hybrid recall lift.
- BNS smoke evaluation set is available from template seed and can gate snapshot publication.
- Hybrid retrieval, evaluation, and feedback tests pass.

---

## Phase 6: LLM Governance, Prompt Registry, Reasoning Engine, and BNS Mapping
**Dependencies:** Phase 4, Phase 5

**Description:**
Add governed LLM execution on top of published snapshots and hybrid retrieval. This includes provider allowlists, encrypted credential usage, prompt versions, cost/token budgets, PII masking, reasoning runs, and the compliant-parser BNS mapping pattern.

**Tasks:**
1. Implement provider credential resolution, model allowlist enforcement, provider fallback, usage/cost tracking, prompt rendering, output schema validation, and strict PII checks for LLM prompt calls.
2. Implement PromptTemplate and ReasoningPattern services with draft/review/approved/active lifecycle, deterministic version resolution, and cost budget checks.
3. Implement reasoning context assembly from published snapshot sources, hybrid retrieval, graph, facts, and wiki with token budget trimming.
4. Implement reasoning execution chain for MVP: rules step plus LLM JSON step, persisted ReasoningRun, citations, privacy summary, and schema-validated result.
5. Seed and test `fir_bns_mapping` reasoning pattern for compliant-parser with BNS section recommendations and citation requirements.

**Files to create/modify:**
- `services/knowledge-intelligence-service/src/db/reasoning_models.py` - ReasoningPattern and ReasoningRun ORM models if not included earlier.
- `services/knowledge-intelligence-service/src/llm/credentials.py` - Credential resolution and secret manager/encryption adapter.
- `services/knowledge-intelligence-service/src/llm/router.py` - Extend with prompt calls, fallback, budgets, and usage tracking.
- `services/knowledge-intelligence-service/src/prompts/registry.py` - Prompt template lifecycle and rendering.
- `services/knowledge-intelligence-service/src/reasoning/context.py` - Snapshot-scoped context assembly and token trimming.
- `services/knowledge-intelligence-service/src/reasoning/executor.py` - Rules/LLM execution and ReasoningRun persistence.
- `services/knowledge-intelligence-service/src/reasoning/bns_mapping.py` - BNS mapping pattern schema and helpers.
- `services/knowledge-intelligence-service/src/api/prompts.py` - Prompt endpoints.
- `services/knowledge-intelligence-service/src/api/reasoning.py` - Pattern and execution endpoints.
- `services/knowledge-intelligence-service/tests/test_provider_governance.py` - Provider/model/credential/budget tests.
- `services/knowledge-intelligence-service/tests/test_prompt_registry.py` - Prompt version and render tests.
- `services/knowledge-intelligence-service/tests/test_reasoning.py` - Reasoning run lifecycle tests.
- `services/knowledge-intelligence-service/tests/test_bns_mapping.py` - BNS mapping output/citation/privacy tests.

**Acceptance criteria:**
- Reasoning execution refuses inactive providers, disallowed models, expired credentials, over-budget calls, and unapproved prompts.
- LLM-bound prompts contain no raw high-risk PII; privacy summary is stored without token map values.
- BNS mapping returns section recommendations, rationale, confidence, and citations from published KIS knowledge.
- ReasoningRun records status, context source summary, LLM usage, privacy summary, result, confidence, and duration.
- Provider governance, prompt registry, reasoning, and BNS mapping tests pass.

---

## Phase 7: Compliant-Parser Adapter, Admin Surface, and PS-WMS Compatibility Plan
**Dependencies:** Phase 5, Phase 6

**Description:**
Connect the existing complaint parser to KIS and add the minimum admin/API surfaces needed to operate MVP v1. Also create the PS-WMS migration compatibility assets so the future cutover is deliberate rather than implicit.

**Tasks:**
1. Add a compliant-parser KIS client that calls KIS hybrid search and BNS reasoning endpoints using `IQW_KIS_BASE_URL`, `IQW_KIS_API_KEY`, `IQW_KIS_DOMAIN`, and `IQW_KIS_KB`.
2. Update `ai_workflows.recommend_sections_from_text` or a narrowly-scoped wrapper so section recommendation can prefer KIS-backed BNS mapping and fall back to the existing live LLM path only when configured.
3. Add minimal admin/API endpoints or UI hooks to expose KIS status, configured domain/KB, BNS snapshot version, and adapter health in the current app health or admin surface.
4. Add PS-WMS compatibility adapter design and test fixtures mapping PS-WMS `app_id`, `client_id`, graph, wiki, and prompt concepts to KIS domain/snapshot concepts.
5. Add integration tests for KIS client success, KIS unavailable fallback behavior, privacy metadata preservation, and no regression to existing section recommendation persistence.

**Files to create/modify:**
- `kis_client.py` - Compliant-parser HTTP client for KIS query/reasoning/citation APIs.
- `ai_workflows.py` - Prefer KIS-backed BNS mapping path behind feature flag.
- `external_interfaces.py` - Optional registry/status inclusion for KIS as an external service.
- `app.py` or `api_v1.py` - Surface KIS health/status where appropriate.
- `.env.example` - Add `IQW_KIS_*` integration variables.
- `README.md` - Document KIS integration configuration and fallback behavior.
- `docs/architecture/kis-ps-wms-migration-adapter.md` - PS-WMS compatibility and migration mapping.
- `tests/test_kis_client.py` - HTTP client contract tests.
- `tests/test_ai_workflows.py` or `tests/test_external_interfaces.py` - KIS-backed section recommendation and fallback tests.
- `services/knowledge-intelligence-service/tests/golden_sets/bns_mapping_smoke.json` - BNS smoke data for adapter/evaluation tests.

**Acceptance criteria:**
- When KIS is configured, compliant-parser section recommendation uses KIS BNS reasoning response and preserves citations/privacy metadata.
- When KIS is not configured and existing LLM provider is configured, current section recommendation behavior remains available.
- Existing section recommendation persistence tests still pass.
- App health or admin status exposes KIS configured/unconfigured state without secrets.
- PS-WMS migration adapter document names concrete source/target entities and cutover gates.

---

## Phase 8: Integration, Security, Migration, and Release Verification
**Dependencies:** Phase 6, Phase 7

**Description:**
Validate the combined service against the BRD's MVP v1 go-live checklist. This phase catches cross-cutting failures in privacy, isolation, idempotency, migrations, retrieval quality, reasoning, and adapters before any deployment.

**Tasks:**
1. Run the KIS test suite, existing compliant-parser tests, and targeted adapter tests with plugin autoload disabled if the local pytest plugin stack is unstable.
2. Run end-to-end smoke flow: create domain from `police_iqw_bns` template, create KB, ingest BNS source text, chunk/embed with privacy controls, publish snapshot, run hybrid search, execute BNS mapping, and call compliant-parser adapter.
3. Verify security controls: cross-domain negative tests, credential no-plaintext checks, audit event creation, idempotency conflict/replay, legal hold blocks deletion, and PII masking before LLM and embedding calls.
4. Verify quality and migration gates: BNS evaluation passes, snapshot gate passes, citations present, PS-WMS compatibility mapping reviewed, and rollback works.
5. Update deployment docs, local run docs, environment variable docs, and final release readiness report.

**Files to create/modify:**
- `services/knowledge-intelligence-service/tests/test_e2e_mvp.py` - MVP smoke flow.
- `services/knowledge-intelligence-service/tests/test_security_release_gates.py` - Privacy, isolation, idempotency, secret, and legal hold release gates.
- `docs/operations/kis-local-deployment.md` - Local KIS run and smoke instructions.
- `docs/reviews/kis-mvp-v1-release-readiness.md` - Final release readiness report.
- `README.md` - Link to KIS service docs and compliant-parser integration.
- `deploy/` files if KIS deployment manifests are added in this phase.

**Acceptance criteria:**
- KIS unit/API tests pass.
- Existing compliant-parser regression tests pass or documented unrelated failures are triaged.
- MVP E2E smoke flow passes with a published snapshot and cited BNS mapping result.
- No test or log captures raw high-risk PII in LLM or embedding outbound payloads.
- Snapshot rollback and idempotent retry behavior are verified.
- Release readiness report documents pass/fail status against the BRD go-live checklist.
