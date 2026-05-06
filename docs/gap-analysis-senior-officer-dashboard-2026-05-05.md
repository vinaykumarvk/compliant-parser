# Gap Analysis: Senior Officer Performance & Effectiveness Dashboard

## Date

2026-05-05

## Inputs

- Final BRD: `docs/senior-officer-dashboard-brd-v2.md`
- Test cases: `docs/test-cases-senior-officer-dashboard-v2.md`
- Existing implementation: FastAPI routes in `api_v1.py`, domain services in `ai_workflows.py`/`cases.py`, ORM models in `models.py`, parse history in `database.py`, UI in `index.html`

## Summary

| Category | Count |
|---|---:|
| Requirements reviewed | 18 FRs |
| Existing / reusable | 7 |
| Partial | 9 |
| Missing | 22 |
| Conflicts | 3 |

The current codebase has the operational source tables needed for a Phase 1 dashboard: users, police stations, cases, case lifecycle status, documents, generated documents, AI analysis rows, usage events, audit logs, and parser records. The existing `/api/v1/analytics/summary` and Admin Analytics tab are too shallow for the senior dashboard: date filters are not actually applied in the service, generated-document/time-spent metrics are hard-coded or incomplete, there is no metric governance, no scope resolver, no non-PII senior DTO layer, and no senior dashboard UI.

## Data Model Gaps

| Entity | Status | Existing Location | Gap Details |
|---|---|---|---|
| User | PARTIAL | `models.py:333` | Existing roles are only IO, Clerk, AI_Admin, System_Admin. BRD roles Senior_Command, Zone_Officer, SHO are missing. Need either add enum values or map senior roles to existing/admin profile metadata. |
| PoliceStation | EXISTS | `models.py:300` | Sufficient for Phase 1 station grouping. Zone/district fields exist. |
| Case | EXISTS | `models.py:386` | Has status, station, IO, created_by, created_at. Good source for lifecycle and station metrics. |
| CaseDocument | EXISTS | `models.py:466` | Has document type, upload method, OCR status, created_by/created_at. Good source for upload/OCR metrics. |
| GeneratedDocument | PARTIAL | `models.py:733` | Supports generated documents and signatures, but FIR draft subtype normalization may be inconsistent. Need rules/tests for `document_subtype = FIR_Draft` and parser fallback. |
| ParseRecord | PARTIAL | `database.py:23` | Has parser output, completeness, KIS fields, created_at. No explicit case/user link. Complaint-to-FIR metrics from parser history must be marked lower confidence unless linked. |
| CaseActivity | EXISTS | `models.py:531` | Good lifecycle and timing source when activity rows are consistently emitted. |
| AIAnalysisResult | PARTIAL | `models.py:573` | Supports confidence, uncertainty, latency, review action. Not all AI workflows consistently emit acceptance/rework signals. |
| UsageEvent | PARTIAL | `models.py:1048` | Entity exists, but event emission is not broadly instrumented. Current analytics reads events but does not ensure coverage. |
| DashboardMetricSnapshot | MISSING | - | Needed for later performance/materialized snapshots; can be deferred from Phase 1 if direct queries are acceptable. |
| MetricDefinition | MISSING | - | Needed in Phase 1 for explainable metric definitions and permitted-use metadata. |
| DashboardSavedView | MISSING | - | Optional later feature; not needed for Phase 1. |
| DashboardAlertRule | MISSING | - | Optional later alert feature; not needed for Phase 1. |
| DashboardAlertInstance | MISSING | - | Optional later alert feature; not needed for Phase 1. |
| DashboardExportJob | MISSING | - | Full export job model missing. Existing monthly report is synchronous and minimal. |
| DashboardMetricDispute | MISSING | - | Needed for v2 governance; can be model-first in Phase 1 or Phase 2 depending rollout. |
| DashboardMetricCorrection | MISSING | - | Needed for correction workflow and superseded exports. |
| DashboardMetricSourceMap | MISSING | - | Needed for source-of-truth and confidence explainability. |

## API Gaps

