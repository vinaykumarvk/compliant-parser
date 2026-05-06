# BRD Coverage Audit: HCP IQW BRD v1

BRD: `docs/HCP_IQW_BRD_v1.docx`  
Audit date: 2026-05-04  
Scope: `full` (`Phases 0-6`)  
Verdict: `AT-RISK`

## Phase 0 - Preflight

### BRD File

- Source file exists: `docs/HCP_IQW_BRD_v1.docx`
- Size: `53,539 bytes`
- Extracted text length: `1,894` lines via `textutil`
- Functional requirements found: `20` (`FR-001` through `FR-020`)
- Auditable functional line items extracted: `121`
  - Acceptance Criteria: `102`
  - Business Rules: `17`
  - Edge Cases: `2`
  - Failure Handling: `0` explicitly labeled; failure behavior is included where the BRD wrote it as AC/EC text.

### Project Structure

Auto-discovered structure is a flat Python/FastAPI service rather than a nested `routes/services/components` layout.

- Root source modules: `app.py`, `api_v1.py`, `auth.py`, `audit.py`, `cases.py`, `models.py`, `database.py`, `quality_engine.py`, `document_generator.py`, `ocr_enhancements.py`, `complaint_parsing.py`, `index.html`, `manifest.json`, `sw.js`
- Tests: `tests/`
- Existing review docs: `docs/reviews/`
- Monorepo: none detected. No `package.json`, workspaces, `services/*`, `apps/*`, or `packages/*`.

### Tech Stack

- Backend: Python, FastAPI, Uvicorn
- Data: SQLAlchemy async, PostgreSQL/Cloud SQL, asyncpg
- Auth: JWT via PyJWT, bcrypt via passlib, legacy Starlette session auth
- UI: single-file vanilla JS/CSS HTML app
- OCR/AI: Google Document AI, translation providers, complaint parser heuristics, optional LLM extraction
- Document generation: Jinja2, python-docx, ReportLab
- Tests: pytest running unittest-style tests under `tests/`

### Git State

- Branch: `main...origin/main [ahead 5]`
- Commit: `8dfa690`
- Existing untracked paths before this audit included `.claude/`, `.codex/`, `PROJECT_SUMMARY.md`, `complaints/`, and `docs/`.

### Verification

- Initial `python -m pytest -q` failed before collection due to a broken auto-loaded external `pytest_recording`/OpenSSL plugin in the active Python 3.9 environment.
- Verified with plugin autoload disabled:
  - Command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
  - Result: `284 passed, 381 warnings in 12.82s`
  - Notable warning: `JWT_SECRET_KEY not set` falls back to insecure development default.

## Evidence Anchors

The traceability matrix cites these anchors. Each anchor contains exact file/line evidence used by multiple rows.

| Anchor | Evidence |
|---|---|
| `E_CASE_NUM` | `cases.py:63`, `cases.py:122`, `cases.py:141`, `api_v1.py:441`, `index.html:4067`, `index.html:8693`, `tests/test_cases.py:43` |
| `E_CASE_LIST` | `cases.py:159`, `api_v1.py:453`, `index.html:8339`, `tests/test_cases.py:101` |
| `E_CASE_UPDATE` | `cases.py:198`, `api_v1.py:493`, `index.html:8636`, `tests/test_cases.py:115` |
| `E_DOC_UPLOAD` | `app.py:43`, `app.py:508`, `api_v1.py:518`, `cases.py:253`, `audit.py:35`, `index.html:8497`, `tests/test_cases.py:166` |
| `E_TIMELINE` | `cases.py:311`, `cases.py:335`, `api_v1.py:563`, `index.html:8543`, `tests/test_cases.py:207` |
| `E_TASK` | `cases.py:350`, `cases.py:385`, `cases.py:430`, `api_v1.py:574`, `index.html:8564`, `tests/test_cases.py:227` |
| `E_QUALITY` | `quality_engine.py:39`, `quality_engine.py:356`, `api_v1.py:667`, `index.html:8784`, `tests/test_quality_engine.py:97` |
| `E_BNS` | `complaint_parsing.py:4166`, `complaint_parsing.py:4224`, `complaint_parsing.py:4693`, `complaint_parsing.py:4777`, `tests/test_complaint_parsing.py:763` |
| `E_MODELS` | `models.py:381`, `models.py:460`, `models.py:548`, `models.py:626`, `models.py:687`, `models.py:726`, `models.py:808`, `models.py:842`, `models.py:886`, `models.py:931`, `models.py:965`, `models.py:988`, `models.py:1026`, `tests/test_models.py:216` |
| `E_DOCGEN` | `document_generator.py:93`, `document_generator.py:480`, `document_generator.py:558`, `document_generator.py:640`, `api_v1.py:697`, `api_v1.py:725`, `api_v1.py:745`, `api_v1.py:759`, `index.html:8903`, `tests/test_document_generator.py:25` |
| `E_OCR` | `ocr_enhancements.py:61`, `ocr_enhancements.py:84`, `ocr_enhancements.py:110`, `ocr_enhancements.py:150`, `ocr_enhancements.py:193`, `app.py:508`, `index.html:5205`, `tests/test_ocr_enhancements.py:44` |
| `E_PWA` | `app.py:389`, `app.py:400`, `manifest.json:1`, `sw.js:1`, `index.html:8131` |
| `E_AUTH` | `auth.py:29`, `auth.py:64`, `auth.py:80`, `auth.py:129`, `auth.py:161`, `auth.py:195`, `api_v1.py:275`, `api_v1.py:308`, `api_v1.py:325`, `api_v1.py:335`, `index.html:4934`, `tests/test_auth.py:28` |
| `E_AUDIT` | `audit.py:64`, `audit.py:102`, `audit.py:170`, `audit.py:222`, `api_v1.py:383`, `api_v1.py:411`, `app.py:359`, `tests/test_audit.py:48` |
| `E_INTEGRITY` | `audit.py:35`, `cases.py:266`, `api_v1.py:426`, `tests/test_audit.py:25`, `tests/test_integration.py:374` |
| `E_API` | `api_v1.py:53`, `api_v1.py:103`, `api_v1.py:258`, `api_v1.py:814` |
| `E_INFRA` | `database.py:47`, `database.py:126`, `database.py:133`, `Dockerfile:1`, `Dockerfile:46` |

