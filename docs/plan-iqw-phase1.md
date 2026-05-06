# Development Plan: IQW Phase 1 — Core Foundation

## Overview
Transform the ADS Complaint Analyser into the HCP Investigation Quality Workbench (IQW) Phase 1 platform. This adds case management, multi-user RBAC, audit logging, document quality evaluation, document generation, OCR enhancements, and API versioning — while preserving all existing complaint parsing functionality.

## Architecture Decisions

- **New modules alongside existing files**: Create `models.py`, `auth.py`, `audit.py`, `cases.py`, `quality_engine.py`, `document_generator.py`, `api_v1.py` rather than bloating `app.py` (784 lines). Existing routes in `app.py` remain untouched for backward compatibility; new v1 routes live in separate routers.
- **SQLAlchemy ORM models**: Extend `database.py` with new `models.py` defining all 18 entities. Reuse the existing async engine and connection patterns (pool_size=5, max_overflow=2).
- **JWT over sessions**: New v1 API uses JWT (PyJWT). Legacy session auth in `app.py` remains for backward compatibility. Both mechanisms coexist.
- **Template engine for documents**: Use Jinja2 for `{{placeholder}}` token substitution in document templates. python-docx for DOCX export, weasyprint or reportlab for PDF.
- **Frontend additive approach**: New UI views (case dashboard, quality check, doc generation, admin panels) are added as new `<section>` elements in `index.html` alongside existing `#parseView`, `#compareView`, `#documentListView`. Navigation updated to include new sections.
- **PWA**: Add `manifest.json` and `sw.js` at project root. Register service worker from `index.html`.

## Conventions

- **Python**: Type hints everywhere (`from __future__ import annotations`), async/await for I/O, PEP 8. Follow patterns in `app.py` (line 1: `from __future__ import annotations`).
- **Database**: SQLAlchemy 2.0 async style with `mapped_column()`. All entities have `created_at`, `updated_at`, `created_by`, `updated_by`, `is_deleted`, `deleted_at` audit fields. UUID primary keys as strings.
- **API routes**: FastAPI `APIRouter` with tags. Dependency injection for auth via `Depends()`. Follow error pattern in `app.py` line ~200: `raise HTTPException(status_code=400, detail="...")`.
- **Frontend**: Vanilla JS, no frameworks. CSS custom properties for theming. ARIA labels on interactive elements. Follow ID naming convention: `camelCase` (e.g., `#caseListView`, `#caseCreateBtn`).
- **Tests**: unittest framework, mock external services, follow `tests/test_app.py` patterns.

---

## Phase 1: Data Model & API Infrastructure
**Dependencies:** none

**Description:**
Create all database entities required by the BRD (18 tables), set up the v1 API router structure with standard error handling, and add new Python dependencies. This is the foundation everything else builds on.

**Tasks:**
1. Update `requirements.txt` to add: `PyJWT==2.10.1`, `passlib[bcrypt]==1.7.4`, `python-docx==1.1.2`, `reportlab==4.4.0`, `jinja2==3.1.6`, `pydantic[email]==2.11.4`. Keep all existing dependencies unchanged.

2. Create `models.py` with all 18 SQLAlchemy ORM models using the declarative base pattern:
   - **Master data**: `PoliceStation`, `OffenceType` (with BNS/IPC section mapping)
   - **Core entities**: `User`, `Case`, `CaseDocument` (extends existing parse_records concept), `CaseActivity`
   - **AI entities**: `AIAnalysisResult`, `Citation`, `CongruenceAlert`, `SectionRecommendation`
   - **Generation entities**: `GeneratedDocument`, `DocumentTemplate`, `InvestigationPlan`
   - **Judgment**: `JudgmentAnalysis`
   - **Admin entities**: `KnowledgeBaseEntry`
   - **System entities**: `AuditLog`, `Notification`, `ActionTrackerTask`, `UsageEvent`
   - Every entity uses UUID string primary key, includes audit fields (created_at, updated_at, created_by, updated_by), and soft-delete (is_deleted, deleted_at).
   - Use SQLAlchemy 2.0 `Mapped`, `mapped_column`, `relationship` patterns.
   - Define all enums as Python Enum classes: `CaseType`, `CaseStatus`, `CCTNSSyncStatus`, `DocumentType`, `OCRStatus`, `OCRConfidence`, `AnalysisType`, `ConfidenceLevel`, `AlertType`, `AlertSeverity`, `DismissReasonCode`, `ActName`, `DocumentCategory`, `SignatureStatus`, `KBEntryType`, `KBEntryStatus`, `UserRole`, `ActionType`, `TaskPriority`, `TaskStatus`, `TaskSource`.
   - Keep existing `parse_records` table in `database.py` untouched.

3. Update `database.py`:
   - Import `Base` metadata from `models.py`
   - Add `initialize_all_tables()` function that creates all new tables (using `Base.metadata.create_all`) alongside existing `initialize_database()` which handles `parse_records`.
   - Both functions called during app startup.

