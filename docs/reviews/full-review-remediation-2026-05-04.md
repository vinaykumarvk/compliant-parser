# Full Review Remediation - 2026-05-04

## Status

The full-review findings from `docs/reviews/full-review-full-repo-2026-05-04.md` have been remediated or converted into explicit release controls.

## Remediated Findings

| Finding | Remediation |
| --- | --- |
| JWT fallback development secret | `auth.py` now fails import/startup when `JWT_SECRET_KEY` or `APP_SESSION_SECRET` is missing, unless `IQW_ALLOW_INSECURE_DEV_SECRET=true` is explicitly set for throwaway local development. `.env.example` and `README.md` document `JWT_SECRET_KEY`. |
| Raw session cookies in audit logs | `audit.py` now stores a short SHA-256 derived session reference instead of the raw Starlette session cookie or caller-supplied session id. Added audit redaction tests. |
| No migration path | Added `migrations.py` with a `schema_migrations` table and idempotent migrations for storage columns and generated-document signature metadata. `database.py` runs migrations during startup initialization. |
| LLM stubs allowed by default | `IQW_ALLOW_LLM_STUBS` now defaults to `false`; `.env.example` reflects the production-safe default. LLM-backed API endpoints catch provider/config errors and return structured `SERVICE_UNAVAILABLE` responses. Automatic congruence after upload reports `Skipped`/`Failed` instead of generating fake alerts. |
| Raw file bytes in DB | Added object-storage adapters in `external_interfaces.py`. Legacy parse records and IQW case documents now store object URIs, provider, hashes, and optional KMS key references; raw DB blob columns are nullable for backward compatibility. Production requires GCS bucket configuration unless local storage is explicitly selected. |
| PWA static icon not served/packaged | `app.py` mounts `/static`, `Dockerfile` copies `static/`, and the manifest/service-worker icon path now resolves. |
| JWT refresh token in localStorage | `index.html` keeps refresh tokens in memory only; no refresh token key is written to `localStorage`. |
| Oversized core files | Added `docs/architecture/module-ownership-2026-05-04.md` to record explicit file-size exceptions, ownership boundaries, and the refactor path. |

## Verification

- `python -m py_compile auth.py audit.py external_interfaces.py migrations.py database.py models.py cases.py ai_workflows.py api_v1.py app.py` - passed.
- Inline `index.html` script syntax check - passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` - 286 passed, 491 warnings.
- `python -m unittest discover -s tests -v` - 286 tests, OK.
- Static icon smoke check: `GET /static/icons/iqw-icon.svg` returned `200 image/svg+xml`.
- Secret-policy smoke check: importing `auth` without `JWT_SECRET_KEY`/`APP_SESSION_SECRET` raises `RuntimeError`.
- LLM-stub-policy smoke check: with no provider keys and `IQW_ALLOW_LLM_STUBS=false`, section recommendation raises `ExternalServiceUnavailable`.

## Remaining Release Checks

- Run a live Google Document AI smoke test with the configured processor.
- Run live OpenAI/Gemini workflow smoke tests with production keys or a controlled staging key.
- Run a Cloud SQL migration dry run on a copy of the deployed schema.
- Run Docker build and Cloud Run smoke tests with `OBJECT_STORAGE_BUCKET`/`GCS_BUCKET` configured.
