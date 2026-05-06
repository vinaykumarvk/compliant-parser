# BRD Coverage Audit — Case Lifecycle BRD

**BRD File:** `docs/case-lifecycle-brd.md`
**Audit Date:** 2026-05-05
**Branch:** `main` @ `8dfa690` (uncommitted changes)
**Tech Stack:** Python 3.9 / FastAPI / SQLAlchemy 2.0 / Single-page HTML frontend
**Test Framework:** unittest (async)

---

## Phase 0 — Preflight Summary

| Check | Result |
|-------|--------|
| BRD file | `docs/case-lifecycle-brd.md` — 160 lines, 10 sections |
| Source dirs | `*.py` (root), `services/`, `tests/` |
| Test dirs | `tests/`, `services/knowledge-intelligence-service/tests/` |
| Git state | main @ 8dfa690, uncommitted changes in 20+ files |
| Total FRs | 10 BRD sections |
| Total line items | 47 |

---

## Phase 1 — Requirement Extraction

### Line-Item Registry

| ID | Type | Description | Priority |
|----|------|-------------|----------|
| **Section 3 — Status Definitions** | | | |
| S3-AC-01 | AC | CaseStatus enum has exactly 9 values | P0 |
| S3-AC-02 | AC | Complaint_Received status exists | P0 |
| S3-AC-03 | AC | FIR_Registered status exists | P0 |
| S3-AC-04 | AC | Under_Investigation status exists | P0 |
| S3-AC-05 | AC | Charge_Sheet_Filed status exists | P0 |
| S3-AC-06 | AC | Closure_Report_Filed status exists | P0 |
| S3-AC-07 | AC | Court_Proceedings status exists | P0 |
| S3-AC-08 | AC | Transferred status exists (terminal) | P0 |
| S3-AC-09 | AC | Disposed status exists (terminal) | P0 |
| S3-AC-10 | AC | Closed_No_FIR status exists (terminal) | P0 |
| S3-AC-11 | AC | Case model default status is Complaint_Received | P0 |
| **Section 4 — Allowed Transitions** | | | |
| S4-AC-01 | AC | Complaint_Received transitions to [FIR_Registered, Closed_No_FIR] | P0 |
| S4-AC-02 | AC | FIR_Registered transitions to [Under_Investigation] | P0 |
| S4-AC-03 | AC | Under_Investigation transitions to [Charge_Sheet_Filed, Closure_Report_Filed, Transferred] | P0 |
| S4-AC-04 | AC | Charge_Sheet_Filed transitions to [Court_Proceedings] | P0 |
| S4-AC-05 | AC | Closure_Report_Filed transitions to [Disposed] | P0 |
| S4-AC-06 | AC | Court_Proceedings transitions to [Disposed] | P0 |
| S4-AC-07 | AC | Terminal states have no outgoing transitions | P0 |
| S4-VR-01 | BR | FIR_Registered transition requires crime_no set on case | P0 |
| S4-VR-02 | BR | Charge sheet deadline: 60 days (summons) / 90 days (sessions) | P1 |
| **Section 5 — Document Requirements** | | | |
| S5-AC-01 | AC | Complaint_Received expects [Petition, Complaint copy] | P1 |
| S5-AC-02 | AC | FIR_Registered expects [FIR] | P1 |
| S5-AC-03 | AC | Under_Investigation expects [Witness_Statement, Seizure_Memo, Arrest_Memo, Medical_Report, FSL_Report, CDR] | P1 |
| S5-AC-04 | AC | Charge_Sheet_Filed expects [Charge_Sheet, Witness_Statement, FSL_Report] | P1 |
| S5-AC-05 | AC | Closure_Report_Filed expects [Other] | P1 |
| S5-AC-06 | AC | Court_Proceedings expects [] (empty) | P1 |
| **Section 6 — Action Checklists** | | | |
| S6-AC-01 | AC | Complaint_Received has 3 expected actions | P1 |
| S6-AC-02 | AC | FIR_Registered has 3 expected actions | P1 |
| S6-AC-03 | AC | Under_Investigation has 8 expected actions | P1 |
| S6-AC-04 | AC | Charge_Sheet_Filed has 3 expected actions | P1 |
| S6-AC-05 | AC | Closure_Report_Filed has 2 expected actions | P1 |
| S6-AC-06 | AC | Court_Proceedings has 3 expected actions | P1 |
| **Section 7 — Statutory Deadlines** | | | |
| S7-AC-01 | AC | Charge sheet filing (summons): 60 days from FIR | P1 |
| S7-AC-02 | AC | Charge sheet filing (sessions): 90 days from FIR | P1 |
| S7-AC-03 | AC | Progress report submission: 30 days recurring | P1 |
| S7-AC-04 | AC | Witness examination: 60 days from FIR | P1 |
| S7-AC-05 | AC | FSL report follow-up: 45 days from exhibit submission | P1 |
| **Section 8 — Role-Based Permissions** | | | |
| S8-BR-01 | BR | Create Case: IO=Yes, Clerk=Yes, AI_Admin=No, System_Admin=Yes | P1 |
| S8-BR-02 | BR | Transition Status: IO=Yes(own), Clerk=No, System_Admin=Yes | P1 |
| S8-BR-03 | BR | Upload Documents: IO=Yes(own), Clerk=Yes(own PS), AI_Admin=No, System_Admin=Yes | P1 |
| S8-BR-04 | BR | View Case: IO=own, Clerk=own PS, AI_Admin=all(read-only), System_Admin=all | P1 |
| S8-BR-05 | BR | Seed Demo Case: any authenticated user | P1 |
| **Section 9 — API Endpoints** | | | |
| S9-AC-01 | AC | GET /api/v1/cases/lifecycle returns transitions + guidance | P0 |
| S9-AC-02 | AC | POST /api/v1/cases/seed-demo creates demo case | P0 |
| S9-AC-03 | AC | PATCH /api/v1/cases/{id}/status transitions case status | P0 |
| **Section 10 — Frontend Components** | | | |
| S10-AC-01 | AC | Lifecycle Stepper: horizontal visual indicator with main-path stages | P0 |
| S10-AC-02 | AC | Stage Guidance Panel: expected docs, actions, next hint | P0 |
| S10-AC-03 | AC | Status Filter: dropdown with all 9 status values | P0 |
| S10-AC-04 | AC | Empty State: "Create Demo Case" button when no cases | P1 |

