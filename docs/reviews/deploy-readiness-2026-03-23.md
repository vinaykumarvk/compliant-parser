# Deploy Readiness Report — 2026-03-23 (UI cleanup deploy)

## Summary

Deployed UI cleanup changes (remove Download JSON, rename Parse to Read document, replace JSON tab with Draft FIR, move FIR content to dedicated tab) plus two infrastructure fixes: resilient DB initialisation and switch to Cloud SQL proxy socket.

## Preflight

| Item | Value |
|---|---|
| Branch | `main` |
| Python | 3.10.11 (local), 3.12 (container) |
| Docker | unavailable locally (cloud-only deploy) |
| gcloud | 561.0.0 |
| Project | `policing-apps` |
| Region | `asia-southeast1` |
| Service | `police-complaints` |
| Rollback revision | `police-complaints-00012-gsn` |

## Findings

### F1: DB init crash blocks container startup (P0) — fixed

- **severity**: P0
- **confidence**: confirmed
- **status**: fixed
- **evidence**: Revision `police-complaints-00013-lkw` failed startup probe. `initialize_database()` raised on Cloud SQL Connector 403, preventing uvicorn from binding the port.
- **fix**: Wrapped `initialize_database()` in try/except in `app.py:281` so the app starts even when DB is unreachable.
- **how to verify**: App starts and serves traffic; DB failures degrade history gracefully.

### F2: Cloud SQL Python Connector 403 on policing-db-v2 (P1) — fixed

- **severity**: P1
- **confidence**: confirmed
- **status**: fixed
- **evidence**: Compute SA `809677427844-compute@developer.gserviceaccount.com` was missing `roles/cloudsql.client`. After granting the role, IAM propagation remained stalled for >10 minutes. The Cloud SQL Python Connector continued to get 403 on `sqladmin.googleapis.com`.
- **fix**: (a) Granted `roles/cloudsql.client` to the compute SA. (b) Added `DATABASE_URL` env var to connect via the Cloud Run built-in proxy Unix socket (`/cloudsql/...`), bypassing the Python Connector entirely.
- **how to verify**: `/health` returns `database_status: ok` and `database_table_ready: true`.

### F3: `--set-env-vars` wiped all Cloud Run env vars (P0) — fixed

- **severity**: P0
- **confidence**: confirmed
- **status**: fixed
- **evidence**: Revisions `00018` and `00019` failed startup with `Missing environment variables: APP_ADMIN_USERNAME, APP_ADMIN_PASSWORD, APP_SESSION_SECRET` because `--set-env-vars` replaced all vars.
- **fix**: Restored all env vars from the working revision `00017` and added `DATABASE_URL`. Previous serving revision `00017` was unaffected (traffic never routed to failed revisions).
- **how to verify**: Revision `00020` starts and serves with all env vars present.

## Build verification

- `py_compile`: all 3 source files pass
- Unit tests: 49/49 pass

## Cloud Build

- Build ID: `26aee0f7-6dca-4379-9a5e-42ec85eb6381`
- Duration: 1m50s
- Image: `asia-southeast1-docker.pkg.dev/policing-apps/policing-apps/police-complaints:latest`
- Digest: `sha256:2b66981167f2824ba5e5d358c29b4effaf3154254f138620946c7e5f95160331`

## Cloud Run deploy

- Final revision: `police-complaints-00021-bnj`
- Traffic: 100%
- Auth: IAM-authenticated (preserved)
- Ingress: all (preserved)
- Max instances: 12 (restored)

## Smoke tests

| Test | Result |
|---|---|
| `GET /health` | 200 — `status: ok`, `database_status: ok`, `database_table_ready: true` |
| `GET /` | 200 |
| `POST /api/parse` (text file) | 401 (app auth gate, expected) |
| HTML contains `Read document` | yes |
| HTML contains `Draft FIR` / `firViewBtn` | yes |
| HTML missing `Download JSON` / `jsonViewBtn` | yes |

## Rollback

```bash
gcloud run services update-traffic police-complaints \
  --to-revisions=police-complaints-00017-dd6=100 \
  --region asia-southeast1 --project policing-apps
```

## Deployed URL

https://police-complaints-809677427844.asia-southeast1.run.app

## Verdict

**READY** — App deployed, all smoke tests pass, database connected, UI changes verified in production.
