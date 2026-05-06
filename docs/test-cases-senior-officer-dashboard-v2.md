# Test Cases: Senior Officer Performance & Effectiveness Dashboard

**Version:** v2  
**Date:** 2026-05-05  
**Source BRD:** `docs/senior-officer-dashboard-brd-v2.md`

## Table of Contents

1. Test Coverage Summary
2. Traceability Matrix
3. Test Cases by Functional Requirement

### TC-FR001-01: Happy path - Senior Officer Dashboard Entry Point

| Field | Value |
|---|---|
| Test ID | TC-FR001-01 |
| Test Name | Happy path - Senior Officer Dashboard Entry Point |
| Category | Happy Path |
| Linked FR | FR-001 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Senior Officer Dashboard Entry Point.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Senior Officer Dashboard Entry Point data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR001-02: Negative/edge - Senior Officer Dashboard Entry Point

| Field | Value |
|---|---|
| Test ID | TC-FR001-02 |
| Test Name | Negative/edge - Senior Officer Dashboard Entry Point |
| Category | Negative |
| Linked FR | FR-001 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR002-01: Happy path - Period, Scope, and Dimension Filters

| Field | Value |
|---|---|
| Test ID | TC-FR002-01 |
| Test Name | Happy path - Period, Scope, and Dimension Filters |
| Category | Happy Path |
| Linked FR | FR-002 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Period, Scope, and Dimension Filters.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Period, Scope, and Dimension Filters data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR002-02: Negative/edge - Period, Scope, and Dimension Filters

| Field | Value |
|---|---|
| Test ID | TC-FR002-02 |
| Test Name | Negative/edge - Period, Scope, and Dimension Filters |
| Category | Negative |
| Linked FR | FR-002 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR003-01: Happy path - User Productivity Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR003-01 |
| Test Name | Happy path - User Productivity Metrics |
| Category | Happy Path |
| Linked FR | FR-003 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for User Productivity Metrics.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders User Productivity Metrics data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR003-02: Negative/edge - User Productivity Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR003-02 |
| Test Name | Negative/edge - User Productivity Metrics |
| Category | Negative |
| Linked FR | FR-003 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR004-01: Happy path - Complaint-to-FIR Draft Processing Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR004-01 |
| Test Name | Happy path - Complaint-to-FIR Draft Processing Metrics |
| Category | Happy Path |
| Linked FR | FR-004 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Complaint-to-FIR Draft Processing Metrics.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Complaint-to-FIR Draft Processing Metrics data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR004-02: Negative/edge - Complaint-to-FIR Draft Processing Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR004-02 |
| Test Name | Negative/edge - Complaint-to-FIR Draft Processing Metrics |
| Category | Negative |
| Linked FR | FR-004 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR005-01: Happy path - Complaint-to-FIR and Investigation Lifecycle Funnel

| Field | Value |
|---|---|
| Test ID | TC-FR005-01 |
| Test Name | Happy path - Complaint-to-FIR and Investigation Lifecycle Funnel |
| Category | Happy Path |
| Linked FR | FR-005 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Complaint-to-FIR and Investigation Lifecycle Funnel.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Complaint-to-FIR and Investigation Lifecycle Funnel data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR005-02: Negative/edge - Complaint-to-FIR and Investigation Lifecycle Funnel

| Field | Value |
|---|---|
| Test ID | TC-FR005-02 |
| Test Name | Negative/edge - Complaint-to-FIR and Investigation Lifecycle Funnel |
| Category | Negative |
| Linked FR | FR-005 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR006-01: Happy path - FIR Draft and Generated Document Analytics

| Field | Value |
|---|---|
| Test ID | TC-FR006-01 |
| Test Name | Happy path - FIR Draft and Generated Document Analytics |
| Category | Happy Path |
| Linked FR | FR-006 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for FIR Draft and Generated Document Analytics.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders FIR Draft and Generated Document Analytics data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR006-02: Negative/edge - FIR Draft and Generated Document Analytics

| Field | Value |
|---|---|
| Test ID | TC-FR006-02 |
| Test Name | Negative/edge - FIR Draft and Generated Document Analytics |
| Category | Negative |
| Linked FR | FR-006 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR007-01: Happy path - Feature Adoption and AI Effectiveness

