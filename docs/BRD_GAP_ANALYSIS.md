# BRD Gap Analysis: HCP Investigation Quality Workbench (IQW)

**BRD Reference:** HCP/AI-QW/BRD/2026/01 v1.0
**Current System:** ADS Complaint Analyser (compliant-parser)
**Analysis Date:** 2026-04-13
**Purpose:** Identify gaps between BRD requirements and current implementation to guide development of new features and modification of existing ones.

---

## Executive Summary

The BRD describes a **10-module Investigation Quality Workbench** — a full case-lifecycle platform for ~100 IOs. The current system is a **single-purpose Complaint Parser** focused on OCR, multilingual translation, 5W+1H extraction, and FIR draft generation. Of the 10 BRD modules and 20 functional requirements, only **Module 7 (OCR & Translation)** has substantial coverage. The remaining modules represent **net-new development**.

### Coverage Heatmap

| Module | BRD Requirement | Current Coverage | Gap Severity |
|--------|----------------|-----------------|--------------|
| Module 1: Case Workbench | Full case management hub | **Not implemented** | CRITICAL |
| Module 2: Document Quality Engine | RAG-grounded quality evaluation | **Partial** (gap analysis only) | HIGH |
| Module 3: Section Recommendation | Legal section + ingredient mapping | **Partial** (BNS suggestion, no ingredients) | HIGH |
| Module 4: Congruence Engine | Cross-document contradiction detection | **Minimal** (basic compare mode) | CRITICAL |
| Module 5: SOP Generator | Investigation plan + deadlines | **Not implemented** | CRITICAL |
| Module 6: Document Generation | Template-based doc generation + DSC | **Partial** (FIR draft only) | HIGH |
| Module 7: OCR & Translation | Multilingual OCR + translation | **Substantially implemented** | LOW |
| Module 8: AI Training & Feedback | Uncertainty flagging + KB management | **Not implemented** | CRITICAL |
| Module 9: Judgment Analysis | Court judgment analysis | **Not implemented** | HIGH |
| Module 10: Usage Analytics | Usage tracking dashboard | **Not implemented** | HIGH |
| Cross-cutting: Authentication | HRMS/LDAP + JWT + RBAC | **Partial** (basic username/password) | HIGH |
| Cross-cutting: Audit Logging | Tamper-evident immutable logs | **Not implemented** | CRITICAL |
| Cross-cutting: Document Integrity | SHA-256 hash verification | **Not implemented** | HIGH |
| Cross-cutting: Digital Signatures | DSC/eSign integration | **Not implemented** | HIGH |
| Cross-cutting: Data Model | 13 entities with full audit trail | **Minimal** (1 table: parse_records) | CRITICAL |
| Cross-cutting: On-premise Deployment | Self-hosted AI, no cloud APIs | **Opposite** (uses cloud APIs) | CRITICAL |

---

## Detailed Gap Analysis by Module

---

### MODULE 1: Case Workbench (Core Hub)

**BRD Requirements:** FR-001 through FR-005
**Current Status:** NOT IMPLEMENTED
**Gap Severity:** CRITICAL

#### FR-001: Case Creation with Crime/Petition Number

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Case entity with Crime No. / Petition No. | Crime No. format NNNN/YYYY, Petition No. format PET/PS/YYYY/NNNN | No case concept exists. System parses individual complaint documents without case context. | **FULL GAP** — Need new Case entity, creation form, validation logic |
| CCTNS sync on creation | Auto-sync with retry (3x at 30s intervals) | No CCTNS integration | **FULL GAP** — Need CCTNS REST API integration layer |
| Case status lifecycle | Open -> Under_Investigation -> Charge_Sheet_Filed -> Closed/Transferred | No case status tracking | **FULL GAP** — Need state machine for case lifecycle |
| Unique Crime No. per police station/year | Validation + duplicate detection | Not applicable | **FULL GAP** |

**Development Required:**
- New `cases` database table matching BRD entity schema (Section 4.1)
- Case creation API (`POST /api/v1/cases`) with validation
- Case dashboard UI (top banner: case number, offence type, IO name, status)
- CCTNS sync service with retry logic and queue
- Case status state machine

#### FR-002: Offence Type Tagging

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Searchable offence dropdown | BNS/IPC section categories | System auto-detects incident type from complaint text but does not allow manual tagging | **FULL GAP** — Need manual offence tagging at case level |
| Primary + secondary offence types | Multi-select with primary designation | Only auto-detected single type | **FULL GAP** |
| Offence type drives downstream AI | SOP, sections, checklists keyed to offence | Partial — BNS suggestions use detected type | **PARTIAL GAP** — Need offence-to-module routing |