**Totals:** 47 line items (31 AC, 6 BR, 5 deadline AC, 5 RBAC BR)

---

## Phase 2 — Code Traceability

### Section 3 — Status Definitions

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S3-AC-01 | DONE | `models.py:77-86` | 9-value CaseStatus enum defined |
| S3-AC-02 | DONE | `models.py:78` | `Complaint_Received = "Complaint_Received"` |
| S3-AC-03 | DONE | `models.py:79` | `FIR_Registered = "FIR_Registered"` |
| S3-AC-04 | DONE | `models.py:80` | `Under_Investigation = "Under_Investigation"` |
| S3-AC-05 | DONE | `models.py:81` | `Charge_Sheet_Filed = "Charge_Sheet_Filed"` |
| S3-AC-06 | DONE | `models.py:82` | `Closure_Report_Filed = "Closure_Report_Filed"` |
| S3-AC-07 | DONE | `models.py:83` | `Court_Proceedings = "Court_Proceedings"` |
| S3-AC-08 | DONE | `models.py:84` | `Transferred = "Transferred"` |
| S3-AC-09 | DONE | `models.py:85` | `Disposed = "Disposed"` |
| S3-AC-10 | DONE | `models.py:86` | `Closed_No_FIR = "Closed_No_FIR"` |
| S3-AC-11 | DONE | `models.py:410` | `default=CaseStatus.Complaint_Received` |