Search discipline for `NOT_FOUND`: keyword, entity, and semantic searches were run across the discovered source layers and tests, including `rg` searches for `CCTNS`, `retry`, `IndexedDB`, `section-recommendation`, `congruence`, `DSC`, `HRMS`, `analytics`, `judgment`, `rollback`, `staging`, `promote`, `Verify Integrity`, and related synonyms.

## Phase 1 - Requirement Inventory

| Priority | FRs |
|---|---|
| `P0` | Phase 1/core launch or cross-cutting controls: `FR-001` to `FR-006`, `FR-010` to `FR-012`, `FR-017`, `FR-019`, `FR-020` |
| `P1` | Phase 2 AI-intensive modules: `FR-007` to `FR-009`, `FR-013`, `FR-014` |
| `P2` | Phase 3 analytics/continuous learning/signing: `FR-015`, `FR-016`, `FR-018` |

## Phase 2/3/4 - Functional Traceability and Flat Gap List

Legend:

- Gap categories: `A=Unimplemented`, `B=Stubbed`, `C=Partial`, `D=Implemented but untested`, `E=UI-only`
- Gap format: `{category}/{size}`. `-` means `DONE + TESTED`.
- Test verdicts: `TESTED`, `INDIRECT`, `TC_ONLY`, `UNTESTED`