4. Create `api_v1.py` with the v1 router structure:
   - `v1_router = APIRouter(prefix="/api/v1")`
   - Standard error response model: `{"error": {"code": str, "message": str, "field": str|null, "request_id": str}}`
   - Error codes enum: VALIDATION_ERROR (400), AUTHENTICATION_ERROR (401), AUTHORIZATION_ERROR (403), NOT_FOUND (404), CONFLICT (409), SERVER_ERROR (500), SERVICE_UNAVAILABLE (503)
   - Helper function `raise_api_error(code, message, field=None)` that generates request_id and raises HTTPException with standard format.
   - Per-endpoint rate limiting decorator: `rate_limit(rpm=100)` for standard endpoints, `rate_limit(rpm=10)` for AI endpoints.
   - Mount sub-routers: `auth_router`, `cases_router`, `analysis_router`, `documents_router`, `admin_router`, `analytics_router`.

5. Update `app.py`:
   - Import and mount `v1_router` from `api_v1.py`: `app.include_router(v1_router)`
   - Add `initialize_all_tables()` call in `lifespan()` after existing `initialize_database()`.
   - Keep ALL existing routes unchanged.

6. Write tests in `tests/test_models.py`:
   - Verify all 18 models can be instantiated
   - Verify enum values match BRD specifications
   - Verify audit field defaults work correctly
   - Verify standard error format helper produces correct JSON

**Files to create/modify:**
- `requirements.txt` — Add 6 new dependencies
- `models.py` — NEW: All 18 SQLAlchemy ORM models + enums (estimated ~800 lines)
- `database.py` — Add `initialize_all_tables()`, import Base from models
- `api_v1.py` — NEW: V1 router scaffold, error handling, rate limiting (~200 lines)
- `app.py` — Mount v1_router, call initialize_all_tables in lifespan
- `tests/test_models.py` — NEW: Model + enum + error format tests

**Acceptance criteria:**
- All 18 tables are created in PostgreSQL on app startup
- Existing `parse_records` table is untouched and still works
- `GET /api/v1/health` returns `{"status": "ok"}` (placeholder)
- All existing routes (`/api/parse`, `/api/history`, etc.) still work identically
- Tests pass: `python -m pytest tests/test_models.py`

---

## Phase 2: Authentication & RBAC
**Dependencies:** Phase 1

**Description:**
Replace single-operator auth with multi-user JWT-based authentication supporting 4 roles (IO, Clerk, AI_Admin, System_Admin). HRMS integration is stubbed (local user store with HRMS-compatible fields). Legacy session auth in `app.py` preserved for backward compatibility.

**Tasks:**
1. Create `auth.py` with JWT authentication system:
   - `create_access_token(user_id, role, expires_delta=8h) -> str` using PyJWT HS256
   - `create_refresh_token(user_id, expires_delta=24h) -> str`
   - `decode_token(token) -> dict` with expiry validation
   - `hash_password(password) -> str` using passlib bcrypt
   - `verify_password(plain, hashed) -> bool`
   - `require_auth(request) -> User` — FastAPI dependency that extracts JWT from Authorization header, validates, returns User object
   - `require_role(*roles)` — Returns dependency that checks user role is in allowed list
   - Account lockout tracking: dict of `{employee_id: (failed_count, locked_until)}` with 5 attempt / 30 minute lockout
   - Environment variables: `JWT_SECRET_KEY` (falls back to APP_SESSION_SECRET), `JWT_ALGORITHM=HS256`

2. Create v1 auth endpoints in `api_v1.py` (or `routes/auth_routes.py`):
   - `POST /api/v1/auth/login` — Accepts `{employee_id, password}`, returns `{access_token, refresh_token, user: {id, name, role, rank, police_station}}`
   - `POST /api/v1/auth/refresh` — Accepts `{refresh_token}`, returns new `{access_token}`
   - `POST /api/v1/auth/logout` — Invalidates token (add to blacklist set)
   - `GET /api/v1/auth/me` — Returns current user profile
   - Account lockout: after 5 failed attempts, return 423 Locked with retry-after header

3. Create user management endpoints:
   - `GET /api/v1/users` — List users (System_Admin only)
   - `POST /api/v1/users` — Create user (System_Admin only)
   - `GET /api/v1/users/{id}` — Get user (self or System_Admin)
   - `PUT /api/v1/users/{id}` — Update user (self or System_Admin)
   - `PATCH /api/v1/users/{id}/deactivate` — Soft-deactivate (System_Admin only)

4. Seed initial admin user on startup:
   - If no users exist in the `users` table, create a System_Admin user from `APP_ADMIN_USERNAME` / `APP_ADMIN_PASSWORD` environment variables.
   - This preserves the existing single-operator setup as the initial admin.

