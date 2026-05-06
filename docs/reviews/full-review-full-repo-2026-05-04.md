# Full Review - Full Repo - 2026-05-04

Mode: review-only (`no-fix` default for the invoked skill).

## Findings

### HIGH - JWT tokens fall back to a hardcoded development secret

- Domains: Security, Infra
- Evidence: `auth.py:29-37` uses `JWT_SECRET_KEY` or `APP_SESSION_SECRET`, then falls back to `"dev-insecure-secret-change-me"` when neither is set. Both `pytest` and `unittest` emitted the warning: `JWT_SECRET_KEY not set - using insecure default`.
- Impact: Any production deployment missing the secret can have `/api/v1` bearer tokens forged. This undermines role enforcement for case, document, admin, audit, and analytics routes.
- Fix: Fail startup outside an explicit local/test mode when no strong JWT secret is configured. Keep tests setting a deterministic test secret rather than relying on the fallback.
- How to verify: Start the app without `JWT_SECRET_KEY`/`APP_SESSION_SECRET` in production mode and confirm startup fails; run auth tests with an explicit test secret.

### HIGH - Audit logs can persist raw session cookies

- Domains: Security, Data Exposure
- Evidence: `audit.py:203-206` decodes the JWT user and stores `session_id = request.headers.get("X-Session-Id") or request.cookies.get("session") or request_id`.
- Impact: The Starlette session cookie is credential material. Persisting it in the audit table widens the blast radius of a database leak and conflicts with the seven-year audit retention posture in `audit.py:22`.
- Fix: Never store raw session cookies. Store a request ID, or an HMAC/hash of a non-secret session identifier, and redact any supplied `X-Session-Id` before persistence.
- How to verify: Exercise a mutating `/api/v1` route with a session cookie and confirm the audit row contains only a generated or hashed identifier.

### HIGH - Expanded schema has no migration path

- Domains: Quality, Infra
- Evidence: `database.py:126-139` uses `metadata.create_all` and `Base.metadata.create_all`; there is no Alembic or `ALTER TABLE` migration path (`rg` found no migration tooling). New runtime code relies on added columns such as `models.py:480-482` (`CaseDocument.file_bytes`) and many new ORM tables.
- Impact: Fresh databases may work, but existing Cloud SQL databases will not receive new columns, enum constraints, or table changes. API paths can fail after deployment even though local tests pass against the in-memory fake session.
- Fix: Add versioned migrations for every new table/column/enum and make deployment run migrations before serving traffic.
- How to verify: Apply migrations to a copy of the existing production schema, then run the API smoke suite against that upgraded database.

### HIGH - Production can silently use LLM stubs instead of live APIs

- Domains: Quality, Infra
- Evidence: `ai_workflows.py:46-49` returns stub metadata when no live LLM is configured and stubs are allowed; `.env.example:19-25` defaults `IQW_ALLOW_LLM_STUBS=true`. The live adapters exist in `external_interfaces.py:230-302`, but live OpenAI/Gemini calls were not exercised in this review.
- Impact: Section recommendation, congruence, investigation plan, and judgment analysis can return empty or template output while appearing operational. This does not meet a production "real LLM API" requirement unless the deployment explicitly disables stubs and validates credentials.
- Fix: Default `IQW_ALLOW_LLM_STUBS=false` for production, add startup/readiness validation for the selected LLM provider, and add integration tests with mocked OpenAI/Gemini success and failure responses.
- How to verify: Run with `IQW_ALLOW_LLM_STUBS=false` and no LLM key; AI endpoints should fail clearly with `503`. Run with a mocked provider and confirm `llm_mode=live`.

### HIGH - Raw complaint files are stored directly in the database

- Domains: Security, Infra, Data Exposure
- Evidence: Legacy parse history stores `database.py:29` `parse_records.file_bytes`; IQW documents store `models.py:480-482` `CaseDocument.file_bytes`. Object storage interfaces are declared in `external_interfaces.py:51-52`, but `rg` shows no production use of `put_bytes` outside the stub definition.
- Impact: Large PDFs and evidence documents increase DB size, backup exposure, retention complexity, and breach blast radius for sensitive complaint data.
- Fix: Move raw files to encrypted object storage with per-object access controls, retention/deletion policy, and DB references; reserve DB columns for hashes and metadata.
- How to verify: Upload a document and confirm the DB row stores a storage key plus hash, not raw bytes; verify delete removes or tombstones the object per policy.

### MEDIUM - LLM provider failures are not normalized by AI endpoints

