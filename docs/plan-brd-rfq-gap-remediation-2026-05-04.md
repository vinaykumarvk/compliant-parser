# BRD/RFQ Gap Remediation Plan

Date: 2026-05-04  
Lifecycle source: `docs/reviews/brd-coverage-hcp-iqw-brd-v1-and-hcp-ai-qw-vendor-rfq-spec-v1-2-2026-05-04.md`  
BRD: `docs/HCP_IQW_BRD_v1.docx`  
RFQ: `docs/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.pdf`

## Lifecycle Resume Point

The feature-life-cycle workflow is resumed from existing artifacts:

| Step | Status | Artifact |
|---|---|---|
| 1-3 BRD/final requirements | Reused | `docs/HCP_IQW_BRD_v1.docx`, `docs/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.pdf` |
| 4 Test cases | Reused | `docs/HCP_IQW_TestCases_v1.docx`, current automated `tests/` suite |
| 5 Gap analysis | Done | `docs/reviews/brd-coverage-hcp-iqw-brd-v1-and-hcp-ai-qw-vendor-rfq-spec-v1-2-2026-05-04.md` |
| 6 Plan | This file | `docs/plan-brd-rfq-gap-remediation-2026-05-04.md` |

## Dependency Graph

1. AI/data-boundary policy and adapters unblock RFQ AI, confidentiality, prompt validation, and NFR work.
2. Security/audit/integrity controls depend on stable models and migrations.
3. Background job and integration contracts depend on the external boundary registry.
4. Deployment/NFR pack depends on final service/env topology.
5. UI/e2e tests depend on API and workflow stabilization.
6. Full review and local deployment are final gates.

## Phase 1 - P0 AI Hosting and Confidentiality Boundary

Goal: Resolve the BRD/RFQ conflict between self-hosted AI requirements and the current Google/OpenAI/Gemini adapters by making self-hosted providers first-class and enforcing explicit external API approval gates.

Tasks:

| Task | Files | Acceptance |
|---|---|---|
| Add self-hosted LLM endpoint adapter | `external_interfaces.py`, `.env.example`, `README.md` | `IQW_LLM_PROVIDER=self_hosted` calls configured internal endpoint and returns structured JSON |
| Add self-hosted OCR endpoint adapter | `external_interfaces.py`, `cases.py`, `api_v1.py` | OCR provider can be `self_hosted` first, with Google Document AI only as approved fallback |
| Add external AI approval guard | `external_interfaces.py`, `docs/operations/nfr-controls.md` | Production use of Google/OpenAI/Gemini requires `EXTERNAL_AI_API_APPROVED=true` and approval metadata |
| Expose boundary status | `api_v1.py` | `/api/v1/admin/external-interfaces` reports self-hosted vs approved external fallback state |
| Unit tests | `tests/test_external_interfaces.py` or focused existing tests | Provider selection and approval failure paths covered |

## Phase 2 - P0 Audit, Integrity, and Access Controls

Goal: Close security gaps that can be implemented inside the app.

Tasks:

| Task | Files | Acceptance |
|---|---|---|
| Add tamper-evident audit chaining | `models.py`, `audit.py`, `migrations.py`, tests | Each audit row stores previous hash and entry hash; verification helper detects broken chain |
| Add generated-document hashing | `models.py`, `document_generator.py`, `api_v1.py`, tests | Generated and exported docs carry SHA-256 metadata |
| Add ABAC policy layer | `auth.py`, `cases.py`, `api_v1.py`, tests | Case/document access considers role, owner IO, police station, and sensitive-data attributes |
| Add retention enforcement artifact | `docs/operations/`, tests/docs | 7-year retention policy has explicit DB/storage controls and verification checklist |

## Phase 3 - P0 Jobs, Integrations, and Workflow Hardening

Goal: Convert manual/inline behaviors into RFQ-aligned queued workflows and harden integration contracts.

Tasks:

| Task | Files | Acceptance |
|---|---|---|
| Add job abstraction | new `jobs.py`, `api_v1.py`, tests | OCR, AI, reminder, and CCTNS tasks can be queued/executed locally; Celery/Redis or Temporal config documented |
| Add HRMS LDAP adapter path | `hrms.py`, `.env.example`, tests | REST remains supported; LDAP config is recognized and testable |
| Add CCTNS contract tests | `cctns.py`, tests | Retry/failure/queued states covered without live endpoint |
| Complete analytics | `ai_workflows.py`, `models.py`, tests | Generated doc counts, date filters, time-spent metrics, and usage-event aggregation work |
| Complete KB lifecycle | `api_v1.py`, tests | Production promotion requires staging validation; rollback creates and uses previous versions |

## Phase 4 - RFQ Deployment and NFR Evidence Pack

Goal: Add repo artifacts for the on-prem deployment, HA, backup, monitoring, performance, and security requirements.

Tasks:

| Task | Files | Acceptance |
|---|---|---|
| Kubernetes reference deployment | `deploy/k8s/**` | App, worker, Postgres HA references, MinIO, OpenSearch, ingress, secrets, config maps |
| Backup/DR runbooks | `docs/operations/**` | RTO/RPO, immutable backups, restore drill, quarterly failover checklist |
| Performance test harness | `tests/performance/**` | k6/Locust scripts cover API, OCR, LLM, 100-user target |
| Observability/SLA docs | `docs/operations/**` | p95/error/fallback/GPU/uptime metrics and dashboards specified |
| Hardware/BOQ response template | `docs/procurement/**` | RFQ hardware/software/service items mapped to response status |

## Phase 5 - UI and E2E Coverage

Goal: Close UI-only and untested workflow gaps.

Tasks:

| Task | Files | Acceptance |
|---|---|---|
| Add visible UI for section/congruence/plan/judgment workflows | `index.html` | API workflows have first-class UI entry points |
| Add offline/PWA browser verification | tests or docs | Installability, IndexedDB queue, reconnect sync, retry verified |
| Add Playwright or documented equivalent | `tests/e2e/**`, config | Critical user paths automated or explicitly documented if browser tooling unavailable |

## Phase 6 - Review, Validation, and Local Deployment

Goal: Complete lifecycle steps 8-10.

Tasks:

| Task | Files | Acceptance |
|---|---|---|
| Test validation report | `docs/test-validation-brd-rfq-gap-remediation-2026-05-04.md` | Automated and code-level validation status documented |
| Full review | `docs/reviews/**` | Run full-review and remediate findings |
| Local deployment verification | `docs/reviews/**` | Run local-deployment and report endpoint/port/manual-test status |

## Non-Code Preconditions

These cannot be fully completed by source changes alone and require owner-provided infrastructure, credentials, or governance artifacts:

| Item | Required owner input |
|---|---|
| Live HRMS/CCTNS/DSC validation | Test endpoints, certificates/tokens, and integration credentials |
| Real self-hosted model deployment | GPU host or Kubernetes cluster with model artifacts |
| Written approval for external AI APIs | Approval authority, approval ID, allowed providers, data classes, expiry |
| Quarterly DR evidence | Actual drill execution logs from target environment |
| BOQ pricing | Procurement/vendor pricing inputs |

## Execution Order

Proceed sequentially from Phase 1 to Phase 6. A phase is complete only when code/doc changes are present and focused tests pass.
