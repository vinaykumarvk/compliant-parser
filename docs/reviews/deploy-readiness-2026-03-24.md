# Deploy Readiness Report — 2026-03-24

## Release: Ensemble Translation + Pipeline Progress Display

### Preflight Context

| Item | Value |
|------|-------|
| Branch | `main` |
| Python | 3.10.11 |
| gcloud SDK | 561.0.0 |
| Active account | `vk@adssoftek.com` |
| Project | `policing-apps` |
| Region | `asia-southeast1` |
| Service | `police-complaints` |
| Rollback revision | `police-complaints-00025-8gt` |
| New revision | `police-complaints-00026-ktt` |
| Service URL | `https://police-complaints-809677427844.asia-southeast1.run.app` |
| Docker local | unavailable (daemon not running) — cloud-only deploy |
| Image | `asia-southeast1-docker.pkg.dev/policing-apps/policing-apps/police-complaints:latest` |
| Image digest | `sha256:c5caa88cc59a7344d3774d10a36459f3fec9d78ea22609576648dbc905b7f6d1` |

### Changes Deployed

| File | Summary |
|------|---------|
| `complaint_parsing.py` | Ensemble translation via `ThreadPoolExecutor` when QE enabled + 2+ providers; `progress_callback` param on `parse_document()`; timing dict in `meta.timing` |
| `app.py` | New `POST /api/parse/stream` SSE endpoint using `queue.Queue` + `asyncio.to_thread()` |
| `index.html` | Pipeline progress UI with step-by-step display, spinner animations, elapsed times; `requestParseFileStream()` SSE reader |
| `tests/test_complaint_parsing.py` | 5 new tests: ensemble picks highest, ensemble flags below threshold, QE disabled sequential, timing metadata, progress callback |
| `tests/test_app.py` | 2 new tests: stream endpoint returns SSE events, stream requires auth |

### Environment Audit

All required env vars are set on Cloud Run:

- **Auth**: `APP_ADMIN_USERNAME`, `APP_ADMIN_PASSWORD`, `APP_SESSION_SECRET`, `APP_SESSION_HTTPS_ONLY`
- **OCR**: `DOC_AI_PROJECT_ID`, `DOC_AI_LOCATION`, `DOC_AI_PROCESSOR_ID`, `DOC_AI_FIELD_MASK`, `DOC_AI_CREDENTIALS_PATH`
- **Translation**: `TRANSLATION_ENABLED`, `TRANSLATION_PROJECT_ID`, `TRANSLATION_LOCATION`, `TRANSLATION_TARGET_LANGUAGE`
- **OpenAI**: `OPENAI_API_KEY`
- **Gemini**: `GEMINI_API_KEY` (sourced from Secret Manager)
- **DB**: `DATABASE_URL`, `CLOUD_SQL_CONNECTION_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

No new env vars required for this release. No orphan config detected.

### Build Verification

| Check | Result |
|-------|--------|
| `py_compile app.py` | PASS |
| `py_compile complaint_parsing.py` | PASS |
| `py_compile database.py` | PASS |
| Tests (65 total) | 65/65 PASS in 0.7s |
| Cloud Build | SUCCESS (1m36s) |

### Smoke Tests

| Test | Endpoint | Expected | Actual | Status |
|------|----------|----------|--------|--------|
| Health check | `GET /health` | 200 + JSON | 200, `status: ok`, DB ready, all providers configured | PASS |
| Index page | `GET /` | 200 + HTML | 200, `<!doctype html>` | PASS |
| Unauth parse | `POST /api/parse` (no session) | 401 | 401 | PASS |
| Non-PDF (classic) | `POST /api/parse` | 400 | 400, "Unsupported file type" | PASS |
| Non-PDF (stream) | `POST /api/parse/stream` | 400 | 400, "Unsupported file type" | PASS |
| Unauth stream | `POST /api/parse/stream` (no session) | 401 | 401 | PASS |
| Real PDF (stream) | `POST /api/parse/stream` (complaint-5.pdf) | 200 + SSE events + done | 200, 7 progress events, `done` with full parsed output, record saved | PASS |
| Real PDF (classic) | `POST /api/parse` (complaint-5.pdf) | 200 + JSON | 200, `schema_version: 3.0`, timing present, record saved | PASS |

### Findings

#### P3 — `TRANSLATION_QE_ENABLED` is `false` in production

- **severity**: P3
- **confidence**: high
- **status**: info / as-expected
- **evidence**: `/health` response shows `translation_qe_enabled: false`
- **fix**: Set `TRANSLATION_QE_ENABLED=true` when ready to enable ensemble translation in production
- **how to verify**: `curl .../health | jq .translation_qe_enabled`

#### P3 — Docker daemon unavailable for local smoke

- **severity**: P3
- **confidence**: high
- **status**: accepted
- **evidence**: `docker ps` returns "Cannot connect to the Docker daemon"
- **fix**: Start Docker Desktop to enable local container testing
- **how to verify**: `docker ps`

### Rollback

```bash
gcloud run services update-traffic police-complaints \
  --to-revisions=police-complaints-00025-8gt=100 \
  --region asia-southeast1 \
  --project policing-apps
```

### Verdict: **READY**

- Cloud Build succeeded
- All 65 tests pass
- All 8 smoke tests pass (including real PDF parse via both endpoints)
- Backward compatibility confirmed — `/api/parse` unchanged
- New `/api/parse/stream` SSE endpoint operational
- `meta.timing` present in parsed output
- Rollback revision recorded