- Domains: Quality, API
- Evidence: `ai_workflows.py:50-55` re-raises `ExternalServiceError` for configured provider failures. `api_v1.py:1238-1258`, `api_v1.py:1313-1323`, and `api_v1.py:1371-1398` call the workflows without catching that exception, while OCR review handles provider errors explicitly at `api_v1.py:1601-1604`.
- Impact: Invalid keys, provider outages, or malformed provider JSON can surface as generic 500 responses and may miss the standard API error envelope.
- Fix: Catch `ExternalServiceError` around all LLM-backed endpoints and return `SERVICE_UNAVAILABLE` with safe operator text; add failure-path tests.
- How to verify: Mock OpenAI/Gemini to return an HTTP error and confirm each AI endpoint returns a structured `503`.

### MEDIUM - PWA static icon path is not served or packaged

- Domains: UI, Infra
- Evidence: `manifest.json:11-18` and `sw.js:1-6` reference `/static/icons/iqw-icon.svg`; `app.py:389-411` serves only `/manifest.json` and `/sw.js`; `Dockerfile:39` copies only `index.html manifest.json sw.js`.
- Impact: The service worker `cache.addAll` can fail on install when `/static/icons/iqw-icon.svg` returns 404, and packaged Docker images omit the icon asset.
- Fix: Serve `/static` with `StaticFiles` and copy `static/` into the Docker image, or remove the asset from the service worker cache list.
- How to verify: Start the Docker image and request `/static/icons/iqw-icon.svg`; confirm HTTP 200 and successful service worker installation in browser devtools.

### MEDIUM - JWT refresh token is stored in localStorage

- Domains: Security, UI
- Evidence: `index.html:5702-5723` stores and retrieves `iqw_refresh_token` from `localStorage`.
- Impact: Any XSS or malicious browser extension can steal a persistent refresh token. The current review did not find a confirmed XSS, but the storage choice raises the impact of any future frontend injection bug.
- Fix: Use secure, HttpOnly, SameSite cookies for refresh tokens, or keep short-lived access tokens in memory and require re-authentication.
- How to verify: After login, inspect browser storage and confirm no refresh token is present in `localStorage`.

### MEDIUM - Core files are far beyond maintainable size thresholds

- Domains: Coding Standards, Quality, UI
- Evidence: `wc -l` reported `complaint_parsing.py` 5022 lines, `index.html` 9711 lines, `api_v1.py` 1633 lines, `models.py` 1046 lines, and `cases.py` 909 lines.
- Impact: Large mixed-responsibility files make review, testing, and regression containment harder. This is especially risky now that BRD modules, live integrations, and legacy parser paths coexist.
- Fix: Split route groups, service adapters, parser stages, and frontend views into smaller modules with focused tests.
- How to verify: Keep core modules below agreed thresholds or document explicit exceptions with ownership and test boundaries.

## Blocked Checks

- Live Google Document AI OCR was not exercised; no live GCP processor credentials were used.
- Live OpenAI/Gemini LLM workflows were not exercised; no provider call was made with real keys during this review.
- HRMS, CCTNS, DSC, object storage, and notification gateways were reviewed as code/config boundaries only; no external system endpoints were available for smoke testing.
- Docker build and Cloud Run deployment were not run in this review pass.
- Browser accessibility/responsive screenshots were not run; frontend verification was limited to static inspection and inline script syntax.
- Local Python is `3.9.13`; Docker targets Python `3.12-slim`, so local test execution did not exactly match the container runtime.

## Verification

- `python -m py_compile external_interfaces.py ai_workflows.py api_v1.py cases.py` - passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` - 284 passed, 492 warnings in 27.71s.
- `python -m unittest discover -s tests -v` - ran 284 tests in 13.124s, OK.
- Inline JS syntax check with `new Function(...)` - `inline script syntax ok`.
- Tooling present: Python 3.9.13, Docker 29.1.3, Google Cloud SDK 561.0.0.

## Domain Scorecard

| Domain | Status | Reason |
| --- | --- | --- |
| Coding Standards | NEEDS-WORK | Tests pass, but major files are monolithic and migration/release hygiene is incomplete. |
| Quality | AT-RISK | BRD workflows are broader now, but live LLM/OCR behavior is not integration-verified and stubs can mask missing providers. |
| Security | AT-RISK | JWT fallback secret and raw session-cookie audit persistence must be fixed before production. |
| UI | CONDITIONAL | Static syntax is clean and accessibility primitives exist, but PWA asset serving and token storage need correction. |
| Infra | NOT-READY | No schema migrations, raw blob storage in DB, and live external dependencies were not smoke-tested. |

## Final Verdict

FAIL for production release.

The implementation has materially improved BRD coverage and all local automated tests pass, but the high-severity security and deployment-readiness issues above make a production release unsafe until they are remediated and re-verified.