**Development Required:**
- Offence type master table (mapped to BNS/IPC sections)
- Searchable dropdown component
- Case-level offence tagging API
- Downstream module integration with offence type

#### FR-003: Document Attachment and Upload

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Multi-file drag-and-drop (up to 20) | Bulk upload with progress | Single file upload per parse request | **PARTIAL GAP** — Need bulk upload |
| Supported formats | PDF, JPEG, PNG, DOCX, TXT | PDF, DOCX, TIFF, JPEG, PNG, WEBP, BMP, GIF | **Exceeds BRD** (more formats), but missing TXT |
| Max file size 50 MB | Per file | 15 MB limit | **GAP** — Need to increase to 50 MB |
| SHA-256 hash on upload | Computed and stored for integrity | Not computed | **FULL GAP** |
| Document type tagging | Required before upload completes | No document type tagging | **FULL GAP** |
| Offline queue (PWA) | IndexedDB local storage, auto-sync | Offline banner exists but no queue functionality | **FULL GAP** |
| Documents belong to a Case | case_id foreign key | Documents standalone (parse_records) | **FULL GAP** |

**Development Required:**
- Bulk upload UI (multi-file dropzone)
- SHA-256 hash computation on upload
- Document type selection dropdown (Petition, FIR, Witness_Statement, etc.)
- Increase max upload to 50 MB
- PWA service worker + IndexedDB offline queue
- Link documents to cases via case_id FK

#### FR-004: Case Timeline View

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Chronological activity timeline | All case activities with version history | Parse history list (creation date only, no activity types) | **FULL GAP** |
| Sort toggle (newest/oldest first) | Bidirectional sort | History sorted newest-first only | **PARTIAL GAP** |
| Clickable entries -> detail view | Navigate to document/analysis | Can load historical records | **PARTIAL** — Exists for parse records, not general activities |
| Version history with diff view | Document version comparison | No versioning | **FULL GAP** |

**Development Required:**
- CaseActivity entity and table
- Timeline UI component with activity icons, timestamps, descriptions
- Document versioning system
- Diff viewer for document comparisons

#### FR-005: Action Tracker with Deadlines

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Task list with deadlines | Sorted by due date, priority levels | No task/action tracking | **FULL GAP** |
| Statutory deadline computation | Auto-populated from offence type | No deadline awareness | **FULL GAP** |
| Overdue highlighting | Red visual indicators | Not applicable | **FULL GAP** |
| In-app reminders | 3-day, 1-day, and due-date notifications | No notification system | **FULL GAP** |
| Task completion tracking | Checkbox to mark done | Not applicable | **FULL GAP** |

**Development Required:**
- Action tracker entity and table
- Statutory deadline reference data (by offence type)
- Task UI component with priority/status indicators
- Notification engine (in-app)
- Reminder scheduling system

---

### MODULE 2: Document Quality and Sufficiency Engine

**BRD Requirements:** FR-006
**Current Status:** PARTIALLY IMPLEMENTED
**Gap Severity:** HIGH

#### FR-006: AI Document Quality Evaluation

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Quality check against checklists | RAG-grounded evaluation by document_type and offence_type | Gap analysis exists (`_build_gap_summary`) — calculates completeness score, flags missing fields, generates review questions | **PARTIAL GAP** — Existing gap analysis covers missing fields but lacks checklist-driven evaluation, trial-risk indicators, and RAG citations |
| Missing elements with citations | Clickable links to specific document excerpts | Review questions generated but no page/excerpt citations | **SIGNIFICANT GAP** |
| Weak areas with improvement suggestions | Actionable IO-facing suggestions | Gap summary provides review questions but not structured improvement guidance | **PARTIAL GAP** |
| Trial-risk indicators | Severity: High/Medium/Low | Not implemented | **FULL GAP** |
| Citation requirement | Every finding must link to source excerpt; uncited findings hidden | Evidence snippets exist from extraction but not linked to quality findings | **SIGNIFICANT GAP** |
| Checklist by document_type + offence_type | KnowledgeBaseEntry-driven | No checklist/knowledge base system | **FULL GAP** |
| p95 < 10 seconds latency | Performance target | Timing metadata tracked but no SLA enforcement | **PARTIAL GAP** |

**What Can Be Reused:**
- `_build_gap_summary()` in complaint_parsing.py — completeness scoring logic
- `_score_to_confidence_label()` — confidence assessment
- `_collect_matching_snippets()` — evidence extraction
- Existing LLM integration (OpenAI) for AI-powered analysis