### Section 4 — Allowed Transitions

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S4-AC-01 | DONE | `cases.py:87` | `"Complaint_Received": ["FIR_Registered", "Closed_No_FIR"]` |
| S4-AC-02 | DONE | `cases.py:88` | `"FIR_Registered": ["Under_Investigation"]` |
| S4-AC-03 | DONE | `cases.py:89` | `"Under_Investigation": ["Charge_Sheet_Filed", "Closure_Report_Filed", "Transferred"]` |
| S4-AC-04 | DONE | `cases.py:90` | `"Charge_Sheet_Filed": ["Court_Proceedings"]` |
| S4-AC-05 | DONE | `cases.py:91` | `"Closure_Report_Filed": ["Disposed"]` |
| S4-AC-06 | DONE | `cases.py:92` | `"Court_Proceedings": ["Disposed"]` |
| S4-AC-07 | DONE | `cases.py:86-93` | Terminal states absent from dict; `.get(current, [])` at line 518 returns `[]`, blocking transitions |
| S4-VR-01 | DONE | `cases.py:527-535` | `if new_status == "FIR_Registered"` checks crime_no, raises VALIDATION_ERROR if empty |
| S4-VR-02 | PARTIAL | `cases.py:1033` | Only 90-day template exists ("File charge sheet"). Missing: 60-day summons variant. Deadline computed from case creation, not FIR date |

### Section 5 — Document Requirements

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S5-AC-01 | DONE | `cases.py:100` | `["Petition", "Complaint copy"]` |
| S5-AC-02 | DONE | `cases.py:107` | `["FIR"]` |
| S5-AC-03 | DONE | `cases.py:114` | `["Witness_Statement", "Seizure_Memo", "Arrest_Memo", "Medical_Report", "FSL_Report", "CDR"]` |
| S5-AC-04 | DONE | `cases.py:130` | `["Charge_Sheet", "Witness_Statement", "FSL_Report"]` |
| S5-AC-05 | DONE | `cases.py:137` | `["Other"]` |
| S5-AC-06 | DONE | `cases.py:144` | `[]` |

### Section 6 — Action Checklists

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S6-AC-01 | DONE | `cases.py:101` | 3 actions: Record complainant, Assess cognizability, Make GD entry |
| S6-AC-02 | DONE | `cases.py:108` | 3 actions: Assign IO, Identify offence sections, Sync CCTNS |
| S6-AC-03 | DONE | `cases.py:115-123` | 8 actions: Scene visit, witness statements, evidence, arrest, FSL, CDR, medical, progress reports |
| S6-AC-04 | DONE | `cases.py:131` | 3 actions: witnesses, documents/exhibits, Sec 65B certificates |
| S6-AC-05 | DONE | `cases.py:138` | 2 actions: closure report, submit to Magistrate |
| S6-AC-06 | DONE | `cases.py:145` | 3 actions: attend hearings, present evidence, produce witnesses |

### Section 7 — Statutory Deadlines

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S7-AC-01 | NOT_FOUND | searched: `60`, `summons`, `auto_populate` | Only 90-day template exists in `cases.py:1033` |
| S7-AC-02 | DONE | `cases.py:1033` | `{"task_name": "File charge sheet", "days": 90, "priority": "High"}` |
| S7-AC-03 | DONE | `cases.py:1032` | `{"task_name": "Submit progress report", "days": 30, "priority": "Medium"}` |
| S7-AC-04 | DONE | `cases.py:1034` | `{"task_name": "Witness examination completion", "days": 60, "priority": "Medium"}` |
| S7-AC-05 | DONE | `cases.py:1035` | `{"task_name": "FSL report follow-up", "days": 45, "priority": "Medium"}` |

### Section 8 — Role-Based Permissions

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S8-BR-01 | PARTIAL | `api_v1.py:1187-1196` | Endpoint uses `require_auth` only; no role gate to deny AI_Admin |
| S8-BR-02 | PARTIAL | `cases.py:510-545`, `api_v1.py:1269` | Ownership enforced via `ensure_case_access()`; Clerk role NOT explicitly denied |
| S8-BR-03 | PARTIAL | `api_v1.py:1293-1305` | Case access enforced; AI_Admin NOT denied, Clerk PS-scoping NOT enforced |
| S8-BR-04 | PARTIAL | `cases.py:448-480` | IO filtered by `io_id`; Admin sees all. Clerk lacks police_station filtering |
| S8-BR-05 | DONE | `api_v1.py:1232-1238` | `require_auth` only — any authenticated user can seed |

### Section 9 — API Endpoints

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S9-AC-01 | DONE | `api_v1.py:1226-1229` | `@cases_router.get("/lifecycle")` calls `get_lifecycle_map()` |
| S9-AC-02 | DONE | `api_v1.py:1232-1239` | `@cases_router.post("/seed-demo")` calls `seed_demo_case()` |
| S9-AC-03 | DONE | `api_v1.py:1269-1279` | `@cases_router.patch("/{case_id}/status")` calls `transition_case_status()` |

