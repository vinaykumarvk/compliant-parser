# BRD/RFQ Coverage Audit: HCP Investigation Quality Workbench

Sources:
- `docs/HCP_IQW_BRD_v1.docx`
- `docs/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.pdf`

Audit date: 2026-05-04  
Scope: `full` BRD coverage audit, phases 0-6  
Verdict: `AT-RISK`

## Executive Summary

The current codebase now covers many application-level BRD workflows: case creation, CCTNS adapter/retry semantics, offence tagging, document upload/hash/versioning, timeline, action tracker, document quality checks, Google Document AI OCR, PWA offline queue code, HRMS REST adapter, audit logging, document integrity verification, document generation, DSC status stubs, AI workflow API endpoints, and analytics endpoints.

The product is still not RFQ-compliant because the RFQ requires an on-premise, self-hosted, Kubernetes-based, multi-engine AI deployment with prompt validation, model fine-tuning, performance evidence, hardware/BOQ deliverables, MinIO/OpenSearch/pgvector/Celery or Temporal, HSM-backed key management, active-passive failover, and quarterly DR drills. The application currently uses Google Document AI and OpenAI/Gemini live API adapters, which matches the latest implementation request but conflicts with BRD/RFQ self-hosted AI constraints unless written approval and fallback justification are produced.

## Phase 0 - Preflight

