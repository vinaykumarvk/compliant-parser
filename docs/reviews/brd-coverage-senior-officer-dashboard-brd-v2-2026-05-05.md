# BRD Coverage Audit: Senior Officer Dashboard BRD v2

Date: 2026-05-05  
BRD: `docs/senior-officer-dashboard-brd-v2.md`  
Phase filter: `full`

## Compliance Verdict

**AT-RISK** for full BRD compliance.

The current implementation covers a useful Phase 1 dashboard slice: read-only aggregate KPIs, officer/station rollups, lifecycle counts, processing-time metrics, feature-adoption metrics, metric definitions, PII-safe payloads, basic dashboard UI, and focused tests. The full BRD, however, also requires senior role scopes, officer/station drill-downs, sortable/exportable tables, snapshots, alert rules, scheduled exports, disputes/corrections, validation gates, anti-gaming controls, and formal data-quality governance. Those are mostly missing or explicitly deferred.

## Phase 0: Preflight

| Area | Finding |
|---|---|
| BRD file | Exists, 87 KB, 1,808 lines. |
| FR count | 18 FR sections. Extracted 186 auditable FR line items: 90 AC, 47 BR, 25 UI behavior, 24 edge/error items. |
| Tech stack | Python/FastAPI-style app from `requirements.txt`; SQLAlchemy models; vanilla HTML/CSS/JS frontend; pytest tests. |
| Source dirs discovered | Root Python modules, `services/`, `services/knowledge-intelligence-service/`, `tests/`. |
| Test infrastructure | `tests/` with pytest/unittest style. No pytest config file found at repo root. |
| Monorepo/service note | Main app plus nested `services/knowledge-intelligence-service/`; dashboard BRD maps to main IQW app, not KIS service except KIS adoption metadata. |
| Git state | Branch `main`, commit `8dfa690`, dirty worktree with many modified/untracked files including dashboard implementation artifacts. |

## Evidence Map

| Evidence ID | Evidence |
|---|---|
| E1 | Role constants and filter model: `senior_dashboard.py:19`, `senior_dashboard.py:119`, `senior_dashboard.py:180`. |
| E2 | Period validation and custom range handling: `senior_dashboard.py:197`, `senior_dashboard.py:211`, `senior_dashboard.py:218`, `senior_dashboard.py:220`. |
| E3 | Scope authorization for IO/admin roles: `senior_dashboard.py:233`, `senior_dashboard.py:237`, `senior_dashboard.py:241`. |
| E4 | Case/station/officer/status/type filtering: `senior_dashboard.py:270`, `senior_dashboard.py:275`, `senior_dashboard.py:277`, `senior_dashboard.py:279`, `senior_dashboard.py:281`. |
| E5 | PII-forbidden dashboard keys and payload guard: `senior_dashboard.py:44`, `senior_dashboard.py:323`. |
| E6 | Dataset source tables: `senior_dashboard.py:339`, `senior_dashboard.py:348`, `senior_dashboard.py:349`, `senior_dashboard.py:350`, `senior_dashboard.py:351`, `senior_dashboard.py:353`. |
| E7 | Freshness/watermark response: `senior_dashboard.py:368`. |
| E8 | Overview KPIs: `senior_dashboard.py:379`, `senior_dashboard.py:402`. |
| E9 | Lifecycle counts/ages: `senior_dashboard.py:434`, `senior_dashboard.py:451`. |
| E10 | Officer metrics: `senior_dashboard.py:463`, `senior_dashboard.py:473`, `senior_dashboard.py:503`, `senior_dashboard.py:512`, `senior_dashboard.py:518`. |
| E11 | Station metrics: `senior_dashboard.py:532`, `senior_dashboard.py:541`, `senior_dashboard.py:557`, `senior_dashboard.py:571`, `senior_dashboard.py:578`. |
| E12 | Processing-time metrics: `senior_dashboard.py:593`, `senior_dashboard.py:603`, `senior_dashboard.py:611`, `senior_dashboard.py:628`, `senior_dashboard.py:647`. |
| E13 | Feature-adoption and AI effectiveness metrics: `senior_dashboard.py:655`, `senior_dashboard.py:658`, `senior_dashboard.py:663`, `senior_dashboard.py:664`, `senior_dashboard.py:666`. |
| E14 | Dashboard usage event logging: `senior_dashboard.py:684`, `api_v1.py:1604`, `api_v1.py:1812`. |
| E15 | API endpoints: `api_v1.py:1613`, `api_v1.py:1643`, `api_v1.py:1673`, `api_v1.py:1703`, `api_v1.py:1733`, `api_v1.py:1763`, `api_v1.py:1793`, router mount at `api_v1.py:2376`. |
| E16 | UI dashboard nav/view/filter/layout: `index.html:3826`, `index.html:4147`, `index.html:4151`, `index.html:4190`. |
| E17 | UI role visibility/navigation: `index.html:8746`, `index.html:8759`, `index.html:7889`, `index.html:8879`. |
| E18 | UI API loading/rendering: `index.html:10620`, `index.html:10640`, `index.html:10647`, `index.html:10674`, `index.html:10707`, `index.html:10731`, `index.html:10751`, `index.html:10773`, `index.html:10795`, `index.html:10818`, `index.html:10836`. |
| E19 | Test fixtures and dashboard assertions: `tests/test_senior_dashboard.py:76`, `tests/test_senior_dashboard.py:174`, `tests/test_senior_dashboard.py:190`, `tests/test_senior_dashboard.py:207`, `tests/test_senior_dashboard.py:227`, `tests/test_senior_dashboard.py:247`. |
| E20 | Existing model support: `models.py:61`, `models.py:288`, `models.py:333`, `models.py:385`, `models.py:466`, `models.py:531`, `models.py:555`, `models.py:733`, `models.py:1048`, parse table at `database.py:23`. |