| Field | Value |
|---|---|
| Test ID | TC-FR007-01 |
| Test Name | Happy path - Feature Adoption and AI Effectiveness |
| Category | Happy Path |
| Linked FR | FR-007 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Feature Adoption and AI Effectiveness.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Feature Adoption and AI Effectiveness data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR007-02: Negative/edge - Feature Adoption and AI Effectiveness

| Field | Value |
|---|---|
| Test ID | TC-FR007-02 |
| Test Name | Negative/edge - Feature Adoption and AI Effectiveness |
| Category | Negative |
| Linked FR | FR-007 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR008-01: Happy path - Station Comparison and Cohort Benchmarking

| Field | Value |
|---|---|
| Test ID | TC-FR008-01 |
| Test Name | Happy path - Station Comparison and Cohort Benchmarking |
| Category | Happy Path |
| Linked FR | FR-008 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Station Comparison and Cohort Benchmarking.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Station Comparison and Cohort Benchmarking data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR008-02: Negative/edge - Station Comparison and Cohort Benchmarking

| Field | Value |
|---|---|
| Test ID | TC-FR008-02 |
| Test Name | Negative/edge - Station Comparison and Cohort Benchmarking |
| Category | Negative |
| Linked FR | FR-008 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR009-01: Happy path - Officer Detail and Case Metadata Drill-Down

| Field | Value |
|---|---|
| Test ID | TC-FR009-01 |
| Test Name | Happy path - Officer Detail and Case Metadata Drill-Down |
| Category | Happy Path |
| Linked FR | FR-009 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Officer Detail and Case Metadata Drill-Down.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Officer Detail and Case Metadata Drill-Down data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR009-02: Negative/edge - Officer Detail and Case Metadata Drill-Down

| Field | Value |
|---|---|
| Test ID | TC-FR009-02 |
| Test Name | Negative/edge - Officer Detail and Case Metadata Drill-Down |
| Category | Negative |
| Linked FR | FR-009 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR010-01: Happy path - Bottleneck Detection and Alerts

| Field | Value |
|---|---|
| Test ID | TC-FR010-01 |
| Test Name | Happy path - Bottleneck Detection and Alerts |
| Category | Happy Path |
| Linked FR | FR-010 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Bottleneck Detection and Alerts.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Bottleneck Detection and Alerts data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR010-02: Negative/edge - Bottleneck Detection and Alerts

| Field | Value |
|---|---|
| Test ID | TC-FR010-02 |
| Test Name | Negative/edge - Bottleneck Detection and Alerts |
| Category | Negative |
| Linked FR | FR-010 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR011-01: Happy path - Report Export and Scheduled Reports

| Field | Value |
|---|---|
| Test ID | TC-FR011-01 |
| Test Name | Happy path - Report Export and Scheduled Reports |
| Category | Happy Path |
| Linked FR | FR-011 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Report Export and Scheduled Reports.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Report Export and Scheduled Reports data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR011-02: Negative/edge - Report Export and Scheduled Reports

| Field | Value |
|---|---|
| Test ID | TC-FR011-02 |
| Test Name | Negative/edge - Report Export and Scheduled Reports |
| Category | Negative |
| Linked FR | FR-011 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR012-01: Happy path - Metric Definition and Data Quality Transparency

| Field | Value |
|---|---|
| Test ID | TC-FR012-01 |
| Test Name | Happy path - Metric Definition and Data Quality Transparency |
| Category | Happy Path |
| Linked FR | FR-012 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Metric Definition and Data Quality Transparency.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Metric Definition and Data Quality Transparency data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR012-02: Negative/edge - Metric Definition and Data Quality Transparency

| Field | Value |
|---|---|
| Test ID | TC-FR012-02 |
| Test Name | Negative/edge - Metric Definition and Data Quality Transparency |
| Category | Negative |
| Linked FR | FR-012 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR013-01: Happy path - Data Refresh and Aggregation

| Field | Value |
|---|---|
| Test ID | TC-FR013-01 |
| Test Name | Happy path - Data Refresh and Aggregation |
| Category | Happy Path |
| Linked FR | FR-013 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Data Refresh and Aggregation.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Data Refresh and Aggregation data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR013-02: Negative/edge - Data Refresh and Aggregation

| Field | Value |
|---|---|
| Test ID | TC-FR013-02 |
| Test Name | Negative/edge - Data Refresh and Aggregation |
| Category | Negative |
| Linked FR | FR-013 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR014-01: Happy path - Privacy, Authorization, and Audit Controls

