# Senior Officer Performance & Effectiveness Dashboard BRD v2

**Document Status:** Final v2  
**Date:** 2026-05-05  
**Classification:** Confidential  
**Product Context:** Hyderabad City Police Investigation Quality Workbench (IQW)  
**Source Inputs:** `docs/HCP_IQW_BRD_v1.docx`, `docs/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.pdf`, current IQW codebase and analytics implementation

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope & Boundaries](#2-scope--boundaries)
3. [User Roles & Permissions](#3-user-roles--permissions)
4. [Data Model](#4-data-model)
5. [Functional Requirements](#5-functional-requirements)
6. [User Interface Requirements](#6-user-interface-requirements)
7. [API & Integration Requirements](#7-api--integration-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Workflow & State Diagrams](#9-workflow--state-diagrams)
10. [Notification & Communication Requirements](#10-notification--communication-requirements)
11. [Reporting & Analytics](#11-reporting--analytics)
12. [Migration & Launch Plan](#12-migration--launch-plan)
13. [Glossary](#13-glossary)
14. [Appendices](#14-appendices)

## 1. Executive Summary

## Version 2 Change Summary

The adversarial council recommended proceeding with the dashboard only after strengthening governance and narrowing the first release. This v2 BRD makes the following changes:

- Separates mandatory Module 10 compliance from optional blue-ocean enhancements.
- Adds a command decision model that maps dashboard signals to allowed operational actions.
- Adds a metric legitimacy framework with permitted-use classes and prohibited uses.
- Adds data-quality confidence tiers, sample-size gates, and officer-level rollout gates.
- Adds metric contestability, adjudication, correction, and corrected-export handling.
- Adds canonical event taxonomy and source-of-truth rules for lifecycle/status metrics.
- Clarifies complaint-to-FIR draft time versus complaint-to-FIR registration time.
- Adds personnel analytics protections, watermarking, export revocation, and shorter export expiry.
- Narrows Phase 1 to trusted read-only overview, filters, officer/station tables, lifecycle funnel, RBAC, audit, and PII exclusion tests.


### 1.1 Project Name

Senior Officer Performance & Effectiveness Dashboard for IQW.

### 1.2 Project Description

The dashboard gives senior police officers a command-level view of IQW adoption, complaint-to-FIR conversion, investigation progress, drafting efficiency, and station/officer-level usage. It builds on the existing BRD Module 10 requirement for usage and adoption analytics and extends it into an operational effectiveness console that answers: who is using the system, how fast complaints move from upload to actionable FIR draft or FIR registration, which stations are progressing investigations, which workflow stages are stuck, and where additional training or supervisory attention is needed.

### 1.3 Business Objectives

- Provide senior officers with daily and monthly visibility into user, police-station, and case-lifecycle activity.
- Measure complaint processing effectiveness from first complaint upload/parse through FIR draft creation, FIR registration, investigation completion, court progression, and disposal.
- Identify low adoption, bottlenecks, rework, delayed investigations, and poor-quality AI usage patterns before they become operational issues.
- Support data-backed training, station review meetings, and governance reporting without exposing sensitive complaint details unnecessarily.
- Preserve BRD/RFQ auditability by making all dashboard metrics traceable to underlying cases, documents, generated drafts, activity logs, and usage events.

### 1.4 Target Users and Pain Points

| User Group | Pain Points | Dashboard Value |
|---|---|---|
| Commissioner / Joint Commissioner | Needs quick command overview across stations without reading individual files | City-wide KPIs, trends, station ranking, alerts |
| DCP / ACP / Zone Officer | Needs to know which stations and IOs are delayed or underusing the platform | Station comparison, IO drill-down, bottleneck detection |
| Station House Officer (SHO) | Needs station-level work allocation and pending investigation visibility | Station dashboard, officer workload, overdue stage alerts |
| AI Admin | Needs feature adoption, AI usefulness, and training gaps | Module usage, AI acceptance/rework metrics, flagged low-confidence work |
| System Admin | Needs operational and audit health | Data freshness, event pipeline, export audit, access logs |

### 1.5 Success Metrics

| KPI | Target |
|---|---:|
| Dashboard load time for default 30-day view | p95 under 3 seconds for 10,000 cases |
| Metric freshness | 95% of events visible within 5 minutes |
| Officer/station filter accuracy | 100% alignment with HRMS/user posting and case `police_station_id` |
| Adoption monitoring coverage | 100% of case creation, document upload, AI check, generated draft, export, and status-transition events counted |
| Senior officer weekly usage | At least 80% of configured senior roles access dashboard weekly after rollout |
| Training gap detection | Stations below 60% active-user adoption flagged within one reporting period |

## 2. Scope & Boundaries

### 2.1 In Scope

- Senior-officer dashboard landing page inside IQW.
- Period filters for last 7 days, last 30 days, current month, previous month, custom date range.
- Police station, officer, role, case type, offence category, and case-status filters.
- User productivity metrics: cases created, FIRs registered, FIR drafts generated, generated document drafts, uploaded documents, AI checks performed, and active days.
- Complaint processing metrics: first complaint upload/parse timestamp, first FIR draft timestamp, last FIR draft timestamp, number of FIR draft iterations, time from complaint to FIR draft, time from complaint to FIR registration.
- Lifecycle effectiveness metrics: complaints received, FIR registered, under investigation, charge sheet filed, closure report filed, court proceedings, disposed, transferred, closed without FIR.
- Funnel and conversion metrics by period, station, and IO.
- Bottleneck detection for cases stuck in a workflow stage beyond configured thresholds.
- Feature adoption metrics for OCR, translation, quality checks, BNS/section recommendation, congruence checks, investigation plan generation, document generation, KIS indexing, and exports.
- Effectiveness indicators: AI recommendation acceptance, AI output uncertainty rate, average document completeness score, quality gate pass rate, and rework indicators.
- Drill-down views from KPI to station, officer, case list, and case timeline.
- Scheduled and on-demand PDF/CSV exports for officer usage, station performance, lifecycle funnel, and monthly trends.
- Audit logging for dashboard access, filter usage, export, and drill-down into case-level metrics.
- Metric definition registry so dashboard numbers are explainable and stable.


### 2.2 Mandatory Module 10 Compliance vs Optional Enhancements

| Category | Requirements | Release Treatment |
|---|---|---|
| Mandatory Module 10 Compliance | Cases per IO/station, documents uploaded, AI checks, drafts generated, time spent, feature frequency, officer usage report, adoption report, monthly trends | Must be implemented before Module 10 is marked compliant |
| Operational Effectiveness Extension | Complaint-to-FIR draft timing, lifecycle funnel, investigation completion, court progression, station comparison, bottleneck detection | Implement after data source and governance checks pass |
| Optional Blue Ocean Enhancements | Predictive bottleneck signal, training recommendations, cohort benchmarking, composite effectiveness index | Disabled by default; require field validation and formal approval |

Phase 1 must not implement punitive scoring, automated personnel conclusions, or predictive alerts. Phase 1 is limited to read-only, explainable, non-PII operational analytics over trusted source data.

### 2.3 Command Decision Model

| Command Question | Primary User | Metric Families | Allowed Actions | Prohibited Actions |
|---|---|---|---|---|
| Which stations need operational attention? | Senior_Command, Zone_Officer | Station volume, backlog, lifecycle movement, adoption | Schedule review, allocate training, inspect process | Declare misconduct from dashboard alone |
| Which cases may be delayed? | SHO, Zone_Officer | Stage age, pending FIR draft, overdue tasks | Open authorized case review, ask IO for update | Penalize IO based only on elapsed time |
| Which IQW features need training? | AI_Admin, SHO | Feature usage, AI review completion, uncertainty rate | Training recommendation, KB/prompt improvement | Treat low AI usage as poor investigation quality |
| Is the dashboard data reliable? | System_Admin | Confidence tier, source completeness, linkage quality | Correct mapping, rerun aggregation, mark metric provisional | Export disputed metrics as final |

Every metric card must map to one of these command questions before it is enabled in production.

### 2.4 Blue Ocean Enhancements for Evaluation

- Predictive bottleneck alerts that identify cases likely to miss charge-sheet or internal review timelines based on current pace.
- Training recommendations that map low usage or high rework to suggested micro-training modules.
- Station cohort comparison that benchmarks similar stations instead of only ranking all stations together.
- Explainable metric cards that show metric definition, data source, last refresh time, and known exclusions.
- Effectiveness index combining conversion, timeliness, quality, and adoption into a transparent composite score.

### 2.5 Out of Scope

- Direct disciplinary scoring or punitive ranking of individual officers.
- Public citizen-facing analytics.
- Direct integration with court management systems; court-stage metrics use IQW case lifecycle status only.
- Automatic reassignment of cases or tasks.
- Predictive policing or crime forecasting unrelated to IQW usage and investigation workflow.
- Cross-district data sharing unless explicitly enabled by role and jurisdiction policy.
- Display of complaint narrative, victim names, accused names, addresses, phone numbers, or other PII on aggregated dashboard screens.

### 2.6 Assumptions

- IQW users have HRMS-synced employee ID, rank, role, and police station posting.
- Cases have `created_by`, optional `io_id`, `police_station_id`, status, and timeline activity.
- FIR draft creation is represented either in parser output (`parse_records.parsed_output.fir_draft`) and/or generated document records categorized as FIR/legal draft.
- Status transitions are recorded through case activity or audit logs.
- Generated documents and exports are persisted with created timestamps and user IDs.
- All dashboard data is internal law-enforcement operational data and must be protected accordingly.

### 2.7 Constraints

- Must comply with existing IQW RBAC and audit logging.
- Must not leak PII into aggregated senior-officer screens.
- Must support Cloud SQL/PostgreSQL in the current deployment and remain compatible with future on-premise PostgreSQL.
- Must not depend on real-time CCTNS or court-system APIs for the first release.
- Must work inside the existing vanilla HTML/CSS/JS IQW frontend unless a separate frontend migration is approved.

## 3. User Roles & Permissions

### 3.1 Role Definitions

| Role | Description |
|---|---|
| Senior_Command | Commissioner/JCP-level user with city-wide operational visibility |
| Zone_Officer | DCP/ACP-level user with zone/division/station visibility |
| SHO | Station-level supervisory user with station and assigned personnel visibility |
| AI_Admin | AI governance user who sees adoption, AI quality, uncertainty, and training metrics |
| System_Admin | Platform admin who can configure metric thresholds and view audit/data freshness |
| IO | Investigating Officer who can view only own usage and case metrics |
| Clerk | Data-entry user who can view own upload activity only |

### 3.2 Permissions Matrix

| Capability | Senior_Command | Zone_Officer | SHO | AI_Admin | System_Admin | IO | Clerk |
|---|---|---|---|---|---|---|---|
| View city-wide dashboard | Yes | No | No | Limited AI metrics | Yes | No | No |
| View assigned zone/station dashboard | Yes | Yes | Own station | No | Yes | No | No |
| View officer-level productivity | Yes | Within scope | Own station | Aggregated only | Yes | Own only | Own only |
| View case-level drill-down | Metadata only | Metadata within scope | Metadata within station | AI metadata only | Yes | Own cases | Own uploads |
| View PII or complaint narrative | No on dashboard | No on dashboard | No on dashboard | No | Only through existing authorized case screens | Existing case access only | Existing upload access only |
| Configure thresholds | No | No | No | AI thresholds only | Yes | No | No |
| Export reports | Yes | Yes within scope | Own station | AI reports | Yes | Own reports | Own upload report |
| Schedule recurring reports | Yes | Yes within scope | No | AI reports | Yes | No | No |
| View dashboard audit logs | No | No | No | AI dashboard actions | Yes | No | No |

### 3.3 Explicit Denials

- No dashboard role can view victim/accused PII in aggregate cards, charts, or exported summary reports.
- IO and Clerk roles cannot compare other officers.
- AI_Admin cannot view officer disciplinary-style rankings unless also assigned a senior supervisory role.
- Exports cannot include raw complaint text, OCR text, or full FIR draft content.


### 3.4 Metric Legitimacy and Permitted-Use Matrix

| Metric Class | Examples | Permitted Use | Prohibited Use | Minimum Confidence |
|---|---|---|---|---|
| Operational Awareness | case volume, stage backlog, station adoption | Review workload and process bottlenecks | Personnel rating or disciplinary action | Medium |
| Training Signal | low feature usage, high AI uncertainty, incomplete reviews | Plan training and product support | Label officer capability without review | Medium |
| Workload Signal | cases assigned, pending tasks, active days | Balance workload and staffing | Compare officers without case complexity context | High |
| Data Quality Signal | missing station, unlinked parse record, stale snapshot | Correct data and improve instrumentation | Infer operational failure | Low allowed |
| Prohibited Personnel Evaluation | composite score, rank list, AI quality as officer score | Not allowed in v1 | Any employment, disciplinary, or punitive decision | Not applicable |

### 3.5 Metric Contestability Rights

- Officers and stations must be able to challenge incorrect attribution, posting, linkage, or status-derived metrics.
- A challenged metric must show `disputed` status in exports and drill-downs until adjudicated.
- Corrected metrics must preserve original values in audit history and record who approved correction.
- Exported reports affected by correction must be marked superseded, and the requester must receive an in-app notification.

## 4. Data Model

### 4.1 Existing Entity: User

Relationship: one police station has many users; one user creates many cases, documents, generated drafts, usage events, and audit logs.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| employee_id | string | Yes | Unique, HRMS employee identifier |
| full_name | string | Yes | 1-160 chars |
| rank | string | No | HRMS rank |
| designation | string | No | HRMS designation |
| police_station_id | UUID string | No | FK to PoliceStation |
| role | enum | Yes | IO, Clerk, AI_Admin, System_Admin, Senior_Command, Zone_Officer, SHO |
| email | string | No | Valid email if present |
| phone | string | No | E.164 or local police directory format |
| is_active | boolean | Yes | Default true |
| last_login_at | datetime | No | UTC |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |
| is_deleted / deleted_at | soft-delete | Yes/No | Default false |

Sample data:

| id | employee_id | full_name | rank | role | police_station_id |
|---|---|---|---|---|---|
| usr_001 | HCP1001 | A. Reddy | Inspector | SHO | ps_abids |
| usr_002 | HCP2088 | S. Khan | SI | IO | ps_abids |
| usr_003 | HCP0007 | M. Rao | DCP | Zone_Officer | null |

### 4.2 Existing Entity: PoliceStation

Relationship: one station has many users and cases.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| name | string | Yes | Unique station name within jurisdiction |
| code | string | Yes | Station code |
| zone | string | No | Zone/division name |
| district | string | No | District/commissionerate |
| is_active | boolean | Yes | Default true |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |
| is_deleted / deleted_at | soft-delete | Yes/No | Default false |

Sample data:

| id | name | code | zone | district |
|---|---|---|---|---|
| ps_abids | Abids Police Station | ABIDS | Central | Hyderabad |
| ps_banjara | Banjara Hills Police Station | BANJ | West | Hyderabad |

### 4.3 Existing Entity: Case

Relationship: one case belongs to one station, may be assigned to one IO, has many documents, activities, generated documents, AI analyses, and tasks.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| crime_no | string | No | Required when case_type = FIR; unique per station/year |
| petition_no | string | No | Required when case_type = Petition |
| case_type | enum | Yes | FIR, Petition, Suo_Motu |
| offence_type | string | No | Free-text legacy value |
| primary_offence_type_id | UUID string | No | FK to OffenceType |
| secondary_offence_type_ids | JSON array | No | Offence type IDs |
| police_station_id | UUID string | No | FK to PoliceStation |
| io_id | UUID string | No | FK to User |
| status | enum | Yes | Complaint_Received, FIR_Registered, Under_Investigation, Charge_Sheet_Filed, Closure_Report_Filed, Court_Proceedings, Transferred, Disposed, Closed_No_FIR |
| cctns_sync_status | enum | Yes | Synced, Pending, Failed, Not_Applicable |
| cctns_case_id | string | No | External ID |
| date_of_occurrence | datetime | No | UTC |
| date_of_registration | datetime | No | UTC |
| brief_facts | text | No | Not shown in senior dashboard aggregates |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |
| is_deleted / deleted_at | soft-delete | Yes/No | Default false |

Sample data:

| id | case_type | crime_no | petition_no | police_station_id | io_id | status | created_at |
|---|---|---|---|---|---|---|---|
| case_001 | Petition | null | PET-2026-001 | ps_abids | usr_002 | Complaint_Received | 2026-05-01T09:10:00Z |
| case_002 | FIR | 112/2026 | null | ps_abids | usr_002 | Under_Investigation | 2026-05-02T11:30:00Z |
| case_003 | FIR | 221/2026 | null | ps_banjara | usr_004 | Court_Proceedings | 2026-04-19T16:15:00Z |

### 4.4 Existing Entity: CaseDocument

Relationship: one case has many uploaded documents; one document may be source for OCR, AI, and quality checks.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| case_id | UUID string | Yes | FK to Case |
| document_type | enum | Yes | Petition, FIR, Witness_Statement, Charge_Sheet, Medical_Report, FSL_Report, Seizure_Memo, Arrest_Memo, Remand_Note, Confession, CDR, Other |
| file_name | string | Yes | Original filename |
| file_size_bytes | integer | No | Max upload size per BRD |
| mime_type | string | No | Detected MIME |
| sha256_hash | string | No | 64-char hex |
| upload_method | enum | No | Drag_Drop, Bulk_Upload, Offline_Queue, Scanner |
| ocr_status | enum | Yes | Not_Required, Pending, Processing, Completed, Failed |
| ocr_confidence | enum | No | High, Medium, Low |
| language_detected | string | No | ISO/code or language name |
| version | integer | Yes | Default 1 |
| is_latest_version | boolean | Yes | Default true |
| parsed_output | JSON | No | Parser/AI output; not exposed raw in dashboard |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | case_id | document_type | file_name | upload_method | ocr_status | created_by |
|---|---|---|---|---|---|---|
| doc_001 | case_001 | Petition | petition_scan.pdf | Scanner | Completed | usr_002 |
| doc_002 | case_002 | FIR | fir_112_2026.docx | Drag_Drop | Not_Required | usr_002 |

### 4.5 Existing Entity: GeneratedDocument

Relationship: one case has many generated documents, including FIR drafts and court/legal documents.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| case_id | UUID string | Yes | FK to Case |
| template_id | UUID string | No | FK to DocumentTemplate |
| document_category | enum | Yes | FSL_Communication, Evidence_Certificate, Legal_Notice, Legal_Draft |
| document_subtype | string | No | FIR_Draft, Remand_Note, Arrest_Memo, etc. |
| generated_content | text | No | Not exported in aggregate reports |
| sha256_hash | string | No | 64-char hex |
| auto_filled_fields | JSON | No | Field names and values |
| io_edited | boolean | Yes | Default false |
| export_format | string | No | docx, pdf |
| digital_signature_status | enum | Yes | Unsigned, Signed, Signature_Failed |
| signed_by | UUID string | No | FK to User |
| signed_at | datetime | No | UTC |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | case_id | document_category | document_subtype | io_edited | created_by | created_at |
|---|---|---|---|---|---|---|
| gen_001 | case_001 | Legal_Draft | FIR_Draft | true | usr_002 | 2026-05-01T09:22:00Z |
| gen_002 | case_002 | Legal_Draft | Remand_Note | false | usr_002 | 2026-05-03T14:44:00Z |

### 4.6 Existing Entity: ParseRecord

Relationship: complaint parser records are source evidence for complaint-to-FIR-draft timing, draft iteration counts, OCR/translation usage, and KIS indexing.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| file_name | text | Yes | Uploaded complaint file name |
| file_size | integer | Yes | Bytes |
| file_sha256 | text | No | 64-char hex |
| parsed_output | JSON | Yes | Contains summary, complaint, FIR draft, sections, quality fields |
| document_format | text | No | PDF, DOCX, image, etc. |
| completeness_score | float | No | 0.0 to 1.0 |
| kis_index_status | text | Yes | not_started, pending, running, indexed, failed |
| kis_source_id | text | No | KIS source ID |
| kis_quality_passed | boolean | No | KIS gate result |
| kis_fact_count | integer | No | Count |
| kis_graph_edge_count | integer | No | Count |
| kis_chunk_count | integer | No | Count |
| kis_attempt_count | integer | Yes | Default 0 |
| kis_indexed_at | datetime | No | UTC |
| created_at | datetime | Yes | UTC |

Sample data:

| id | file_name | document_format | completeness_score | kis_index_status | created_at |
|---|---|---|---:|---|---|
| pr_001 | complaint_001.pdf | PDF | 0.82 | indexed | 2026-05-01T09:11:00Z |
| pr_002 | handwritten_petition.jpg | IMAGE | 0.64 | pending | 2026-05-02T12:03:00Z |

### 4.7 Existing Entity: CaseActivity

Relationship: one case has many activity events; dashboard uses these for lifecycle timing.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| case_id | UUID string | Yes | FK to Case |
| activity_type | string | Yes | Case_Created, Status_Change, Document_Attached, Task_Created, etc. |
| user_id | UUID string | No | FK to User |
| description | text | No | Operational description |
| entity_type | string | No | case, document, task, generated_document, ai_analysis |
| entity_id | string | No | Referenced ID |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | case_id | activity_type | user_id | entity_type | created_at |
|---|---|---|---|---|---|
| act_001 | case_001 | Case_Created | usr_002 | case | 2026-05-01T09:10:00Z |
| act_002 | case_001 | Status_Change | usr_002 | case | 2026-05-01T10:05:00Z |

### 4.8 Existing Entity: AIAnalysisResult

Relationship: one case/document has many AI analyses; dashboard uses counts, latency, confidence, uncertainty, and quality outcomes.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| case_id | UUID string | Yes | FK to Case |
| document_id | UUID string | No | FK to CaseDocument |
| analysis_type | enum | Yes | Quality_Check, Section_Recommendation, Congruence_Detection, SOP_Generation, Judgment_Analysis, Ingredient_Mapping |
| model_name | string | No | Provider/model |
| model_version | string | No | Version |
| prompt_version | string | No | Prompt ID/version |
| result_json | JSON | No | Structured output |
| confidence_score | enum | No | High, Medium, Low |
| has_uncertainty_flag | boolean | Yes | Default false |
| uncertainty_tags | JSON array | No | Tags |
| io_reviewed | boolean | Yes | Default false |
| io_review_action | string | No | accepted, edited, rejected |
| latency_ms | integer | No | >= 0 |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | case_id | analysis_type | confidence_score | has_uncertainty_flag | io_review_action |
|---|---|---|---|---|---|
| ai_001 | case_001 | Section_Recommendation | High | false | accepted |
| ai_002 | case_002 | Quality_Check | Medium | true | edited |

### 4.9 Existing Entity: UsageEvent

Relationship: one user has many usage events; dashboard uses this for feature adoption.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| user_id | UUID string | No | FK to User |
| event_type | string | Yes | case.create, document.upload, ai.quality_check, document.generate, export.pdf, dashboard.view |
| module | string | No | cases, documents, ai, docgen, kis, dashboard |
| details | JSON | No | Non-PII metadata only |
| timestamp | datetime | Yes | UTC default now |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | user_id | event_type | module | timestamp |
|---|---|---|---|---|
| use_001 | usr_002 | case.create | cases | 2026-05-01T09:10:00Z |
| use_002 | usr_002 | document.generate | docgen | 2026-05-01T09:22:00Z |

### 4.10 New Entity: DashboardMetricSnapshot

Relationship: materialized aggregate for fast dashboard loading; each snapshot covers a period/scope/metric definition.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| metric_key | string | Yes | Must exist in MetricDefinition |
| period_start | datetime | Yes | UTC inclusive |
| period_end | datetime | Yes | UTC exclusive |
| scope_type | enum | Yes | city, zone, police_station, officer |
| scope_id | string | No | Station ID, user ID, zone code, or null for city |
| filters_hash | string | Yes | SHA-256 of normalized filters |
| value_json | JSON | Yes | Aggregated value and breakdowns |
| source_watermark_at | datetime | Yes | Last event timestamp included |
| computed_at | datetime | Yes | UTC |
| computation_ms | integer | Yes | >= 0 |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | metric_key | scope_type | scope_id | period_start | value_json |
|---|---|---|---|---|---|
| snap_001 | cases_created | police_station | ps_abids | 2026-05-01T00:00:00Z | {"count": 18} |
| snap_002 | complaint_to_fir_rate | officer | usr_002 | 2026-05-01T00:00:00Z | {"rate": 0.72, "numerator": 13, "denominator": 18} |

### 4.11 New Entity: MetricDefinition

Relationship: one definition can have many snapshots and dashboard cards.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| metric_key | string | Yes | Unique lowercase key |
| display_name | string | Yes | 1-120 chars |
| description | text | Yes | Explain calculation |
| numerator_definition | text | No | For ratio metrics |
| denominator_definition | text | No | For ratio metrics |
| source_tables | JSON array | Yes | Table names |
| refresh_frequency_seconds | integer | Yes | Default 300 |
| pii_classification | enum | Yes | aggregate_only, metadata, sensitive |
| is_active | boolean | Yes | Default true |
| version | integer | Yes | Starts 1 |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | metric_key | display_name | source_tables | pii_classification |
|---|---|---|---|---|
| md_001 | fir_drafts_created | FIR Drafts Created | ["generated_documents","parse_records"] | aggregate_only |
| md_002 | median_complaint_to_fir_minutes | Median Complaint-to-FIR Time | ["cases","case_activities","parse_records"] | metadata |

### 4.12 New Entity: DashboardSavedView

Relationship: one user can save many dashboard views for recurring reviews.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| user_id | UUID string | Yes | FK to User |
| name | string | Yes | 1-80 chars |
| description | text | No | Optional |
| filters_json | JSON | Yes | Period, station, officer, status, case type |
| layout_json | JSON | No | Card order/chart config |
| is_default | boolean | Yes | Default false |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |
| is_deleted / deleted_at | soft-delete | Yes/No | Default false |

Sample data:

| id | user_id | name | filters_json | is_default |
|---|---|---|---|---|
| view_001 | usr_003 | Central Zone 30 Days | {"period":"last_30_days","zone":"Central"} | true |
| view_002 | usr_001 | Abids Weekly Review | {"period":"last_7_days","police_station_id":"ps_abids"} | false |

### 4.13 New Entity: DashboardAlertRule

Relationship: one rule can produce many alert instances.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| metric_key | string | Yes | FK-like reference to MetricDefinition.metric_key |
| scope_type | enum | Yes | city, zone, police_station, officer |
| threshold_operator | enum | Yes | lt, lte, gt, gte, eq |
| threshold_value | decimal | Yes | Numeric threshold |
| period | enum | Yes | daily, weekly, monthly |
| severity | enum | Yes | info, warning, critical |
| notification_channels | JSON array | Yes | in_app, email |
| is_active | boolean | Yes | Default true |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | metric_key | scope_type | threshold_operator | threshold_value | severity |
|---|---|---|---|---:|---|
| rule_001 | active_user_adoption_rate | police_station | lt | 60 | warning |
| rule_002 | median_complaint_to_fir_minutes | officer | gt | 240 | critical |

### 4.14 New Entity: DashboardAlertInstance

Relationship: generated from DashboardAlertRule and tied to metric snapshots.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| rule_id | UUID string | Yes | FK to DashboardAlertRule |
| metric_snapshot_id | UUID string | No | FK to DashboardMetricSnapshot |
| scope_type | enum | Yes | city, zone, police_station, officer |
| scope_id | string | No | Station/user/zone |
| observed_value | decimal | Yes | Numeric observed value |
| status | enum | Yes | open, acknowledged, resolved, muted |
| message | text | Yes | Non-PII summary |
| acknowledged_by | UUID string | No | FK to User |
| acknowledged_at | datetime | No | UTC |
| resolved_at | datetime | No | UTC |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | rule_id | scope_type | scope_id | observed_value | status |
|---|---|---|---|---:|---|
| alert_001 | rule_001 | police_station | ps_abids | 48 | open |
| alert_002 | rule_002 | officer | usr_002 | 310 | acknowledged |

### 4.15 New Entity: DashboardExportJob

Relationship: one user creates many export jobs.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| requested_by | UUID string | Yes | FK to User |
| report_type | enum | Yes | officer_usage, station_performance, lifecycle_funnel, monthly_trends |
| format | enum | Yes | pdf, csv |
| filters_json | JSON | Yes | Same normalized filter contract as dashboard |
| status | enum | Yes | queued, running, completed, failed, expired |
| file_storage_uri | text | No | Object storage path |
| file_sha256 | string | No | 64-char hex |
| error_code | string | No | Standard error code |
| requested_at | datetime | Yes | UTC |
| completed_at | datetime | No | UTC |
| expires_at | datetime | No | UTC, default 30 days |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | requested_by | report_type | format | status | requested_at |
|---|---|---|---|---|---|
| exp_001 | usr_003 | station_performance | pdf | completed | 2026-05-05T08:00:00Z |
| exp_002 | usr_001 | officer_usage | csv | queued | 2026-05-05T08:15:00Z |


### 4.16 New Entity: DashboardMetricDispute

Relationship: one user or station may file many disputes against metric snapshots, officer rows, station rows, or exported reports.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| disputed_by | UUID string | Yes | FK to User |
| scope_type | enum | Yes | officer, police_station, case_metadata, export, metric_snapshot |
| scope_id | string | Yes | Referenced scope ID |
| metric_key | string | Yes | Metric being challenged |
| reason_code | enum | Yes | wrong_posting, wrong_assignment, duplicate_record, missing_event, external_status_mismatch, other |
| description | text | Yes | 20-2000 chars, no complaint narrative PII |
| status | enum | Yes | open, under_review, accepted, rejected, corrected |
| reviewed_by | UUID string | No | FK to User |
| reviewed_at | datetime | No | UTC |
| resolution_notes | text | No | Non-PII explanation |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | disputed_by | scope_type | scope_id | metric_key | reason_code | status |
|---|---|---|---|---|---|---|
| disp_001 | usr_002 | officer | usr_002 | cases_created | wrong_assignment | open |
| disp_002 | usr_001 | police_station | ps_abids | active_user_adoption_rate | wrong_posting | accepted |

### 4.17 New Entity: DashboardMetricCorrection

Relationship: one accepted dispute or System_Admin data-quality action can produce one or more metric corrections.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| dispute_id | UUID string | No | FK to DashboardMetricDispute |
| metric_key | string | Yes | Corrected metric |
| affected_snapshot_id | UUID string | No | FK to DashboardMetricSnapshot |
| original_value_json | JSON | Yes | Original value retained for audit |
| corrected_value_json | JSON | Yes | Corrected value |
| correction_reason | text | Yes | Non-PII reason |
| approved_by | UUID string | Yes | FK to User |
| approved_at | datetime | Yes | UTC |
| supersedes_export_ids | JSON array | No | Export IDs marked superseded |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | dispute_id | metric_key | original_value_json | corrected_value_json | approved_by |
|---|---|---|---|---|---|
| corr_001 | disp_001 | cases_created | {"count": 7} | {"count": 6} | usr_admin |
| corr_002 | disp_002 | active_user_adoption_rate | {"rate": 48} | {"rate": 62} | usr_admin |

### 4.18 New Entity: DashboardMetricSourceMap

Relationship: each metric definition has one or more source-map rows that define authoritative source precedence and confidence rules.

| Field | Type | Required | Validation / Default |
|---|---|---|---|
| id | UUID string | Yes | Primary key |
| metric_key | string | Yes | MetricDefinition.metric_key |
| source_name | string | Yes | cases, case_activities, generated_documents, parse_records, usage_events, audit_logs, external_cctns |
| precedence_rank | integer | Yes | 1 is highest precedence |
| confidence_when_present | enum | Yes | high, medium, low |
| confidence_when_missing | enum | Yes | medium, low, unavailable |
| reconciliation_rule | text | Yes | Exact rule for conflict handling |
| is_active | boolean | Yes | Default true |
| created_at / updated_at / created_by / updated_by | audit fields | Yes/No | Standard audit |

Sample data:

| id | metric_key | source_name | precedence_rank | confidence_when_present | reconciliation_rule |
|---|---|---|---:|---|---|
| srcmap_001 | firs_registered | cases.status | 1 | high | Use IQW lifecycle status until CCTNS status integration exists |
| srcmap_002 | fir_drafts_created | generated_documents.document_subtype | 1 | high | Count FIR_Draft subtype before parser-only draft fallback |

## 5. Functional Requirements

### FR-001: Senior Officer Dashboard Entry Point

Description: The system shall provide a dedicated dashboard entry point for senior officers and authorized admins. The dashboard shall be visible only to roles with analytics permissions and shall default to a role-appropriate scope.

User story: As a senior officer, I want a single dashboard entry point so that I can review station and officer performance without navigating individual case files.

Acceptance criteria:

- Dashboard navigation is visible to Senior_Command, Zone_Officer, SHO, AI_Admin, and System_Admin.
- IO and Clerk users see only their own usage view if analytics self-view is enabled.
- The default period is last 30 days.
- The default scope is city-wide for Senior_Command/System_Admin, assigned zone for Zone_Officer, station for SHO, and AI module metrics for AI_Admin.
- Unauthorized access returns `403 AUTHORIZATION_ERROR`.

Business rules:

- Dashboard access must be audit logged with role, scope, filters, and timestamp.
- No aggregate card may display raw complaint text or party names.

UI behavior:

- Selecting Dashboard from navigation opens the overview tab.
- If the user has no permitted scope, show "No dashboard scope assigned" and do not call metric endpoints.

Edge cases and errors:

- If metric service is unavailable, show stale cached snapshot with freshness warning if available.
- If no data exists for period, show zero states with active filters.

### FR-002: Period, Scope, and Dimension Filters

Description: The dashboard shall support consistent filters across all cards, charts, tables, and exports. Filters shall include period presets, custom date range, police station, zone, IO, role, case type, offence category, and status.

User story: As a Zone_Officer, I want to filter metrics by station, IO, and period so that I can review the specific operational area under my command.

Acceptance criteria:

- Period presets include last 7 days, last 30 days, current month, previous month, and custom range.
- Custom range requires `date_from <= date_to` and maximum span of 366 days.
- Officer options are constrained to the selected station/zone and user permissions.
- All charts and exports use the same normalized filter object.
- Active filters are shown as removable chips.

Business rules:

- Date filtering uses event timestamps in UTC and displays dates in local timezone.
- Custom ranges include `date_from` start of day and `date_to` end of day in local timezone before UTC conversion.

UI behavior:

- Changing a filter refreshes metrics and updates URL query parameters.
- Reset clears all optional filters and restores role default scope.

Edge cases and errors:

- If selected officer is outside the user scope, API returns `403`.
- Invalid dates return `400 VALIDATION_ERROR` with field name.

### FR-003: User Productivity Metrics

Description: The dashboard shall show officer-wise productivity including cases created, FIR cases registered, FIR drafts created, generated documents, uploaded documents, AI checks, exports, and active days.

User story: As a SHO, I want to see productivity by user in my station so that I can identify training needs and workload imbalance.

Acceptance criteria:

- Officer productivity table displays user name, employee ID, rank, role, station, cases created, FIRs registered, FIR drafts, generated documents, uploaded documents, AI checks, active days, and last activity.
- Table supports sorting by every numeric metric.
- Metrics can be grouped by user or police station.
- Drill-down on a user opens that officer's dashboard detail without exposing raw case narratives.
- Exported CSV includes the same visible columns.

Business rules:

- `cases_created` counts cases where `cases.created_by = user.id`.
- `firs_registered` counts cases where status reached `FIR_Registered` or later in lifecycle.
- `active_days` counts distinct local dates with at least one usage event, case activity, document upload, generated document, or AI analysis by the user.

UI behavior:

- Top performers and low-adoption officers use neutral labels, not disciplinary wording.
- Empty rows show zero values.

Edge cases and errors:

- Unassigned cases are grouped under "Unassigned".
- Deleted users are displayed as "Former user" with employee ID if available.

### FR-004: Complaint-to-FIR Draft Processing Metrics

Description: The dashboard shall measure the time and iteration count from first complaint intake to FIR draft creation. It shall support parse-record based complaint flows and case-linked generated-document flows.

User story: As a senior officer, I want to know how long it takes to convert complaints into FIR drafts so that I can reduce delays and rework.

Acceptance criteria:

- Metric cards show median, p75, and p95 complaint-to-first-FIR-draft time.
- Metric cards show average and median FIR draft iterations per complaint/case.
- Table shows complaint/case ID, station, IO, first intake time, first FIR draft time, last FIR draft time, draft count, and elapsed minutes.
- Users can group by IO and station.
- Records without FIR draft are counted in pending-draft backlog.

Business rules:

- First intake timestamp is the earliest of case creation, petition document upload, or parse record creation when linked.
- FIR draft timestamp is the earliest generated document with subtype `FIR_Draft` or parser output containing `fir_draft`.
- Last iteration is the latest generated FIR draft or parse iteration associated with the complaint/case.
- If a parse record is not linked to a case, it appears under "Unlinked parser history" for System_Admin and AI_Admin only.

UI behavior:

- Clicking a timing outlier opens a metadata drill-down showing event timestamps and links to authorized case screen.
- Show a warning if linkage confidence is below high.

Edge cases and errors:

- Negative durations caused by clock skew are excluded and reported in data quality warnings.
- Duplicate parse records with same SHA-256 within 10 minutes are treated as one intake event for timing unless the user explicitly regenerated a draft.

### FR-005: Complaint-to-FIR and Investigation Lifecycle Funnel

Description: The dashboard shall show case movement through complaint received, FIR registered, investigation, charge sheet, closure report, court proceedings, disposed, transferred, and closed without FIR.

User story: As a senior command officer, I want to see lifecycle conversion and backlog by stage so that I can identify systemic delays.

Acceptance criteria:

- Funnel chart displays counts and conversion percentages for each lifecycle status.
- Stage backlog table shows count, median age, p90 age, and oldest case age by station and IO.
- Users can filter funnel by period, station, IO, offence category, and case type.
- Drill-down on a funnel stage lists cases in that stage with metadata only.
- Closed_No_FIR is shown separately from FIR-based lifecycle.

Business rules:

- A case is counted in the highest status it reached during the selected period and in current backlog if still in that status at period end.
- `Charge_Sheet_Filed` and `Closure_Report_Filed` are both investigation completion outcomes.
- `Court_Proceedings` means charge sheet reached court-stage according to IQW status, not external court validation.

UI behavior:

- Funnel stages use consistent colors with existing case lifecycle stepper.
- Hover/tap shows definition and source data.

Edge cases and errors:

- Cases created before the period but transitioned during the period appear in transition metrics but not new complaint count.
- Transferred cases are excluded from disposal timeliness after transfer date.

### FR-006: FIR Draft and Generated Document Analytics

Description: The dashboard shall measure draft generation volume, export volume, digital signature status, and template usage.

User story: As a senior officer, I want to know how many FIR and legal drafts are created through IQW so that I can assess whether officers are using automation.

Acceptance criteria:

- Cards show FIR drafts, total generated documents, exported PDFs, exported DOCX files, signed documents, and signature failures.
- Template usage chart ranks document templates by count.
- FIR drafts are visible by user, station, and period.
- Generated document metrics distinguish created, edited, exported, and signed states.
- Reports include document subtype breakdown.

Business rules:

- FIR draft count uses `document_subtype = FIR_Draft` and parser `parsed_output.fir_draft` where no generated document exists.
- Export count uses generated document export events or `export_format` if persisted.
- Signed document count uses `digital_signature_status = Signed`.

UI behavior:

- Signature failures link to operational errors without revealing document content.

Edge cases and errors:

- If old generated documents lack subtype, infer FIR draft only when template name or content metadata explicitly marks FIR.

### FR-007: Feature Adoption and AI Effectiveness

Description: The dashboard shall show module-level adoption and AI usefulness indicators across OCR, translation, quality checks, BNS mapping, congruence detection, investigation plan, document generation, KIS, and exports.

User story: As an AI Admin, I want to see which AI features are used and trusted so that I can prioritize training, prompts, and knowledge-base improvement.

Acceptance criteria:

- Feature adoption chart shows counts by module and trend over time.
- AI effectiveness cards show AI checks performed, AI outputs accepted, edited, rejected, low-confidence flags, average latency, and citation coverage where available.
- Quality metrics show average completeness score and quality gate pass rate.
- KIS metrics show indexed documents, failed indexing, graph facts, wiki articles, and quality gate status.
- Users can filter by station and IO where permitted.

Business rules:

- AI acceptance rate = accepted AI outputs / reviewed AI outputs.
- Low-confidence rate = outputs with uncertainty flag or confidence below configured threshold / total AI outputs.
- Feature counts must be emitted as UsageEvent records or derived from domain tables if event gaps exist.

UI behavior:

- AI metrics use governance labels such as "needs review" rather than "bad output".

Edge cases and errors:

- If review actions are missing, acceptance rate shows "Insufficient reviewed samples".

### FR-008: Station Comparison and Cohort Benchmarking

Description: The dashboard shall compare police stations by adoption, volume, timeliness, lifecycle movement, and quality while preserving context.

User story: As a DCP, I want to compare stations in my zone so that I can identify where operational support is needed.

Acceptance criteria:

- Station table displays cases created, FIRs registered, FIR draft count, median complaint-to-FIR time, investigation completion count, court progression count, active users, and adoption rate.
- Station rankings can be sorted by any metric.
- Cohort mode compares stations within the same zone or similar case volume band.
- Station drill-down opens station-level dashboard.
- Export includes station code, zone, and metrics.

Business rules:

- Adoption rate = active users in period / active users posted to station.
- Volume band cohort is low/medium/high based on previous 90-day case volume tertiles.
- Stations with fewer than five cases in period show caution marker for rate metrics.

UI behavior:

- Avoid red/green-only encoding; include icons/text labels.

Edge cases and errors:

- Stations with no assigned active users show "No active users assigned" data quality warning.

### FR-009: Officer Detail and Case Metadata Drill-Down

Description: Authorized users shall drill from aggregates to officer detail and then to case metadata lists. Drill-down must not expose complaint text on dashboard views.

User story: As a SHO, I want to drill into an officer's metadata and case list so that I can follow up on delayed work without exposing sensitive facts unnecessarily.

Acceptance criteria:

- Officer detail shows summary cards, trend line, module usage, lifecycle cases by status, and pending-draft backlog.
- Case list shows case number/petition number, status, station, IO, created date, last activity date, age in stage, and action links.
- Case links open existing case detail only if the user already has case access.
- Dashboard list excludes raw complaint narrative, victim/accused names, addresses, and phone numbers.
- All drill-down events are audit logged.

Business rules:

- For senior roles, case detail link uses existing case authorization rules.
- Metadata drill-down may show counts for cases not individually accessible, but not case-sensitive fields.

UI behavior:

- Drill-down opens in a dashboard subview with breadcrumb back to overview.

Edge cases and errors:

- If a case is deleted or outside scope between list load and click, show "Case no longer available in your scope".

### FR-010: Bottleneck Detection and Alerts

Description: The dashboard shall identify cases, stations, and officers with delays or low adoption based on configurable thresholds.

User story: As a senior officer, I want alerts for bottlenecks and low adoption so that I can intervene early.

Acceptance criteria:

- Alerts are generated for low station adoption, high complaint-to-FIR time, high pending-draft backlog, cases stuck in a stage, high failed KIS indexing, and high low-confidence AI output rate.
- Alert rules are configurable by System_Admin.
- Alert instances show observed value, threshold, period, scope, severity, and recommended action.
- Users can acknowledge alerts.
- Alert list can be filtered by severity, status, station, and metric.

Business rules:

- Default low adoption alert triggers when station active-user adoption is below 60% for last 7 days.
- Default complaint-to-FIR delay alert triggers when median time exceeds 240 minutes for at least five completed records.
- Alert rules never include raw complaint text in messages.

UI behavior:

- Alerts appear as a compact list on overview and full table in alert subview.

Edge cases and errors:

- Rules with insufficient sample size show "not evaluated" rather than open alert.

### FR-011: Report Export and Scheduled Reports

Description: The dashboard shall support PDF and CSV export of visible metrics and scheduled monthly reports.

User story: As a senior officer, I want to export monthly station and officer reports so that I can use them in review meetings.

Acceptance criteria:

- User can export overview, officer usage, station comparison, lifecycle funnel, and monthly trend reports.
- Export respects current filters and user scope.
- PDF includes title, period, generated by, generated at, filters, metric definitions, and data freshness.
- CSV includes machine-readable rows and no PII beyond employee ID/name/rank when authorized.
- Export jobs are audited and stored with SHA-256.

Business rules:

- Export links expire after 30 days.
- Scheduled reports run on the first day of each month for previous month.
- Failed export jobs show error code and retry option.

UI behavior:

- Export button opens a menu with PDF and CSV.
- For long reports, show queued job status.

Edge cases and errors:

- If export exceeds synchronous limit, API returns queued job.

### FR-012: Metric Definition and Data Quality Transparency

Description: Every dashboard metric shall expose definition, source tables, last refresh, exclusions, and data-quality warnings.

User story: As a System_Admin, I want metric definitions and data quality warnings so that dashboard numbers are trusted and explainable.

Acceptance criteria:

- Every KPI card has an info action showing metric definition.
- Data freshness timestamp is visible on overview.
- Dashboard shows warnings for missing IO assignment, missing police station, invalid negative durations, unlinked parse records, and low sample size.
- System_Admin can view metric registry.
- Metric version changes are audited.

Business rules:

- Changing metric definition creates a new MetricDefinition version.
- Historical snapshots retain the metric version used at computation time.

UI behavior:

- Warnings are displayed as a dismissible panel for the session.

Edge cases and errors:

- If metric definition is inactive, dependent cards are hidden and logged as disabled.

### FR-013: Data Refresh and Aggregation

Description: The dashboard shall compute metrics from operational tables and usage events with near-real-time freshness and optional materialized snapshots.

User story: As a System_Admin, I want reliable metric refresh so that senior officers see current and performant dashboards.

Acceptance criteria:

- Default dashboard uses materialized snapshots when available.
- Freshness target is 5 minutes for normal usage.
- Manual refresh recomputes current filters if the user has permission.
- Data source watermark is returned with each metric response.
- Failed aggregation is logged and visible to System_Admin.

Business rules:

- Aggregation jobs must be idempotent by metric key, period, scope, and filters hash.
- Raw operational tables remain source of truth.

UI behavior:

- Show "Last refreshed" and "Refresh" action.

Edge cases and errors:

- If snapshot is stale beyond 30 minutes, show warning and attempt direct computation.

### FR-014: Privacy, Authorization, and Audit Controls

Description: The dashboard shall implement least-privilege access, non-PII aggregates, auditable exports, and tamper-evident usage logging.

User story: As a System_Admin, I want the dashboard access and exports controlled and audited so that operational analytics do not become a data-leak path.

Acceptance criteria:

- All endpoints require JWT/session auth and role/scope authorization.
- Dashboard aggregate APIs do not return complaint text, OCR text, generated draft content, party names, addresses, or phone numbers.
- Drill-down returns only metadata unless opening existing authorized case screens.
- Dashboard view, drill-down, export, scheduled report change, and threshold change are audit logged.
- Export files include access scope and filters in metadata.

Business rules:

- PII masking is mandatory for any AI-generated narrative summary used in dashboard explanation.
- Exports require same or stricter permission as on-screen view.

UI behavior:

- If a user attempts unauthorized drill-down, show "You do not have permission for this case".

Edge cases and errors:

- If role mapping is ambiguous, deny by default.

### FR-015: Training and Adoption Recommendations

Description: The dashboard shall produce non-punitive training recommendations from usage and effectiveness patterns.

User story: As an AI Admin, I want to identify where training is needed so that officers use the app effectively.

Acceptance criteria:

- Recommendation engine flags stations with low active-user adoption, low AI review completion, high edit/reject rate, or high low-confidence AI outputs.
- Recommendations include metric evidence, suggested training topic, and affected scope.
- Recommendations can be exported in adoption reports.
- Recommendations do not create disciplinary records.
- AI_Admin can mark recommendation as reviewed.

Business rules:

- Training recommendations use aggregate data; individual naming is allowed only to station supervisors and senior command roles.
- Recommendations must include the metric threshold that triggered them.

UI behavior:

- Recommendations appear below alerts with "Review", "Export", and "Dismiss for period" actions.

Edge cases and errors:

- If sample size is below five events, show "Insufficient data" and do not create recommendation.

### FR-016: Predictive Bottleneck Signal

Description: As a blue-ocean enhancement, the dashboard may identify cases likely to exceed configured stage-duration thresholds based on age, activity rate, pending tasks, and missing expected documents.

User story: As a senior officer, I want early warning of likely delays so that supervisors can intervene before deadlines are missed.

Acceptance criteria:

- Predictive signal is disabled by default until validated.
- When enabled, signal shows reason codes: stage age, missing expected documents, no activity in seven days, overdue tasks, or repeated low-quality drafts.
- Signal is explainable and never uses protected attributes.
- Signal does not automatically change case status or officer score.
- False-positive feedback can be captured.

Business rules:

- Predictive output is advisory only.
- No LLM call may receive PII for predictive summary generation.

UI behavior:

- Predictive cards use "Likely needs attention" language.

Edge cases and errors:

- If model/rule confidence is below threshold, no alert is shown.


### FR-017: Metric Legitimacy, Challenge, and Correction

Description: The dashboard shall support formal governance for metric ownership, permitted use, challenges, adjudication, and correction. This prevents dashboard metrics from becoming unreviewed personnel conclusions or disputed station statistics.

User story: As a station supervisor or officer, I want disputed metrics to be challengeable and corrected when source data is wrong so that dashboard reports remain fair and trustworthy.

Acceptance criteria:

- Every metric has an owner, source map, permitted-use class, confidence tier, and minimum sample rule.
- Authorized users can submit a metric dispute with reason code and non-PII explanation.
- Disputed metrics show `disputed` status in drill-downs and exports until reviewed.
- Accepted disputes create DashboardMetricCorrection records that preserve original and corrected values.
- Superseded exports are marked and requester receives an in-app notification.

Business rules:

- No single dashboard metric may be used as a disciplinary or personnel conclusion.
- AI-derived quality indicators require independent supervisory validation before being used beyond training/product-improvement signals.
- Officer-level comparison is disabled for any metric whose confidence tier is below High or sample size is below configured threshold.

UI behavior:

- Metric detail panels include "Challenge metric" for authorized users.
- Disputed rows show a visible `Disputed` badge and link to review status.

Edge cases and error handling:

- Disputes containing raw complaint narrative or PII are rejected with `VALIDATION_ERROR`.
- Duplicate open disputes for the same metric/scope/user are rejected with `CONFLICT`.

### FR-018: MVP Rollout and Field Validation Controls

Description: The dashboard shall include a controlled rollout path that validates metric definitions, data quality, and senior-officer usefulness before enabling advanced features or officer-level comparisons.

User story: As a System_Admin, I want dashboard features released behind validation gates so that senior officers do not rely on untrusted or misleading metrics.

Acceptance criteria:

- Phase 1 exposes only read-only overview, filters, station/officer tables, lifecycle funnel, data warnings, audit, and exports disabled by default.
- Officer-level comparison is enabled only after source completeness, posting accuracy, and sample-size gates pass for selected metrics.
- Predictive signals, training recommendations, scheduled reports, and composite indexes remain disabled until field validation is signed off.
- UAT must include at least one senior command user, one zone officer, one SHO, one IO, one AI Admin, and one System_Admin.
- Field validation findings are recorded before production enablement.

Business rules:

- Phase 1 metrics are labelled `Operational awareness only`.
- Mandatory Module 10 compliance metrics are prioritized before optional enhancements.
- Metric definitions cannot be changed in production without audit and version increment.

UI behavior:

- Disabled advanced modules show `Requires validation` for System_Admin and are hidden from other users.

Edge cases and error handling:

- If validation state is missing, default to Phase 1 restricted mode.

## 6. User Interface Requirements

### 6.1 Senior Dashboard Overview

Purpose: command overview for current user scope.

Layout:

- Top filter bar with period preset, custom dates, station, IO, status, case type, offence category.
- KPI strip: cases created, FIRs registered, complaint-to-FIR rate, FIR drafts, median complaint-to-FIR time, investigation completion, court progression, active users.
- Lifecycle funnel chart occupying main left band.
- Station/officer summary table on main right band.
- Alerts and training recommendations band below.
- Data freshness and export controls in header.

Components: segmented period control, searchable selects, KPI cards, funnel chart, trend chart, sortable data table, alert list, export menu.

Design system: use the existing IQW CSS tokens, `btn`, `iqw-select`, `case-info-grid`, status badges, and admin table patterns. If later migrated to React, use Tailwind plus shadcn/ui/Radix primitives for Select, Tabs, Table, Dialog, Tooltip, Popover, and Toast.

Responsive behavior: desktop two-column operational layout; tablet stacks chart/table; mobile shows filters collapsed and KPI cards in two columns.

### 6.2 Officer Performance Screen

Purpose: officer-wise productivity and timing review.

Layout:

- Officer search and station filter.
- Summary chart showing cases/FIR drafts/AI checks by officer.
- Sortable table with user productivity fields.
- Drill-down side panel for selected officer.

Navigation: Dashboard Overview -> Officer Performance -> Officer Detail -> Authorized Case Detail.

### 6.3 Station Comparison Screen

Purpose: station-level comparison and cohort benchmarking.

Layout:

- Station table with zone grouping.
- Cohort toggle.
- Volume/timeliness scatter plot.
- Station drill-down panel with stage backlog and user adoption.

### 6.4 Lifecycle Funnel Screen

Purpose: detailed workflow conversion and backlog view.

Layout:

- Funnel chart from complaint received to disposal.
- Stage age histogram.
- Backlog table by station and IO.
- Stage definition side panel.

### 6.5 Processing Time Screen

Purpose: complaint-to-FIR draft and complaint-to-FIR registration analysis.

Layout:

- Median/p75/p95 cards.
- Outlier list.
- Timeline mini-view for selected complaint/case metadata.
- Data-quality warnings for unlinked parser records.

### 6.6 Feature Adoption and AI Effectiveness Screen

Purpose: AI_Admin and senior users assess feature usage and AI usefulness.

Layout:

- Module usage bar chart.
- Acceptance/rework trend chart.
- AI output confidence and uncertainty chart.
- KIS indexing/quality mini-panel.
- Feature usage event table.

### 6.7 Alerts and Recommendations Screen

Purpose: operational alerts and training recommendations.

Layout:

- Severity/status filter.
- Alert table with observed value, threshold, scope, period, status.
- Alert detail panel with metric explanation and recommended action.
- Acknowledge/review actions.

### 6.8 Report Builder Screen

Purpose: export current dashboard or schedule monthly report.

Layout:

- Report type selector.
- Filter preview.
- PDF/CSV format selector.
- Schedule toggle for monthly reports.
- Export job history table.

## 7. API & Integration Requirements

### 7.1 Authentication and Authorization

- All endpoints use existing IQW authentication.
- Authorization must enforce role and jurisdiction scope.
- System_Admin can configure thresholds and metric definitions.
- Dashboard APIs must return metadata only unless caller already has underlying case access.

### 7.2 Standard Error Response

All dashboard endpoints use:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "date_from must be before date_to.",
    "field": "date_from",
    "request_id": "abc12345"
  }
}
```

Allowed error codes: `VALIDATION_ERROR`, `AUTHENTICATION_ERROR`, `AUTHORIZATION_ERROR`, `NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`, `SERVICE_UNAVAILABLE`, `SERVER_ERROR`.

### 7.3 Internal API Endpoints

| Method | Path | Purpose | Permission |
|---|---|---|---|
| GET | `/api/v1/senior-dashboard/overview` | KPI cards, funnel, summary tables | Dashboard read |
| GET | `/api/v1/senior-dashboard/officers` | Officer productivity table | Scoped dashboard read |
| GET | `/api/v1/senior-dashboard/officers/{user_id}` | Officer detail | Scoped dashboard read |
| GET | `/api/v1/senior-dashboard/stations` | Station comparison | Scoped dashboard read |
| GET | `/api/v1/senior-dashboard/lifecycle` | Lifecycle funnel and stage backlog | Scoped dashboard read |
| GET | `/api/v1/senior-dashboard/processing-times` | Complaint-to-FIR timing | Scoped dashboard read |
| GET | `/api/v1/senior-dashboard/feature-adoption` | AI/module usage | AI_Admin or senior roles |
| GET | `/api/v1/senior-dashboard/alerts` | Alert instances | Scoped dashboard read |
| POST | `/api/v1/senior-dashboard/alerts/{alert_id}:acknowledge` | Acknowledge alert | Scoped dashboard write |
| GET | `/api/v1/senior-dashboard/metric-definitions` | Metric registry | System_Admin/AI_Admin read |
| PATCH | `/api/v1/senior-dashboard/metric-definitions/{id}` | Update metric definition | System_Admin |
| GET | `/api/v1/senior-dashboard/alert-rules` | List alert rules | System_Admin |
| POST | `/api/v1/senior-dashboard/alert-rules` | Create alert rule | System_Admin |
| PATCH | `/api/v1/senior-dashboard/alert-rules/{id}` | Update alert rule | System_Admin |
| POST | `/api/v1/senior-dashboard/exports` | Create export job | Scoped dashboard export |
| GET | `/api/v1/senior-dashboard/exports/{job_id}` | Export job status/download metadata | Requester or System_Admin |
| POST | `/api/v1/senior-dashboard/snapshots:refresh` | Trigger metric refresh | System_Admin |

### 7.4 Request/Response Examples

#### Overview Request

`GET /api/v1/senior-dashboard/overview?period=last_30_days&police_station_id=ps_abids`

Response:

```json
{
  "filters": {
    "period": "last_30_days",
    "date_from": "2026-04-06T00:00:00+05:30",
    "date_to": "2026-05-05T23:59:59+05:30",
    "police_station_id": "ps_abids"
  },
  "scope": {"type": "police_station", "id": "ps_abids", "label": "Abids Police Station"},
  "freshness": {"last_refreshed_at": "2026-05-05T08:25:00Z", "source_watermark_at": "2026-05-05T08:22:11Z"},
  "kpis": {
    "cases_created": 42,
    "firs_registered": 31,
    "fir_drafts_created": 38,
    "median_complaint_to_fir_minutes": 96,
    "investigation_completed": 12,
    "court_progressed": 4,
    "active_users": 14
  },
  "lifecycle": [
    {"status": "Complaint_Received", "count": 11, "conversion_from_previous": null},
    {"status": "FIR_Registered", "count": 31, "conversion_from_previous": 73.8}
  ],
  "warnings": []
}
```

#### Officer Productivity Request

`GET /api/v1/senior-dashboard/officers?period=last_7_days&police_station_id=ps_abids&sort=median_complaint_to_fir_minutes:desc`

Response:

```json
{
  "items": [
    {
      "user_id": "usr_002",
      "employee_id": "HCP2088",
      "full_name": "S. Khan",
      "rank": "SI",
      "police_station_name": "Abids Police Station",
      "cases_created": 6,
      "firs_registered": 4,
      "fir_drafts_created": 7,
      "documents_uploaded": 18,
      "ai_checks_performed": 9,
      "active_days": 5,
      "median_complaint_to_fir_minutes": 84,
      "last_activity_at": "2026-05-05T07:55:00Z"
    }
  ],
  "total": 1
}
```

#### Export Job Request

`POST /api/v1/senior-dashboard/exports`

Request:

```json
{
  "report_type": "station_performance",
  "format": "pdf",
  "filters": {
    "period": "current_month",
    "zone": "Central"
  }
}
```

Response:

```json
{
  "id": "exp_001",
  "status": "queued",
  "report_type": "station_performance",
  "format": "pdf",
  "requested_at": "2026-05-05T08:30:00Z",
  "expires_at": "2026-06-04T08:30:00Z"
}
```

#### Alert Rule Request

`POST /api/v1/senior-dashboard/alert-rules`

Request:

```json
{
  "metric_key": "active_user_adoption_rate",
  "scope_type": "police_station",
  "threshold_operator": "lt",
  "threshold_value": 60,
  "period": "weekly",
  "severity": "warning",
  "notification_channels": ["in_app"]
}
```

Response:

```json
{
  "id": "rule_001",
  "metric_key": "active_user_adoption_rate",
  "is_active": true,
  "created_at": "2026-05-05T08:31:00Z"
}
```

### 7.5 Integrations

| Integration | Requirement |
|---|---|
| HRMS | Use existing synced user profile and posting for officer/station scoping |
| CCTNS | No new dependency in v1; use IQW case sync status and case lifecycle only |
| KIS | Use existing KIS status/indexing metadata for feature adoption and quality metrics |
| Audit Log | Record dashboard views, drill-downs, exports, threshold changes |
| Object Storage | Store generated exports if configured |


### 7.7 Canonical Event Taxonomy

| Event Type | Primary Source | Required Metadata | PII Allowed |
|---|---|---|---|
| case.create | cases | case_id, station_id, created_by, case_type | No |
| case.status_change | case_activities | case_id, from_status, to_status, actor_id | No |
| document.upload | case_documents | case_id, document_id, document_type, upload_method | No |
| complaint.parse | parse_records | parse_record_id, file_sha256, format, completeness_score | No |
| fir_draft.create | generated_documents or parse_records | case_id or parse_record_id, draft_source, iteration_number | No |
| ai.check | ai_analysis_results | case_id, analysis_type, confidence, latency_ms | No |
| document.export | generated_documents / audit | generated_document_id, format, actor_id | No |
| kis.index | parse_records KIS columns | parse_record_id, status, quality_passed, fact_count | No |
| dashboard.view | audit/usage_events | user_id, scope_type, filters_hash | No |
| dashboard.export | DashboardExportJob | report_type, format, filters_hash, requester | No |

### 7.8 Source-of-Truth and Confidence Rules

| Metric Area | Primary Source | Secondary Source | Confidence Rule |
|---|---|---|---|
| Case lifecycle status | cases.status and case_activities | audit logs | High when status transition activity exists; Medium when current status only |
| FIR draft count | generated_documents.document_subtype = FIR_Draft | parse_records.parsed_output.fir_draft | High for generated documents; Medium for parser-only unlinked drafts |
| Complaint intake time | cases.created_at / petition document upload | parse_records.created_at | High when linked to case; Low when unlinked |
| Officer assignment | cases.io_id | created_by or activity user | High with explicit IO; Medium with created_by fallback; unavailable if neither exists |
| Station attribution | cases.police_station_id | user.police_station_id at event time | High with case station; Medium with current user posting fallback |
| Court progression | cases.status = Court_Proceedings | case activity transition | Medium until external court integration exists |

When primary and secondary sources conflict, the API must return a data-quality warning and lower the metric confidence tier rather than silently choosing a favorable value.

### 7.9 Rate Limits

- Dashboard read endpoints: 120 requests/user/minute.
- Export creation: 10 requests/user/hour.
- Snapshot refresh: 6 requests/System_Admin/hour.
- Alert-rule mutations: 60 requests/System_Admin/hour.

## 8. Non-Functional Requirements

### 8.1 Performance

- Default overview p95 under 3 seconds for 10,000 cases and 500 users.
- Drill-down p95 under 2 seconds for 1,000 rows before pagination.
- Export job API returns queued response within 2 seconds for large reports.
- Use indexed filters on timestamps, station, IO, status, event type, and generated document subtype.

### 8.2 Security

- Enforce existing auth and RBAC.
- Add scope checks for station/zone/officer visibility.
- Do not return raw complaint text, OCR text, generated draft content, addresses, or phone numbers in dashboard APIs.
- Audit all dashboard access and export activity.
- Export files must have SHA-256 hash and expiry.

### 8.3 Privacy

- Aggregate screens are PII-free except permitted employee identifiers and names.
- Case drill-down shows metadata only.
- Any AI-generated dashboard explanation must use masked data and must not receive PII.

### 8.4 Scalability

- Support materialized snapshots by day, station, and officer.
- Use async aggregation jobs for exports and snapshot refresh.
- Allow horizontal scaling of API because raw state is in database/object storage.

### 8.5 Availability

- Target 99.5% availability for dashboard APIs in v1.
- Dashboard should degrade to stale snapshot with warning if live aggregation fails.

### 8.6 Backup and Recovery

- Dashboard configuration tables are included in standard database backups.
- Export files can be regenerated from source data; RPO for config is 24 hours, RTO 4 hours.

### 8.7 Accessibility

- Meet WCAG 2.1 AA for keyboard navigation, color contrast, focus states, labels, table captions, and chart text alternatives.
- Charts must have table alternatives.

### 8.8 Browser and Device Support

- Desktop-first for Chrome, Edge, and Firefox current versions.
- Tablet responsive support.
- Mobile read-only support for overview and alerts.


### 8.9 Personnel Analytics Safeguards

- Officer-level data is personnel-sensitive even when it is not case PII.
- Officer comparison exports require explicit purpose selection: operational review, training planning, workload balancing, or data-quality correction.
- Exports must be watermarked with requester, timestamp, scope, and permitted-use label.
- Export expiry defaults to 7 days for officer-level reports and 30 days for aggregate station reports.
- System_Admin can revoke an export link; revoked exports return `AUTHORIZATION_ERROR`.
- Dashboard reports cannot state or imply disciplinary conclusions.

### 8.10 Anti-Gaming Controls

- Metrics must include sample-size warnings where denominators are below configured thresholds.
- Sudden spikes in low-value activity, duplicate generated drafts, or same-day status churn are flagged as data-quality/anomaly warnings.
- Case complexity and staffing normalization are required before any workload comparison is labelled reliable.
- Qualitative supervisory review is required before acting on outlier officer metrics.

## 9. Workflow & State Diagrams

### 9.1 Case Lifecycle State Table

| Current State | Action | Next State | Side Effects |
|---|---|---|---|
| Complaint_Received | Register FIR | FIR_Registered | Record status activity, update funnel, count complaint-to-FIR conversion |
| Complaint_Received | Close without FIR | Closed_No_FIR | Record closure, count non-FIR outcome |
| FIR_Registered | Begin investigation | Under_Investigation | Record stage age start |
| Under_Investigation | File charge sheet | Charge_Sheet_Filed | Count investigation completion and charge-sheet outcome |
| Under_Investigation | File closure report | Closure_Report_Filed | Count investigation completion and closure outcome |
| Under_Investigation | Transfer case | Transferred | Exclude from local pending backlog after transfer |
| Charge_Sheet_Filed | Move to court proceedings | Court_Proceedings | Count court progression |
| Closure_Report_Filed | Dispose | Disposed | Count disposed |
| Court_Proceedings | Dispose | Disposed | Count disposed |

### 9.2 Dashboard Metric Refresh

| Current State | Action | Next State | Side Effects |
|---|---|---|---|
| No Snapshot | Scheduled refresh starts | Computing | Lock metric scope/filter hash |
| Computing | Compute succeeds | Current | Store DashboardMetricSnapshot and watermark |
| Computing | Compute fails | Failed | Log aggregation failure and keep previous snapshot |
| Current | Source data newer than refresh target | Stale | UI shows freshness warning |
| Stale | Manual refresh | Computing | Audit refresh request |

### 9.3 Export Job Workflow

| Current State | Action | Next State | Side Effects |
|---|---|---|---|
| queued | Worker starts | running | Audit export started |
| running | PDF/CSV generated | completed | Store file URI, SHA-256, completed_at |
| running | Error occurs | failed | Store error code |
| completed | Expiry date passes | expired | Hide download link |
| failed | User retries | queued | Create retry activity |

### 9.4 Alert Workflow

| Current State | Action | Next State | Side Effects |
|---|---|---|---|
| open | User acknowledges | acknowledged | Record acknowledged_by/at and audit |
| acknowledged | Metric returns within threshold | resolved | Set resolved_at |
| open | Rule muted | muted | Suppress notifications for period |
| muted | Mute expires | open | Re-evaluate rule |


### 9.5 Metric Dispute and Correction Workflow

| Current State | Action | Next State | Side Effects |
|---|---|---|---|
| normal | User challenges metric | disputed | Dashboard row/card shows Disputed badge; audit event recorded |
| disputed | Reviewer accepts dispute | accepted | DashboardMetricCorrection is created; affected snapshots marked corrected |
| disputed | Reviewer rejects dispute | rejected | Resolution notes stored; disputed badge removed after notification |
| accepted | Correction recomputed | corrected | Superseded exports marked; requester notified |
| corrected | Next snapshot refresh | normal | Corrected value becomes baseline if source data fixed |

## 10. Notification & Communication Requirements

| Event | Channel | Recipient | Trigger | Template |
|---|---|---|---|---|
| Low station adoption | In-app | SHO, Zone_Officer | Adoption below rule threshold | `Station {station_name} adoption is {value}% for {period}, below {threshold}%.` |
| Complaint-to-FIR delay | In-app | SHO, Zone_Officer | Median exceeds threshold | `{scope_label} median complaint-to-FIR time is {value} minutes for {period}.` |
| High pending-draft backlog | In-app | SHO | Pending drafts exceed threshold | `{scope_label} has {count} complaints without FIR draft after {age_threshold}.` |
| Snapshot refresh failure | In-app | System_Admin | Aggregation job fails | `Dashboard metric refresh failed for {metric_key}: {error_code}.` |
| Export completed | In-app | Requester | Export job completed | `{report_type} export is ready and expires on {expires_at}.` |
| Export failed | In-app | Requester | Export job failed | `{report_type} export failed with {error_code}. Retry from Report Builder.` |

Notification preferences:

- System_Admin can disable alert notifications per rule.
- Users cannot disable security/export completion notices.
- Senior users can mute low-severity dashboard alerts for a period.

## 11. Reporting & Analytics

### 11.1 Dashboard Reports

| Report | Audience | Data Sources | Filters | Refresh |
|---|---|---|---|---|
| Command Overview | Senior_Command, System_Admin | cases, activities, generated_documents, usage_events | period, zone, station, IO, status | 5 min |
| Officer Usage Report | SHO, Zone_Officer, Senior_Command | users, cases, documents, AI results, generated docs | period, station, officer | 5 min |
| Station Performance Report | Zone_Officer, Senior_Command | station, users, cases, lifecycle, usage events | period, zone, station | 5 min |
| Lifecycle Funnel Report | Senior_Command, SHO | cases, status activities | period, station, IO, case type | 5 min |
| Monthly Trend Report | Senior_Command, AI_Admin | metric snapshots | month, zone, station | Daily/monthly |
| Feature Adoption Report | AI_Admin, System_Admin | usage_events, AIAnalysisResult, KIS status | period, feature, station | 5 min |
| Alert Report | Senior_Command, System_Admin | alert instances, metric snapshots | period, severity, status | 5 min |

### 11.2 Metric Calculation Definitions

| Metric | Calculation |
|---|---|
| Cases Created | Count of Case records created in period and scope |
| FIRs Registered | Count of cases whose current or reached status is FIR_Registered or later |
| Complaint-to-FIR Rate | FIRs Registered / Complaints Received |
| FIR Drafts Created | Count of GeneratedDocument subtype FIR_Draft plus unlinked parse-record FIR drafts not already represented |
| FIR Draft Iterations | Count of FIR draft generations per complaint/case |
| Median Complaint-to-FIR Draft Minutes | Median minutes from first intake to first FIR draft |
| Investigation Completion Count | Count of cases reaching Charge_Sheet_Filed or Closure_Report_Filed |
| Court Progression Count | Count of cases reaching Court_Proceedings |
| Active User Adoption Rate | Active users with one or more events / active users assigned to scope |
| AI Acceptance Rate | Reviewed accepted AI outputs / reviewed AI outputs |
| Low Confidence Rate | AI outputs with low confidence or uncertainty flag / total AI outputs |
| Quality Pass Rate | Quality checks passed / quality checks performed |


### 11.3 Permitted-Use Classification for Initial MVP Metrics

| Metric | Permitted Use | Prohibited Use | Confidence Gate |
|---|---|---|---|
| Cases Created | Workload awareness | Officer productivity conclusion without case mix review | Medium |
| FIRs Registered | Lifecycle awareness | Quality conclusion | High |
| FIR Drafts Created | Adoption and drafting support | Quality or diligence conclusion | Medium |
| Median Complaint-to-FIR Draft Minutes | Bottleneck investigation | Faster-is-better ranking | High plus sample >= 5 |
| Active User Adoption Rate | Training planning | Personnel action | Medium |
| AI Checks Performed | Feature adoption | Investigation quality conclusion | Medium |
| AI Acceptance Rate | AI governance | Officer competence conclusion | High plus reviewed sample >= 10 |
| Low Confidence Rate | AI/KB improvement | Officer competence conclusion | Medium |
| Investigation Completion Count | Lifecycle monitoring | Outcome quality conclusion | High |
| Court Progression Count | Lifecycle monitoring | Court success conclusion | Medium until court integration exists |

## 12. Migration & Launch Plan


### 12.0 Pre-Implementation Validation Gate

Before code execution, the team must produce a source inventory for the first 10 MVP metrics. Each metric must be marked `available`, `derivable`, `unreliable`, or `missing`, with file/table evidence. Metrics marked `unreliable` cannot appear in officer-level comparisons until corrected.

### 12.1 Data Migration Needs

- Add dashboard config tables: MetricDefinition, DashboardMetricSnapshot, DashboardSavedView, DashboardAlertRule, DashboardAlertInstance, DashboardExportJob, DashboardMetricDispute, DashboardMetricCorrection, DashboardMetricSourceMap.
- Backfill MetricDefinition seed records.
- Backfill UsageEvent rows from existing cases, documents, generated documents, AI analyses, and audit logs where direct usage events are missing.
- Add optional generated document subtype normalization for FIR drafts.
- Add indexes for dashboard query patterns.

### 12.2 Phased Rollout

| Phase | Scope |
|---|---|
| Phase 0 | Source inventory, metric legitimacy approval, event taxonomy, data-quality gate, and field-validation script |
| Phase 1 | Read-only overview KPIs, filters, station/officer tables, lifecycle funnel, PII-safe DTOs, audit, and direct queries |
| Phase 2 | Processing-time metrics, FIR draft iterations, feature adoption, export reports |
| Phase 3 | Materialized snapshots, alert rules, scheduled reports, data-quality warnings |
| Phase 4 | Training recommendations and predictive bottleneck signal after validation |
| Phase 5 | Scheduled reports, materialized snapshots, metric disputes/corrections, and advanced exports |

### 12.3 Go-Live Checklist

- Role mapping for senior officers configured.
- Metric definitions approved by HCP product owner.
- Data-quality warnings reviewed for missing station/IO assignments.
- Performance tested with representative case volume.
- Dashboard access/export audit verified.
- Senior-officer UAT completed using last 30 days and current month views.

## 13. Glossary

| Term | Definition |
|---|---|
| IQW | Investigation Quality Workbench |
| FIR | First Information Report |
| IO | Investigating Officer |
| SHO | Station House Officer |
| CCTNS | Crime and Criminal Tracking Network & Systems |
| KIS | Knowledge Intelligence Service |
| Complaint-to-FIR Time | Elapsed time from first complaint intake to FIR registration or FIR draft, depending on metric |
| FIR Draft Iteration | Each generated or regenerated FIR draft for a complaint/case |
| Lifecycle Funnel | Aggregated counts and conversion percentages across case statuses |
| Active User | User with at least one recorded dashboard-relevant event in the selected period |
| Adoption Rate | Active users divided by active users assigned to the selected scope |
| Metric Snapshot | Precomputed dashboard aggregate for a metric, period, and scope |
| Data Watermark | Latest source event timestamp included in a metric response |

## 14. Appendices

### Appendix A: BRD/RFQ Alignment

This BRD expands original BRD Module 10 / RFQ Module 10 requirements:

- Cases created per IO.
- Documents uploaded.
- AI checks performed.
- Drafts generated.
- Time spent per case.
- Feature usage frequency.
- Officer usage report.
- Feature adoption report.
- Monthly trends.

It also adds senior-officer effectiveness needs identified from the current application lifecycle:

- Complaint-to-FIR draft timing and iteration count.
- Complaint-to-FIR conversion funnel.
- Investigation completion and court progression tracking.
- Station and cohort comparison.
- Dashboard metric governance and privacy controls.

### Appendix B: Data Privacy Rules

- Dashboard aggregate APIs must not include raw complaint text, OCR extracted text, full generated draft content, addresses, phone numbers, victim names, accused names, witness names, or other case narrative PII.
- Drill-down views show operational metadata only.
- Exports inherit the same data minimization rules.
- Any LLM-generated dashboard explanation must be built from masked/aggregate data only.

### Appendix C: Quality Checklist Result

| Check | Result |
|---|---|
| Data model supports all FRs | Pass |
| Every FR has user story and acceptance criteria | Pass |
| UI screens defined | Pass |
| API endpoints and examples included | Pass |
| Error contract included | Pass |
| Notifications defined | Pass |
| Sample data for each entity | Pass |
| Glossary terms used in document | Pass |


### Appendix D: Adversarial Evaluation Synthesis

Council recommendation: proceed with the dashboard, but only as governed operational intelligence. Do not position it as a raw officer performance dashboard. The highest-priority safeguards are metric permitted-use labels, challenge/correction workflow, confidence tiers, sample-size gates, anti-gaming controls, and a Phase 1 release that avoids predictions and composite scoring.

| Recommendation | BRD v2 Response |
|---|---|
| Separate adoption from investigation quality | Added command decision model and permitted-use classification |
| Avoid de facto disciplinary scoring | Added prohibited-use rules and personnel analytics safeguards |
| Address metric gaming | Added anti-gaming controls and qualitative review rules |
| Make data quality visible | Added source maps, confidence rules, and warnings |
| Add contestability | Added MetricDispute and MetricCorrection entities plus workflow |
| Narrow implementation | Added Phase 0/Phase 1 gates and optional enhancement split |
| Clarify source-of-truth | Added canonical event taxonomy and source confidence table |