## Requirement Traceability Matrix

Legend: `DONE`, `PARTIAL`, `NOT_FOUND`, `DEFERRED`; test status `TESTED`, `INDIRECT`, `TC_ONLY`, `UNTESTED`.

| ID | Line item verdicts | Key evidence / notes |
|---|---|---|
| FR-001 | AC-01 `PARTIAL/UNTESTED`; AC-02 `PARTIAL/UNTESTED`; AC-03 `DONE/INDIRECT`; AC-04 `PARTIAL/UNTESTED`; AC-05 `DONE/INDIRECT`; BR-01 `PARTIAL/UNTESTED`; BR-02 `DONE/TESTED`; UI-01 `DONE/UNTESTED`; UI-02 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED`; EC-02 `PARTIAL/INDIRECT` | Dashboard nav and UI exist (E16/E17); only `System_Admin`, `AI_Admin`, `IO` are allowed in code (E1/E3/E17). Senior_Command/Zone_Officer/SHO/Clerk and no-scope message are missing. Usage logging exists but is not full audit with role/scope/timestamp proof (E14). PII exclusion is implemented and tested (E5/E19). No stale snapshot fallback. |
| FR-002 | AC-01 `DONE/INDIRECT`; AC-02 `DONE/TESTED`; AC-03 `PARTIAL/TESTED`; AC-04 `PARTIAL/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `PARTIAL/UNTESTED`; UI-01 `PARTIAL/UNTESTED`; UI-02 `NOT_FOUND/UNTESTED`; EC-01 `DONE/TESTED`; EC-02 `DONE/TESTED` | Period presets and max range exist (E2/E16); invalid dates tested (E19). Filters lack role/offence/zone and removable chips. Officer selection is a free text field, not constrained options (E16). Query object is reused for current dashboard calls (E18) but exports are not implemented. |
| FR-003 | AC-01 `PARTIAL/TESTED`; AC-02 `PARTIAL/UNTESTED`; AC-03 `PARTIAL/TESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `DONE/TESTED`; BR-02 `DONE/TESTED`; BR-03 `PARTIAL/TESTED`; UI-01 `PARTIAL/UNTESTED`; UI-02 `PARTIAL/UNTESTED`; EC-01 `DONE/UNTESTED`; EC-02 `NOT_FOUND/UNTESTED` | Backend computes core officer metrics (E10/E19), but UI omits several visible columns, every-numeric sorting, drill-down, and CSV. `active_days` does not include UsageEvent/CaseActivity sources despite the BRD rule. Former/deleted users are not handled. |
| FR-004 | AC-01 `PARTIAL/TESTED`; AC-02 `PARTIAL/UNTESTED`; AC-03 `PARTIAL/TESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `DONE/TESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `PARTIAL/UNTESTED`; BR-03 `PARTIAL/UNTESTED`; BR-04 `PARTIAL/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; UI-02 `PARTIAL/UNTESTED`; EC-01 `PARTIAL/UNTESTED`; EC-02 `NOT_FOUND/UNTESTED` | Backend has median/p75/p95 and per-case draft count from generated documents (E12/E19). It does not use petition uploads or linked parser records as first intake, does not include parser `fir_draft`, does not produce average/median iteration cards, does not group by station/IO, and excludes negative durations without warning. |
| FR-005 | AC-01 `PARTIAL/TESTED`; AC-02 `PARTIAL/UNTESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `DONE/TESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `DONE/INDIRECT`; BR-03 `DONE/INDIRECT`; UI-01 `PARTIAL/UNTESTED`; UI-02 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED`; EC-02 `NOT_FOUND/UNTESTED` | Lifecycle status counts/median/oldest age exist (E9/E18/E19), but no conversion percentages, p90 age, station/IO backlog table, stage drill-down, transition metrics, or transfer-date exclusion. |
| FR-006 | AC-01 `PARTIAL/UNTESTED`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `PARTIAL/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `PARTIAL/UNTESTED`; BR-03 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Generated and FIR-draft counts are derived from `GeneratedDocument.document_subtype` (E8/E12), but export counts, signatures, template usage, subtype breakdowns, parser fallback, and failure links are missing. |
| FR-007 | AC-01 `PARTIAL/TESTED`; AC-02 `PARTIAL/TESTED`; AC-03 `NOT_FOUND/UNTESTED`; AC-04 `PARTIAL/UNTESTED`; AC-05 `PARTIAL/UNTESTED`; BR-01 `DONE/TESTED`; BR-02 `DONE/TESTED`; BR-03 `DONE/TESTED`; UI-01 `PARTIAL/UNTESTED`; EC-01 `PARTIAL/UNTESTED` | Feature counts and acceptance/low-confidence rates exist (E13/E19). Trends, edited/rejected/rework cards, latency, citation coverage, completeness score, quality gates, failed KIS, graph facts, wiki articles, and insufficient-sample wording are missing. |
| FR-008 | AC-01 `PARTIAL/UNTESTED`; AC-02 `PARTIAL/UNTESTED`; AC-03 `DEFERRED/TC_ONLY`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `NOT_FOUND/UNTESTED`; BR-02 `DEFERRED/TC_ONLY`; BR-03 `NOT_FOUND/UNTESTED`; UI-01 `PARTIAL/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Station table exists (E11/E18) but lacks median timing, investigation completion, court progression, adoption rate, sortable UI, cohort mode, drill-down, exports, and low-sample/no-user warnings. |
| FR-009 | AC-01 `NOT_FOUND/UNTESTED`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `DONE/TESTED`; AC-05 `PARTIAL/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `PARTIAL/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | PII-free aggregate DTOs are covered (E5/E19). Officer detail, case metadata list, breadcrumbs, audit for drill-down, and outside-scope click handling are missing. Existing case authorization exists elsewhere, but dashboard drill-down is not implemented. |
| FR-010 | AC-01 `DEFERRED/TC_ONLY`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `NOT_FOUND/UNTESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `NOT_FOUND/UNTESTED`; BR-02 `NOT_FOUND/UNTESTED`; BR-03 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | No dashboard alert entities, endpoints, UI, thresholds, acknowledgement, or sample-size evaluation. Searches: `DashboardAlert`, `alert-rules`, `senior-dashboard/alerts`, `threshold`, `acknowledge`. |
| FR-011 | AC-01 `NOT_FOUND/UNTESTED`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `NOT_FOUND/UNTESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `NOT_FOUND/UNTESTED`; BR-02 `NOT_FOUND/UNTESTED`; BR-03 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; UI-02 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Existing `/api/v1/analytics/monthly-trend-report` is not dashboard-scoped export. No dashboard export jobs, CSV/PDF menu, SHA-256, expiry, scheduled reports, retry, or queued response. Searches: `senior-dashboard/exports`, `DashboardExportJob`, `export job`, `scheduled report`, `expires_at`. |
| FR-012 | AC-01 `PARTIAL/UNTESTED`; AC-02 `DONE/UNTESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `PARTIAL/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `NOT_FOUND/UNTESTED`; BR-02 `NOT_FOUND/UNTESTED`; UI-01 `PARTIAL/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Metric definitions constants and overview freshness exist (E1/E7/E15/E18), but no per-card info action, registry persistence, versioning, low-sample/negative-duration warnings, dismissible panel, inactive definition behavior, or metric-version audit. |
| FR-013 | AC-01 `NOT_FOUND/UNTESTED`; AC-02 `PARTIAL/UNTESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `DONE/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `NOT_FOUND/UNTESTED`; BR-02 `DONE/UNTESTED`; UI-01 `DONE/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Direct queries and watermarks exist (E6/E7/E18). Materialized snapshots, idempotent aggregation jobs, 5-minute target enforcement, aggregation failure visibility, and stale snapshot fallback are missing. |
| FR-014 | AC-01 `PARTIAL/INDIRECT`; AC-02 `DONE/TESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `PARTIAL/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `DONE/TESTED` | All implemented dashboard endpoints require auth (E15) and service authorization denies unknown roles/IO cross-scope (E3/E19). Scope model lacks senior jurisdiction. View usage is logged, but drill-down/export/scheduled/threshold logs and export metadata do not exist. |
| FR-015 | AC-01 `DEFERRED/TC_ONLY`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `NOT_FOUND/UNTESTED`; AC-04 `PARTIAL/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `NOT_FOUND/UNTESTED`; BR-02 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Training recommendations are absent. Non-disciplinary posture is partially present in metric definitions/prohibited-use labels (E1/E18). Searches: `training recommendation`, `reviewed recommendation`, `dismiss for period`, `low active-user adoption`. |
| FR-016 | AC-01 `PARTIAL/UNTESTED`; AC-02 `DEFERRED/TC_ONLY`; AC-03 `DEFERRED/TC_ONLY`; AC-04 `DONE/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Predictive signal is not implemented, which effectively prevents status/score mutation. No explicit feature flag, validation control, reason codes, confidence gate, feedback capture, or PII-safe LLM predictive summary path. |
| FR-017 | AC-01 `PARTIAL/UNTESTED`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `NOT_FOUND/UNTESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `PARTIAL/UNTESTED`; BR-03 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; UI-02 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED`; EC-02 `NOT_FOUND/UNTESTED` | Metric definitions include permitted/prohibited use and confidence (E1/E18), but there are no owners, source-map records, minimum sample rules, disputes, corrections, disputed badges, superseded exports, notifications, PII validation for disputes, or duplicate-dispute conflict handling. |
| FR-018 | AC-01 `PARTIAL/UNTESTED`; AC-02 `NOT_FOUND/UNTESTED`; AC-03 `PARTIAL/UNTESTED`; AC-04 `NOT_FOUND/UNTESTED`; AC-05 `NOT_FOUND/UNTESTED`; BR-01 `PARTIAL/UNTESTED`; BR-02 `PARTIAL/UNTESTED`; BR-03 `NOT_FOUND/UNTESTED`; UI-01 `NOT_FOUND/UNTESTED`; EC-01 `NOT_FOUND/UNTESTED` | Implementation is mostly Phase 1 read-only (E15/E18) but includes Phase 2-style processing/adoption metrics, lacks validation gates, field validation records, senior-role UAT support, operational-awareness labels on all metrics, and production metric version controls. |

## Data Model Traceability

| Requirement area | Verdict | Evidence |
|---|---|---|
| Existing operational sources | `DONE` | User, station, case, case document, case activity, AI analysis, generated document, usage events, and parse records exist (E20). |
| Senior role model | `PARTIAL` | User roles are only `IO`, `Clerk`, `AI_Admin`, `System_Admin` at `models.py:61`; no `Senior_Command`, `Zone_Officer`, or `SHO`. |
| DashboardMetricSnapshot | `NOT_FOUND` | Searched `DashboardMetricSnapshot`, `metric_snapshot`, `snapshots:refresh`; only KIS snapshots exist. |
| MetricDefinition persistence/versioning | `PARTIAL` | In-code `METRIC_DEFINITIONS` only (E1); no table/version records. |
| DashboardSavedView | `NOT_FOUND` | No saved-view model or endpoint. |
| DashboardAlertRule / DashboardAlertInstance | `NOT_FOUND` | No dashboard alert model or endpoint. |
| DashboardExportJob | `NOT_FOUND` | No dashboard export-job model or worker. |
| DashboardMetricDispute / Correction | `NOT_FOUND` | No dispute or correction model/endpoints. |
| DashboardMetricSourceMap | `NOT_FOUND` | No source-map model; only constants contain `source_tables`. |

## API and Integration Audit

| API requirement | Verdict | Evidence / gap |
|---|---|---|
| `/overview`, `/officers`, `/stations`, `/lifecycle`, `/processing-times`, `/feature-adoption`, `/metric-definitions` | `DONE` | Implemented and mounted (E15). |
| `/officers/{user_id}` | `NOT_FOUND` | No route under `senior_dashboard_router`. |
| `/alerts`, alert acknowledgement, alert rules | `NOT_FOUND` | No dashboard alert routes; only unrelated congruence alerts. |
| `/exports`, `/exports/{job_id}` | `NOT_FOUND` | No dashboard export routes/job model. |
| `/snapshots:refresh` | `NOT_FOUND` | No dashboard snapshot refresh endpoint. |
| Standard API errors | `PARTIAL` | Validation/auth errors use `raise_api_error` (E15), but `CONFLICT`, `RATE_LIMITED`, export/alert failures are not represented for missing features. |
| HRMS scoping | `PARTIAL` | User profile has posting fields (E20) and HRMS auth exists elsewhere, but no senior zone/SHO scope resolver. |
| CCTNS dependency avoided | `DONE` | Dashboard uses IQW case status only (E8/E9). |
| KIS adoption metadata | `PARTIAL` | Counts only indexed parse records (E13); no failed indexing, graph, wiki, quality gate summary. |
| Audit log integration | `PARTIAL` | Dashboard view usage events are inserted (E14); not full tamper-evident audit or export/drill-down/threshold audit. |
| Rate limits | `NOT_FOUND` | Existing generic rate limiter exists, but no dashboard-specific 120/min, export/hour, snapshot/hour, or alert-rule mutation limits. |

## NFR and Constraint Audit

| NFR | Verdict | Evidence / gap |
|---|---|---|
| p95 overview under 3s at 10,000 cases / 500 users | `UNVERIFIED` | Direct in-memory style queries exist (E6); no benchmark or pagination/snapshot strategy. |
| Drill-down p95 under 2s for 1,000 rows | `NOT_FOUND` | Drill-down not implemented. |
| Export queued response under 2s | `NOT_FOUND` | Dashboard exports not implemented. |
| Indexed filters | `PARTIAL` | Parse records have indexes (`database.py:64`); no dashboard-specific indexes for generated subtype, station, IO, usage event. |
| Existing auth/RBAC | `PARTIAL` | Auth dependency and service role checks exist (E3/E15), but no senior jurisdiction roles. |
| PII-free aggregate APIs | `DONE` | Payload guard and tests (E5/E19). |
| Audit access/export | `PARTIAL` | View usage only (E14), exports absent. |
| Materialized snapshots and async aggregation | `NOT_FOUND` | No dashboard snapshot model/job. |
| Availability stale fallback | `NOT_FOUND` | No cached snapshot fallback. |
| Backup/recovery of dashboard config | `NOT_FOUND` | Config tables absent. |
| WCAG/table alternatives | `PARTIAL` | Inputs have labels (E16); charts use CSS funnel plus table-like rows, but no formal captions, keyboard review, or accessibility tests. |
| Browser/device support | `PARTIAL` | Responsive CSS exists for dashboard grid (E16); not tested across browsers/devices. |
| Personnel safeguards | `PARTIAL` | Prohibited-use labels exist (E1/E18); no export purpose selection, watermarking, revocation, disciplinary disclaimer enforcement. |
| Anti-gaming controls | `NOT_FOUND` | No sample-size warnings, duplicate draft spike detection, same-day churn detection, case complexity/staffing normalization, or supervisory review workflow. |

## Flat Gap List

| Priority | Category | Size | Line items | Gap |
|---|---|---:|---|---|
| P0 | Authorization/scope | M | FR-001 AC-01/02/04, FR-014 AC-01 | Add senior roles or mapping for Senior_Command/Zone_Officer/SHO/Clerk self-view, jurisdiction scope resolver, and no-scope handling. |
| P0 | Privacy/audit | M | FR-001 BR-01, FR-009 AC-05, FR-014 AC-04/05 | Replace usage-only logging with audit-grade dashboard view/drill/export/threshold records containing role, scope, filters, timestamp, and tamper evidence. |
| P0 | Metric governance | L | FR-012 BR-01/02, FR-017 all dispute/correction items, data model gaps | Add MetricDefinition, SourceMap, Dispute, Correction tables/endpoints/UI and versioned metric changes. |
| P0 | Report/export compliance | L | FR-003 AC-05, FR-011 all, FR-014 export items | Implement dashboard-scoped PDF/CSV exports, queued jobs, SHA-256, expiry, metadata, audit, retry, and scheduled monthly reports. |
| P0 | Dashboard alerting | L | FR-010 all, notifications section | Add alert rule/instance models, thresholds, sample-size handling, alert list, acknowledgement, and in-app notifications. |
| P1 | Filter completeness | S | FR-002 AC-03/05, UI-01/02 | Add constrained officer/station/zone select options, role/case type/offence filters, active removable chips, reset, and URL query sync. |
| P1 | Officer metrics UI | S | FR-003 AC-01/02/04 | Show all required columns, add client/server sorting, and implement officer detail drill-down. |
| P1 | Processing-time source fidelity | M | FR-004 BR-01/02/03/04, EC-01/02 | Link parse records to cases, use petition upload/parse intake, include parser FIR drafts, deduplicate duplicate parses, and warn on clock skew. |
| P1 | Lifecycle fidelity | M | FR-005 AC-01/02/04, BR-01, EC-01/02 | Add conversion percentages, p90 age, stage backlog by station/IO, highest-reached status, transition metrics, and transfer exclusions. |
| P1 | Generated document analytics | M | FR-006 all missing/partial | Count exports, DOCX/PDF, signed/failure status, template usage, subtype breakdowns, parser fallback, and legacy subtype inference. |
| P1 | Feature adoption completeness | M | FR-007 AC-01/02/03/04, EC-01 | Add trends, edited/rejected/rework, latency, citation coverage, completeness score, KIS failure/graph/wiki/quality metrics, and insufficient-sample wording. |
| P1 | Station benchmarking | M | FR-008 all missing/partial | Add adoption rate denominator, median timing, investigation/court counts, cohorts, low-sample warnings, station drill-down, and sortable/exportable table. |
| P1 | Drill-down metadata | M | FR-009 all missing/partial | Add officer/station/stage drill-down subviews with metadata-only case lists and authorized case links. |
| P1 | Refresh/snapshot architecture | L | FR-001 EC-01, FR-013 AC-01/02/05, BR-01, EC-01 | Add metric snapshots, refresh jobs, 5-minute target, stale warnings, direct-compute fallback, and aggregation failure reporting. |
| P1 | Rollout gates | M | FR-018 AC-02/03/04/05, BR-01/03, UI-01/EC-01 | Add validation-state config, operational-awareness labels, field-validation records, UAT tracking, and hide/disable advanced modules until approved. |
| P2 | Training recommendations | M | FR-015 all | Add recommendation engine, thresholds, review/export/dismiss actions, sample-size guard, and non-disciplinary records. |
| P2 | Predictive bottleneck signal | L | FR-016 all missing/partial | Add disabled-by-default feature flag, validation gate, reason codes, explainability, no-PII LLM boundary, and feedback capture. |
| P2 | Personnel safeguards / anti-gaming | M | NFR 8.9/8.10 | Add purpose selection, watermarks, export revocation, sample-size/anomaly warnings, case complexity/staffing normalization, and qualitative review hooks. |
| P2 | Accessibility verification | S | UI 6.x / NFR 8.7 | Add table captions, chart text alternatives, keyboard focus checks, screen-reader labels, and automated/manual accessibility tests. |

## Search Discipline Notes

For missing areas, searches covered at least three strategies:

- Keyword: exact BRD terms such as `DashboardMetricDispute`, `scheduled report`, `cohort`, `sample-size`, `disputed`, `export job`, `alert rule`.
- Entity/path: route paths such as `senior-dashboard/exports`, `senior-dashboard/alerts`, `officers/{user_id}`, `snapshots:refresh`; model names such as `DashboardExportJob`, `DashboardAlertRule`, `MetricDefinition`.
- Semantic/synonym: `threshold`, `acknowledge`, `correction`, `watermark`, `revoked`, `training recommendation`, `predictive`, `low adoption`, `stale snapshot`.

Only unrelated KIS snapshots and unrelated congruence alerts were found for several terms; these do not satisfy senior dashboard requirements.

## Scorecard

Functional FR line-item coverage:

| Metric | Count |
|---|---:|
| Total auditable FR items | 186 |
| Acceptance Criteria | 90 |
| Business Rules | 47 |
| UI Behavior Items | 25 |
| Edge/Error Items | 24 |
| DONE implementation | 47 |
| PARTIAL implementation | 64 |
| DEFERRED | 25 |
| NOT_FOUND | 50 |
| Implementation rate (`DONE + PARTIAL`) | 111 / 186 = 59.7% |
| Automated/indirect test coverage | 37 / 186 = 19.9% |
| Total non-compliant or untested gaps | 149 |

Verdict rule application:

- ACs fully DONE are below 70% for the full BRD.
- P0 gaps exceed 3.
- Automated test coverage is below the 70% compliance threshold.

Final verdict: **AT-RISK**.

## Top 10 Priority Actions

1. Add senior role/jurisdiction scope model and enforce Senior_Command, Zone_Officer, SHO, IO, Clerk behavior.
2. Implement audit-grade dashboard read/drill/export/threshold logging.
3. Add dashboard export job model/API/UI with scoped PDF/CSV, SHA-256, expiry, retry, and scheduled monthly reports.
4. Add metric registry/source-map/dispute/correction persistence with versioning.
5. Add dashboard alert rules/instances, acknowledgement, sample-size handling, and notifications.
6. Complete filter UX: constrained selects, active chips, reset, URL sync, role/case type/offence filters.
7. Improve processing-time source fidelity with linked parse records, petition uploads, duplicate detection, and clock-skew warnings.
8. Complete lifecycle/station/officer drill-downs with metadata-only case lists and sortable/exportable tables.
9. Add data-quality and anti-gaming warnings: low samples, missing postings, duplicate draft spikes, same-day status churn.
10. Add accessibility and performance validation: table alternatives, keyboard checks, representative p95 tests, and indexes/snapshots.

## Commands Run

- `ls -lh docs/senior-officer-dashboard-brd-v2.md && wc -l docs/senior-officer-dashboard-brd-v2.md`
- `find . -maxdepth 3 ...` source/test discovery
- `git branch --show-current && git rev-parse --short HEAD && git status --short`
- `rg` searches for dashboard routes, models, alerts, exports, disputes, snapshots, rate limits
- `JWT_SECRET_KEY=test-jwt-secret-not-for-production PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_senior_dashboard.py -q` -> 5 passed
- `python -m py_compile senior_dashboard.py api_v1.py tests/test_senior_dashboard.py`
- Inline Node parse of `index.html` scripts -> `syntax ok`