| Item | Pri | Requirement summary | Code verdict | Evidence or searched terms | Test | Gap |
|---|---:|---|---|---|---|---|
| AC-001-1 | P0 | Enter Crime No. `NNNN/YYYY` or Petition No. `PET/PS/YYYY/NNNN` | PARTIAL | `E_CASE_NUM`; UI petition example differs from BRD | TESTED | C/S |
| AC-001-2 | P0 | Reject invalid case number with exact BRD error | PARTIAL | `E_CASE_NUM`; backend validates but message differs | TESTED | C/XS |
| AC-001-3 | P0 | Initiate CCTNS sync and display status | PARTIAL | `E_CASE_NUM`; status defaults to `Pending`, no sync service | INDIRECT | C/M |
| AC-001-4 | P0 | On CCTNS failure create locally with Failed status and retry button | NOT_FOUND | searched: `CCTNS`, `retry`, `Failed`, `sync queue` | UNTESTED | A/M |
| BR-001-1 | P0 | Crime number unique within police station/year | NOT_FOUND | searched: `crime_no unique`, `police_station year`, `CONFLICT` | UNTESTED | A/S |
| BR-001-2 | P0 | CCTNS retries 3 times at 30-second intervals | NOT_FOUND | searched: `CCTNS`, `retry`, `30`, `attempt` | UNTESTED | A/M |
| EC-001-1 | P0 | Duplicate crime number exact error | NOT_FOUND | searched: `already exists`, `duplicate crime`, `crime_no` | UNTESTED | A/S |
| EC-001-2 | P0 | CCTNS unavailable queues sync retry | NOT_FOUND | searched: `unavailable`, `sync queued`, `CCTNS` | UNTESTED | A/M |
| AC-002-1 | P0 | Searchable offence dropdown mapped to BNS/IPC | PARTIAL | `E_CASE_NUM`, `E_CASE_LIST`; seeded offence list/datalist only | TESTED | C/S |
| AC-002-2 | P0 | One primary and optional secondary offence types | PARTIAL | `E_MODELS`, `E_CASE_UPDATE`; model has secondary IDs, UI/API do not expose full flow | INDIRECT | C/S |
| AC-002-3 | P0 | Display selected offence type on case dashboard header | PARTIAL | `index.html:8465`; shown in detail grid, not header | UNTESTED | C/XS |
| AC-002-4 | P0 | IO can modify offence type during investigation | PARTIAL | `E_CASE_UPDATE`; update path exists, UI sends primary field | INDIRECT | C/S |
| AC-003-1 | P0 | Drag/drop accepts up to 20 files | NOT_FOUND | searched: `multiple`, `20`, `bulk`, `files[]` | UNTESTED | A/M |
| AC-003-2 | P0 | Supported PDF/JPEG/PNG/DOCX/TXT and unsupported type error | PARTIAL | `E_DOC_UPLOAD`; legacy parse validates many formats but no TXT, v1 upload lacks validation | TESTED | C/S |
| AC-003-3 | P0 | 50 MB per document with exact oversized error | PARTIAL | `app.py:96`, `app.py:530`; default is 15 MB and v1 upload lacks limit | UNTESTED | C/XS |
| AC-003-4 | P0 | SHA-256 computed and stored for each upload | DONE | `E_DOC_UPLOAD`, `E_INTEGRITY` | TESTED | - |
| AC-003-5 | P0 | Offline/low-connectivity queue and auto-upload | NOT_FOUND | searched: `IndexedDB`, `offline queue`, `sync status` | UNTESTED | A/L |
| BR-003-1 | P0 | Document type required before upload completes | PARTIAL | `api_v1.py:518`, `index.html:3899`; query param/select exist, no enum validation | INDIRECT | C/S |
| BR-003-2 | P0 | Offline queue shows progress and sync per file | NOT_FOUND | searched: `Queued`, `Syncing`, `IndexedDB`, `progress` | UNTESTED | A/L |
| AC-004-1 | P0 | Timeline reverse chronological default with oldest-first toggle | PARTIAL | `E_TIMELINE`; API supports sort, UI lacks visible toggle | TESTED | C/XS |
| AC-004-2 | P0 | Each entry has timestamp, action, user, description | DONE | `E_TIMELINE` | TESTED | - |
| AC-004-3 | P0 | Clicking entry navigates to detailed activity | PARTIAL | `cases.py:316`, `index.html:8543`; entity IDs stored, no click navigation | UNTESTED | C/S |
| AC-004-4 | P0 | Version history with diff view | NOT_FOUND | searched: `diff`, `version history`, `previous version`, `is_latest_version` | UNTESTED | A/M |
| AC-005-1 | P0 | Tasks sorted by due date | DONE | `E_TASK` | TESTED | - |
| AC-005-2 | P0 | Task fields: name, due, priority, status, source | PARTIAL | `E_TASK`; model/API include fields, UI omits source | TESTED | C/XS |
| AC-005-3 | P0 | Overdue tasks highlighted red | PARTIAL | `index.html:8572`; status rendered, no overdue computation | UNTESTED | C/S |
| AC-005-4 | P0 | Reminders at 3 days, 1 day, due date | NOT_FOUND | searched: `reminder`, `3 days`, `due tomorrow`, `scheduler` | UNTESTED | A/M |
| AC-005-5 | P0 | IO can complete tasks or snooze reminders | PARTIAL | `E_TASK`; complete/update exists, snooze field exists, no reminder snooze UI | TESTED | C/S |
| AC-006-1 | P0 | Select document/click quality check with processing indicator | DONE | `E_QUALITY` | TESTED | - |
| AC-006-2 | P0 | Missing elements with clickable source citations | PARTIAL | `E_QUALITY`; excerpts exist, not clickable persisted citations | TESTED | C/M |
| AC-006-3 | P0 | Weak areas with actionable suggestions | DONE | `E_QUALITY` | TESTED | - |
| AC-006-4 | P0 | Trial-risk indicators with High/Medium/Low | DONE | `E_QUALITY` | TESTED | - |
| AC-006-5 | P0 | Every finding has citation; uncited findings hidden | PARTIAL | `E_QUALITY`; missing findings intentionally have no excerpt and remain visible | TESTED | C/M |
| AC-006-6 | P0 | No separate audit report; IO-facing suggestions only | DONE | `E_QUALITY` | INDIRECT | D/XS |
| BR-006-1 | P0 | Checklist selected by document_type and offence_type from KB | PARTIAL | `E_QUALITY`, `E_MODELS`; document_type only, KB not used | TESTED | C/M |
| BR-006-2 | P0 | Generic checklist fallback plus exact note | PARTIAL | `quality_engine.py:97`; fallback exists, no note | UNTESTED | C/XS |
| BR-006-3 | P0 | p95 inference latency less than 10 seconds | NOT_FOUND | searched: `p95`, `latency`, `SLA`, `benchmark` | UNTESTED | A/S |
| AC-007-1 | P1 | Paste/upload complaint and click Recommend Sections | PARTIAL | `E_BNS`; parser upload suggests sections, no dedicated endpoint/button | INDIRECT | C/M |
| AC-007-2 | P1 | Primary sections with 0-1 confidence and reasoning | PARTIAL | `E_BNS`; confidence/rationale exist, not primary endpoint schema | TESTED | C/M |
| AC-007-3 | P1 | Supporting factual ingredients found | PARTIAL | `E_BNS`; evidence snippets exist, no ingredient taxonomy | INDIRECT | C/M |
| AC-007-4 | P1 | Missing facts required to sustain section | NOT_FOUND | searched: `missing_ingredients`, `facts required`, `ingredient mapping` | UNTESTED | A/M |
| AC-007-5 | P1 | Alternative sections with confidence and reasoning | PARTIAL | `E_BNS`; `fit=related` exists, no `alternative_sections` flow | INDIRECT | C/S |
| AC-007-6 | P1 | Mandatory exact legal disclaimer | PARTIAL | `complaint_parsing.py:4777`; disclaimer differs from BRD text | UNTESTED | C/XS |
| BR-007-1 | P1 | Hide confidence below 0.30 unless Show all | NOT_FOUND | searched: `Show all`, `0.30`, `threshold`, `hide` | UNTESTED | A/S |
| BR-007-2 | P1 | Fine-tuned self-hosted Llama/Mistral models | NOT_FOUND | searched: `llama`, `mistral`, `self-hosted`, `model server` | UNTESTED | A/L |
| AC-008-1 | P1 | Supported comparison pairs | NOT_FOUND | searched: `Petition vs FIR`, `Medical_Report`, `comparison pairs` | UNTESTED | A/L |
| AC-008-2 | P1 | Conflict type, severity, description, dual excerpts | STUB | `E_MODELS`; `CongruenceAlert` schema only | TC_ONLY | B/L |
| AC-008-3 | P1 | Dismiss false positives with reason code/notes | STUB | `E_MODELS`; fields exist, no API/UI workflow | TC_ONLY | B/M |
| AC-008-4 | P1 | Dismissals feed model refinement | STUB | `models.py:664`; boolean field only | TC_ONLY | B/M |
| AC-008-5 | P1 | Missing carry-forward facts flagged separately | STUB | `models.py:133`; enum exists, no engine | TC_ONLY | B/L |
| BR-008-1 | P1 | Congruence auto-runs after related upload | NOT_FOUND | searched: `auto`, `new document`, `congruence`, `background` | UNTESTED | A/L |
| BR-008-2 | P1 | In-app notification for new congruence alerts | NOT_FOUND | searched: `congruence notification`, `alert generated` | UNTESTED | A/M |
| AC-009-1 | P1 | Auto-detect offence and confirm before plan | STUB | `E_MODELS`; plan model only | TC_ONLY | B/L |
| AC-009-2 | P1 | Numbered steps with legal citations | STUB | `models.py:818`; JSON field only | TC_ONLY | B/L |
| AC-009-3 | P1 | Evidence to collect with forensic requirements | STUB | `models.py:821`; JSON field only | TC_ONLY | B/L |
| AC-009-4 | P1 | Documents to generate identified | STUB | `models.py:824`; JSON field only | TC_ONLY | B/M |
| AC-009-5 | P1 | Statutory deadlines calendar/countdowns | STUB | `models.py:827`, `E_TASK`; no plan calendar UI | TC_ONLY | B/M |
| AC-009-6 | P1 | Plan editable by IO | STUB | `models.py:830`; no plan API/UI | TC_ONLY | B/M |
| AC-009-7 | P1 | Completion checkbox for each task | STUB | `E_TASK`; task checkbox exists outside plan module | TC_ONLY | B/M |
| AC-010-1 | P0 | Select doc type and auto-populate template from case data | PARTIAL | `E_DOCGEN`; manual case_data is passed, no automatic ORM case fill | TESTED | C/M |
| AC-010-2 | P0 | Auto-filled fields highlighted and editable | PARTIAL | `E_DOCGEN`; missing fields highlighted, editable preview exists | TESTED | C/S |
| AC-010-3 | P0 | Export DOCX and PDF | DONE | `E_DOCGEN` | TESTED | - |
| AC-010-4 | P0 | Apply DSC digital signature in platform | NOT_FOUND | searched: `DSC`, `Sign Document`, `PKCS#11`, `Web Crypto` | UNTESTED | A/L |
| AC-010-5 | P0 | Missing case data exact prompt/list | PARTIAL | `E_DOCGEN`; missing placeholders returned/highlighted, no exact prompt | TESTED | C/S |
| BR-010-1 | P0 | FSL communication templates | DONE | `document_generator.py:102` | TESTED | - |
| BR-010-2 | P0 | Evidence certificates | DONE | `document_generator.py:173` | TESTED | - |
| BR-010-3 | P0 | Legal notices incl. platform requests | PARTIAL | `document_generator.py:228`; no Google/Meta platform request templates | TESTED | C/S |
| BR-010-4 | P0 | Legal drafts: arrest/seizure/remand/confession | DONE | `document_generator.py:332` | TESTED | - |
| AC-011-1 | P0 | Upload scanned/photo document and detect language | PARTIAL | `E_OCR`; language utilities and image upload exist | TESTED | C/M |
| AC-011-2 | P0 | Extracted text side-by-side with original image | PARTIAL | `E_OCR`; preview and result views exist, not strict side-by-side for OCR text | UNTESTED | C/M |
| AC-011-3 | P0 | English translation in third pane | PARTIAL | `index.html:5205`; translation tab exists, not simultaneous third pane | UNTESTED | C/M |
| AC-011-4 | P0 | Segment confidence High/Medium/Low with manual review flag | PARTIAL | `E_OCR`; utility/ack endpoint exists, not integrated into case save UI | TESTED | C/M |
| AC-011-5 | P0 | OCR p95 less than 5 seconds per page | NOT_FOUND | searched: `p95`, `latency`, `OCR`, `benchmark` | UNTESTED | A/S |
| BR-011-1 | P0 | Low-confidence segments highlighted and acknowledged before save | PARTIAL | `E_OCR`; acknowledge utility exists, no visible save gate/highlight | TESTED | C/M |
| BR-011-2 | P0 | Self-hosted TrOCR/Donut, Gemini fallback only with approval | NOT_FOUND | searched: `TrOCR`, `Donut`, `Gemini approval`, `self-hosted` | UNTESTED | A/L |
| AC-012-1 | P0 | PWA installable on desktop/mobile | PARTIAL | `E_PWA`; manifest/service worker exist, icon assets not present in repo | UNTESTED | C/S |
| AC-012-2 | P0 | Offline uploads stored in IndexedDB | NOT_FOUND | searched: `indexedDB`, `IndexedDB`, `local queue` | UNTESTED | A/L |
| AC-012-3 | P0 | Offline queue shows file name/size/time/status | NOT_FOUND | searched: `Queued`, `Syncing`, `Synced`, `Failed`, `offline queue` | UNTESTED | A/L |
| AC-012-4 | P0 | Queued docs auto-sync on connectivity restored | NOT_FOUND | searched: `online`, `sync`, `background sync`, `queue` | UNTESTED | A/L |
| AC-012-5 | P0 | Failed sync reason plus manual retry | NOT_FOUND | searched: `manual retry`, `sync failed`, `error reason` | UNTESTED | A/M |
| AC-013-1 | P1 | Low-confidence AI outputs auto-flagged | STUB | `E_MODELS`; `has_uncertainty_flag` exists, no flagging service | TC_ONLY | B/M |
| AC-013-2 | P1 | Flag item includes tag/output/source/model/prompt | STUB | `E_MODELS`; fields exist on analysis model | TC_ONLY | B/M |
| AC-013-3 | P1 | Dedicated AI Admin queue sorted by severity | NOT_FOUND | searched: `admin queue`, `uncertainty`, `severity`, `AI Admin` | UNTESTED | A/M |
| AC-013-4 | P1 | AI Admin corrections update KB | NOT_FOUND | searched: `correction`, `rationale`, `knowledge base update` | UNTESTED | A/M |
| AC-014-1 | P1 | AI Admin creates checklist/SOP Draft | STUB | `E_MODELS`; KB model/status only | TC_ONLY | B/M |
| AC-014-2 | P1 | Promote entry to Staging | STUB | `E_MODELS`; status enum only | TC_ONLY | B/M |
| AC-014-3 | P1 | Run validation tests against staging | NOT_FOUND | searched: `staging validation`, `test prompts`, `KB validation` | UNTESTED | A/M |
| AC-014-4 | P1 | Promote validated entry to Production | STUB | `models.py:907`; promoted fields only | TC_ONLY | B/M |
| AC-014-5 | P1 | Version number, change description, timestamp | STUB | `models.py:899`, `models.py:913`; no change description workflow | TC_ONLY | B/S |
| AC-014-6 | P1 | Roll back production entry, immediate and audited | STUB | `models.py:913`; previous version field only | TC_ONLY | B/M |
| AC-015-1 | P2 | Upload judgment PDF/TXT max 50 MB | NOT_FOUND | searched: `judgment upload`, `JudgmentAnalysis`, `court judgment` | UNTESTED | A/M |
| AC-015-2 | P2 | Extract facts/issues/verdict/lapses/evidence observations | STUB | `E_MODELS`; fields only | TC_ONLY | B/L |
| AC-015-3 | P2 | Investigation lessons summary | STUB | `models.py:859`; field only | TC_ONLY | B/M |
| AC-015-4 | P2 | Avoidable errors summary | STUB | `models.py:862`; field only | TC_ONLY | B/M |
| AC-015-5 | P2 | Checklist update proposals require AI Admin approval | STUB | `models.py:863`, `models.py:866`; fields only | TC_ONLY | B/M |
| AC-015-6 | P2 | Approved findings feed checklist/SOP/training | NOT_FOUND | searched: `approved findings`, `training loop`, `checklist engine` | UNTESTED | A/L |
| AC-016-1 | P2 | Dashboard totals for cases/docs/AI checks/docs generated | NOT_FOUND | searched: `analytics_router`, `UsageEvent`, `dashboard totals` | UNTESTED | A/M |
| AC-016-2 | P2 | Average time per case/activity | NOT_FOUND | searched: `time spent`, `duration`, `UsageEvent`, `latency aggregation` | UNTESTED | A/M |
| AC-016-3 | P2 | Feature usage frequency chart | NOT_FOUND | searched: `feature usage`, `chart`, `usage_events` | UNTESTED | A/M |
| AC-016-4 | P2 | Filter reports by date/station/IO | NOT_FOUND | searched: `analytics filters`, `date range`, `police_station`, `IO` | UNTESTED | A/M |
| AC-016-5 | P2 | Monthly trend PDF export | NOT_FOUND | searched: `monthly trend`, `PDF report`, `analytics export` | UNTESTED | A/M |
| AC-016-6 | P2 | IO own usage only; Admins all data | PARTIAL | `auth.py:170`; permissions exist, no analytics route | INDIRECT | C/M |
| AC-017-1 | P0 | Login accepts Employee ID and password | DONE | `E_AUTH` | TESTED | - |
| AC-017-2 | P0 | Auth request sent to HRMS REST/LDAP | NOT_FOUND | searched: `HRMS`, `LDAP`, `employee sync`, `REST API` | UNTESTED | A/L |
| AC-017-3 | P0 | Successful auth syncs name/rank/posting/role from HRMS | PARTIAL | `E_AUTH`; local user profile only | INDIRECT | C/M |
| AC-017-4 | P0 | Failed login exact invalid message | PARTIAL | `api_v1.py:286`; wording differs | UNTESTED | C/XS |
| AC-017-5 | P0 | Lock after 5 attempts for 30 minutes with exact message | PARTIAL | `E_AUTH`; lockout exists, status/message differ | TESTED | C/S |
| AC-018-1 | P2 | Sign Document button on all generated docs | NOT_FOUND | searched: `Sign Document`, `DSC`, `signature` | UNTESTED | A/S |
| AC-018-2 | P2 | DSC token detection and PIN prompt | NOT_FOUND | searched: `PKCS`, `Web Crypto`, `PIN`, `token detection` | UNTESTED | A/L |
| AC-018-3 | P2 | Signed status records signer/timestamp/certificate details | STUB | `models.py:748`, `models.py:753`; no certificate details | TC_ONLY | B/M |
| AC-018-4 | P2 | Missing DSC token exact error | NOT_FOUND | searched: `Digital Signature Certificate not detected`, `DSC token` | UNTESTED | A/S |
| AC-018-5 | P2 | Signed docs read-only | NOT_FOUND | searched: `read-only`, `Signed`, `contentEditable`, `signature_status` | UNTESTED | A/M |
| AC-019-1 | P0 | Every AuditLog enum action recorded automatically | PARTIAL | `E_AUDIT`; mutating v1 requests logged, broad action mapping and GET skipped | TESTED | C/M |
| AC-019-2 | P0 | Audit logs cannot be edited/deleted | DONE | `E_AUDIT`; no update/delete functions/endpoints | TESTED | - |
| AC-019-3 | P0 | Log entry has user/action/entity/timestamp/IP/session ID | PARTIAL | `E_AUDIT`; session_id optional and not populated by middleware | TESTED | C/S |
| AC-019-4 | P0 | Search by date/user/action/entity | DONE | `E_AUDIT` | TESTED | - |
| AC-019-5 | P0 | Retain audit logs for 7 years | NOT_FOUND | searched: `retention`, `7 years`, `partition`, `lifecycle` | UNTESTED | A/M |
| AC-020-1 | P0 | SHA-256 computed on upload and stored | DONE | `E_INTEGRITY` | TESTED | - |
| AC-020-2 | P0 | Verify Integrity button recomputes and compares hash | STUB | `api_v1.py:426`; endpoint returns hard-coded verified true, no UI button | INDIRECT | B/S |
| AC-020-3 | P0 | Matching hashes exact success message | PARTIAL | `api_v1.py:432`; generic success, no recompute | INDIRECT | C/S |
| AC-020-4 | P0 | Hash mismatch warning and Sys Admin alert | NOT_FOUND | searched: `integrity failed`, `System_Admin`, `tamper`, `notification` | UNTESTED | A/S |

