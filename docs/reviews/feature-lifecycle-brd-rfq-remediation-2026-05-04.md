# Feature Lifecycle Remediation Report

Date: 2026-05-04

Scope:
- BRD: `docs/HCP_IQW_BRD_v1.docx`
- RFQ: `docs/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.pdf`
- Gap source: `docs/reviews/brd-coverage-hcp-iqw-brd-v1-and-hcp-ai-qw-vendor-rfq-spec-v1-2-2026-05-04.md`
- Plan: `docs/plan-brd-rfq-gap-remediation-2026-05-04.md`

## Verdict

CONDITIONAL PASS.

The implementation gaps targeted in this lifecycle pass are remediated in code, configuration, tests, and deployment artifacts. Production release remains conditioned on environment-specific evidence that cannot be produced in this local workspace: live HRMS/CCTNS/DSC credentials, actual self-hosted OCR/LLM endpoints, Kubernetes cluster apply, restore drill, and full 100-concurrent-user load evidence.

## Remediated Gap Groups

### 1. AI Hosting and Confidentiality Boundary

Status: Remediated.

- Added self-hosted OCR gateway support through `IQW_SELF_HOSTED_OCR_URL`.
- Added self-hosted OpenAI-compatible LLM gateway support through `IQW_SELF_HOSTED_LLM_URL`.
- Changed OCR/LLM provider selection to self-hosted-first when configured.
- Added written-approval gate for external Google Document AI, OpenAI, and Gemini usage in production.
- Added non-secret admin readiness status for AI boundary configuration.
- Updated `.env.example`, README, and NFR docs.

### 2. Audit, Integrity, and Access Controls

Status: Remediated.

- Added SHA-256 hash chaining for new audit log rows with `previous_hash` and `entry_hash`.
- Added admin audit-chain verification endpoint at `/api/v1/audit-logs/integrity`.
- Added generated-document content hashes and persisted `sha256_hash`.
- Added generated-document hash into DSC signature metadata.
- Added case-scope authorization helper and enforced it on direct case/document/generated-document/OCR/congruence/investigation-plan routes.
- Added migrations for audit chain, generated-document hashes, and KB validation metadata.

### 3. On-Prem Deployment and NFR Evidence

Status: Remediated as implementation artifacts; production evidence pending target environment.

- Added MinIO/S3-compatible object storage adapter.
- Added `deploy/docker-compose.onprem.yml` for pgvector Postgres, MinIO, OpenSearch, Redis, and app boundary validation.
- Added `deploy/k8s/iqw-onprem.yaml` with 3 replicas, HPA, PDB, probes, non-root container security context, and NetworkPolicy.
- Added `scripts/nfr_smoke.py` for repeatable p95/error-rate evidence.
- Updated NFR operational documentation.

### 4. Workflow Governance and External Interface Coverage

Status: Remediated.

- Added deterministic KB/prompt governance checks in `governance.py`.
- Enforced Draft -> Staging -> validated -> Production promotion.
- Persisted validation status, validation report, validator, and validation timestamp.
- Expanded admin external-interface readiness to include self-hosted OCR/LLM, MinIO/S3, OpenSearch, Redis/Celery, and Temporal.
- Expanded external interface registry for search, vector store, and job queue boundaries.

## Verification

Passed:

- `python -m py_compile governance.py api_v1.py models.py migrations.py external_interfaces.py`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
  - Result: 298 passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_external_interfaces.py`
  - Result: 6 passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_cases.py tests/test_audit.py tests/test_document_generator.py`
  - Result: 83 passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_governance.py tests/test_external_interfaces.py tests/test_models.py`
  - Result: 43 passed.
- `APP_ADMIN_PASSWORD=test APP_SESSION_SECRET=testsecret JWT_SECRET_KEY=testjwt docker compose -f deploy/docker-compose.onprem.yml config --quiet`
  - Result: passed.
- Kubernetes YAML parsed with PyYAML.
  - Result: `deploy/k8s/iqw-onprem.yaml: 8 YAML documents parsed`.
- Local server smoke on port 8097.
  - `/api/v1/health`: `{"status":"ok","version":"1.0.0"}`
- NFR smoke:
  - `python scripts/nfr_smoke.py --base-url http://127.0.0.1:8097 --path /api/v1/health --requests 20 --concurrency 5 --p95-ms 500 --max-error-rate 0.0`
  - Result: 20/20 OK, p95 88.46 ms, error rate 0.0.

Blocked by local environment:

- `kubectl apply --dry-run=client` could not validate without a reachable Kubernetes API server on localhost. YAML syntax was parsed locally instead.
- Legacy `/health` reports database readiness and remains 503 without a configured database. `/api/v1/health` was used for process smoke.

## Remaining Production Evidence

These are no longer code gaps, but must be collected before go-live:

- Live HRMS authentication test with agency endpoint.
- Live CCTNS sync/retry test with agency endpoint.
- DSC signing test with a real token and approved local bridge.
- Self-hosted OCR and LLM gateway throughput/latency evidence.
- Kubernetes apply in target cluster with real Secrets and image tag.
- 100-concurrent-user load test and OCR/LLM SLA test against production-like data.
- Database backup/restore drill and object-storage restore drill.