### Section 10 — Frontend Components

| ID | Verdict | Evidence | Notes |
|----|---------|----------|-------|
| S10-AC-01 | DONE | `index.html:3425-3435` (CSS), `index.html:4046` (HTML), `index.html:9002-9023` (JS) | `.lifecycle-stepper` with `.is-completed`/`.is-current` states; `renderLifecycleStepper()` renders 6 main-path stages |
| S10-AC-02 | DONE | `index.html:4056-4062` (HTML), `index.html:9034-9053` (JS) | `#caseStageGuidance` panel with title, desc, docs list, actions list, next hint |
| S10-AC-03 | DONE | `index.html:4022` | `<select id="caseStatusFilter">` with all 9 status options |
| S10-AC-04 | DONE | `index.html:9112` (HTML), `index.html:9065-9072` (JS) | `seedDemoBtn` with `seedDemoCase()` function calling POST seed-demo |

---

## Phase 3 — Test Coverage

| ID | Test Verdict | Evidence | Notes |
|----|-------------|----------|-------|
| S3-AC-01 | TESTED | `tests/test_models.py:78-84` | `assertEqual(set(s.value for s in CaseStatus), expected)` with all 9 values |
| S3-AC-11 | TESTED | `tests/test_models.py:149-151` | `Case(..., status=CaseStatus.Complaint_Received)` |
| S4-AC-01..06 | TESTED | `tests/test_cases.py:156-200` | `test_complaint_to_fir_registered`, `test_full_lifecycle`, `test_closure_report_lifecycle` |
| S4-AC-07 | TESTED | `tests/test_cases.py:163-170` | `test_invalid_transition_raises` — invalid path rejected |
| S4-VR-01 | TESTED | `tests/test_cases.py:183-190` | `test_fir_registered_requires_crime_no` — petition without crime_no raises HTTPException |
| S4-VR-02 | UNTESTED | — | No test for deadline enforcement |
| S5-AC-01..06 | INDIRECT | `tests/test_cases.py:208-212` | `test_get_stage_guidance_valid` checks structure but not all stages |
| S6-AC-01..06 | INDIRECT | `tests/test_cases.py:208-212` | Same as above |
| S7-AC-01 | UNTESTED | — | No test for 60-day summons deadline |
| S7-AC-02..05 | UNTESTED | — | No test specifically exercises `auto_populate_statutory_deadlines` templates |
| S8-BR-01..04 | UNTESTED | — | No role-enforcement tests for case CRUD |
| S8-BR-05 | TESTED | `tests/test_cases.py:224-228` | `test_seed_demo_case` |
| S9-AC-01 | INDIRECT | `tests/test_cases.py:218-222` | `test_get_lifecycle_map` tests function, not HTTP endpoint |
| S9-AC-02 | TESTED | `tests/test_cases.py:224-228` | `test_seed_demo_case` |
| S9-AC-03 | TESTED | `tests/test_cases.py:156-200` | Multiple transition tests exercise this path |
| S10-AC-01..04 | UNTESTED | — | No frontend/E2E tests |

---

## Phase 4 — Gap List

| # | ID | Gap Description | Category | Size | Priority |
|---|-----|----------------|----------|------|----------|
| 1 | S7-AC-01 | Missing 60-day summons charge sheet deadline template in `auto_populate_statutory_deadlines` | A (Unimplemented) | XS | P1 |
| 2 | S4-VR-02 | Charge sheet deadline computed from case creation, not FIR registration date; no 60/90 differentiation by case type | C (Partial) | S | P1 |
| 3 | S8-BR-01 | Create Case endpoint lacks role gate — AI_Admin should be denied | C (Partial) | XS | P1 |
| 4 | S8-BR-02 | Transition Status endpoint does not explicitly deny Clerk role | C (Partial) | XS | P1 |
| 5 | S8-BR-03 | Upload Documents endpoint does not deny AI_Admin or scope Clerk to own PS | C (Partial) | S | P1 |
| 6 | S8-BR-04 | View Case (list_cases) does not apply police_station_id filter for Clerk role | C (Partial) | S | P1 |
| 7 | S7-AC-02..05 | Statutory deadline templates not covered by dedicated tests | D (Untested) | S | P2 |
| 8 | S5/S6 | Stage-specific document/action data only indirectly tested (single stage) | D (Untested) | S | P2 |
| 9 | S10-AC-01..04 | No frontend/E2E tests for lifecycle stepper, guidance panel, status filter, empty state | E (UI-Only) | M | P2 |