**Development Required:**
- Checklist engine with configurable rules per document_type + offence_type
- RAG pipeline: embed document chunks -> retrieve relevant checklist items -> evaluate
- Trial-risk severity classifier
- Citation linking system (excerpt -> page -> character offset)
- Quality check API endpoint (`POST /api/v1/cases/{case_id}/analysis/quality-check`)
- Quality check results UI with expandable findings, citations, and severity badges

---

### MODULE 3: Act and Section Recommendation Engine

**BRD Requirements:** FR-007
**Current Status:** PARTIALLY IMPLEMENTED
**Gap Severity:** HIGH

#### FR-007: Section Recommendation from Complaint Text

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Section recommendation with confidence scores | 0.00-1.00 decimal scores per section | `_suggest_bns_sections()` suggests BNS sections based on keyword-weighted incident classification. Scores are internal weights, not calibrated 0-1 confidence. | **PARTIAL GAP** — Need calibrated confidence scoring |
| Legal reasoning per section | Why this section applies | Not provided — only section numbers returned | **FULL GAP** |
| Supporting factual ingredients | Facts found in complaint that match section requirements | Not implemented — no ingredient mapping | **FULL GAP** |
| Missing ingredients | Facts needed but not found | Not implemented | **FULL GAP** |
| Alternative sections with confidence | Secondary recommendations | Only primary sections suggested | **PARTIAL GAP** |
| Mandatory disclaimer | "Final legal determination rests with IO..." | Not present in output | **FULL GAP** (easy fix) |
| Confidence threshold (< 0.30 hidden) | Show all results toggle | No threshold filtering | **PARTIAL GAP** |
| Self-hosted LLM (Llama 3 / Mistral) | Fine-tuned models | Uses cloud OpenAI GPT | **ARCHITECTURAL GAP** — Need self-hosted model |
| IO can paste or upload complaint text | Direct text input option | Only file upload currently | **PARTIAL GAP** |

**What Can Be Reused:**
- `_suggest_bns_sections()` — incident classification and BNS mapping logic
- `_INCIDENT_KEYWORDS` — weighted keyword dictionary
- `_extract_complaint_insights_via_openai()` — LLM extraction pipeline
- BNS section reference data already built into the system

**Development Required:**
- Section recommendation API endpoint (`POST /api/v1/cases/{case_id}/analysis/section-recommendation`)
- Legal ingredient mapping database (BNS sections -> required factual ingredients)
- Ingredient matching algorithm (complaint text -> ingredient checklist)
- Confidence score calibration (0.00-1.00 scale)
- Legal reasoning generation (LLM-powered)
- Missing ingredient identification
- "Paste complaint text" UI input mode
- Mandatory disclaimer injection
- Self-hosted LLM deployment (Llama 3 / Mistral) or adapter layer

---

### MODULE 4: Document Congruence Engine

**BRD Requirements:** FR-008
**Current Status:** MINIMAL IMPLEMENTATION
**Gap Severity:** CRITICAL

#### FR-008: Cross-Document Contradiction Detection

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Comparison pairs | Petition vs FIR, FIR vs Witness Statements, FIR vs Charge Sheet, Medical vs narrative | Basic compare mode exists: side-by-side view of two complaints with field-level comparison | **SIGNIFICANT GAP** — Compare mode shows differences but doesn't detect semantic contradictions, timeline inconsistencies, or role mismatches |
| Alert types | Contradiction, Timeline_Inconsistency, Role_Mismatch, Medical_Narrative_Discrepancy, Missing_Carry_Forward | No typed alerts | **FULL GAP** |
| Severity levels | High/Medium/Low per alert | No severity classification | **FULL GAP** |
| Excerpts from both documents | Side-by-side conflict excerpts | Some field comparison visible | **PARTIAL GAP** |
| False-positive dismissal | Reason codes + notes -> model refinement | No dismissal workflow | **FULL GAP** |
| Auto-trigger on document upload | Runs when related documents exist in case | Compare is manual-only | **FULL GAP** |
| In-app notification on new alerts | IO receives alert notification | No notification system | **FULL GAP** |

**What Can Be Reused:**
- Compare mode UI (compareView, compareSlotA/B)
- Field-by-field comparison rendering
- 5W+1H extraction results for structured comparison

**Development Required:**
- CongruenceAlert entity and table (BRD Section 4.5)
- Semantic contradiction detection engine (LLM-based)
- Timeline consistency checker (date/time cross-validation)
- Role mismatch detector (accused/witness name consistency)
- Medical-narrative discrepancy detector
- Missing carry-forward fact detection
- Alert severity classifier
- False-positive dismissal workflow with reason codes
- Auto-trigger on document upload (event-driven)
- Notification system for new alerts