## Phase 5 - Constraint and NFR Audit

| Requirement | Verdict | Evidence or searched terms | Gap |
|---|---|---|---|
| On-premise sensitive data boundary | NOT_FOUND | `PROJECT_SUMMARY.md:161` documents Cloud Run/Cloud SQL; current code integrates cloud Document AI/translation | A/XL |
| Self-hosted AI models; cloud APIs only with approval | NOT_FOUND | `requirements.txt:5`, `requirements.txt:7`, `complaint_parsing.py` provider references; no approval gate | A/XL |
| 100 concurrent users scalable | PARTIAL | `Dockerfile:49` workers configurable, DB pool in `database.py:47`; no load test | C/M |
| RTO <= 1 hour | NOT_FOUND | searched: `RTO`, `recovery`, `restore` | A/L |
| RPO <= 15 minutes | NOT_FOUND | searched: `RPO`, `backup`, `point in time` | A/L |
| OCR p95 < 5s | NOT_FOUND | searched: `p95`, `OCR latency`, `benchmark` | A/S |
| LLM p95 < 10s | NOT_FOUND | searched: `p95`, `LLM latency`, `benchmark` | A/S |
| Non-AI API p95 < 500ms | NOT_FOUND | searched: `load test`, `latency`, `p95` | A/S |
| Uptime 99.5% | NOT_FOUND | searched: `SLO`, `availability`, `uptime` | A/M |
| Continuous/daily/immutable backups | NOT_FOUND | searched: `backup`, `immutable`, `daily full` | A/L |
| Quarterly DR drills | NOT_FOUND | searched: `DR`, `failover drill`, `disaster` | A/M |
| AES-256 data at rest | NOT_FOUND | no app/infrastructure config proving database/object/backups encryption | A/M |
| TLS 1.3 data in transit | PARTIAL | Cloud deployment likely terminates TLS, but app has no TLS 1.3 enforcement; inference only | C/M |
| HSM/equivalent key management | NOT_FOUND | searched: `HSM`, `KMS`, `key rotation` | A/L |
| RBAC with attribute-based policies | PARTIAL | `E_AUTH`; role permissions exist, no ABAC policy layer | C/M |
| AI failed inference < 1% | NOT_FOUND | searched: `error rate`, `inference failure`, `metrics` | A/M |
| AI fallback < 5% | NOT_FOUND | translation fallback exists in parser, but no metric/threshold | A/M |
| GPU utilization < 80% | NOT_FOUND | no self-hosted GPU service or metric | A/L |
| Hallucination rate 0% | PARTIAL | `E_QUALITY`, `E_BNS`; excerpts/evidence used in places, no universal enforcement | C/L |
| Browser support Chrome/Firefox/Edge 100+ | NOT_FOUND | no compatibility tests or browser matrix | A/S |
| WCAG 2.1 AA | PARTIAL | `index.html` has ARIA/skip link patterns, but no WCAG audit/test | C/M |