| Endpoint | Status | Existing Location | Gap Details |
|---|---|---|---|
| `GET /api/v1/analytics/summary` | PARTIAL | `api_v1.py:1501`, `ai_workflows.py:478` | Existing usage summary is basic. Date filters are passed but not applied; generated docs are hard-coded `0`; time-spent metrics are `0`; feature frequency can duplicate modules. |
| `GET /api/v1/analytics/monthly-trend-report` | PARTIAL | `api_v1.py:1520` | Minimal PDF only. No filters, no trend tables, no metric definitions, no export governance. |
| `GET /api/v1/senior-dashboard/overview` | MISSING | - | Required Phase 1 endpoint for KPI cards, lifecycle, warnings, freshness, and scope. |
| `GET /api/v1/senior-dashboard/officers` | MISSING | - | Required Phase 1 endpoint for officer productivity table. |
| `GET /api/v1/senior-dashboard/stations` | MISSING | - | Required Phase 1 endpoint for station comparison. |
| `GET /api/v1/senior-dashboard/lifecycle` | MISSING | - | Required Phase 1 endpoint for funnel/stage backlog. |
| `GET /api/v1/senior-dashboard/processing-times` | MISSING | - | Needed for complaint-to-FIR timing; can be lower-confidence where parse linkage is missing. |
| `GET /api/v1/senior-dashboard/feature-adoption` | MISSING | - | Needed for AI/KIS/module adoption. |
| Metric definition endpoints | MISSING | - | Needed for BRD FR-012/FR-017. |
| Metric dispute/correction endpoints | MISSING | - | Needed for contestability workflow. |
| Alert endpoints | MISSING | - | Later phase. |
| Export job endpoints | MISSING | - | Later phase; Phase 1 can keep export disabled or simple CSV/PDF without job queue. |

## UI Gaps

| Screen | Status | Existing Location | Gap Details |
|---|---|---|---|
| Admin Analytics tab | PARTIAL | `index.html:4183`, `index.html:10358` | Shows only five basic cards and monthly PDF button. No filters, station/officer tables, lifecycle funnel, warnings, metric definitions, or privacy/governance UI. |
| Senior Dashboard Overview | MISSING | - | Need main navigation entry or admin tab based on role. |
| Officer Performance Screen | MISSING | - | Required Phase 1 table/detail. |
| Station Comparison Screen | MISSING | - | Required Phase 1 station table. |
| Lifecycle Funnel Screen | MISSING | - | Required Phase 1 funnel/backlog. |
| Processing Time Screen | MISSING | - | Can be Phase 2 if source linkage uncertain. |
| Feature Adoption/AI Effectiveness Screen | MISSING | - | Can be Phase 2; some KIS admin metrics already exist in Admin > KIS. |
| Alerts, Report Builder, Metric Registry | MISSING | - | Later phases. |

## UI Design-System Gaps

| Area | Status | Existing Location | Gap Details |
|---|---|---|---|
| Design tokens and primitives | EXISTS | `index.html:10-3500` | App uses vanilla CSS tokens, `btn`, `iqw-select`, tabs, tables, status badges. New UI should reuse these. |
| Charting primitives | MISSING | - | No charting library. Phase 1 should use CSS/table-based bars/funnels to avoid new dependencies unless needed. |
| Accessibility conventions | PARTIAL | `index.html` existing tabs/forms | Need keyboard/focus/labels for new filters, tables, metric cards, chart alternatives. |
| Responsive dashboard layout | MISSING | - | Need compact operational layout with stable dimensions and no card nesting. |

## Business Logic Gaps