5. Create permissions matrix as a data structure:
   ```python
   PERMISSIONS = {
       "create_case": [UserRole.IO],
       "upload_document": [UserRole.IO, UserRole.Clerk],
       "run_quality_check": [UserRole.IO, UserRole.AI_Admin],
       "run_section_recommendation": [UserRole.IO, UserRole.AI_Admin],
       "run_congruence": [UserRole.IO, UserRole.AI_Admin],
       "generate_document": [UserRole.IO],
       "sign_document": [UserRole.IO],
       "dismiss_alert": [UserRole.IO, UserRole.AI_Admin],
       "view_own_analytics": [UserRole.IO],
       "view_all_analytics": [UserRole.AI_Admin, UserRole.System_Admin],
       "manage_kb": [UserRole.AI_Admin],
       "manage_users": [UserRole.System_Admin],
       "manage_config": [UserRole.System_Admin],
       "upload_judgment": [UserRole.IO, UserRole.AI_Admin],
       "access_ocr": [UserRole.IO, UserRole.Clerk, UserRole.AI_Admin],
   }
   ```

6. Update login UI in `index.html`:
   - Change username field label to "Employee ID" and id to `#loginEmployeeId`
   - Add JWT token storage in localStorage (access_token, refresh_token)
   - Update `fetchWithApiFallback()` to include `Authorization: Bearer <token>` header for v1 API calls
   - Keep existing session-based auth for legacy `/api/` routes
   - Show user role badge in topbar next to avatar
   - Update profile modal to show: name, employee_id, rank, designation, police_station, role

7. Write tests in `tests/test_auth.py`:
   - JWT creation and validation
   - Password hashing and verification
   - Account lockout after 5 failures
   - Role-based access control (IO can create case, Clerk cannot)
   - Token refresh flow
   - Login with invalid credentials returns 401
   - Locked account returns 423

**Files to create/modify:**
- `auth.py` — NEW: JWT auth, password hashing, RBAC, lockout (~300 lines)
- `api_v1.py` — Add auth routes and user management routes
- `app.py` — Add user seeding in lifespan startup
- `index.html` — Update login form, add JWT handling, role badge
- `tests/test_auth.py` — NEW: Auth + RBAC tests

**Acceptance criteria:**
- `POST /api/v1/auth/login` with valid credentials returns JWT tokens
- `POST /api/v1/auth/login` with wrong password 5 times returns 423 on 6th attempt
- `GET /api/v1/auth/me` with valid Bearer token returns user profile
- Role-restricted endpoints return 403 for unauthorized roles
- Existing `/api/auth/login` session-based auth still works
- Initial admin user auto-created from environment variables on first startup
- Tests pass: `python -m pytest tests/test_auth.py`

---

## Phase 3: Audit Logging & Document Integrity
**Dependencies:** Phase 1, Phase 2

**Description:**
Implement tamper-evident immutable audit logging and SHA-256 document integrity verification. The audit middleware intercepts all v1 API calls and records who did what, when, and from where.

**Tasks:**
1. Create `audit.py` with audit logging system:
   - `AuditMiddleware` class (Starlette middleware) that wraps all `/api/v1/` requests:
     - Captures: user_id (from JWT), action_type (inferred from method+path), entity_type, entity_id (from path params), ip_address, session_id, request details
     - Inserts into `audit_logs` table after response is sent (non-blocking background task)
     - Action type mapping: POST->Upload/AI_Analysis/Document_Generation, PUT/PATCH->Edit, DELETE->Delete, GET (for exports)->Export
   - `log_audit_event(user_id, action_type, entity_type, entity_id, details, ip, session)` — Direct logging function for non-request events (e.g., login, config changes)
   - Audit log query functions:
     - `search_audit_logs(filters: dict, page, size) -> list[AuditLog]` — Filter by date_range, user_id, action_type, entity_type
   - The `audit_logs` table has NO update or delete operations (enforced in code — no PUT/DELETE endpoints for audit logs, no SQLAlchemy update/delete queries).

2. Create audit log API endpoints:
   - `GET /api/v1/audit-logs` — Search/list audit logs (System_Admin only). Params: date_from, date_to, user_id, action_type, entity_type, page, page_size.
   - `GET /api/v1/audit-logs/{log_id}` — Get single log entry (System_Admin only).
   - No PUT, PATCH, or DELETE endpoints for audit logs (immutability enforced).