## UI/API/Integration Audit

| Area | Verdict | Evidence | Gap |
|---|---|---|---|
| 6.1 Case dashboard | PARTIAL | `index.html:3873`, `index.html:8465`; no CCTNS bottom bar, no full sidebar modules | C/M |
| 6.2 Document viewer/annotation | PARTIAL | `index.html:3805`, `index.html:5205`; no AI overlay or true three-pane OCR layout | C/M |
| 6.3 AI Admin dashboard | NOT_FOUND | searched: `Uncertainty Review Queue`, `Knowledge Base Manager`, `Model Version Tracker` | A/L |
| 6.4 Analytics dashboard | NOT_FOUND | `api_v1.py:266` router exists only; no routes/UI | A/M |
| 6.5 Login screen | PARTIAL | `index.html:3501`, `api_v1.py:275`; branding/text differs, Employee ID label not primary login label | C/S |
| 7.1 JWT auth | PARTIAL | `E_AUTH`; refresh is 24h, access token default is 30m not 8h inactivity | C/S |
| 7.2 HRMS integration | NOT_FOUND | searched: `HRMS`, `LDAP` | A/L |
| 7.2 CCTNS integration | NOT_FOUND | searched: `CCTNS` | A/L |
| 7.2 DSC/eSign integration | NOT_FOUND | searched: `DSC`, `PKCS`, `Web Crypto` | A/L |
| 7.3 `POST /api/v1/cases` | DONE | `api_v1.py:441`, `cases.py:122` | - |
| 7.3 `POST /api/v1/cases/{case_id}/documents` | PARTIAL | `api_v1.py:518`; accepts upload but lacks BRD format/size validation and OCR trigger | C/M |
| 7.3 case-scoped quality endpoint | PARTIAL | `api_v1.py:667`; implemented as `/api/v1/analysis/quality-check`, not case-scoped path | C/S |
| 7.3 section recommendation endpoint | NOT_FOUND | searched: `/section-recommendation`, `Recommend Sections` | A/M |
| 7.4 standard error format | PARTIAL | `E_API`; format helper exists but not uniformly used by legacy endpoints | C/S |
| 7.5 rate limits | PARTIAL | `api_v1.py:103`; per-IP/path in-memory, no per-user limits or `Retry-After` header | C/S |