| Field | Value |
|---|---|
| Test ID | TC-FR014-01 |
| Test Name | Happy path - Privacy, Authorization, and Audit Controls |
| Category | Happy Path |
| Linked FR | FR-014 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Privacy, Authorization, and Audit Controls.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Privacy, Authorization, and Audit Controls data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR014-02: Negative/edge - Privacy, Authorization, and Audit Controls

| Field | Value |
|---|---|
| Test ID | TC-FR014-02 |
| Test Name | Negative/edge - Privacy, Authorization, and Audit Controls |
| Category | Negative |
| Linked FR | FR-014 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR015-01: Happy path - Training and Adoption Recommendations

| Field | Value |
|---|---|
| Test ID | TC-FR015-01 |
| Test Name | Happy path - Training and Adoption Recommendations |
| Category | Happy Path |
| Linked FR | FR-015 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Training and Adoption Recommendations.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Training and Adoption Recommendations data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR015-02: Negative/edge - Training and Adoption Recommendations

| Field | Value |
|---|---|
| Test ID | TC-FR015-02 |
| Test Name | Negative/edge - Training and Adoption Recommendations |
| Category | Negative |
| Linked FR | FR-015 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR016-01: Happy path - Predictive Bottleneck Signal

| Field | Value |
|---|---|
| Test ID | TC-FR016-01 |
| Test Name | Happy path - Predictive Bottleneck Signal |
| Category | Happy Path |
| Linked FR | FR-016 |
| Priority | High |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Predictive Bottleneck Signal.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Predictive Bottleneck Signal data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR016-02: Negative/edge - Predictive Bottleneck Signal

| Field | Value |
|---|---|
| Test ID | TC-FR016-02 |
| Test Name | Negative/edge - Predictive Bottleneck Signal |
| Category | Negative |
| Linked FR | FR-016 |
| Priority | High |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR017-01: Happy path - Metric Legitimacy, Challenge, and Correction

| Field | Value |
|---|---|
| Test ID | TC-FR017-01 |
| Test Name | Happy path - Metric Legitimacy, Challenge, and Correction |
| Category | Happy Path |
| Linked FR | FR-017 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for Metric Legitimacy, Challenge, and Correction.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders Metric Legitimacy, Challenge, and Correction data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR017-02: Negative/edge - Metric Legitimacy, Challenge, and Correction

| Field | Value |
|---|---|
| Test ID | TC-FR017-02 |
| Test Name | Negative/edge - Metric Legitimacy, Challenge, and Correction |
| Category | Negative |
| Linked FR | FR-017 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

### TC-FR018-01: Happy path - MVP Rollout and Field Validation Controls

| Field | Value |
|---|---|
| Test ID | TC-FR018-01 |
| Test Name | Happy path - MVP Rollout and Field Validation Controls |
| Category | Happy Path |
| Linked FR | FR-018 |
| Priority | Critical |
| Preconditions | User is authenticated with a role permitted by the BRD. Test data includes cases, users, stations, generated documents, AI results, usage events, and audit records for the selected scope. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Select period Last 30 days.<br>3. Apply a valid police-station or role-default scope.<br>4. Navigate to the feature area for MVP Rollout and Field Validation Controls.<br>5. Review cards/tables/charts and open metric definition where available. |
| Test Data | Role: Senior_Command or System_Admin; Period: last_30_days; Station: ps_abids; Officer: HCP2088 where applicable. |
| Expected Result | The dashboard renders MVP Rollout and Field Validation Controls data for the authorized scope. Values match seeded source data. Metric definition, freshness, and confidence are visible where required. No complaint narrative, OCR text, addresses, phone numbers, victim names, accused names, or FIR draft body appears. |
| Postconditions | A dashboard.view audit event or equivalent usage event is recorded with filters hash and scope metadata. |

### TC-FR018-02: Negative/edge - MVP Rollout and Field Validation Controls

