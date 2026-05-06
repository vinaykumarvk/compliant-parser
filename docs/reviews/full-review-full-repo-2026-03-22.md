# Full Review — Compliant Parser (full-repo)

**Date:** 2026-03-22  
**Target:** Full repository  
**Mode:** `fix-all`  
**Follow-up to:** full review findings recorded earlier on 2026-03-22

## Remediated Findings

### 1. Sensitive routes now require backend authentication

- domains: `Security + Quality + UI`
- severity: `CRITICAL` fixed
- evidence:
  - `app.py:193-198` enforces authenticated sessions
  - `app.py:316-356` adds `session`, `login`, and `logout` endpoints
  - `app.py:359-365` protects parse
  - `app.py:449-520` protects history, PDF fetch, and delete routes
  - `index.html:3074-3138` replaces the client-side credential check with backend session login
- impact fixed:
  - History and destructive routes are no longer public.
  - The UI login is now tied to server-side auth instead of hardcoded browser credentials.
- how to verify:
  - Anonymous `POST /api/parse` and `GET /api/history` now return `401`.
  - Session login succeeds only with configured `APP_ADMIN_USERNAME` and `APP_ADMIN_PASSWORD`.

### 2. History persistence is now explicit and the DB schema is bootstrapped at startup

- domains: `Quality + Infra`
- severity: `HIGH` fixed
- evidence:
  - `database.py:89-93` creates the required schema at startup
  - `database.py:96-125` checks DB reachability and table readiness
  - `app.py:232-237` fails startup if config/bootstrap cannot complete
  - `app.py:273-313` reports DB readiness in `/health`
  - `app.py:409-421` returns `503` when parse output cannot be saved to history
- impact fixed:
  - Parse success no longer silently hides history-write failure.
  - New environments have an in-repo schema bootstrap path.
  - Health now reflects DB readiness instead of only OCR config.
- how to verify:
  - Break DB connectivity and confirm `/health` returns `503`.
  - Force `save_parse_record()` to fail and confirm the parse route returns `503`.

### 3. Compare-from-history now loads the selected slot correctly

- domains: `UI + Quality`
- severity: `HIGH` fixed
- evidence:
  - `index.html:4898-4901` captures `selectedSlot` before closing the modal
- impact fixed:
  - Choosing a saved record in compare mode now loads it into slot A or B instead of doing nothing.
- how to verify:
  - Open compare mode, pick a history item, and confirm the slot is populated.

### 4. Malformed PDFs are rejected before OCR instead of surfacing as generic 500s

- domains: `Security + Quality + Standards`
- severity: `MEDIUM` fixed
- evidence:
  - `app.py:161-166` performs PDF signature checks
  - `app.py:373-383` rejects malformed uploads at the API boundary
  - `app.py:436-441` still maps downstream invalid-format errors to `422`
- impact fixed:
  - Obvious malformed uploads no longer fall through to Document AI.
  - Client input errors return actionable `422` responses.
- how to verify:
  - Submit `test.pdf` with fake bytes and confirm the API returns `422`.

### 5. Runtime docs and config now match the shipped app

- domains: `Standards + Quality + Infra`
- severity: `MEDIUM` fixed
- evidence:
  - `.env.example:1-15` adds required auth/session settings
  - `.env.example:45-53` makes DB setup explicit
  - `README.md:23-91` documents auth, DB, startup, and mounted credentials correctly
  - `README.md:159-170` lists only live API routes
  - `.claude/coding-standards.md:7-9`, `.claude/coding-standards.md:39-40`, `.claude/coding-standards.md:71`, `.claude/coding-standards.md:86` now reflect DB-backed history and the current `unittest` suite
- impact fixed:
  - Operators are no longer pointed at removed features or incorrect Docker behavior.
  - Review standards now describe the actual repo surface.
- how to verify:
  - Follow the README on a clean environment and confirm the documented routes all exist.

### 6. Explicit runtime env vars now take precedence over `.env`

- domains: `Quality + Infra`
- severity: `MEDIUM` fixed
- evidence:
  - `complaint_parsing.py:315` changes `load_dotenv(..., override=False)`
- impact fixed:
  - Tests and production env injection can override local `.env` values reliably.
  - Server-side auth credentials are no longer silently replaced by stale local defaults.
- how to verify:
  - Export an env var that differs from `.env`, start the app, and confirm the exported value wins.

## Verification

- `python3 -m py_compile app.py complaint_parsing.py database.py ta_doc_parsing.py tests/test_app.py tests/test_complaint_parsing.py`
  - passed
- `python3 -m unittest discover -s tests -v`
  - passed: 32 tests

## Blocked Checks

- No live Cloud SQL instance or Cloud Run deployment was exercised after the fixes.
- No browser automation or visual regression pass was run against `index.html`.
- Live OCR and translation behavior with production credentials was not revalidated end to end.
- Local verification ran on Python `3.10.11`, while the repo and Dockerfile target Python `3.12`.

## Domain Scorecard

- Coding Standards: `COMPLIANT` — auth, upload validation, and standards-doc drift were addressed.
- Quality: `SOLID` — parse persistence is explicit, session state is real, and regression coverage expanded.
- Security: `SECURE` — parse/history routes now require backend auth and the client no longer contains hardcoded credentials.
- UI: `CONDITIONAL` — the broken compare-history flow was fixed, but no browser automation pass was run.
- Infra: `CONDITIONAL` — schema bootstrap and readiness reporting were fixed, but live Cloud SQL / Cloud Run verification is still pending.

## Final Verdict

`CONDITIONAL`

The code-level blockers from the earlier full review are fixed and locally verified. Release readiness now depends on environment-specific checks that were not exercised in this pass: browser smoke testing, live Cloud SQL connectivity, and deployment validation on the target platform.
