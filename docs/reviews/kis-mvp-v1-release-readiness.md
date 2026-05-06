# KIS MVP v1 Release Readiness

## Scope

MVP v1 implements a standalone reusable Knowledge Intelligence Service under `services/knowledge-intelligence-service/` plus a compliant-parser adapter.

## Implemented Gates

- Standalone FastAPI service scaffold with health/readiness and API-key auth.
- Domain-scoped control plane with knowledge bases, templates, providers, credentials metadata, audit, legal holds, and idempotency.
- Ingestion, chunking, PII-masked embeddings, vector search, citations, and redacted retrieval traces.
- Ontology, facts, graph, wiki compilation, snapshots, rollback, and quality gates.
- Hybrid retrieval, evaluation sets/runs, and feedback routing.
- Prompt registry, provider/model governance, protected LLM prompt calls, reasoning runs, and BNS mapping.
- Compliant-parser HTTP adapter with explicit fallback behavior.
- PS-WMS migration mapping document and BNS smoke golden set.
- Cloud SQL connector configuration for the separate `police_kb` logical database in `policing-apps:asia-southeast1:policing-db-v2`.
- Deployed DB details verified from Cloud Run/Secret Manager: `police-kb` uses `police-kb-database-url`, DB `police_kb`, DB user `puda`, and Cloud SQL socket host `/cloudsql/policing-apps:asia-southeast1:policing-db-v2`.
- Real self-hosted/OpenAI/Gemini JSON provider calls behind provider allowlists, credential resolution, budget checks, and PII masking.

## Verification

Run locally:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest services/knowledge-intelligence-service/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_kis_client.py tests/test_ai_workflows.py -q
```

Latest local verification on 2026-05-05:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest services/knowledge-intelligence-service/tests -q` passed: 40 tests.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -p pytest_asyncio tests -q` passed: 308 tests.

## Residual Work Before Production

- Replace snapshot-based MVP persistence with fully normalized Postgres/pgvector repositories where needed for scale.
- Add deployment manifests and managed secret storage for hosted KIS environments.
- Run PS-WMS golden-set parity against production-like migrated data before cutover.