| Field | Value |
|---|---|
| Test ID | TC-FR018-02 |
| Test Name | Negative/edge - MVP Rollout and Field Validation Controls |
| Category | Negative |
| Linked FR | FR-018 |
| Priority | Critical |
| Preconditions | User is authenticated. Dataset includes at least one out-of-scope station/officer and one empty-result filter combination. |
| Test Steps | 1. Open the Senior Dashboard.<br>2. Attempt to access the feature with an out-of-scope station or officer filter.<br>3. Repeat with a filter combination that returns zero rows.<br>4. If the feature accepts input, submit one invalid or PII-containing value. |
| Test Data | Out-of-scope station: ps_other; Invalid date range: date_from after date_to; PII text sample: complainant phone number in dispute description. |
| Expected Result | Out-of-scope access returns or displays AUTHORIZATION_ERROR. Empty filters show a clear zero-state without crashing. Invalid input returns VALIDATION_ERROR with field name. PII-containing dashboard governance text is rejected where the BRD prohibits PII. |
| Postconditions | No unauthorized metric data is persisted or displayed. Error path is audit-safe and does not leak secrets or PII. |

## 1. Test Coverage Summary

| Metric | Value |
|---|---:|
| Total Test Cases | 41 |
| FRs Covered | 18 / 18 |
| Happy Path Tests | 18 |
| Negative Tests | 18 |
| Boundary Tests | 2 |
| Permission Tests | 4 |
| Integration Tests | 4 |
| Critical Priority | 20 |
| High Priority | 21 |
| Medium Priority | 0 |
| Low Priority | 0 |

## 2. Traceability Matrix

| Requirement | Test Cases |
|---|---|
| FR-001 | TC-FR001-01, TC-FR001-02 |
| FR-002 | TC-FR002-01, TC-FR002-02 |
| FR-003 | TC-FR003-01, TC-FR003-02 |
| FR-004 | TC-FR004-01, TC-FR004-02 |
| FR-005 | TC-FR005-01, TC-FR005-02 |
| FR-006 | TC-FR006-01, TC-FR006-02 |
| FR-007 | TC-FR007-01, TC-FR007-02 |
| FR-008 | TC-FR008-01, TC-FR008-02 |
| FR-009 | TC-FR009-01, TC-FR009-02 |
| FR-010 | TC-FR010-01, TC-FR010-02 |
| FR-011 | TC-FR011-01, TC-FR011-02 |
| FR-012 | TC-FR012-01, TC-FR012-02 |
| FR-013 | TC-FR013-01, TC-FR013-02 |
| FR-014 | TC-FR014-01, TC-FR014-02 |
| FR-015 | TC-FR015-01, TC-FR015-02 |
| FR-016 | TC-FR016-01, TC-FR016-02 |
| FR-017 | TC-FR017-01, TC-FR017-02 |
| FR-018 | TC-FR018-01, TC-FR018-02 |
| Cross-feature boundaries and permissions | TC-DASH-BOUNDARY-01, TC-DASH-PERM-01, TC-DASH-INTEGRATION-01, TC-DASH-GOV-01, TC-DASH-PRIVACY-01 |

## 3. Test Cases by Functional Requirement

## FR-001: Senior Officer Dashboard Entry Point

### TC-FR001-01: Happy path - Senior Officer Dashboard Entry Point

| Field | Value |
|---|---|
| Test ID | TC-FR001-01 |
| Test Name | Happy path - Senior Officer Dashboard Entry Point |
| Category | Happy Path |
| Linked FR | FR-001 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Senior Officer Dashboard Entry Point feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Senior Officer Dashboard Entry Point renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR001-02: Negative/edge - Senior Officer Dashboard Entry Point

| Field | Value |
|---|---|
| Test ID | TC-FR001-02 |
| Test Name | Negative/edge - Senior Officer Dashboard Entry Point |
| Category | Negative |
| Linked FR | FR-001 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-002: Period, Scope, and Dimension Filters

### TC-FR002-01: Happy path - Period, Scope, and Dimension Filters

| Field | Value |
|---|---|
| Test ID | TC-FR002-01 |
| Test Name | Happy path - Period, Scope, and Dimension Filters |
| Category | Happy Path |
| Linked FR | FR-002 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Period, Scope, and Dimension Filters feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Period, Scope, and Dimension Filters renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR002-02: Negative/edge - Period, Scope, and Dimension Filters

| Field | Value |
|---|---|
| Test ID | TC-FR002-02 |
| Test Name | Negative/edge - Period, Scope, and Dimension Filters |
| Category | Negative |
| Linked FR | FR-002 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-003: User Productivity Metrics