---

### MODULE 5: SOP and Plan of Action Generator

**BRD Requirements:** FR-009
**Current Status:** NOT IMPLEMENTED
**Gap Severity:** CRITICAL

#### FR-009: Case-Specific Investigation Plan Generation

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Auto-detect offence type | From case data, confirm with IO | Auto-detects incident type from complaint text | **PARTIAL** — Detection exists but not case-linked |
| Investigation steps with legal citations | Numbered steps + BNSS references | Not implemented | **FULL GAP** |
| Evidence to collect | With forensic requirements per item | Not implemented | **FULL GAP** |
| Documents to generate | List of required documents | Not implemented | **FULL GAP** |
| Statutory deadlines in calendar format | Countdown indicators | Not implemented | **FULL GAP** |
| Editable plan | IO can add/remove/modify steps | Not implemented | **FULL GAP** |
| Task completion checkboxes | Per step | Not implemented | **FULL GAP** |

**Development Required:**
- InvestigationPlan entity and table (BRD Section 4.8)
- SOP reference data by offence type (investigation steps, evidence requirements, deadlines)
- Plan generation engine (template + LLM augmentation)
- Calendar UI with deadline visualization
- Editable plan UI with drag-and-drop reordering
- Step completion tracking
- Integration with Action Tracker (FR-005)

---

### MODULE 6: Document Generation Engine

**BRD Requirements:** FR-010
**Current Status:** PARTIALLY IMPLEMENTED
**Gap Severity:** HIGH

#### FR-010: Template-Based Document Auto-Generation

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Template-based generation | Templates with placeholder tokens | FIR draft generation exists (`_build_fir_draft`, `_build_fir_narrative`) — generates structured FIR from extracted fields | **PARTIAL** — Only FIR drafts, no template system |
| FSL Communications | Forwarding letters, sample memos, reminders | Not implemented | **FULL GAP** |
| Evidence Certificates | Section 63 BSA / 65B Certificate, hash declarations | Not implemented | **FULL GAP** |
| Legal Notices | Bank info requests, freeze requests, ISP/CDR requisitions, platform requests | Not implemented | **FULL GAP** |
| Legal Drafts | Arrest memo, seizure memo, remand note, confession template | Not implemented | **FULL GAP** |
| Auto-fill from case data | case_number, police_station, IO details, date, accused details | FIR draft auto-fills from extracted 5W+1H | **PARTIAL** — Only for FIR, not template-driven |
| Highlighted editable fields | All auto-filled fields remain editable | FIR draft is read-only in current UI | **GAP** — Need editable fields |
| Export to DOCX and PDF | Both formats | No export functionality | **FULL GAP** |
| Digital signature (DSC) | Sign within platform | Not implemented | **FULL GAP** |
| Missing field prompts | System highlights empty required fields | Not implemented | **FULL GAP** |

**What Can Be Reused:**
- `_build_fir_draft()` — FIR template structure and field population
- `_build_fir_narrative()` — narrative generation from 5W+1H
- `_suggest_bns_sections()` — section data for document population
- `_guess_district_unit()` — jurisdiction data
- `_extract_injury_or_harm_summary()` — medical data extraction