| Check | Result |
|---|---|
| BRD file | `docs/HCP_IQW_BRD_v1.docx`, `53,539` bytes |
| RFQ file | `docs/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.pdf`, `417,419` bytes |
| Extraction | BRD extracted to `/tmp/iqw_req_extract/HCP_IQW_BRD_v1.txt`; RFQ extracted to `/tmp/iqw_req_extract/HCP_AI_QW_Vendor_RFQ_Spec_v1.2.txt` |
| BRD functional FRs | `20`, `FR-001` through `FR-020` |
| BRD acceptance criteria | `102`, lines `95-309` in extracted BRD |
| RFQ functional module items | `60`, RFQ lines `104-227` |
| Tech stack | Python/FastAPI, SQLAlchemy async, PostgreSQL/Cloud SQL path, vanilla `index.html` PWA, Jinja2/python-docx/ReportLab, Google Document AI adapter, OpenAI/Gemini structured JSON adapter |
| Test infrastructure | `tests/`, pytest/unittest style, no frontend browser test suite found |
| Git state | Branch `main`, commit `8dfa690`, dirty working tree existed before this report |
| Verification run | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` -> `286 passed, 491 warnings in 36.47s` |

Auto-discovered structure:

| Layer | Evidence |
|---|---|
| API/routes | `api_v1.py`, `app.py` |
| Domain/services | `cases.py`, `quality_engine.py`, `ai_workflows.py`, `document_generator.py`, `ocr_enhancements.py`, `external_interfaces.py`, `cctns.py`, `hrms.py` |
| Data/model | `models.py`, `database.py`, `migrations.py` |
| Middleware/security | `auth.py`, `audit.py` |
| UI/PWA | `index.html`, `manifest.json`, `sw.js`, `static/` |
| Tests | `tests/test_*.py` |

Search discipline: for `NOT_FOUND` rows, searches were run by keyword, entity/route/model, and semantic variants across the source, UI, config, tests, Docker files, README, and docs. Representative searches included `rg` terms for `TrOCR`, `Donut`, `Llama`, `Mistral`, `Kubernetes`, `MinIO`, `OpenSearch`, `pgvector`, `Celery`, `Temporal`, `ABAC`, `HSM`, `TLS 1.3`, `p95`, `load test`, `prompt`, `dataset`, `annotation`, `model fine`, `Rancher`, `OpenShift`, and the relevant FR/RFQ feature terms.

## Scorecard

Procurement/pricing-only RFQ BOQ lines are listed separately and excluded from the code implementation denominator.

| Metric | Count |
|---|---:|
| Total auditable implementation items | `282` |
| Acceptance criteria / module requirements | `172` |
| Business rules / policy constraints | `58` |
| Edge cases | `4` |
| Failure-handling / NFR / operational controls | `48` |
| `DONE` | `92` |
| `PARTIAL` | `91` |
| `STUB` | `7` |
| `NOT_FOUND` | `92` |
| Implementation rate, `DONE + PARTIAL` | `183 / 282 = 64.9%` |
| Automated `TESTED` or `INDIRECT` evidence | `112 / 282 = 39.7%` |
| Gaps, not `DONE + TESTED` | `225` |
| P0 blockers | `10` |

Verdict rationale: `AT-RISK`, because implementation coverage is below the `70%` threshold and there are more than three P0 blockers, mostly from RFQ infrastructure, self-hosted AI, NFR validation, and production integrations.

## Evidence Anchors

| Anchor | Evidence |
|---|---|
| `E_CASE` | `cases.py:255-316`, `api_v1.py:798-882`, `cctns.py:19-92`, `index.html:8666-8689`, `tests/test_cases.py:84`, `tests/test_cases.py:193-216` |
| `E_OFFENCE` | `models.py:308-323`, `cases.py:884-930`, `api_v1.py:1144-1153`, `index.html:4126-4128`, `index.html:8986-9041`, `tests/test_cases.py:299-312` |
| `E_DOC_UPLOAD` | `cases.py:75-81`, `cases.py:201-220`, `cases.py:444-536`, `cases.py:540-563`, `api_v1.py:885-956`, `index.html:8737-8830`, `tests/test_cases.py:166-195` |
| `E_TIMELINE` | `cases.py:634-666`, `api_v1.py:1006-1014`, `index.html:8840-8873`, `tests/test_cases.py:193-216` |
| `E_TASKS` | `models.py:994-1025`, `cases.py:673-784`, `cases.py:787-822`, `api_v1.py:1017-1059`, `index.html:8877-8900`, `tests/test_cases.py:227-254` |
| `E_QUALITY` | `quality_engine.py:40-83`, `quality_engine.py:359-480`, `api_v1.py:1168-1256`, `index.html:3913`, `index.html:9117-9128`, `tests/test_quality_engine.py:99-127` |
| `E_LLM` | `external_interfaces.py:392-468`, `ai_workflows.py:34-55`, `ai_workflows.py:103-194`, `api_v1.py:1259-1286` |
| `E_CONGRUENCE` | `models.py:629-669`, `ai_workflows.py:197-319`, `api_v1.py:1289-1343` |
| `E_PLAN` | `models.py:814-841`, `ai_workflows.py:322-388`, `api_v1.py:1346-1405` |
| `E_DOCGEN` | `document_generator.py:105-480`, `document_generator.py:560-575`, `document_generator.py:582-633`, `api_v1.py:1486-1585`, `index.html:3980-3989`, `tests/test_document_generator.py:107-172` |
| `E_OCR` | `external_interfaces.py:130-182`, `ocr_enhancements.py:85-104`, `ocr_enhancements.py:111-184`, `ocr_enhancements.py:194-251`, `api_v1.py:1599-1656`, `tests/test_ocr_enhancements.py:122-164` |
| `E_PWA` | `manifest.json`, `sw.js:1-6`, `app.py:410-424`, `index.html:4277-4347`, `index.html:4937-4992`, `index.html:8336`, `index.html:8799-8828` |
| `E_AI_ADMIN` | `models.py:551-583`, `models.py:892-930`, `api_v1.py:539-687`, `index.html:4016`, `index.html:9497` |
| `E_JUDGMENT` | `models.py:848-878`, `ai_workflows.py:391-454`, `api_v1.py:1408-1440` |
| `E_ANALYTICS` | `models.py:1032-1049`, `ai_workflows.py:457-489`, `api_v1.py:1085-1128`, `index.html:4030-4033`, `index.html:9551-9581` |
| `E_AUTH` | `auth.py:29-47`, `auth.py:131-155`, `auth.py:166-182`, `api_v1.py:386-421`, `hrms.py:44-69`, `tests/test_auth.py:90-112` |
| `E_AUDIT` | `models.py:937-964`, `audit.py:22`, `audit.py:66-97`, `audit.py:104-141`, `audit.py:176-245`, `audit.py:252-294`, `api_v1.py:690-730`, `tests/test_audit.py:64-200` |
| `E_INTEGRITY` | `audit.py:36-38`, `models.py:471-479`, `cases.py:500-518`, `api_v1.py:735-793`, `index.html:8742-8756`, `tests/test_integration.py:404-420` |
| `E_INFRA_PARTIAL` | `Dockerfile:39`, `database.py:50-103`, `database.py:129-147`, `external_interfaces.py:263-343`, `docs/operations/nfr-controls.md:13-29` |

## BRD Functional Traceability

Legend: code verdicts are `DONE`, `PARTIAL`, `STUB`, or `NOT_FOUND`. Test verdicts are `TESTED`, `INDIRECT`, or `UNTESTED`.

| Item | Source | Requirement | Code | Evidence | Test | Gap |
|---|---|---|---|---|---|---|
| AC-001-1 | BRD:95 | Crime/Petition number entry formats | DONE | `cases.py:91-98`, `cases.py:255-269`, `api_v1.py:798-807` | INDIRECT | UI/API covered, petition test missing |
| AC-001-2 | BRD:96 | Reject invalid Crime No. with exact message | DONE | `cases.py:259-264`, `tests/test_cases.py:84` | TESTED | Petition exact-message test missing |
| AC-001-3 | BRD:97 | CCTNS sync initiated and status shown | PARTIAL | `cases.py:291-316`, `cctns.py:50-92`, `index.html:8674-8689` | UNTESTED | Real CCTNS smoke test missing |
| AC-001-4 | BRD:98 | Local case retained on CCTNS failure, retry shown | PARTIAL | `cases.py:307-316`, `cases.py:415-437`, `api_v1.py:875-882`, `index.html:8676` | UNTESTED | Configured remote failure test missing |
| BR-001-1 | BRD:100 | Crime number unique within police station/year | DONE | `cases.py:182-198`, `cases.py:271-273` | UNTESTED | Add duplicate same-year automated test |
| BR-001-2 | BRD:101 | 3 retries, 30-second interval before failed | DONE | `cctns.py:19-20`, `cctns.py:72-92` | UNTESTED | Add adapter retry test with fake sleeper |
| EC-001-1 | BRD:103 | Duplicate crime exact error | DONE | `cases.py:193-198` | UNTESTED | Add exact error assertion |
| EC-001-2 | BRD:104 | CCTNS unavailable queues sync retry | DONE | `cctns.py:63-70`, `cases.py:152-160` | UNTESTED | Add no-url case creation test |
| AC-002-1 | BRD:109 | Searchable offence dropdown mapped to BNS/IPC | DONE | `cases.py:884-930`, `api_v1.py:1144-1153`, `index.html:4126-4128` | TESTED | Browser interaction untested |
| AC-002-2 | BRD:110 | Primary and secondary offence types | PARTIAL | `models.py:416-421`, `api_v1.py:200-211`, `cases.py:281-282` | INDIRECT | UI only captures primary offence |
| AC-002-3 | BRD:111 | Offence displayed on dashboard header | DONE | `index.html:8666-8668`, `index.html:8702` | UNTESTED | Browser assertion missing |
| AC-002-4 | BRD:112 | Offence type modifiable during investigation | DONE | `cases.py:364-380`, `api_v1.py:850-860`, `index.html:8991-9041` | INDIRECT | Secondary offence edit missing |
| AC-003-1 | BRD:117 | Drag/drop or bulk up to 20 files | DONE | `cases.py:77`, `cases.py:540-563`, `api_v1.py:918-956`, `index.html:8787-8792` | INDIRECT | Bulk endpoint unit test missing |
| AC-003-2 | BRD:118 | Supported formats and exact unsupported error | DONE | `cases.py:79-81`, `cases.py:201-217`, `index.html:8793-8796` | INDIRECT | Invalid extension API test missing |
| AC-003-3 | BRD:119 | 50 MB limit and exact error | DONE | `cases.py:78`, `cases.py:212-213`, `index.html:8796` | UNTESTED | Oversize API test missing |
| AC-003-4 | BRD:120 | SHA-256 hash stored | DONE | `audit.py:36-38`, `cases.py:500-518`, `models.py:478` | TESTED | Covered |
| AC-003-5 | BRD:121 | Offline queue and auto-upload | PARTIAL | `index.html:4277-4347`, `index.html:4937-4992`, `index.html:8799-8828` | UNTESTED | No browser/offline sync test; no background sync |
| BR-003-1 | BRD:123 | `document_type` required | DONE | `cases.py:207-211`, `api_v1.py:887-903` | INDIRECT | Exact validation test missing |
| BR-003-2 | BRD:124 | Offline progress/status per file | PARTIAL | `index.html:4977-4982` | UNTESTED | Status exists; progress percentage not implemented |
| AC-004-1 | BRD:129 | Timeline newest-first default plus oldest-first toggle | DONE | `cases.py:658-666`, `api_v1.py:1006-1014`, `index.html:8868-8873` | TESTED | Browser toggle test missing |
| AC-004-2 | BRD:130 | Entry timestamp/action/user/description | DONE | `models.py:527-540`, `cases.py:634-655`, `index.html:8844-8848` | TESTED | Covered |
| AC-004-3 | BRD:131 | Timeline entry navigates to detail | PARTIAL | `index.html:8851-8861` | UNTESTED | Only document/task tab navigation; not AI analysis/generated docs |
| AC-004-4 | BRD:132 | Version history and diff view | DONE | `cases.py:586-627`, `api_v1.py:983-1003`, `index.html:8759-8779` | UNTESTED | Add version/diff tests |
| AC-005-1 | BRD:137 | Tasks sorted by due date | DONE | `cases.py:708-715` | TESTED | Covered |
| AC-005-2 | BRD:138 | Task fields shown | DONE | `models.py:994-1022`, `index.html:8877-8900` | TESTED | Browser visual test missing |
| AC-005-3 | BRD:139 | Overdue tasks red/visual indicator | PARTIAL | `cases.py:163-179`, `index.html:8887-8896` | UNTESTED | Backend marks overdue; explicit red UI class not verified |
| AC-005-4 | BRD:140 | Reminders 3 days, 1 day, due date | PARTIAL | `cases.py:759-784`, `api_v1.py:1052-1059` | UNTESTED | Manual endpoint only; no scheduler/background job |
| AC-005-5 | BRD:141 | Complete or snooze tasks | DONE | `cases.py:718-756`, `index.html:8896` | TESTED | Browser snooze test missing |
| AC-006-1 | BRD:147 | Run quality check with processing indicator | PARTIAL | `api_v1.py:1196-1256`, `index.html:3913`, `index.html:9117-9128` | TESTED | No estimated-time UI |
| AC-006-2 | BRD:148 | Missing elements with direct citations | DONE | `quality_engine.py:425-443`, `api_v1.py:1241-1255` | TESTED | Citation click UI untested |
| AC-006-3 | BRD:149 | Weak areas with suggestions | DONE | `quality_engine.py:220-336`, `quality_engine.py:434-443` | TESTED | Covered |
| AC-006-4 | BRD:150 | Trial risk severity | DONE | `quality_engine.py:188-213`, `quality_engine.py:457` | TESTED | Covered |
| AC-006-5 | BRD:151 | Every finding has citation; uncited hidden | DONE | `quality_engine.py:417-443`, `quality_engine.py:474` | TESTED | Covered |
| AC-006-6 | BRD:152 | IO-facing suggestions only | DONE | `quality_engine.py:468-485` | INDIRECT | No separate supervisor report found |
| BR-006-1 | BRD:154 | Checklist by doc/offence from KB | DONE | `api_v1.py:1168-1193`, `api_v1.py:1214-1220` | UNTESTED | KB override route test missing |
| BR-006-2 | BRD:155 | Generic checklist fallback note | DONE | `quality_engine.py:81-82`, `quality_engine.py:471-472` | TESTED | Covered |
| BR-006-3 | BRD:156 | p95 quality latency <10s | PARTIAL | `quality_engine.py:82`, `quality_engine.py:478-480` | UNTESTED | Per-call target recorded, no p95/load test |
| AC-007-1 | BRD:162 | Paste/upload complaint and recommend sections | PARTIAL | `api_v1.py:1259-1286`, `ai_workflows.py:103-147` | UNTESTED | API exists; no dedicated UI button |
| AC-007-2 | BRD:163 | Primary sections with confidence/reasoning | DONE | `ai_workflows.py:115-124`, `ai_workflows.py:174-190` | UNTESTED | LLM contract test missing |
| AC-007-3 | BRD:164 | Supporting ingredients | DONE | `ai_workflows.py:122`, `ai_workflows.py:184` | UNTESTED | LLM contract test missing |
| AC-007-4 | BRD:165 | Missing ingredients | DONE | `ai_workflows.py:123`, `ai_workflows.py:185` | UNTESTED | LLM contract test missing |
| AC-007-5 | BRD:166 | Alternatives with confidence/reasoning | DONE | `ai_workflows.py:126-140`, `ai_workflows.py:174-190` | UNTESTED | LLM contract test missing |
| AC-007-6 | BRD:167 | Mandatory disclaimer | DONE | `ai_workflows.py:28-31`, `ai_workflows.py:142`, `ai_workflows.py:188` | UNTESTED | Add exact-text API test |
| BR-007-1 | BRD:169 | Hide confidence <0.30 unless show all | DONE | `ai_workflows.py:135-141`, `api_v1.py:238` | UNTESTED | Add threshold test |
| BR-007-2 | BRD:170 | Fine-tuned self-hosted Llama/Mistral | NOT_FOUND | searched: `Llama`, `Mistral`, `vLLM`, `TGI`, `self-hosted` | UNTESTED | P0 self-hosted model gap |
| AC-008-1 | BRD:176 | Required comparison pairs | DONE | `ai_workflows.py:197-204` | UNTESTED | Pair tests missing |
| AC-008-2 | BRD:177 | Alert type/severity/description/excerpts | DONE | `ai_workflows.py:231-283`, `api_v1.py:1315-1328` | UNTESTED | LLM contract test missing |
| AC-008-3 | BRD:178 | Dismiss with reason and notes | DONE | `ai_workflows.py:302-319`, `api_v1.py:1331-1343` | UNTESTED | API test missing |
| AC-008-4 | BRD:179 | Dismissals feed refinement | PARTIAL | `ai_workflows.py:317-319` | UNTESTED | Boolean stored; no training/refinement pipeline |
| AC-008-5 | BRD:180 | Missing carry-forward flagged separately | DONE | `ai_workflows.py:234`, `ai_workflows.py:248-254` | UNTESTED | LLM contract test missing |
| BR-008-1 | BRD:182 | Auto-run congruence on related upload | DONE | `api_v1.py:904-915`, `api_v1.py:941-955` | UNTESTED | Endpoint upload test missing |
| BR-008-2 | BRD:183 | In-app notification for alerts | DONE | `ai_workflows.py:285-299` | UNTESTED | Notification test missing |
| AC-009-1 | BRD:189 | Auto-detect offence and IO confirmation | DONE | `ai_workflows.py:326-337`, `ai_workflows.py:379-380` | UNTESTED | No UI confirmation flow |
| AC-009-2 | BRD:190 | Numbered steps with citations | DONE | `ai_workflows.py:338-340`, `ai_workflows.py:353-356` | UNTESTED | LLM contract test missing |
| AC-009-3 | BRD:191 | Evidence with forensic requirements | DONE | `ai_workflows.py:340`, `ai_workflows.py:357-360` | UNTESTED | LLM contract test missing |
| AC-009-4 | BRD:192 | Documents to generate | DONE | `ai_workflows.py:341`, `ai_workflows.py:361` | UNTESTED | LLM contract test missing |
| AC-009-5 | BRD:193 | Deadlines/calendar/countdown | PARTIAL | `ai_workflows.py:342`, `ai_workflows.py:347-370` | UNTESTED | JSON deadlines exist; no calendar UI |
| AC-009-6 | BRD:194 | Plan editable by IO | DONE | `api_v1.py:1388-1405`, `ai_workflows.py:371-385` | UNTESTED | API test missing |
| AC-009-7 | BRD:195 | Completion checkbox per task | PARTIAL | `ai_workflows.py:339`, `index.html:8896` | UNTESTED | Plan steps not integrated into action tracker UI |
| AC-010-1 | BRD:201 | Template auto-fill from case data | DONE | `api_v1.py:1486-1524`, `document_generator.py:560-575` | TESTED | Covered indirectly |
| AC-010-2 | BRD:202 | Auto-filled fields editable/highlighted | DONE | `document_generator.py:72-87`, `document_generator.py:582-602`, `index.html:3980-3981` | TESTED | Highlight visual untested |
| AC-010-3 | BRD:203 | Export DOCX/PDF | DONE | `api_v1.py:1569-1585`, `document_generator.py:640-650`, `tests/test_integration.py:166-171` | TESTED | Covered |
| AC-010-4 | BRD:204 | Apply DSC signature | STUB | `document_generator.py:605-633`, `api_v1.py:1553-1566` | UNTESTED | Env-gated status update, no real PKCS#11/WebCrypto DSC |
| AC-010-5 | BRD:205 | Missing fields prompt/list | DONE | `document_generator.py:72-87`, `document_generator.py:560-575` | TESTED | Covered |
| BR-010-1 | BRD:207 | FSL forwarding/sample/reminder | DONE | `document_generator.py:114-183` | TESTED | Covered |
| BR-010-2 | BRD:208 | Evidence certificates/hash declaration | DONE | `document_generator.py:185-238` | TESTED | Covered |
| BR-010-3 | BRD:209 | Legal notices incl. bank/freeze/ISP/CDR/Google/Meta | DONE | `document_generator.py:240-378` | TESTED | Covered |
| BR-010-4 | BRD:210 | Arrest/seizure/remand/confession templates | DONE | `document_generator.py:380-480` | TESTED | Covered |
| AC-011-1 | BRD:216 | Scan/photo upload and language detection | DONE | `cases.py:472-482`, `ocr_enhancements.py:85-104`, `api_v1.py:1618-1656` | TESTED | OCR live call untested |
| AC-011-2 | BRD:217 | Extracted text alongside original | PARTIAL | `ocr_enhancements.py:236-251`, `api_v1.py:1650-1656` | UNTESTED | Payload label only; no actual image rendering verification |
| AC-011-3 | BRD:218 | English translation in third pane | PARTIAL | `ocr_enhancements.py:243-247` | UNTESTED | Non-English translation is placeholder, not translated text |
| AC-011-4 | BRD:219 | Segment confidence tags and review flag | DONE | `ocr_enhancements.py:111-184`, `ocr_enhancements.py:231-251` | TESTED | Covered |
| AC-011-5 | BRD:220 | OCR p95 <5s per page | PARTIAL | `ocr_enhancements.py:250` | UNTESTED | Target declared; no p95/load benchmark |
| BR-011-1 | BRD:222 | Low confidence acknowledged before save | PARTIAL | `ocr_enhancements.py:194-228`, `api_v1.py:1599-1615` | TESTED | Acknowledgement not enforced as save gate |
| BR-011-2 | BRD:223 | Self-hosted TrOCR/Donut primary | NOT_FOUND | searched: `TrOCR`, `Donut`, `EasyOCR`, `Tesseract`, `self-hosted` | UNTESTED | Current OCR is Google Document AI |
| AC-012-1 | BRD:228 | Installable PWA | DONE | `manifest.json`, `sw.js:1-6`, `app.py:410-424` | UNTESTED | Browser installability test missing |
| AC-012-2 | BRD:229 | Offline upload stored in IndexedDB | DONE | `index.html:4277-4347`, `index.html:8799-8801` | UNTESTED | Browser offline test missing |
| AC-012-3 | BRD:230 | Queue displays name/size/time/status | DONE | `index.html:4977-4982` | UNTESTED | Browser offline test missing |
| AC-012-4 | BRD:231 | Auto-sync on reconnect | DONE | `index.html:8336`, `index.html:8799-8828` | UNTESTED | Browser reconnect test missing |
| AC-012-5 | BRD:232 | Failed sync reason and retry | DONE | `index.html:4982-4988`, `index.html:8820-8828` | UNTESTED | Browser retry test missing |
| AC-013-1 | BRD:238 | Low-confidence AI outputs flagged | PARTIAL | `models.py:574-577`, `ai_workflows.py:167-169` | UNTESTED | Only section hidden-threshold flags; quality/congruence/judgment not consistently flagged |
| AC-013-2 | BRD:239 | Tag/output/source/model/prompt included | DONE | `models.py:565-583`, `api_v1.py:553-562` | UNTESTED | Queue API test missing |
| AC-013-3 | BRD:240 | AI Admin queue sorted by severity | DONE | `api_v1.py:539-563`, `index.html:4016`, `index.html:9497` | UNTESTED | API/UI test missing |
| AC-013-4 | BRD:241 | Corrections update KB | DONE | `api_v1.py:566-593` | UNTESTED | API test missing |
| AC-014-1 | BRD:246 | KB entry Draft | DONE | `api_v1.py:596-616` | UNTESTED | API test missing |
| AC-014-2 | BRD:247 | Promote to Staging | DONE | `api_v1.py:619-639` | UNTESTED | API test missing |
| AC-014-3 | BRD:248 | Validate staging entries | PARTIAL | `api_v1.py:642-661` | UNTESTED | Validation is lightweight content-present only |
| AC-014-4 | BRD:249 | Promote validated to Production | PARTIAL | `api_v1.py:619-639`, `api_v1.py:1168-1193` | UNTESTED | No enforcement that validation passed |
| AC-014-5 | BRD:250 | Version/change/timestamp tracked | PARTIAL | `models.py:905-920`, `api_v1.py:605-616` | UNTESTED | Change description stored in content; version increment workflow incomplete |
| AC-014-6 | BRD:251 | Rollback production entry audited | PARTIAL | `api_v1.py:664-687`, `audit.py:118-123` | UNTESTED | Rollback depends on unset `previous_version_id`; notification missing |
| AC-015-1 | BRD:257 | Judgment PDF/TXT max 50 MB | DONE | `api_v1.py:1408-1431` | UNTESTED | API test missing |
| AC-015-2 | BRD:258 | Facts/issues/verdict/lapses/evidence observations | DONE | `ai_workflows.py:391-454` | UNTESTED | LLM contract test missing |
| AC-015-3 | BRD:259 | Investigation lessons | DONE | `ai_workflows.py:404`, `ai_workflows.py:448` | UNTESTED | LLM contract test missing |
| AC-015-4 | BRD:260 | Avoidable errors | DONE | `ai_workflows.py:405`, `ai_workflows.py:449` | UNTESTED | LLM contract test missing |
| AC-015-5 | BRD:261 | Checklist proposals require AI Admin approval | DONE | `ai_workflows.py:406`, `ai_workflows.py:435-436`, `api_v1.py:566-593` | UNTESTED | End-to-end approval test missing |
| AC-015-6 | BRD:262 | Approved findings feed checklist/SOP/training | PARTIAL | `api_v1.py:582-593`, `api_v1.py:1168-1193` | UNTESTED | Checklist path exists; SOP/training loop not implemented |
| AC-016-1 | BRD:268 | Usage totals dashboard | PARTIAL | `ai_workflows.py:469-474`, `api_v1.py:1085-1101` | UNTESTED | `documents_generated` hard-coded `0` |
| AC-016-2 | BRD:269 | Time-spent metrics | STUB | `ai_workflows.py:479-482` | UNTESTED | Hard-coded zeros |
| AC-016-3 | BRD:270 | Feature usage frequency | PARTIAL | `models.py:1032-1049`, `ai_workflows.py:483-486` | UNTESTED | Usage events not broadly emitted |
| AC-016-4 | BRD:271 | Date/station/IO filters | PARTIAL | `api_v1.py:1085-1101`, `ai_workflows.py:457-463` | UNTESTED | Date filters passed but not applied |
| AC-016-5 | BRD:272 | Monthly PDF trend report | PARTIAL | `api_v1.py:1104-1128`, `index.html:9576-9581` | UNTESTED | Minimal PDF only; trend data missing |
| AC-016-6 | BRD:273 | IO own data; Admin all data | PARTIAL | `ai_workflows.py:458-460`, `auth.py:175-176` | UNTESTED | AI Admin/System Admin route roles not explicit |
| AC-017-1 | BRD:279 | Login accepts employee ID/password | DONE | `api_v1.py:386-421`, `index.html:3551` | TESTED | Covered |
| AC-017-2 | BRD:280 | Send auth request to HRMS REST/LDAP | PARTIAL | `hrms.py:44-69`, `api_v1.py:394-397` | UNTESTED | REST only; LDAP not implemented; live HRMS not validated |
| AC-017-3 | BRD:281 | Sync name/rank/posting/role | DONE | `api_v1.py:317-345`, `hrms.py:61-69` | UNTESTED | Live HRMS test missing |
| AC-017-4 | BRD:282 | Exact failed login message | DONE | `api_v1.py:397-402` | UNTESTED | API exact-message test missing |
| AC-017-5 | BRD:283 | 5-attempt lockout, 30 minutes, exact message | DONE | `auth.py:46-47`, `auth.py:131-155` | TESTED | Covered |
| AC-018-1 | BRD:288 | Sign Document button | DONE | `index.html:3989`, `api_v1.py:1553-1566` | UNTESTED | Browser test missing |
| AC-018-2 | BRD:289 | DSC token detection and PIN prompt | STUB | `document_generator.py:618-621`, `index.html:3989` | UNTESTED | Env variable check only, no real token bridge |
| AC-018-3 | BRD:290 | Signed status/signer/timestamp/cert | STUB | `document_generator.py:623-633`, `models.py:751-763` | UNTESTED | No real signature/certificate chain validation |
| AC-018-4 | BRD:291 | Missing token exact error | DONE | `document_generator.py:618-619`, `api_v1.py:1561-1564` | UNTESTED | API exact-message test missing |
| AC-018-5 | BRD:292 | Signed docs read-only | DONE | `document_generator.py:88-90`, `document_generator.py:593-596` | UNTESTED | API test missing |
| AC-019-1 | BRD:297 | Every AuditLog enum action auto-recorded | PARTIAL | `audit.py:104-141`, `audit.py:194-245` | TESTED | GET exports skipped before `infer_action_type`; not every internal AI action is direct-logged |
| AC-019-2 | BRD:298 | Audit logs immutable/non-editable | DONE | `models.py:934-964`, `api_v1.py:690-730`, `tests/test_audit.py:196-200` | TESTED | Covered |
| AC-019-3 | BRD:299 | User/action/entity/time/IP/session | DONE | `audit.py:45-59`, `audit.py:217-240` | TESTED | Covered |
| AC-019-4 | BRD:300 | Search by date/user/action/entity | DONE | `audit.py:252-288`, `api_v1.py:692-717` | TESTED | Covered |
| AC-019-5 | BRD:301 | 7-year retention | PARTIAL | `audit.py:22`, `audit.py:58`, `docs/operations/nfr-controls.md:22` | UNTESTED | No DB partition/lifecycle retention enforcement |
| AC-020-1 | BRD:306 | Hash upload and store | DONE | `cases.py:500-518`, `models.py:478` | TESTED | Covered |
| AC-020-2 | BRD:307 | Verify button recomputes/compares | DONE | `api_v1.py:735-755`, `index.html:8742-8756` | TESTED | Covered |
| AC-020-3 | BRD:308 | Matching hash success message | DONE | `api_v1.py:755-761` | TESTED | Covered |
| AC-020-4 | BRD:309 | Mismatch warning and System Admin alert | DONE | `api_v1.py:763-793` | TESTED | Covered |

## RFQ Functional Module Traceability

RFQ modules largely restate BRD functional scope. Rows below identify deviations introduced by the RFQ language.

| RFQ Item | Source | Code | Evidence | Gap |
|---|---|---|---|---|
| 1.1 Case with Crime/Petition and CCTNS sync | RFQ:104 | PARTIAL | `E_CASE` | Real CCTNS validation missing |
| 1.2 Offence type at creation | RFQ:105 | PARTIAL | `E_OFFENCE` | Secondary offence UI missing |
| 1.3 Documents via drag/drop, bulk, offline | RFQ:106 | PARTIAL | `E_DOC_UPLOAD`, `E_PWA` | Browser offline tests/background sync missing |
| 1.4 Timeline and version history | RFQ:107 | PARTIAL | `E_TIMELINE`, `cases.py:586-627` | AI/generated-doc timeline navigation incomplete |
| 1.5 Action tracker/reminders | RFQ:108 | PARTIAL | `E_TASKS` | No scheduler/background job |
| 2.1 Checklist evaluation | RFQ:113 | DONE | `E_QUALITY` | Automated KB override test missing |
| 2.2 RAG/no hallucination | RFQ:114-115 | PARTIAL | `quality_engine.py:121-148`, `quality_engine.py:425-443` | Rule/excerpt grounding exists; no RAG retrieval architecture |
| 2.3 Missing elements with citations | RFQ:116 | DONE | `E_QUALITY` | Browser click test missing |
| 2.4 Weak areas suggestions | RFQ:117 | DONE | `E_QUALITY` | Covered |
| 2.5 Trial risk severity | RFQ:118 | DONE | `E_QUALITY` | Covered |
| 2.6 Suggestions link to excerpts | RFQ:119 | DONE | `quality_engine.py:425-431` | Browser click test missing |
| 2.7 IO-facing only | RFQ:120-121 | DONE | `quality_engine.py:468-485` | Covered indirectly |
| 3.1 Section recommendation with reasoning | RFQ:126 | PARTIAL | `E_LLM` | API only, no UI |
| 3.2 Supporting ingredients | RFQ:127 | DONE | `ai_workflows.py:122`, `ai_workflows.py:184` | LLM contract test missing |
| 3.3 Missing facts | RFQ:128 | DONE | `ai_workflows.py:123`, `ai_workflows.py:185` | LLM contract test missing |
| 3.4 Alternative sections/confidence | RFQ:129 | DONE | `ai_workflows.py:126-140` | LLM contract test missing |
| 3.5 Disclaimer | RFQ:130-131 | DONE | `ai_workflows.py:28-31`, `ai_workflows.py:142` | Exact API test missing |
| 4.1-4.9 Congruence engine | RFQ:140-149 | PARTIAL | `E_CONGRUENCE` | API/service exists; UI absent; model-refinement pipeline absent |
| 5.1-5.7 SOP/plan generator | RFQ:154-160 | PARTIAL | `E_PLAN` | API/service exists; UI/calendar/action-tracker integration incomplete |
| 6 doc categories | RFQ:162-170 | DONE | `document_generator.py:114-480` | Covered |
| 6.1 Auto-fill | RFQ:174 | DONE | `api_v1.py:1486-1524` | Covered |
| 6.2 Editable fields | RFQ:175 | DONE | `document_generator.py:582-602` | Browser test missing |
| 6.3 DOCX/PDF export | RFQ:176 | DONE | `api_v1.py:1569-1585` | Covered |
| 6.4 DSC | RFQ:183 | STUB | `document_generator.py:605-633` | Real DSC integration absent |
| 7.1 Handwritten/scanned docs | RFQ:187 | PARTIAL | `E_OCR` | Google Document AI, not self-hosted handwritten engine |
| 7.2 Telugu/Urdu/Hindi/English | RFQ:188 | PARTIAL | `ocr_enhancements.py:85-104`, `complaint_parsing.py` | Detection exists; translation/OCR quality not validated across all languages |
| 7.3 Extracted/translated/side-by-side | RFQ:189 | PARTIAL | `ocr_enhancements.py:243-247` | Translation placeholder for non-English |
| 7.4 Confidence tagging | RFQ:190-191 | DONE | `ocr_enhancements.py:111-184` | Covered |
| 7.5 PWA offline OCR queue | RFQ:192-193 | PARTIAL | `E_PWA` | Offline upload queue exists; OCR job queue/backend worker absent |
| 7.6 Auto-sync on reconnect | RFQ:194 | DONE | `index.html:8336`, `index.html:8799-8828` | Browser test missing |
| 8.1 Uncertainty tags | RFQ:198-199 | PARTIAL | `models.py:574-577`, `ai_workflows.py:167-169` | Not consistently applied across AI outputs |
| 8.2 AI Admin queue | RFQ:200 | DONE | `api_v1.py:539-563` | API test missing |
| 8.3 Corrections update KB | RFQ:201 | DONE | `api_v1.py:566-593` | API test missing |
| 8.4 Staging first | RFQ:202 | PARTIAL | `api_v1.py:619-639` | Production promotion not blocked by missing staging validation |
| 8.5 Validate staging | RFQ:203 | PARTIAL | `api_v1.py:642-661` | Lightweight validation only |
| 8.6 Version tracking | RFQ:204 | PARTIAL | `models.py:905-920` | Model update versioning absent |
| 8.7 Rollback | RFQ:205 | PARTIAL | `api_v1.py:664-687` | Previous-version creation incomplete |
| 9.1-9.6 Judgment analysis | RFQ:209-214 | PARTIAL | `E_JUDGMENT` | API/service exists; no tests/live validation |
| 9.7 Findings feed downstream | RFQ:215 | PARTIAL | `api_v1.py:582-593`, `api_v1.py:1168-1193` | Training loop and SOP propagation missing |
| 10.1 Usage counts | RFQ:225 | PARTIAL | `E_ANALYTICS` | Documents generated hard-coded `0` |
| 10.2 Time spent/frequency | RFQ:226 | STUB | `ai_workflows.py:479-486` | Time spent hard-coded `0`; usage event emission incomplete |
| 10.3 Reports/trends | RFQ:227 | PARTIAL | `api_v1.py:1104-1128` | Minimal monthly PDF; adoption/officer reports missing |

## RFQ-Only Constraint and NFR Audit

| Item | Source | Code | Evidence or searched terms | Gap |
|---|---|---|---|---|
| No hallucination/RAG for all AI | RFQ:238-242 | PARTIAL | `quality_engine.py:425-443`, `ai_workflows.py:105-110`, searched `RAG`, `vector`, `citation` | RAG/vector retrieval absent for LLM workflows |
| Suggestive, not prescriptive | RFQ:243-244 | DONE | `ai_workflows.py:28-31`, `document_generator.py:582-602` | Human acceptance tests missing |
| Confidence tagging all uncertain outputs | RFQ:245-246 | PARTIAL | `models.py:570-577`, `ocr_enhancements.py:111-184` | Not uniformly enforced for all AI outputs |
| Editable outputs | RFQ:247-248 | PARTIAL | `document_generator.py:582-602`, `api_v1.py:1388-1405` | Section/congruence/judgment suggestions not all editable in UI |
| Human-in-loop high-stakes outputs | RFQ:249-252 | PARTIAL | DSC/doc edit paths exist; searched `senior review`, `finalisation`, `approval` | Senior-review workflow absent |
| On-premise Kubernetes microservices | RFQ:256-264 | NOT_FOUND | searched `Kubernetes`, `k8s`, `Helm`, `Rancher`, `OpenShift` | Current repo has Dockerfile only |
| 100 concurrent users | RFQ:257,274 | NOT_FOUND | searched `k6`, `locust`, `load test`, `100 concurrent` | No load test evidence |
| Active-passive failover | RFQ:264 | NOT_FOUND | searched `active-passive`, `failover`, `replica` | No HA manifests/runbook |
| RTO <=1h / RPO <=15m | RFQ:265-272 | PARTIAL | `docs/operations/nfr-controls.md:13-15` | Control doc only; no tested implementation |
| Continuous/daily/immutable backups | RFQ:272 | PARTIAL | `docs/operations/nfr-controls.md:15` | No backup automation |
| Quarterly DR drills | RFQ:273 | PARTIAL | `docs/operations/nfr-controls.md:15` | No drill records/runbook |
| Hardware app/db servers | RFQ:279-289 | NOT_FOUND | searched `Xeon`, `EPYC`, `NVMe`, `10 GbE` | Procurement/hardware not represented |
| AI GPU server | RFQ:291-301 | NOT_FOUND | searched `RTX 6000`, `GPU`, `CUDA`, `vLLM` | No self-hosted GPU deployment |
| MinIO/NAS 12-20TB | RFQ:303-310 | NOT_FOUND | searched `MinIO`, `S3-compatible`, `NAS`, `snapshot` | Current object storage is local/GCS |
| Networking/security hardware | RFQ:319-326 | NOT_FOUND | searched `firewall`, `UTM`, `load balancer`, `UPS` | Procurement/infrastructure gap |
| React TypeScript frontend | RFQ:333-334 | NOT_FOUND | searched `package.json`, `React`, `TypeScript` | Current UI is vanilla HTML/JS |
| Material UI / Ant Design | RFQ:335 | NOT_FOUND | searched `@mui`, `antd`, `Material UI` | Not implemented |
| Service worker/IndexedDB | RFQ:336-337 | DONE | `E_PWA` | Browser test missing |
| FastAPI backend | RFQ:338-339 | DONE | `api_v1.py`, `app.py`, `requirements.txt` | Covered |
| Celery/Redis or Temporal | RFQ:340-341 | NOT_FOUND | searched `Celery`, `Redis`, `Temporal`, `RQ`, `worker` | No async job stack |
| Docker | RFQ:342 | DONE | `Dockerfile` | Docker build not run in this audit |
| Kubernetes active-passive | RFQ:343-344 | NOT_FOUND | searched `Deployment`, `StatefulSet`, `Ingress`, `Helm` | No manifests |
| NGINX/Traefik ingress | RFQ:345 | NOT_FOUND | searched `nginx`, `traefik`, `Ingress` | No ingress config |
| PostgreSQL v17+ HA replication | RFQ:346-347 | PARTIAL | `database.py:66-103`, `requirements.txt` | PostgreSQL path exists; no v17/replication evidence |
| MinIO encrypted object storage | RFQ:348-349 | NOT_FOUND | `external_interfaces.py:263-343`, searched `MinIO` | GCS/local only |
| OpenSearch/Elasticsearch | RFQ:350 | NOT_FOUND | searched `OpenSearch`, `Elasticsearch` | No search stack |
| pgvector | RFQ:351 | NOT_FOUND | searched `pgvector`, `vector`, `embedding` | No vector storage |
| AES-256 at rest | RFQ:356-357 | PARTIAL | `external_interfaces.py:273-288`, `docs/operations/nfr-controls.md:19` | KMS ref optional; DB/backups not enforced |
| TLS 1.3 | RFQ:358 | PARTIAL | `docs/operations/nfr-controls.md:20` | No ingress/TLS config |
| HSM key storage/rotation | RFQ:365-366 | NOT_FOUND | searched `HSM`, `PKCS#11`, `KMS rotation` | No HSM implementation |
| RBAC + ABAC | RFQ:367-368 | PARTIAL | `auth.py:166-182`, `cases.py:325-361` | RBAC and IO scoping exist; ABAC policies absent |
| Tamper-evident immutable logs | RFQ:369-370 | PARTIAL | `models.py:937-964`, `audit.py:66-97` | Immutable table pattern; no hash chain/WORM proof |
| Hash all uploaded/generated docs | RFQ:371-372 | PARTIAL | `cases.py:500-518`, `api_v1.py:735-793` | Uploaded docs hashed; generated docs not hashed/export-hashed |
| AI traceability to excerpt/model version | RFQ:373-374 | PARTIAL | `models.py:565-583`, `api_v1.py:1225-1255`, `ai_workflows.py:158-169` | Strong for quality; weaker for section/congruence/judgment citations |
| HRMS REST/LDAP | RFQ:375-379 | PARTIAL | `hrms.py:44-69` | REST only; LDAP absent |
| Self-hosted sensitive AI | RFQ:381-386 | NOT_FOUND | searched `self-hosted`, `vLLM`, `TGI`, `Llama`, `Mistral` | Current LLM uses OpenAI/Gemini APIs |
| Task-to-model mapping | RFQ:388-417 | PARTIAL | `quality_engine.py`, `external_interfaces.py:392-468` | No Tesseract/EasyOCR/TrOCR/IndicTrans/Llama/Mistral/NER/BGE/E5 implementations |
| Self-hosting inference methods | RFQ:418-425 | NOT_FOUND | searched `ONNX`, `HuggingFace`, `Fairseq`, `vLLM`, `TGI` | No model server deployment |
| Model fine-tuning | RFQ:426-438 | NOT_FOUND | searched `fine-tune`, `dataset`, `annotation`, `training` | No training pipeline |
| AI p95/error/fallback/GPU/uptime SLAs | RFQ:440-449 | NOT_FOUND | searched `p95`, `error rate`, `fallback rate`, `GPU utilization`, `uptime` | No observability/load evidence |
| Prompt categories testing | RFQ:461-486 | PARTIAL | `ai_workflows.py` prompt strings | Prompts exist; no formal prompt test matrix |
| Prompt testing phases/timeline | RFQ:488-495 | NOT_FOUND | searched `prompt testing`, `dry run`, `expert review`, `held-out` | No deliverable evidence |
| Prompt sign-off metrics | RFQ:497-511 | NOT_FOUND | searched `accuracy`, `precision`, `recall`, `hallucination`, `calibration` | No validation dataset/results |
| AI training completion criteria | RFQ:513-524 | NOT_FOUND | searched `200 cases`, `legal sign-off`, `annotation interface`, `prompt library` | No evidence |
| Data confidentiality/no external transmission | RFQ:751-755 | PARTIAL | `external_interfaces.py:140-182`, `external_interfaces.py:392-468`, `docs/operations/nfr-controls.md:5-9` | Cloud APIs transmit data unless separately approved |