### TC-FR003-01: Happy path - User Productivity Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR003-01 |
| Test Name | Happy path - User Productivity Metrics |
| Category | Happy Path |
| Linked FR | FR-003 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use User Productivity Metrics feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | User Productivity Metrics renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR003-02: Negative/edge - User Productivity Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR003-02 |
| Test Name | Negative/edge - User Productivity Metrics |
| Category | Negative |
| Linked FR | FR-003 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-004: Complaint-to-FIR Draft Processing Metrics

### TC-FR004-01: Happy path - Complaint-to-FIR Draft Processing Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR004-01 |
| Test Name | Happy path - Complaint-to-FIR Draft Processing Metrics |
| Category | Happy Path |
| Linked FR | FR-004 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Complaint-to-FIR Draft Processing Metrics feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Complaint-to-FIR Draft Processing Metrics renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR004-02: Negative/edge - Complaint-to-FIR Draft Processing Metrics

| Field | Value |
|---|---|
| Test ID | TC-FR004-02 |
| Test Name | Negative/edge - Complaint-to-FIR Draft Processing Metrics |
| Category | Negative |
| Linked FR | FR-004 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-005: Complaint-to-FIR and Investigation Lifecycle Funnel

### TC-FR005-01: Happy path - Complaint-to-FIR and Investigation Lifecycle Funnel

| Field | Value |
|---|---|
| Test ID | TC-FR005-01 |
| Test Name | Happy path - Complaint-to-FIR and Investigation Lifecycle Funnel |
| Category | Happy Path |
| Linked FR | FR-005 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Complaint-to-FIR and Investigation Lifecycle Funnel feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Complaint-to-FIR and Investigation Lifecycle Funnel renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR005-02: Negative/edge - Complaint-to-FIR and Investigation Lifecycle Funnel

| Field | Value |
|---|---|
| Test ID | TC-FR005-02 |
| Test Name | Negative/edge - Complaint-to-FIR and Investigation Lifecycle Funnel |
| Category | Negative |
| Linked FR | FR-005 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-006: FIR Draft and Generated Document Analytics

### TC-FR006-01: Happy path - FIR Draft and Generated Document Analytics

| Field | Value |
|---|---|
| Test ID | TC-FR006-01 |
| Test Name | Happy path - FIR Draft and Generated Document Analytics |
| Category | Happy Path |
| Linked FR | FR-006 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use FIR Draft and Generated Document Analytics feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | FIR Draft and Generated Document Analytics renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR006-02: Negative/edge - FIR Draft and Generated Document Analytics

| Field | Value |
|---|---|
| Test ID | TC-FR006-02 |
| Test Name | Negative/edge - FIR Draft and Generated Document Analytics |
| Category | Negative |
| Linked FR | FR-006 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-007: Feature Adoption and AI Effectiveness

### TC-FR007-01: Happy path - Feature Adoption and AI Effectiveness

| Field | Value |
|---|---|
| Test ID | TC-FR007-01 |
| Test Name | Happy path - Feature Adoption and AI Effectiveness |
| Category | Happy Path |
| Linked FR | FR-007 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Feature Adoption and AI Effectiveness feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Feature Adoption and AI Effectiveness renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR007-02: Negative/edge - Feature Adoption and AI Effectiveness

| Field | Value |
|---|---|
| Test ID | TC-FR007-02 |
| Test Name | Negative/edge - Feature Adoption and AI Effectiveness |
| Category | Negative |
| Linked FR | FR-007 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-008: Station Comparison and Cohort Benchmarking

### TC-FR008-01: Happy path - Station Comparison and Cohort Benchmarking

| Field | Value |
|---|---|
| Test ID | TC-FR008-01 |
| Test Name | Happy path - Station Comparison and Cohort Benchmarking |
| Category | Happy Path |
| Linked FR | FR-008 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Station Comparison and Cohort Benchmarking feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Station Comparison and Cohort Benchmarking renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR008-02: Negative/edge - Station Comparison and Cohort Benchmarking

| Field | Value |
|---|---|
| Test ID | TC-FR008-02 |
| Test Name | Negative/edge - Station Comparison and Cohort Benchmarking |
| Category | Negative |
| Linked FR | FR-008 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-009: Officer Detail and Case Metadata Drill-Down

### TC-FR009-01: Happy path - Officer Detail and Case Metadata Drill-Down

| Field | Value |
|---|---|
| Test ID | TC-FR009-01 |
| Test Name | Happy path - Officer Detail and Case Metadata Drill-Down |
| Category | Happy Path |
| Linked FR | FR-009 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Officer Detail and Case Metadata Drill-Down feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Officer Detail and Case Metadata Drill-Down renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR009-02: Negative/edge - Officer Detail and Case Metadata Drill-Down

