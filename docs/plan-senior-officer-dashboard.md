# Development Plan: Senior Officer Performance & Effectiveness Dashboard

## Overview

Build the Phase 1 senior-officer dashboard from `docs/senior-officer-dashboard-brd-v2.md`: read-only, PII-safe, scoped operational analytics over existing IQW tables. The first release focuses on overview KPIs, officer/station breakdowns, lifecycle funnel, metric definitions, confidence warnings, and UI access. Predictive alerts, scheduled exports, materialized snapshots, and metric dispute workflows are intentionally deferred until data quality is proven.

## Assumptions

- Phase 1 maps senior-dashboard access to existing `System_Admin` and `AI_Admin` roles. Full enum migration for `Senior_Command`, `Zone_Officer`, and `SHO` is a later phase.
- IQW `cases.status` is the authoritative lifecycle source until external CCTNS/court status integration exists.
- Unlinked `parse_records` are included only as lower-confidence parser metrics and are not attributed to an officer unless a link exists.
- Dashboard APIs return metadata and aggregate values only; raw complaint text, OCR text, generated draft content, addresses, phone numbers, victim names, accused names, and witness names are forbidden.

## Codebase Findings

- `models.py:333` defines User; existing roles are `IO`, `Clerk`, `AI_Admin`, `System_Admin`.
- `models.py:386` defines Case with status, station, IO, created_by, and lifecycle fields.
- `models.py:466` defines CaseDocument with document type, upload method, OCR status, created_by, and created_at.
- `models.py:733` defines GeneratedDocument with subtype, export format, signature status, created_by, and created_at.
- `models.py:1048` defines UsageEvent, but broad event emission is incomplete.
- `database.py:23` defines `parse_records`, including parser output, completeness, KIS indexing, and created_at.
- `api_v1.py:1501` exposes `/api/v1/analytics/summary`; `ai_workflows.py:478` has partial analytics with hard-coded generated-document and time metrics.
- `index.html:4183` has a basic Admin Analytics panel with only simple KPI cards.

## Architecture Decisions

- **Dedicated service module:** Create `senior_dashboard.py` instead of expanding `ai_workflows.usage_analytics`, because existing analytics is partial and should remain backward-compatible.
- **Dedicated router prefix:** Add `/api/v1/senior-dashboard/*` endpoints for the BRD surface.
- **PII-safe DTO boundary:** Return only aggregate and operational metadata. Do not reuse case-detail DTOs.
- **Direct-query MVP:** Use direct SQLAlchemy queries for Phase 1. Add materialized snapshots later if performance requires.
- **Metric definitions as constants first:** Seed metric definitions in code for Phase 1; database-backed governance tables are later phases.
- **UI without new dependencies:** Use existing `index.html` CSS tokens, buttons, selects, tabs, badges, and tables.

## Dependency Graph

```text
Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

## Conventions

- Keep endpoint errors aligned with `api_v1.raise_api_error`.
- Use `require_auth` plus service-level scope checks for dashboard access.
- Add tests with direct endpoint/service calls where possible.
- Avoid changing existing enum roles in Phase 1.
- Add succinct comments only around non-obvious metric calculations.

---

## Phase 1: Backend Metrics Service and Contracts

**Dependencies:** none

**Description:**
Create the reusable dashboard service layer: filter normalization, scope checks, metric definitions, confidence/warning model, lifecycle counts, officer/station aggregations, and PII-safe output contracts.

**Tasks:**
1. Create `senior_dashboard.py` with normalized filters, scope authorization, source-confidence helpers, and metric definition constants.
2. Implement direct-query functions for overview, officers, stations, lifecycle, processing-time summary, and feature adoption summary.
3. Add explicit PII-exclusion guard helper for dashboard payloads.
4. Add focused tests in `tests/test_senior_dashboard.py` for metrics, filtering, role scope, empty states, and PII exclusion.

**Files to create/modify:**
- `senior_dashboard.py` - New service module.
- `tests/test_senior_dashboard.py` - Service/API tests.

**Acceptance criteria:**
- Service returns zero-safe metrics with freshness and warnings.
- Officer/station/lifecycle aggregations reflect seeded case/document/generated-document data.
- Dashboard payloads do not include seeded forbidden PII strings.

---

## Phase 2: API Endpoints and Audit Hooks

**Dependencies:** Phase 1

**Description:**
Expose Phase 1 dashboard data through `/api/v1/senior-dashboard/*` endpoints and log dashboard views/drill-downs without altering global audit middleware.

**Tasks:**
1. Add `senior_dashboard_router` in `api_v1.py`.
2. Implement `GET /overview`, `/officers`, `/stations`, `/lifecycle`, `/processing-times`, `/feature-adoption`, and `/metric-definitions`.
3. Add explicit usage/audit metadata logging where safe and non-blocking.
4. Extend tests to call endpoint functions with role variations.

**Files to create/modify:**
- `api_v1.py` - Router, endpoint models, route inclusion.
- `tests/test_senior_dashboard.py` - Endpoint coverage.

**Acceptance criteria:**
- Authorized admin roles can retrieve dashboard data.
- Unauthorized role/scope requests are denied.
- Endpoints use standardized errors for invalid dates and authorization failures.

---

## Phase 3: Senior Dashboard UI

**Dependencies:** Phase 2

**Description:**
Add a senior dashboard view in the existing vanilla UI with filters, KPI cards, lifecycle funnel, officer table, station table, feature adoption summary, warnings, and metric definition visibility.

**Tasks:**
1. Add dashboard navigation/view markup in `index.html`.
2. Add CSS for dense operational cards/tables/funnel bars using existing design tokens.
3. Add JS fetch/render functions for overview, officers, stations, lifecycle, processing-times, feature-adoption, and metric definitions.
4. Add empty/error/loading states and role-safe navigation.
5. Validate inline script parsing with Node.

**Files to create/modify:**
- `index.html` - UI markup, styles, and JS.

**Acceptance criteria:**
- Dashboard renders from live API payloads.
- Filters update dashboard data.
- No PII fields are rendered.
- JS parses without syntax errors.

---

## Phase 4: Validation and Lifecycle Reports

**Dependencies:** Phase 1, Phase 2, Phase 3

**Description:**
Run the feature test suite, app regression tests, and generate the feature-life-cycle validation report.

**Tasks:**
1. Run `python -m py_compile` for changed Python files.
2. Run focused senior dashboard tests.
3. Run full app test suite.
4. Run inline JS parse check.
5. Save `docs/test-validation-senior-officer-dashboard-2026-05-05.md`.
6. Save `docs/feature-life-cycle-senior-officer-dashboard-2026-05-05.md`.

**Files to create/modify:**
- `docs/test-validation-senior-officer-dashboard-2026-05-05.md` - Validation report.
- `docs/feature-life-cycle-senior-officer-dashboard-2026-05-05.md` - Lifecycle report.

**Acceptance criteria:**
- Focused tests pass.
- Full app regression tests pass or documented with clear blocker.
- Dashboard UI JS parses successfully.
- Lifecycle artifacts list BRD, evaluation, tests, gap, plan, code, and validation outputs.