**Development Required:**
- DocumentTemplate entity and table (BRD Section 4.12)
- Template engine with `{{placeholder}}` token substitution
- Template library for all 4 categories (FSL, Evidence, Legal Notices, Legal Drafts)
- Template management UI (AI Admin)
- Document editing UI with highlighted auto-filled fields
- DOCX export (python-docx) and PDF export
- DSC/eSign integration (PKCS#11 / Web Crypto API)
- GeneratedDocument entity for tracking generated outputs

---

### MODULE 7: Multilingual OCR and Translation Engine

**BRD Requirements:** FR-011, FR-012
**Current Status:** SUBSTANTIALLY IMPLEMENTED
**Gap Severity:** LOW

#### FR-011: Handwritten and Scanned Document Processing

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Upload scanned/photographed docs | Detect language automatically | Fully implemented: multi-format upload + `_detect_language()` | **COVERED** |
| Side-by-side original + extracted text | Two-pane view | Implemented: preview tabs for original text and translation | **COVERED** |
| English translation in third pane | Three-pane layout | Translation tab exists; three-pane layout not explicit | **MINOR GAP** — Need three-pane simultaneous view |
| Confidence tagging per segment | High/Medium/Low with visual flags | Confidence scoring exists per field; segment-level granularity missing | **PARTIAL GAP** — Need per-segment (not per-field) confidence |
| Low-confidence yellow highlight | IO acknowledgement required | Confidence levels displayed but no mandatory acknowledgement | **GAP** — Need acknowledgement workflow for low-confidence |
| p95 < 5 seconds per page | OCR latency target | Timing tracked; uses Google Document AI (cloud) | **PARTIAL** — Performance likely met, but self-hosted OCR required |
| Self-hosted OCR (TrOCR/Donut) | Primary engine, Gemini fallback only | Google Document AI (cloud) as primary | **ARCHITECTURAL GAP** — BRD requires self-hosted primary |
| Urdu language support | Telugu, Urdu, Hindi, English | Telugu, Hindi, English supported; Urdu missing | **GAP** — Need Urdu language support |
| Self-hosted translation (IndicTrans2/NLLB) | On-premise models | Uses Google Cloud Translation, OpenAI, Gemini (all cloud) | **ARCHITECTURAL GAP** — Need self-hosted translation |

**What Is Already Implemented:**
- Google Document AI OCR integration (printed + handwritten)
- Language detection (English, Hindi, Telugu) with confidence scoring
- Multi-provider translation (Google, OpenAI, Gemini) with fallback
- OCR noise cleanup for Indic scripts
- Side-by-side original/translation preview
- Translation editing capability
- Translation quality estimation
- SSE streaming progress for OCR pipeline
- Dual-language analysis (original + translation)

**Development Required:**
- Urdu language detection and support
- Per-segment confidence tagging (not just per-field)
- Low-confidence acknowledgement workflow (IO must accept before saving)
- Three-pane simultaneous view (original image | extracted text | translation)
- **Architecture migration**: Self-hosted OCR engine (TrOCR/Donut) as primary, cloud as fallback
- **Architecture migration**: Self-hosted translation (IndicTrans2/NLLB-200) as primary

#### FR-012: PWA Offline Document Upload and OCR Queuing

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| PWA installable | Desktop and mobile browsers | Offline banner exists but no PWA manifest or service worker | **FULL GAP** |
| IndexedDB offline storage | Documents queued locally | Not implemented | **FULL GAP** |
| Offline queue UI | File name, size, timestamp, sync status | Not implemented | **FULL GAP** |
| Auto-sync on reconnect | Without user intervention | Not implemented | **FULL GAP** |
| Failed sync retry | Error reason + manual retry | Not implemented | **FULL GAP** |

**Development Required:**
- PWA manifest.json and service worker
- IndexedDB storage layer for offline document queue
- Background sync API integration
- Offline queue UI component
- Sync status tracking per document
- Auto-retry with exponential backoff

---

### MODULE 8: AI Training and Feedback Loop

**BRD Requirements:** FR-013, FR-014
**Current Status:** NOT IMPLEMENTED
**Gap Severity:** CRITICAL

#### FR-013: AI Uncertainty Flagging

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Auto-flag below Medium confidence | Uncertainty tags: Ambiguous_Statement, Unclear_Handwriting, Possible_Legal_Mismatch, Missing_Ingredient | Confidence scoring exists but no flagging/routing mechanism | **SIGNIFICANT GAP** |
| AI Admin review queue | Dashboard sorted by severity with filters | No admin role or queue | **FULL GAP** |
| Corrections with rationale | Update knowledge base | No correction workflow | **FULL GAP** |

#### FR-014: Knowledge Base Management with Staging

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Checklist/SOP entries | Draft -> Staging -> Production lifecycle | No knowledge base system | **FULL GAP** |
| Staging validation | Test prompts against staging entries | No staging environment | **FULL GAP** |
| Version tracking + rollback | Full version history with instant rollback | No versioning | **FULL GAP** |

**Development Required:**
- KnowledgeBaseEntry entity and table (BRD Section 4.11)
- AI Admin role and dashboard
- Uncertainty flagging pipeline
- Review queue with sorting, filtering, and bulk actions
- Correction workflow with rationale capture
- Knowledge base CRUD API with staging lifecycle
- Staging validation environment
- Version tracking and rollback system
- Model/prompt version tracking

---

### MODULE 9: Judgment Analysis Engine

**BRD Requirements:** FR-015
**Current Status:** NOT IMPLEMENTED
**Gap Severity:** HIGH

#### FR-015: Court Judgment Upload and Analysis

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Judgment upload (PDF/TXT, 50 MB) | Upload and process court judgments | Not implemented | **FULL GAP** |
| Extract case facts, issues, verdict | Structured analysis output | Not implemented | **FULL GAP** |
| Investigation lapses | Court observations on investigation quality | Not implemented | **FULL GAP** |
| Investigation Lessons summary | Bullet-point format | Not implemented | **FULL GAP** |
| Avoidable Errors summary | What could have been done differently | Not implemented | **FULL GAP** |
| Propose checklist updates | Feed into KB staging workflow (FR-014) | Not implemented | **FULL GAP** |

**Development Required:**
- JudgmentAnalysis entity and table (BRD Section 4.9)
- Judgment upload and text extraction pipeline
- Judgment analysis LLM pipeline (structured extraction)
- Investigation lessons summarizer
- Avoidable errors classifier
- Checklist update proposal generator
- Integration with KB staging workflow (Module 8)

---

### MODULE 10: Usage and Adoption Analytics

**BRD Requirements:** FR-016
**Current Status:** NOT IMPLEMENTED
**Gap Severity:** HIGH

#### FR-016: Usage Tracking Dashboard

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Cases created per IO/station | Aggregated metrics | No case tracking | **FULL GAP** |
| Documents uploaded count | By type and time period | Parse history exists but no analytics aggregation | **PARTIAL GAP** |
| AI checks performed | By type | No analytics | **FULL GAP** |
| Time-spent metrics | Per case and activity | Timing metadata exists per parse but no aggregation | **PARTIAL GAP** |
| Feature usage frequency | Module usage chart | No usage tracking | **FULL GAP** |
| Date/station/IO filters | Multi-dimensional filtering | Not implemented | **FULL GAP** |
| Monthly trend exports (PDF) | Exportable reports | Not implemented | **FULL GAP** |
| IO sees own data only | RBAC-scoped visibility | Single operator role | **FULL GAP** |

**Development Required:**
- Usage event tracking system (log every user action)
- Analytics aggregation service
- Dashboard UI with summary cards and charts
- Interactive chart library integration (Chart.js or similar)
- Filter system (date range, police station, IO)
- PDF report generation
- RBAC-scoped data visibility

---

## Cross-Cutting Requirements Gaps

### FR-017: User Authentication via HRMS Integration

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| HRMS authentication | REST API or LDAP | Basic username/password auth (single hardcoded operator) | **CRITICAL GAP** |
| Employee ID login | Synced from HRMS | Username only | **FULL GAP** |
| Profile sync | Name, rank, posting, role from HRMS | No profile data | **FULL GAP** |
| Account lockout | 5 failed attempts -> 30 min lockout | No lockout mechanism | **FULL GAP** |
| JWT tokens | 8-hour expiry + refresh tokens | Session cookie (12-hour expiry) | **ARCHITECTURAL GAP** — Need JWT |
| Multiple user roles | IO, Clerk, AI_Admin, System_Admin | Single "operator" role | **CRITICAL GAP** |
| ~100 concurrent users | Scalable multi-user | Single-operator design | **CRITICAL GAP** |

**Development Required:**
- User entity and table (BRD Section 4.10) with full RBAC
- HRMS REST API / LDAP integration adapter
- JWT-based authentication (access + refresh tokens)
- Account lockout mechanism (5 attempts / 30 minutes)
- Role-based permissions matrix implementation
- Multi-user session management
- Employee ID-based login form

### FR-018: Digital Signature Integration

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| DSC/eSign support | PKCS#11 / Web Crypto API | Not implemented | **FULL GAP** |
| Sign Document button | On all generated documents | Not applicable (no generated documents beyond FIR draft) | **FULL GAP** |
| Signature status tracking | Unsigned/Signed/Failed | Not implemented | **FULL GAP** |
| Signed = read-only | No further edits after signing | Not implemented | **FULL GAP** |

**Development Required:**
- DSC token detection (PKCS#11 browser extension or Web Crypto API)
- Signature workflow UI
- Signature status tracking in GeneratedDocument entity
- Read-only enforcement after signing

### FR-019: Audit Logging

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Tamper-evident immutable logs | No UPDATE/DELETE on audit table | No audit logging | **CRITICAL GAP** |
| All action types logged | Upload, Edit, Delete, AI_Analysis, Sign, Export, Login, Logout, Config_Change, etc. | No action logging (parse history records creation timestamp only) | **FULL GAP** |
| User, action, entity, timestamp, IP, session | Per log entry | Not tracked | **FULL GAP** |
| Searchable by date/user/action/entity | Multi-dimensional search | Not applicable | **FULL GAP** |
| 7-year retention | Minimum retention policy | No retention policy | **FULL GAP** |

**Development Required:**
- AuditLog entity and table (BRD Section 4.13) — append-only, no UPDATE/DELETE
- Audit logging middleware (intercept all API calls)
- Audit log search/filter UI
- Retention policy configuration
- IP address and session ID capture per request

### FR-020: Document Integrity Verification

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| SHA-256 hash on upload | Automatic computation and storage | File bytes stored in BYTEA but no hash | **FULL GAP** |
| Verify Integrity button | Re-compute and compare hashes | Not implemented | **FULL GAP** |
| Tamper alert | Warning message + System Admin notification | Not implemented | **FULL GAP** |

**Development Required:**
- SHA-256 computation on upload (hashlib)
- `sha256_hash` column in document tables
- Verification API endpoint
- Integrity check UI button with status display
- Alert system for hash mismatches

---

## Data Model Gaps

The BRD specifies **13 entities**. The current system has **1 table** (`parse_records`).

| BRD Entity | Current Equivalent | Gap |
|-----------|-------------------|-----|
| Case | None | **NEW** — Full case management entity |
| CaseDocument | parse_records (partial) | **MAJOR REWORK** — Add case_id FK, document_type, SHA-256, versioning, OCR status |
| AIAnalysisResult | Embedded in parse_records.parsed_output | **NEW** — Separate entity for each analysis type |
| Citation | None | **NEW** — Source document excerpt linking |
| CongruenceAlert | None | **NEW** — Cross-document conflict tracking |
| SectionRecommendation | Embedded in parsed_output | **NEW** — Separate entity with ingredients |
| GeneratedDocument | None | **NEW** — Template-generated document tracking |
| InvestigationPlan | None | **NEW** — Case investigation plan |
| JudgmentAnalysis | None | **NEW** — Court judgment analysis results |
| User | None (single hardcoded operator) | **NEW** — Full user management with RBAC |
| KnowledgeBaseEntry | None | **NEW** — Checklists, SOPs, templates |
| DocumentTemplate | None | **NEW** — Template library |
| AuditLog | None | **NEW** — Immutable audit trail |

**Additional tables likely needed:**
- PoliceStation (master data)
- OffenceType (master data, mapped to BNS/IPC)
- Notification (in-app notification queue)
- ActionTrackerTask (deadline-driven tasks)
- UsageEvent (analytics tracking)

---

## Architecture and Infrastructure Gaps

| Requirement | BRD Spec | Current State | Gap |
|------------|----------|---------------|-----|
| Deployment model | On-premise data centre | Google Cloud Run (cloud-hosted) | **CRITICAL** — Need on-premise deployment path |
| AI models | Self-hosted (Llama 3, Mistral, TrOCR, IndicTrans2) | Cloud APIs (OpenAI GPT, Google Document AI, Google Translate, Gemini) | **CRITICAL** — Need self-hosted model infrastructure |
| GPU infrastructure | On-premise GPU servers | No GPU; relies on cloud inference | **CRITICAL** — Need GPU procurement and setup |
| Data residency | All case data on-premise; no cloud transmission | All data processed via cloud APIs | **CRITICAL** — Violates data residency constraint |
| Concurrent users | ~100 users | Single-operator design | **CRITICAL** — Major scalability rework |
| Object storage | S3-compatible for documents | PostgreSQL BYTEA (in-database) | **HIGH** — Need separate object storage for 50 MB files |
| RTO / RPO | 1 hour / 15 minutes | No DR plan | **HIGH** |
| Backup strategy | Continuous incremental + daily full + immutable | No backup configuration | **HIGH** |
| Encryption at rest | AES-256 | Not configured | **HIGH** |
| Encryption in transit | TLS 1.3 | HTTPS optional (configurable) | **PARTIAL GAP** — Need TLS 1.3 enforcement |
| Key management | HSM or equivalent | No key management | **HIGH** |
| Browser support | Chrome 100+, Firefox 100+, Edge 100+ | Not explicitly tested/validated | **LOW** |
| Accessibility | WCAG 2.1 Level AA | Not tested | **MEDIUM** |
| Monitoring | 99.5% uptime with infrastructure monitoring | Basic health check endpoint | **HIGH** — Need full observability stack |

---

## UI/UX Gaps

| BRD UI Requirement | Current State | Gap |
|-------------------|---------------|-----|
| Case Dashboard (primary landing) | Parse view (upload-focused) | **FULL GAP** — Need case-centric dashboard |
| Left sidebar navigation (Docs, AI Analysis, Congruence, Plan, Generated, Timeline, Tracker) | Sidebar with document list + parse history | **SIGNIFICANT GAP** — Need case-scoped navigation |
| Document Viewer with AI overlays | PDF preview + result views (JSON, summary, table, FIR) | **PARTIAL** — Preview exists but no AI overlays |
| Three-pane OCR view | Two-tab view (original + translation) | **PARTIAL GAP** — Need simultaneous three-pane |
| AI Admin Dashboard | Not implemented | **FULL GAP** |
| Analytics Dashboard | Not implemented | **FULL GAP** |
| Login with Employee ID | Username/password | **GAP** — Need Employee ID field |
| 1366x768 minimum resolution | Responsive design exists | **NEEDS VALIDATION** |
| Sidebar -> hamburger on tablets | Collapsible sidebar exists | **PARTIAL** — Needs validation against BRD spec |

---

## API Gaps

The BRD specifies a versioned REST API (`/api/v1/...`). Current API uses `/api/...` without versioning.

| BRD API Endpoint | Current Equivalent | Gap |
|-----------------|-------------------|-----|
| `POST /api/v1/cases` | None | **NEW** |
| `POST /api/v1/cases/{id}/documents` | `POST /api/parse` | **REWORK** — Need case-scoped upload |
| `POST /api/v1/cases/{id}/analysis/quality-check` | None | **NEW** |
| `POST /api/v1/cases/{id}/analysis/section-recommendation` | None | **NEW** |
| `POST /api/v1/cases/{id}/analysis/congruence` | None | **NEW** |
| `POST /api/v1/cases/{id}/plan/generate` | None | **NEW** |
| `POST /api/v1/cases/{id}/documents/generate` | None | **NEW** |
| `POST /api/v1/judgments/analyze` | None | **NEW** |
| `GET /api/v1/analytics/...` | None | **NEW** |
| `GET /api/v1/admin/uncertainty-queue` | None | **NEW** |
| `POST /api/v1/admin/knowledge-base` | None | **NEW** |
| JWT-based auth | Session cookie auth | **REWORK** |
| Standard error format | Ad-hoc errors | **REWORK** — Need standard `{error: {code, message, field, request_id}}` |
| Rate limits: 100/min standard, 10/min AI | 30/min global | **REWORK** — Need per-endpoint rate limiting |

---

## Recommended Development Phases

Based on the BRD's own phased rollout plan (Section 12.2):

### Phase 1: Core Foundation (Aligns with BRD Go-Live)

**Priority: CRITICAL — Build the platform foundation**

1. **Data Model Migration** — Create all 13+ database entities
2. **User Management + RBAC** (FR-017) — Replace single-operator with multi-user HRMS auth
3. **Case Workbench** (Module 1 / FR-001 to FR-005) — Case CRUD, timeline, action tracker
4. **Document Quality Engine** (Module 2 / FR-006) — Extend gap analysis to checklist-based evaluation
5. **Document Generation Engine** (Module 6 / FR-010) — Template system + export
6. **OCR & Translation Enhancements** (Module 7 / FR-011, FR-012) — Urdu support, PWA offline, per-segment confidence
7. **Audit Logging** (FR-019) — Immutable audit trail
8. **API Versioning** — Migrate to `/api/v1/...` with standard error format

### Phase 2: AI-Intensive Modules (Go-Live + 4 weeks)

9. **Section Recommendation Engine** (Module 3 / FR-007) — Ingredient mapping, legal reasoning
10. **Congruence Engine** (Module 4 / FR-008) — Contradiction detection
11. **SOP Generator** (Module 5 / FR-009) — Investigation plans
12. **AI Feedback Loop** (Module 8 / FR-013, FR-014) — Uncertainty flagging, KB management

### Phase 3: Analytics and Advanced (Go-Live + 8 weeks)

13. **Judgment Analysis** (Module 9 / FR-015) — Court judgment processing
14. **Usage Analytics** (Module 10 / FR-016) — Dashboards and reports
15. **Digital Signatures** (FR-018) — DSC integration
16. **Document Integrity** (FR-020) — SHA-256 verification

### Phase 4: Architecture Migration (Parallel Track)

17. **On-premise deployment** — Migrate from Cloud Run to on-premise
18. **Self-hosted AI models** — Replace cloud APIs with Llama 3/Mistral, TrOCR, IndicTrans2
19. **GPU infrastructure** — Provision and configure
20. **CCTNS integration** — Connect to national police database
21. **Security hardening** — AES-256 encryption, TLS 1.3, HSM key management
22. **DR/Backup** — Implement RTO/RPO targets

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total BRD Functional Requirements (FR-001 to FR-020) | 20 |
| Fully implemented | 0 |
| Substantially implemented | 1 (FR-011: OCR/Translation) |
| Partially implemented | 4 (FR-006, FR-007, FR-008, FR-010) |
| Not implemented | 15 |
| New database entities required | 12+ |
| New API endpoints required | ~30+ |
| New UI views/pages required | ~8+ |
| Architecture migrations required | 3 (on-prem, self-hosted AI, object storage) |