| Field | Value |
|---|---|
| Test ID | TC-FR009-02 |
| Test Name | Negative/edge - Officer Detail and Case Metadata Drill-Down |
| Category | Negative |
| Linked FR | FR-009 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-010: Bottleneck Detection and Alerts

### TC-FR010-01: Happy path - Bottleneck Detection and Alerts

| Field | Value |
|---|---|
| Test ID | TC-FR010-01 |
| Test Name | Happy path - Bottleneck Detection and Alerts |
| Category | Happy Path |
| Linked FR | FR-010 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Bottleneck Detection and Alerts feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Bottleneck Detection and Alerts renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR010-02: Negative/edge - Bottleneck Detection and Alerts

| Field | Value |
|---|---|
| Test ID | TC-FR010-02 |
| Test Name | Negative/edge - Bottleneck Detection and Alerts |
| Category | Negative |
| Linked FR | FR-010 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-011: Report Export and Scheduled Reports

### TC-FR011-01: Happy path - Report Export and Scheduled Reports

| Field | Value |
|---|---|
| Test ID | TC-FR011-01 |
| Test Name | Happy path - Report Export and Scheduled Reports |
| Category | Happy Path |
| Linked FR | FR-011 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Report Export and Scheduled Reports feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Report Export and Scheduled Reports renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR011-02: Negative/edge - Report Export and Scheduled Reports

| Field | Value |
|---|---|
| Test ID | TC-FR011-02 |
| Test Name | Negative/edge - Report Export and Scheduled Reports |
| Category | Negative |
| Linked FR | FR-011 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-012: Metric Definition and Data Quality Transparency

### TC-FR012-01: Happy path - Metric Definition and Data Quality Transparency

| Field | Value |
|---|---|
| Test ID | TC-FR012-01 |
| Test Name | Happy path - Metric Definition and Data Quality Transparency |
| Category | Happy Path |
| Linked FR | FR-012 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Metric Definition and Data Quality Transparency feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Metric Definition and Data Quality Transparency renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR012-02: Negative/edge - Metric Definition and Data Quality Transparency

| Field | Value |
|---|---|
| Test ID | TC-FR012-02 |
| Test Name | Negative/edge - Metric Definition and Data Quality Transparency |
| Category | Negative |
| Linked FR | FR-012 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-013: Data Refresh and Aggregation

### TC-FR013-01: Happy path - Data Refresh and Aggregation

| Field | Value |
|---|---|
| Test ID | TC-FR013-01 |
| Test Name | Happy path - Data Refresh and Aggregation |
| Category | Happy Path |
| Linked FR | FR-013 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Data Refresh and Aggregation feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Data Refresh and Aggregation renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR013-02: Negative/edge - Data Refresh and Aggregation

| Field | Value |
|---|---|
| Test ID | TC-FR013-02 |
| Test Name | Negative/edge - Data Refresh and Aggregation |
| Category | Negative |
| Linked FR | FR-013 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-014: Privacy, Authorization, and Audit Controls

### TC-FR014-01: Happy path - Privacy, Authorization, and Audit Controls

| Field | Value |
|---|---|
| Test ID | TC-FR014-01 |
| Test Name | Happy path - Privacy, Authorization, and Audit Controls |
| Category | Happy Path |
| Linked FR | FR-014 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Privacy, Authorization, and Audit Controls feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Privacy, Authorization, and Audit Controls renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR014-02: Negative/edge - Privacy, Authorization, and Audit Controls

| Field | Value |
|---|---|
| Test ID | TC-FR014-02 |
| Test Name | Negative/edge - Privacy, Authorization, and Audit Controls |
| Category | Negative |
| Linked FR | FR-014 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-015: Training and Adoption Recommendations

### TC-FR015-01: Happy path - Training and Adoption Recommendations

| Field | Value |
|---|---|
| Test ID | TC-FR015-01 |
| Test Name | Happy path - Training and Adoption Recommendations |
| Category | Happy Path |
| Linked FR | FR-015 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Training and Adoption Recommendations feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Training and Adoption Recommendations renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR015-02: Negative/edge - Training and Adoption Recommendations