## Data Model Coverage

The ORM includes most BRD entity shells, which is useful foundation work, but many BRD validation rules, uniqueness constraints, immutable guarantees, and workflows are not enforced.

| BRD entity area | Verdict | Evidence | Primary gap |
|---|---|---|---|
| Core case/document/activity/action entities | PARTIAL | `E_MODELS`, `E_CASE_NUM`, `E_DOC_UPLOAD`, `E_TIMELINE`, `E_TASK` | Missing uniqueness, CCTNS, version diff, bulk/offline upload |
| AI analysis/citation/congruence/section entities | STUB | `E_MODELS` | Mostly data models without services/API/UI |
| Generated documents/templates | PARTIAL | `E_DOCGEN` | Good template/export base; missing case autofill and DSC |
| Investigation plan/judgment/KB/usage entities | STUB | `E_MODELS` | Data models only |
| Audit logs/notifications | PARTIAL | `E_AUDIT`, `E_TASK` | Audit search works; retention, full action coverage, and critical notifications incomplete |

## Phase 6 - Scorecard

```
LINE-ITEM COVERAGE
==================
Total auditable functional items: 121
  Acceptance Criteria (AC):      102
  Business Rules (BR):           17
  Edge Cases (EC):               2
  Failure Handling (FH):         0

Implementation verdicts:
  DONE:                          15
  PARTIAL:                       41
  STUB:                          24
  NOT_FOUND:                     41

Implementation Rate:
  DONE + PARTIAL:                56 / 121 = 46.3%

Automated Test Coverage:
  TESTED:                        35 / 121 = 28.9%
  INDIRECT:                      12 / 121 = 9.9%
  TC_ONLY:                       23 / 121 = 19.0%
  UNTESTED:                      51 / 121 = 42.1%

Total non-DONE+TESTED gaps:      107
P0 non-DONE+TESTED gaps:         58

AC DONE rate:
  DONE ACs:                      12 / 102 = 11.8%

BR DONE rate:
  DONE BRs:                      3 / 17 = 17.6%
```

