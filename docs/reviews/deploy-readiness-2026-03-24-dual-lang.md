# Deploy Readiness Report — 2026-03-24 (Dual-Language Extraction)

## Service

| Key | Value |
|-----|-------|
| Service name | `police-complaints` |
| Project | `policing-apps` |
| Region | `asia-southeast1` |
| Image | `asia-southeast1-docker.pkg.dev/policing-apps/policing-apps/police-complaints:latest` |
| Image digest | `sha256:2403c2113788f5607d591288e47cec20e27d8c33b79687b91664e7cb5e75ebaa` |
| Rollback revision | `police-complaints-00026-ktt` |
| New revision | `police-complaints-00027-2k9` |
| Branch | `main` |
| Commit | `4f2291a` — feat: dual-language LLM extraction and original text display |
| Service URL | `https://police-complaints-809677427844.asia-southeast1.run.app` |

## Changes

| File | Summary |
|------|---------|
| `complaint_parsing.py` | Dual-language system prompt; `original_text` param on `_extract_complaint_insights_via_openai()`; combined source text for evidence validation |
| `index.html` | CSS + JS for collapsible original-text `<details>` block in translation panel |
| `tests/test_complaint_parsing.py` | 3 new tests: dual-language prompt, single-language fallback, original-language evidence validation |
| `app.py` | Accumulated changes from previous session (filter chips, history enhancements) |
| `tests/test_app.py` | Accumulated test additions from previous session |
| `.env.example` | Doc alignment |

No new env vars required. No new pip dependencies. No new API calls.

## Phase Results

| Phase | Status | Notes |
|-------|--------|-------|
| Preflight | PASS | Git clean after commit, gcloud configured |
| Env audit | PASS | All required env vars set on Cloud Run service |
| Build verification | PASS | 3 core files compile, 68/68 tests pass (0.7s) |
| Docker build | SKIPPED | Docker daemon not running — cloud-only deploy |
| Docker smoke test | SKIPPED | Docker daemon not running — cloud-only deploy |
| Cloud build | PASS | SUCCESS in 1m41s |
| Cloud deploy | PASS | Revision `police-complaints-00027-2k9` serving 100% |
| Post-deploy smoke | PASS | All 5 checks pass (see below) |

## Smoke Tests

| Test | Endpoint | Expected | Actual | Status |
|------|----------|----------|--------|--------|
| Health check | `GET /health` | 200 + JSON | 200, `status: ok`, DB ready, all providers configured | PASS |
| Index page | `GET /` | 200 + HTML | 200, `<!doctype html>`, 270KB | PASS |
| Unauth parse | `POST /api/parse` (no session) | 401 | 401 | PASS |
| Non-PDF (authed) | `POST /api/parse` (text/plain) | 400 | 400 | PASS |
| Real Hindi PDF | `POST /api/parse` (complaint-1) | 200 + parsed output | 200, translated Hindi→English, `texts_differ: True`, `heuristic_plus_question_guided`, 4 fields accepted | PASS |

### Hindi PDF parse details (dual-language path verified)

- `translation_status`: translated (Hindi → English via OpenAI)
- `texts_differ`: True — original Hindi OCR text differs from English translation
- `extraction_strategy`: heuristic_plus_question_guided
- `accepted_fields`: who, what, when, where
- Extracted: Ramesh Kumar (complainant), theft of cash and gold, 11 March 2026, Shivaji Nagar Hyderabad

## Findings

### F1: Docker daemon unavailable (P3)

- **severity**: P3
- **confidence**: high
- **status**: ACCEPTED (cloud-only deploy)
- **evidence**: `docker ps` → "Cannot connect to the Docker daemon"
- **fix**: Start Docker Desktop if local testing needed
- **verify**: `docker ps`

## Rollback

```bash
gcloud run services update-traffic police-complaints \
  --to-revisions=police-complaints-00026-ktt=100 \
  --region asia-southeast1 \
  --project policing-apps
```

## Blocked Checks

None.

## Verdict: **READY**

- Cloud Build succeeded (1m41s)
- All 68 unit tests pass
- All 5 smoke tests pass (including real Hindi PDF parse exercising the new dual-language extraction path)
- IAM policy unchanged (`allUsers` invoker, app-level auth)
- Dual-language extraction confirmed working: Hindi OCR text and English translation both sent to LLM, `texts_differ: True`
- Rollback revision recorded: `police-complaints-00026-ktt`