| Field | Value |
|---|---|
| Test ID | TC-FR015-02 |
| Test Name | Negative/edge - Training and Adoption Recommendations |
| Category | Negative |
| Linked FR | FR-015 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-016: Predictive Bottleneck Signal

### TC-FR016-01: Happy path - Predictive Bottleneck Signal

| Field | Value |
|---|---|
| Test ID | TC-FR016-01 |
| Test Name | Happy path - Predictive Bottleneck Signal |
| Category | Happy Path |
| Linked FR | FR-016 |
| Priority | High |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Predictive Bottleneck Signal feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Predictive Bottleneck Signal renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR016-02: Negative/edge - Predictive Bottleneck Signal

| Field | Value |
|---|---|
| Test ID | TC-FR016-02 |
| Test Name | Negative/edge - Predictive Bottleneck Signal |
| Category | Negative |
| Linked FR | FR-016 |
| Priority | High |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-017: Metric Legitimacy, Challenge, and Correction

### TC-FR017-01: Happy path - Metric Legitimacy, Challenge, and Correction

| Field | Value |
|---|---|
| Test ID | TC-FR017-01 |
| Test Name | Happy path - Metric Legitimacy, Challenge, and Correction |
| Category | Happy Path |
| Linked FR | FR-017 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use Metric Legitimacy, Challenge, and Correction feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | Metric Legitimacy, Challenge, and Correction renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR017-02: Negative/edge - Metric Legitimacy, Challenge, and Correction

| Field | Value |
|---|---|
| Test ID | TC-FR017-02 |
| Test Name | Negative/edge - Metric Legitimacy, Challenge, and Correction |
| Category | Negative |
| Linked FR | FR-017 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

## FR-018: MVP Rollout and Field Validation Controls

### TC-FR018-01: Happy path - MVP Rollout and Field Validation Controls

| Field | Value |
|---|---|
| Test ID | TC-FR018-01 |
| Test Name | Happy path - MVP Rollout and Field Validation Controls |
| Category | Happy Path |
| Linked FR | FR-018 |
| Priority | Critical |
| Preconditions | Authorized user and seeded operational data exist. |
| Test Steps | 1. Open Senior Dashboard.<br>2. Apply valid scope and period.<br>3. Use MVP Rollout and Field Validation Controls feature.<br>4. Inspect metric definition/freshness/confidence.<br>5. Verify audit-safe payload. |
| Test Data | Period=last_30_days; Station=ps_abids; Officer=HCP2088 where applicable. |
| Expected Result | MVP Rollout and Field Validation Controls renders correct scoped metrics. No PII appears. Confidence/freshness metadata is present when required. |
| Postconditions | Dashboard access is auditable. |

### TC-FR018-02: Negative/edge - MVP Rollout and Field Validation Controls

| Field | Value |
|---|---|
| Test ID | TC-FR018-02 |
| Test Name | Negative/edge - MVP Rollout and Field Validation Controls |
| Category | Negative |
| Linked FR | FR-018 |
| Priority | Critical |
| Preconditions | Authorized user exists plus out-of-scope and empty-result data. |
| Test Steps | 1. Use an out-of-scope filter.<br>2. Use an empty-result filter.<br>3. Submit invalid input if feature accepts input.<br>4. Verify error and zero states. |
| Test Data | Out-of-scope station=ps_other; invalid date range; PII in governance text if applicable. |
| Expected Result | Unauthorized scope is denied, empty result is stable, invalid input gives standardized error, and no restricted data leaks. |
| Postconditions | No invalid data is persisted. |

### TC-DASH-BOUNDARY-01: Custom date range boundaries

| Field | Value |
|---|---|
| Test ID | TC-DASH-BOUNDARY-01 |
| Test Name | Custom date range boundaries |
| Category | Boundary |
| Linked FR | FR-002 |
| Priority | High |
| Preconditions | User has dashboard access. |
| Test Steps | 1. Submit a custom date range of exactly 366 days.<br>2. Submit 367 days.<br>3. Submit date_from one day after date_to. |
| Test Data | date_from=2025-05-05, date_to=2026-05-05; date_from=2025-05-04, date_to=2026-05-05; date_from=2026-05-06, date_to=2026-05-05. |
| Expected Result | Exactly 366 days is accepted. 367 days and reversed date range return VALIDATION_ERROR with field date_from/date_to. |
| Postconditions | No metric snapshot is created for invalid ranges. |