## Procurement / BOQ Items

The RFQ includes commercial quotation lines for rack servers, GPUs, network hardware, OS subscriptions, Kubernetes platform support, professional services, training, AMC, and optional items (`O1`-`O8`) at RFQ lines `537-737`. These are `OUT_OF_SCOPE` for source-code coverage, but still open delivery/procurement gaps:

| Area | Source | Status |
|---|---|---|
| Hardware items 1-13 | RFQ:537-604 | OUT_OF_SCOPE for code; procurement quote required |
| Software/license items 14-19 | RFQ:610-628 | OUT_OF_SCOPE for code; procurement quote required |
| Optional API services 20-22 | RFQ:632-642 | PARTIAL; app supports OpenAI/Gemini but no approval/quote evidence |
| Professional services 23-36 | RFQ:644-695 | PARTIAL; code exists, but training/manuals/runbooks not complete |
| AMC/support items 37-41 | RFQ:699-713 | OUT_OF_SCOPE for code; support plan required |
| Optional items O1-O8 | RFQ:720-737 | NOT_FOUND/OPTIONAL; no implementation evidence |

## Flat Priority Gap List

| Pri | Gap | Category | Size | Impact |
|---|---|---|---:|---|
| P0 | Replace or augment Google/OpenAI/Gemini AI paths with self-hosted OCR/translation/LLM model serving, or produce written approval for API fallback | RFQ architecture | XL | Blocks BRD/RFQ sensitive-data and self-hosted AI compliance |
| P0 | Create Kubernetes/on-prem deployment pack: manifests/Helm, ingress, active-passive failover, MinIO, PostgreSQL HA, backups, DR drill runbook | Infrastructure | XL | Blocks RFQ deployment model, RTO/RPO, HA, backup |
| P0 | Add prompt testing deliverables: datasets >=200 cases/category, metrics, expert/legal sign-off, prompt version library | AI validation | XL | Blocks RFQ go-live acceptance and zero hallucination claims |
| P0 | Implement observability/load tests for p95 OCR/LLM/API, 100 users, error/fallback rates, uptime, GPU utilization | NFR evidence | L | Blocks performance and SLA claims |
| P0 | Enforce confidentiality boundary and approval workflow for any external AI/OCR API call | Security/compliance | L | Current cloud APIs can send case data outside organization boundary |
| P0 | Implement real DSC/eSign bridge with token detection, PIN flow, certificate chain, and signed document bytes | Integration | L | Current DSC is an env-gated status stub |
| P0 | Implement ABAC policies and sensitive-data authorization beyond role checks | Security | L | RFQ requires RBAC plus ABAC |
| P0 | Add tamper-evident audit chain/WORM storage controls and generated-document hashing | Security/integrity | M | Current audit table is append-only by API but not cryptographically tamper-evident |
| P0 | Validate HRMS/CCTNS with real endpoints and add LDAP support if required | Integration | M | REST adapters exist but no live validation |
| P0 | Add background job stack for OCR, reminders, AI tasks, and offline-sync processing | Platform | L | RFQ requires Celery/Redis or Temporal and queued processing |
| P1 | Add browser/e2e tests for PWA offline queue, upload sync, timeline navigation, document diff, task reminders, generated doc signing | Test coverage | L | UI-heavy BRD features are not automated |
| P1 | Add API/contract tests for LLM section, congruence, investigation plan, judgment analysis, AI Admin queue, KB staging/rollback | Test coverage | M | Most AI workflows are untested |
| P1 | Complete analytics: generated document counts, time-spent metrics, date filters, officer/adoption reports, real trends | Functional | M | Module 10 currently has placeholders |
| P1 | Complete AI Admin lifecycle: validation gating, version creation, rollback previous-version wiring, production notifications | Functional | M | Staging workflow is present but weak |
| P1 | Add UI surfaces for section recommendation, congruence alerts, investigation plan, AI review correction workflow | Functional/UI | L | Several APIs lack first-class BRD UI |
| P1 | Implement real translation in OCR review third pane | Functional | M | Non-English OCR review currently shows placeholder text |
| P2 | Produce user training, AI Admin training, technical docs, architecture docs, API docs, and runbooks | Documentation | M | RFQ professional-services deliverables incomplete |
| P2 | Decide whether to migrate frontend to React TypeScript with MUI/AntD or document a formal deviation | RFQ stack | XL | Current frontend does not match RFQ stack requirement |

## Compliance Verdict

`AT-RISK`

The application can support an internal demo of many IQW workflows, but it is not release-ready against the combined BRD/RFQ. The main blockers are not small feature bugs; they are architecture and assurance gaps: self-hosted AI, on-prem Kubernetes/HA, DR/backups, real external integrations, prompt validation, security hardening, and NFR evidence.

## Top 10 Actions

1. Decide and document the AI hosting policy: self-hosted primary implementation vs. approved external API fallback.
2. Build the on-prem Kubernetes reference deployment, including MinIO, PostgreSQL HA, ingress, backups, monitoring, and failover procedures.
3. Add formal prompt/model validation datasets, metrics, and sign-off records.
4. Add load/latency/error/fallback-rate tests and publish p95 evidence.
5. Implement real DSC/eSign and generated-document hash verification.
6. Add ABAC and tamper-evident audit chain controls.
7. Validate HRMS/CCTNS against live or mocked contract endpoints, including LDAP if required.
8. Add Celery/Redis or Temporal for OCR/AI/reminder jobs.
9. Add frontend/e2e tests for PWA, offline queue, timeline, document diff, and signing.
10. Complete analytics and AI Admin lifecycle gaps.