3. Implement SHA-256 document integrity:
   - Add utility function `compute_sha256(file_bytes: bytes) -> str` in `audit.py`
   - Add `sha256_hash` column to `CaseDocument` model (already in Phase 1 models, ensure it's populated)
   - Create integrity verification endpoint: `POST /api/v1/documents/{id}/verify-integrity`
     - Re-computes SHA-256 from stored file_bytes, compares with stored hash
     - Returns `{"verified": true, "message": "Document integrity verified."}` or `{"verified": false, "message": "WARNING: Document integrity check failed."}`
     - On failure: creates audit log entry and Notification for System_Admin

4. Add audit logging middleware to app startup in `app.py`:
   - `app.add_middleware(AuditMiddleware)` — after existing middleware

5. Write tests in `tests/test_audit.py`:
   - Audit log creation on API calls
   - Audit log immutability (no update/delete)
   - SHA-256 computation correctness
   - Integrity verification pass/fail scenarios
   - Audit log search with filters

**Files to create/modify:**
- `audit.py` — NEW: AuditMiddleware, SHA-256 utils, log functions (~250 lines)
- `api_v1.py` — Add audit-logs and integrity verification endpoints
- `app.py` — Mount AuditMiddleware
- `tests/test_audit.py` — NEW: Audit + integrity tests

**Acceptance criteria:**
- Every v1 API call produces an audit log entry with user_id, action, timestamp, IP
- `GET /api/v1/audit-logs` returns searchable, filterable log entries
- No code path exists to UPDATE or DELETE audit_logs records
- `POST /api/v1/documents/{id}/verify-integrity` correctly verifies SHA-256 hash
- Tampered document returns integrity failure + notification created
- Tests pass: `python -m pytest tests/test_audit.py`

---

## Phase 4: Case Workbench
**Dependencies:** Phase 1, Phase 2

**Description:**
Implement the core case management system (BRD Module 1: FR-001 to FR-005). This is the heart of the IQW platform — everything else hangs off cases.

**Tasks:**
1. Create `cases.py` with case management service layer:
   - `create_case(data, user) -> Case` — Validates Crime No. format (NNNN/YYYY) or Petition No. (PET/PS/YYYY/NNNN), checks uniqueness per police_station+year, creates case with status=Open, triggers CCTNS sync stub
   - `get_case(case_id, user) -> Case` — Returns case with related counts
   - `list_cases(user, filters) -> list[Case]` — Filter by status, police_station, date_range. IO sees own cases only.
   - `update_case(case_id, data, user) -> Case` — Update offence_type, status, brief_facts
   - `transition_case_status(case_id, new_status, user)` — State machine validation:
     - Open -> Under_Investigation (on first document upload)
     - Under_Investigation -> Charge_Sheet_Filed | Closed | Transferred
     - Charge_Sheet_Filed -> Closed
   - `cctns_sync_stub(case_id)` — Background task that simulates CCTNS sync (3 retries at 30s intervals, marks Synced or Failed). Real CCTNS integration is Phase 4 (architecture migration).

2. Create case document management (extends FR-003):
   - `attach_document(case_id, file, document_type, user) -> CaseDocument` — Computes SHA-256, stores file, links to case, triggers OCR if scanned
   - `list_case_documents(case_id, user) -> list[CaseDocument]`
   - `get_case_document(case_id, doc_id, user) -> CaseDocument`
   - Support bulk upload: accept up to 20 files in a single request
   - Max file size: 50 MB (update MAX_PARSE_UPLOAD_BYTES default)
   - Document type tagging required (enum: Petition, FIR, Witness_Statement, Charge_Sheet, Medical_Report, FSL_Report, Seizure_Memo, Arrest_Memo, Remand_Note, Confession, CDR, Other)

3. Create offence type management (FR-002):
   - Seed `offence_types` table with BNS/IPC section categories on startup
   - `GET /api/v1/offence-types` — Returns searchable list
   - `GET /api/v1/offence-types?q=theft` — Search by name
   - Case creation and update accept primary_offence_type_id and secondary_offence_type_ids

4. Implement case timeline (FR-004):
   - `CaseActivity` records created automatically on: document upload, AI analysis, document generation, status change, edit
   - `GET /api/v1/cases/{id}/timeline` — Returns activities in reverse chronological order
   - Query param `?sort=asc` for oldest-first
   - Each entry: timestamp, action_type, user name, description, link to entity

5. Implement action tracker (FR-005):
   - `ActionTrackerTask` entity with: task_name, due_date, priority (High/Medium/Low), status (Pending/Overdue/Completed), source (Statutory/SOP/Manual), case_id
   - On case creation: auto-populate statutory deadlines based on offence_type (e.g., charge sheet filing deadline)
   - `GET /api/v1/cases/{id}/tasks` — List tasks sorted by due_date
   - `PUT /api/v1/cases/{id}/tasks/{task_id}` — Update status (mark completed, snooze)
   - `POST /api/v1/cases/{id}/tasks` — Create manual task
   - Overdue detection: tasks past due_date automatically flagged

6. Implement in-app notifications:
   - `Notification` entity with: user_id, type, message, is_read, entity_type, entity_id
   - `GET /api/v1/notifications` — List unread notifications for current user
   - `PATCH /api/v1/notifications/{id}/read` — Mark as read
   - Notifications created for: overdue tasks, CCTNS sync failures, integrity failures, congruence alerts

7. Create all case API endpoints:
   - `POST /api/v1/cases` — Create case (IO only)
   - `GET /api/v1/cases` — List cases (IO: own; Admin: all)
   - `GET /api/v1/cases/{id}` — Get case detail
   - `PUT /api/v1/cases/{id}` — Update case
   - `PATCH /api/v1/cases/{id}/status` — Transition status
   - `POST /api/v1/cases/{id}/documents` — Upload document(s) to case
   - `GET /api/v1/cases/{id}/documents` — List case documents
   - `GET /api/v1/cases/{id}/documents/{doc_id}` — Get document detail
   - `GET /api/v1/cases/{id}/documents/{doc_id}/file` — Download original file
   - `GET /api/v1/cases/{id}/timeline` — Get timeline
   - `GET /api/v1/cases/{id}/tasks` — List tasks
   - `POST /api/v1/cases/{id}/tasks` — Create task
   - `PUT /api/v1/cases/{id}/tasks/{task_id}` — Update task
   - `GET /api/v1/notifications` — List notifications
   - `PATCH /api/v1/notifications/{id}/read` — Mark notification read
   - `GET /api/v1/police-stations` — List police stations
   - `GET /api/v1/offence-types` — List/search offence types

8. Create case workbench frontend in `index.html`:
   - Add new `<section id="caseListView">` — Case list with search, filters (status, station, date), create button
   - Add new `<section id="caseDetailView">` — Case dashboard with:
     - Top banner: case number, offence type, IO name, status badge, CCTNS sync status
     - Left sidebar tabs: Documents, AI Analysis, Timeline, Action Tracker, Generated Docs
     - Main content area changes based on selected tab
   - Case creation modal with: case_type selector (FIR/Petition), crime_no/petition_no input with format validation, offence_type searchable dropdown (primary + secondary), police_station dropdown, brief_facts textarea
   - Document upload panel: multi-file dropzone (up to 20), document_type dropdown per file, progress bars
   - Timeline view: reverse-chronological activity list with icons per action type
   - Action tracker: task list with priority badges, due dates, overdue highlighting (red), completion checkboxes
   - Notification bell icon in topbar with unread count badge
   - Update sidebar navigation: add "Cases" as primary nav item above existing "Documents"

9. Write tests in `tests/test_cases.py`:
   - Case creation with valid/invalid Crime No. format
   - Duplicate Crime No. detection
   - Case status transitions (valid and invalid)
   - Offence type tagging
   - Document upload with SHA-256
   - Bulk upload (multiple files)
   - Timeline activity creation
   - Action tracker CRUD
   - Notification creation and read
   - RBAC: IO can create cases, Clerk cannot

**Files to create/modify:**
- `cases.py` — NEW: Case service layer, CCTNS stub, state machine (~500 lines)
- `api_v1.py` — Add all case/document/timeline/task/notification endpoints
- `index.html` — Add caseListView, caseDetailView, case creation modal, notifications
- `tests/test_cases.py` — NEW: Case management tests

**Acceptance criteria:**
- `POST /api/v1/cases` with Crime No. `0125/2026` creates a case with status Open
- Invalid Crime No. format returns 400 with standard error format
- Duplicate Crime No. per station/year returns 409 Conflict
- Case status transitions follow the state machine (invalid transitions return 400)
- Document upload computes SHA-256 and requires document_type
- Bulk upload accepts up to 20 files
- Timeline shows all case activities in chronological order
- Action tracker auto-populates statutory deadlines on case creation
- Overdue tasks are flagged
- Notifications appear for relevant events
- Case list shows IO's own cases only (RBAC enforced)
- Tests pass: `python -m pytest tests/test_cases.py`

---

## Phase 5: Document Quality Engine
**Dependencies:** Phase 4

**Description:**
Extend the existing gap analysis in complaint_parsing.py into a full checklist-driven quality evaluation engine with RAG-grounded citations, trial-risk indicators, and actionable improvement suggestions (BRD Module 2, FR-006).

**Tasks:**
1. Create `quality_engine.py` with the quality evaluation system:
   - `QualityChecker` class that evaluates documents against checklists:
     - `run_quality_check(document_text, document_type, offence_type) -> QualityCheckResult`
     - Loads checklist from `KnowledgeBaseEntry` table (filtered by document_type + offence_type)
     - If no specific checklist found, uses generic checklist with note: "Generic checklist applied."
   - Checklist evaluation engine:
     - Each checklist item has: requirement_text, severity (High/Medium/Low), category
     - For each item, search document text for evidence using existing `_collect_matching_snippets()` from complaint_parsing.py
     - Score each item: present (with citation), weak (partial evidence), missing (no evidence)
   - Trial-risk indicator classification:
     - High: Missing elements likely to cause acquittal (e.g., missing witness identification, no time of occurrence)
     - Medium: Elements that may be challenged (e.g., vague location, no corroboration)
     - Low: Minor deficiencies (e.g., formatting issues, minor omissions)
   - Citation system:
     - Every finding must include `excerpt_text` from the source document
     - Include approximate character offset (start, end) for UI highlighting
     - Findings without citations are excluded from output
   - Improvement suggestions:
     - For each missing/weak item, generate actionable IO-facing suggestion
     - Use LLM (via existing OpenAI integration in complaint_parsing.py) to generate context-specific suggestions
   - Reuse from complaint_parsing.py:
     - `_build_gap_summary()` for completeness scoring
     - `_collect_matching_snippets()` for evidence extraction
     - `_score_to_confidence_label()` for confidence assessment

2. Seed default checklists in `KnowledgeBaseEntry`:
   - Generic Investigation Document checklist (15-20 items covering: complainant details, incident description, time/date, location, witness list, evidence list, etc.)
   - FIR-specific checklist
   - Witness Statement checklist
   - Charge Sheet checklist
   - Each checklist item: requirement text, severity, legal reference

3. Create quality check API endpoints:
   - `POST /api/v1/cases/{case_id}/analysis/quality-check` — Body: `{document_id}`. Returns structured quality report.
   - Response format:
     ```json
     {
       "analysis_id": "uuid",
       "findings": [
         {
           "type": "missing_element|weak_area",
           "description": "...",
           "severity": "High|Medium|Low",
           "suggestion": "...",
           "citation": {"excerpt": "...", "page": null, "char_start": 0, "char_end": 50}
         }
       ],
       "trial_risk_indicators": [
         {"risk": "...", "severity": "High|Medium|Low"}
       ],
       "completeness_score": 0.72,
       "confidence_score": "High|Medium|Low"
     }
     ```
   - Stores result in `AIAnalysisResult` table with analysis_type=Quality_Check

4. Create quality check UI in `index.html`:
   - In case detail view, "AI Analysis" tab:
     - "Run Quality Check" button on each document
     - Processing indicator with estimated time
     - Results panel with expandable findings
     - Each finding shows: severity badge (red/yellow/green), description, suggestion, citation excerpt (highlighted)
     - Trial-risk summary at top with severity counts
     - Completeness score gauge/bar

5. Write tests in `tests/test_quality_engine.py`:
   - Checklist loading by document_type + offence_type
   - Generic checklist fallback
   - Citation extraction accuracy
   - Trial-risk classification
   - Quality check API endpoint integration test
   - Result persistence in AIAnalysisResult table

**Files to create/modify:**
- `quality_engine.py` — NEW: QualityChecker class, checklist evaluation (~400 lines)
- `api_v1.py` — Add quality-check endpoint
- `models.py` — Ensure KnowledgeBaseEntry seeds exist
- `index.html` — Add quality check UI in case detail view
- `tests/test_quality_engine.py` — NEW: Quality engine tests

**Acceptance criteria:**
- `POST /api/v1/cases/{id}/analysis/quality-check` returns structured findings with citations
- Findings without citations are excluded
- Trial-risk indicators classified as High/Medium/Low
- Generic checklist applied when no specific checklist matches
- Results stored in AIAnalysisResult table
- UI shows findings with severity badges, expandable citations, and improvement suggestions
- Tests pass: `python -m pytest tests/test_quality_engine.py`

---

## Phase 6: Document Generation Engine
**Dependencies:** Phase 4

**Description:**
Build a template-based document generation system with auto-fill from case data, editable fields, and DOCX/PDF export (BRD Module 6, FR-010).

**Tasks:**
1. Create `document_generator.py` with the template engine:
   - `DocumentGenerator` class:
     - `generate_document(template_id, case_id, user) -> GeneratedDocument`
     - Loads template from `DocumentTemplate` table
     - Collects case data: case_number, police_station, IO details, date, accused details, complainant details
     - Substitutes `{{placeholder}}` tokens using Jinja2
     - Returns generated text with list of auto-filled fields
   - `export_docx(generated_doc_id) -> bytes` — Generates .docx using python-docx with professional formatting
   - `export_pdf(generated_doc_id) -> bytes` — Generates PDF using reportlab
   - Missing field detection: if a placeholder has no data, flag it in response: `{"missing_fields": ["accused_name", "date_of_arrest"]}`

2. Seed document templates in `DocumentTemplate` table:
   - **FSL Communications** (3 templates):
     - FSL Forwarding Letter: `{{case_number}}`, `{{police_station}}`, `{{io_name}}`, `{{io_rank}}`, `{{date}}`, `{{accused_name}}`, `{{evidence_description}}`, `{{fsl_lab_name}}`
     - Sample Forwarding Memo
     - FSL Reminder Letter
   - **Evidence Certificates** (2 templates):
     - Section 63 BSA / 65B Certificate: `{{case_number}}`, `{{document_description}}`, `{{hash_value}}`, `{{io_name}}`, `{{date}}`
     - Hash Value Declaration
   - **Legal Notices** (4 templates):
     - Bank Account Information Request
     - Bank Account Freeze Request
     - ISP Data Request
     - CDR Requisition
   - **Legal Drafts** (4 templates):
     - Arrest Memo: `{{accused_name}}`, `{{date_time_arrest}}`, `{{place_arrest}}`, `{{io_name}}`, `{{witnesses}}`
     - Seizure Memo
     - Remand Note
     - Confession Recording Template

3. Create document generation API endpoints:
   - `GET /api/v1/templates` — List available templates by category
   - `GET /api/v1/templates/{id}` — Get template detail with placeholders
   - `POST /api/v1/cases/{case_id}/documents/generate` — Body: `{template_id}`. Returns generated document with auto-filled fields highlighted.
   - `PUT /api/v1/generated-documents/{id}` — Save IO edits to generated content
   - `GET /api/v1/generated-documents/{id}/export?format=docx` — Download as DOCX
   - `GET /api/v1/generated-documents/{id}/export?format=pdf` — Download as PDF

4. Create document generation UI in `index.html`:
   - In case detail view, "Generated Docs" tab:
     - "Generate Document" button → opens template selector modal
     - Template selector: 4 category tabs (FSL, Evidence, Legal Notices, Legal Drafts) with template cards
     - Generated document editor:
       - Rendered document with auto-filled fields highlighted in blue
       - All fields are editable (contenteditable or textarea)
       - Missing fields highlighted in yellow with prompt message
       - Save button, Export DOCX button, Export PDF button
     - List of previously generated documents with status (Draft/Final/Signed)

5. Write tests in `tests/test_document_generator.py`:
   - Template loading and placeholder extraction
   - Auto-fill from case data
   - Missing field detection
   - DOCX export produces valid file
   - PDF export produces valid file
   - IO edit and save workflow
   - Template seeding validation

**Files to create/modify:**
- `document_generator.py` — NEW: Template engine, DOCX/PDF export (~350 lines)
- `api_v1.py` — Add template and document generation endpoints
- `index.html` — Add document generation UI in case detail view
- `tests/test_document_generator.py` — NEW: Document generation tests

**Acceptance criteria:**
- `GET /api/v1/templates` returns 13 templates across 4 categories
- `POST /api/v1/cases/{id}/documents/generate` produces document with case data auto-filled
- Missing placeholder fields are flagged in response
- DOCX export produces downloadable .docx file with correct content
- PDF export produces downloadable .pdf file
- IO can edit generated content and save changes
- Previously generated documents are listed in case view
- Tests pass: `python -m pytest tests/test_document_generator.py`

---

## Phase 7: OCR Enhancements & PWA
**Dependencies:** Phase 1

**Description:**
Enhance the existing OCR/translation engine with Urdu language support, per-segment confidence tagging, three-pane view, and PWA offline capabilities (BRD Module 7, FR-011 + FR-012).

**Tasks:**
1. Add Urdu language support in `complaint_parsing.py`:
   - Update `_detect_language()` to recognize Urdu script (Unicode range U+0600-U+06FF Arabic/Urdu block)
   - Add Urdu-specific OCR noise cleanup patterns in `_clean_ocr_noise()`
   - Add Urdu to translation provider configuration
   - Update language detection confidence scoring for Urdu
   - Note: Self-hosted OCR/translation models (TrOCR, IndicTrans2) are Phase 4 architecture work; this phase adds Urdu support using existing cloud providers.

2. Implement per-segment confidence tagging:
   - Modify `parse_document()` output to include segment-level confidence:
     ```python
     "segments": [
       {"text": "...", "confidence": "High|Medium|Low", "source": "ocr", "char_start": 0, "char_end": 150},
       ...
     ]
     ```
   - Each OCR segment gets its own confidence tag based on character recognition quality
   - Low-confidence segments flagged for mandatory IO review

3. Add low-confidence acknowledgement workflow:
   - New field in API response: `requires_acknowledgement: bool`
   - New endpoint: `POST /api/v1/cases/{case_id}/documents/{doc_id}/acknowledge-ocr` — IO confirms low-confidence segments
   - Until acknowledged, document cannot be used in AI analysis

4. Update frontend three-pane OCR view in `index.html`:
   - When viewing an OCR-processed document, show three simultaneous panes:
     - Left: Original scanned image/PDF (existing `#pdfPreview`)
     - Center: Extracted text with confidence highlighting (yellow for Low, no highlight for High)
     - Right: English translation
   - Low-confidence segments have "Review Required" badge and click-to-acknowledge button
   - Persist the three-pane layout using CSS Grid

5. Create PWA infrastructure:
   - `manifest.json` at project root:
     - name: "HCP Investigation Quality Workbench"
     - short_name: "IQW"
     - start_url: "/"
     - display: "standalone"
     - theme_color and background_color matching current theme
     - icons: generate placeholder icons (192x192, 512x512)
   - `sw.js` (service worker) at project root:
     - Cache-first strategy for static assets (index.html, manifest.json, icons)
     - Network-first for API calls
     - Offline fallback page
   - Register service worker in `index.html` `<script>` section
   - Serve manifest.json and sw.js from FastAPI static routes in `app.py`

6. Implement IndexedDB offline document queue:
   - In `index.html` JavaScript:
     - `OfflineQueue` class using IndexedDB:
       - `enqueue(file, document_type, case_id)` — Store file in IndexedDB with metadata
       - `getQueue()` — Return all queued items with status
       - `sync()` — Upload all queued files when online
       - `removeItem(id)` — Remove from queue after successful upload
     - Online/offline detection: `navigator.onLine` + `online`/`offline` events
     - Auto-sync on reconnect
     - Queue UI panel (visible when offline items exist):
       - File name, size, timestamp, status (Queued/Syncing/Synced/Failed)
       - Manual retry button for failed items
       - Progress bar during sync

7. Update `app.py` to serve PWA files:
   - `GET /manifest.json` — Serve PWA manifest
   - `GET /sw.js` — Serve service worker with correct `Service-Worker-Allowed` header

8. Write tests in `tests/test_ocr_enhancements.py`:
   - Urdu language detection
   - Per-segment confidence tagging
   - Acknowledgement workflow API
   - PWA manifest validity (JSON structure)
   - Service worker registration (file exists and is served)

**Files to create/modify:**
- `complaint_parsing.py` — Add Urdu detection, per-segment confidence (careful: minimal changes to preserve existing logic)
- `manifest.json` — NEW: PWA manifest
- `sw.js` — NEW: Service worker (~100 lines)
- `app.py` — Add routes to serve manifest.json and sw.js
- `api_v1.py` — Add OCR acknowledgement endpoint
- `index.html` — Three-pane view, offline queue UI, service worker registration, PWA meta tags
- `tests/test_ocr_enhancements.py` — NEW: OCR enhancement tests

**Acceptance criteria:**
- Urdu text detected correctly by `_detect_language()`
- Parse output includes segment-level confidence tags
- Low-confidence segments require IO acknowledgement before AI analysis
- Three-pane OCR view shows original, extracted text, and translation simultaneously
- PWA manifest served correctly, app installable in Chrome
- Service worker caches static assets and provides offline fallback
- Offline queue stores documents in IndexedDB and syncs when reconnected
- Tests pass: `python -m pytest tests/test_ocr_enhancements.py`

---

## Phase 8: Integration Testing & Verification
**Dependencies:** Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7

**Description:**
End-to-end integration testing across all Phase 1 features. Verify the complete workflow: login -> create case -> upload documents -> run quality check -> generate documents -> verify integrity. Also verify backward compatibility with existing complaint parser.

**Tasks:**
1. Create `tests/test_integration.py` with end-to-end scenarios:
   - **Scenario 1: Full case lifecycle**
     - Login as IO via JWT
     - Create case with Crime No.
     - Tag offence type
     - Upload complaint document (compute SHA-256)
     - Run quality check on document
     - Generate FIR draft from template
     - Export as DOCX
     - Verify timeline shows all activities
     - Verify action tracker has statutory deadlines
   - **Scenario 2: RBAC enforcement**
     - Clerk cannot create cases
     - IO cannot access admin endpoints
     - System_Admin can manage users
     - AI_Admin can access quality checks
   - **Scenario 3: Audit trail completeness**
     - Every action in Scenario 1 produced an audit log entry
     - Audit logs are searchable by case_id
   - **Scenario 4: Backward compatibility**
     - Existing `/api/auth/login` still works with session cookies
     - Existing `/api/parse` still works (single file, no case context)
     - Existing `/api/history` still returns parse_records
     - Existing `/api/health` still reports system status
   - **Scenario 5: Document integrity**
     - Upload document, verify SHA-256 stored
     - Run integrity check, verify passes
     - (Simulate) tamper with stored bytes, verify integrity check fails

2. Run build verification:
   - `pip install -r requirements.txt` succeeds
   - `python -m pytest` — all tests pass
   - `docker build -t iqw-phase1 .` — Docker build succeeds (update Dockerfile to copy new files)
   - Application starts without errors: `uvicorn app:app --port 8080`

3. Update `Dockerfile` to include new files:
   - Add COPY commands for: models.py, auth.py, audit.py, cases.py, quality_engine.py, document_generator.py, api_v1.py, manifest.json, sw.js

4. Verify database initialization:
   - All 18 tables created on startup
   - Seed data loaded (offence types, default checklists, document templates, initial admin user)
   - Existing parse_records table untouched

5. Performance smoke test:
   - Health endpoint responds in <500ms
   - Case creation responds in <500ms
   - Quality check responds in <10s (BRD target)
   - Document generation responds in <2s

**Files to create/modify:**
- `tests/test_integration.py` — NEW: E2E integration tests (~300 lines)
- `Dockerfile` — Add COPY commands for new files
- Verify all existing test files still pass

**Acceptance criteria:**
- All 5 integration scenarios pass
- All existing tests still pass (backward compatibility)
- Docker build succeeds
- Application starts and serves all endpoints
- Database initialization creates all tables + seed data
- Performance targets met for key endpoints
- Zero regressions in existing complaint parsing functionality