### TC-DASH-PERM-01: Role scope authorization matrix

| Field | Value |
|---|---|
| Test ID | TC-DASH-PERM-01 |
| Test Name | Role scope authorization matrix |
| Category | Permission |
| Linked FR | FR-001, FR-014 |
| Priority | Critical |
| Preconditions | Users exist for Senior_Command, Zone_Officer, SHO, AI_Admin, System_Admin, IO, and Clerk roles. |
| Test Steps | 1. Call overview as each role.<br>2. Verify default scope for each role.<br>3. Attempt city-wide scope as IO and Clerk.<br>4. Attempt AI metric view as AI_Admin.<br>5. Attempt threshold configuration as non-System_Admin. |
| Test Data | Roles: Senior_Command, Zone_Officer, SHO, AI_Admin, System_Admin, IO, Clerk. |
| Expected Result | Authorized scopes succeed. IO and Clerk cannot view other users. AI_Admin sees AI/adoption metrics only. Threshold mutation is allowed only for System_Admin. |
| Postconditions | Authorization failures are logged without returning restricted metric payloads. |

### TC-DASH-INTEGRATION-01: Complaint intake to FIR draft lifecycle journey

| Field | Value |
|---|---|
| Test ID | TC-DASH-INTEGRATION-01 |
| Test Name | Complaint intake to FIR draft lifecycle journey |
| Category | Integration |
| Linked FR | FR-003, FR-004, FR-005, FR-006, FR-012 |
| Priority | Critical |
| Preconditions | A complaint parse record, case, FIR draft generated document, status transition, and usage events are linked to the same workflow. |
| Test Steps | 1. Create or seed complaint parse record.<br>2. Create case linked to the complaint.<br>3. Generate FIR draft.<br>4. Transition case to FIR_Registered.<br>5. Open processing-times and lifecycle dashboard.<br>6. Open the case metadata drill-down. |
| Test Data | Complaint file complaint_001.pdf; Case case_001; Generated document subtype FIR_Draft. |
| Expected Result | FIR draft count increments by one. Complaint-to-FIR-draft minutes equals first draft timestamp minus first intake timestamp. Lifecycle funnel shows FIR_Registered. Drill-down shows metadata only and no raw complaint text. |
| Postconditions | Dashboard source warning is absent when all links are high confidence. |

### TC-DASH-GOV-01: Metric dispute correction supersedes export

| Field | Value |
|---|---|
| Test ID | TC-DASH-GOV-01 |
| Test Name | Metric dispute correction supersedes export |
| Category | Integration |
| Linked FR | FR-011, FR-017 |
| Priority | Critical |
| Preconditions | A completed officer usage export exists and a metric row has incorrect officer attribution. |
| Test Steps | 1. Submit a metric dispute with reason wrong_assignment.<br>2. Approve the dispute as System_Admin.<br>3. Create DashboardMetricCorrection.<br>4. Check prior export status.<br>5. Request corrected export. |
| Test Data | Metric: cases_created; Original count 7; Corrected count 6; Reason: wrong_assignment. |
| Expected Result | Dispute status becomes accepted/corrected. Original and corrected values are retained. Prior export is marked superseded. Requester receives in-app notification. New export includes corrected value and permitted-use watermark. |
| Postconditions | Audit trail distinguishes original, disputed, corrected, and superseded states. |

### TC-DASH-PRIVACY-01: PII exclusion in APIs and exports

| Field | Value |
|---|---|
| Test ID | TC-DASH-PRIVACY-01 |
| Test Name | PII exclusion in APIs and exports |
| Category | Permission |
| Linked FR | FR-009, FR-014 |
| Priority | Critical |
| Preconditions | Dashboard source records include complaint narrative, OCR text, generated FIR draft content, phone number, and address in operational tables. |
| Test Steps | 1. Call overview, officers, stations, lifecycle, processing-times, and export endpoints.<br>2. Search response payloads and exported file text for seeded PII values.<br>3. Open authorized case detail separately for comparison. |
| Test Data | Seeded forbidden values: +91-9999999999, 1-2-3 Test Address, Victim Name Test, Accused Name Test. |
| Expected Result | Dashboard APIs and exports do not contain forbidden values. Existing case-detail screen may show authorized case data according to pre-existing permissions. Dashboard DTOs are separate from case-detail DTOs. |
| Postconditions | Any PII leakage fails the release gate. |