### Compliance Verdict

`AT-RISK`

Reason: AC DONE rate is far below the 70% threshold, P0 gaps greatly exceed the `<= 3` allowance, and automated test coverage for BRD line items is below 70%. The repo has a strong Phase 1 foundation, but the BRD describes a much larger investigation workbench than the currently implemented product.

## Top 10 Priority Actions

1. Implement CCTNS sync service and queue for `FR-001`, including retry policy, failure status, retry UI, and duplicate crime-number enforcement.
2. Complete document upload controls for `FR-003`: 20-file bulk upload, 50 MB limit, strict MIME/TXT support, document type validation, OCR trigger, and offline queue.
3. Finish case dashboard parity for `FR-004`/`FR-005`: navigation to activity detail, document version diff, overdue logic, reminders, and snooze behavior.
4. Make quality checks BRD-grade for `FR-006`: persisted `AIAnalysisResult`/`Citation`, clickable excerpts, uncited finding suppression, KB-driven checklist selection, and latency measurement.
5. Add HRMS/LDAP integration for `FR-017`, including profile sync of rank/posting and exact account lockout semantics.
6. Replace the document integrity stub with real recomputation from stored bytes plus UI button, mismatch warning, audit log, and System Admin notification.
7. Build the offline PWA queue for `FR-012` with IndexedDB, per-file status, automatic sync, failure reasons, and manual retry.
8. Add the case-scoped section recommendation API/UI for `FR-007` with ingredient mapping, missing facts, alternatives, calibrated confidence, and exact legal disclaimer.
9. Implement congruence detection for `FR-008`, starting with typed alerts, false-positive dismissal workflow, auto-run after upload, and notifications.
10. Address deployment constraints: on-prem/self-hosted model architecture, backup/RTO/RPO design, TLS/key management evidence, and performance/load tests for 100 users.

## Quality Checklist

- [x] Every FR in the BRD has a traceability section or rows in the flat matrix.
- [x] Every AC and explicit BR/EC under `FR-001` to `FR-020` has its own row.
- [x] Every verdict has code evidence or searched terms.
- [x] PARTIAL verdicts explain what is implemented and what remains missing.
- [x] Gap rows include category and size.
- [x] Scorecard arithmetic reconciles to `121` functional items.
- [x] Verdict follows the skill criteria.
- [x] Small gaps are included, including exact message mismatches, missing notes, missing UI toggles, and stubbed integrity verification.
- [x] Project structure was auto-detected and this report uses the flat local repo layout.