| Workflow/Rule | Status | Existing Location | Gap Details |
|---|---|---|---|
| Role/scope resolver | MISSING | `auth.py:211` only checks roles | Need station/zone/officer scope enforcement for dashboard queries. |
| Date filtering | PARTIAL | `api_v1.py:1501`, `ai_workflows.py:478` | Existing filters are accepted but not applied in `usage_analytics`. |
| Officer productivity metrics | PARTIAL | `ai_workflows.py:491` | Cases by IO exists in a rough dict, but no user metadata, active days, FIR drafts, generated docs, documents, AI checks, last activity. |
| Station metrics | PARTIAL | `ai_workflows.py:492` | Cases by station exists, but no active-user adoption, lifecycle, timing, documents, generated drafts. |
| Lifecycle funnel | PARTIAL | `cases.py:86`, `models.py:74` | State machine exists; dashboard aggregation missing. |
| Complaint-to-FIR draft timing | MISSING | - | Requires linking case/doc/generated documents/parse records and confidence warnings. |
| FIR draft counting | PARTIAL | `models.py:733`, `database.py:23` | Data sources exist; subtype/fallback normalization missing. |
| Metric permitted-use/governance | MISSING | - | Required by v2 council update. |
| Metric dispute/correction | MISSING | - | Required by v2 council update. |
| PII-safe dashboard DTOs | MISSING | - | Must explicitly exclude complaint text, OCR text, generated draft content, phone/address/person names. |
| Dashboard audit for read actions | PARTIAL | `audit.py:247` audits mutating `/api/v1` requests | Read/dashboard view and drill-down actions need explicit audit/usage events. |

## Integration Gaps

| Integration | Status | Gap Details |
|---|---|---|
| HRMS profile/posting | PARTIAL | User profile fields exist; historical posting changes are not modelled. Phase 1 can use current posting with a confidence warning. |
| CCTNS | PARTIAL | Case sync status exists, but dashboard lifecycle must treat IQW status as source until external CCTNS/court source is integrated. |
| KIS | PARTIAL | KIS status/admin exists; feature adoption endpoint should include KIS indexing counts from parse records and KIS admin status when configured. |
| Audit | PARTIAL | Mutating endpoint audit exists; dashboard reads/export require explicit audit. |
| Object storage/export | PARTIAL | Generated docs can store paths; dashboard export job lifecycle missing. |

## Non-Functional Gaps

| Requirement | Status | Gap Details |
|---|---|---|
| Performance p95 under 3 seconds | MISSING | No senior dashboard queries or benchmarks. Need indexes/direct query design. |
| PII exclusion | MISSING | Existing APIs may return rich case/document data. Need separate dashboard DTOs and tests. |
| Metric freshness/watermark | MISSING | No freshness metadata in analytics. |
| Data-quality confidence tiers | MISSING | No confidence/warnings per metric. |
| Export watermark/revocation | MISSING | Existing monthly report lacks export governance. |
| Accessibility for dashboard | MISSING | New UI required. |

## Conflicts Requiring Resolution

| Conflict | Current Implementation | BRD Requirement | Resolution |
|---|---|---|---|
| Role enum | `models.py:56` only defines IO, Clerk, AI_Admin, System_Admin | BRD introduces Senior_Command, Zone_Officer, SHO | For Phase 1, avoid DB enum migration by mapping senior dashboard access to System_Admin/AI_Admin plus optional future role migration. Add explicit role migration in later phase if required. |
| Analytics accuracy | `ai_workflows.py:496` sets generated docs and time metrics to zero | BRD requires generated draft and time metrics | Replace or bypass current `usage_analytics` for senior dashboard with dedicated service functions. |
| Read audit | `audit.py:247` skips non-mutating reads | BRD requires dashboard view/drill-down audit | Add explicit dashboard audit/usage logging in senior dashboard endpoints instead of changing global audit middleware. |

## Recommended MVP Cut

Build a Phase 1 senior dashboard that includes:

- `senior_dashboard.py` service with filter normalization, scope resolution, PII-safe DTOs, metric definitions, confidence warnings.
- `GET /api/v1/senior-dashboard/overview`
- `GET /api/v1/senior-dashboard/officers`
- `GET /api/v1/senior-dashboard/stations`
- `GET /api/v1/senior-dashboard/lifecycle`
- Basic UI tab/page with filters, KPI cards, officer/station tables, lifecycle funnel, warnings, and freshness.
- Tests for authorization, PII exclusion, date filters, lifecycle counts, officer/station breakdowns, and zero-data behavior.

Defer:

- Predictive bottleneck signal.
- Scheduled reports.
- Materialized snapshots.
- Alert rules/instances.
- Full metric dispute/correction workflow.
- Composite effectiveness index.