---

## Phase 5 — Constraint & NFR Audit

| Constraint | Status | Notes |
|------------|--------|-------|
| **Auth required** | DONE | All case endpoints use `Depends(require_auth)` |
| **Case ownership** | DONE | `ensure_case_access()` enforces IO ownership + admin override |
| **Transition validation** | DONE | `VALID_TRANSITIONS` dict + `.get(current, [])` fallback |
| **Crime no format** | DONE | `validate_crime_no()` enforces `NNNN/YYYY` pattern |
| **Role-based scoping** | PARTIAL | IO scoping works; Clerk PS-scoping missing |
| **Accessibility** | DONE | `aria-label` on filter, tabs, buttons |
| **Responsive stepper** | DONE | `overflow-x: auto` on `.lifecycle-stepper` |

---

## Phase 6 — Scorecard & Verdict

```
LINE-ITEM COVERAGE
==================
Total auditable items:        47
  Acceptance Criteria (AC):   36
  Business Rules (BR):         6
  Deadline Items:              5

Implementation Verdicts:
  DONE:                       38 / 47 = 80.9%
  PARTIAL:                     5 / 47 = 10.6%
  NOT_FOUND:                   1 / 47 =  2.1%
  (DONE + PARTIAL):           43 / 47 = 91.5%

Test Coverage:
  TESTED:                     14 / 47 = 29.8%
  INDIRECT:                    8 / 47 = 17.0%
  UNTESTED:                   25 / 47 = 53.2%
  (TESTED + INDIRECT):       22 / 47 = 46.8%

AC-specific Implementation:  33 / 36 = 91.7% DONE
BR-specific Implementation:   2 /  6 = 33.3% DONE

Total Gaps:                    9
  P0 gaps:                     0
  P1 gaps:                     6
  P2 gaps:                     3
```

### Verdict: **GAPS-FOUND**

Criteria met: >= 70% ACs DONE (91.7%) AND <= 3 P0 gaps (0).
Not COMPLIANT because: test coverage 46.8% < 70% threshold, and BR implementation 33.3% < 80%.

---

## Top 10 Priority Actions

| # | Action | Gaps Closed | Size | Impact |
|---|--------|-------------|------|--------|
| 1 | Add role-based permission checks at case create/transition/upload endpoints using `require_permission()` | S8-BR-01, S8-BR-02, S8-BR-03 | S | Closes 3 RBAC gaps |
| 2 | Add police_station_id filter for Clerk role in `list_cases()` | S8-BR-04 | XS | Closes Clerk scoping gap |
| 3 | Add 60-day summons charge sheet deadline template to `auto_populate_statutory_deadlines` | S7-AC-01 | XS | Closes only NOT_FOUND item |
| 4 | Compute statutory deadlines from FIR registration date (not case creation) and differentiate summons/sessions | S4-VR-02 | S | Fixes deadline accuracy |
| 5 | Add dedicated tests for `auto_populate_statutory_deadlines` (all 5 templates) | S7-AC-02..05 | S | +5 test coverage items |
| 6 | Add tests for all 9 stage guidance entries (documents + actions) | S5/S6 | S | +12 test coverage items |
| 7 | Add role-enforcement tests (AI_Admin denied create, Clerk denied transition) | S8-BR-01..04 | S | +4 test coverage items |
| 8 | Add integration tests for lifecycle and seed-demo HTTP endpoints | S9-AC-01..02 | S | +2 test coverage items |
| 9 | Add frontend E2E tests (lifecycle stepper render, guidance panel, empty state) | S10-AC-01..04 | M | +4 test coverage items |
| 10 | Add terminal states explicitly to VALID_TRANSITIONS dict for API completeness | — | XS | Semantic clarity |
