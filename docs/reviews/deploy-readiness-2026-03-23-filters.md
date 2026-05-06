# Deploy Readiness Report — 2026-03-23 (Document Filters)

## Summary

Deployed enhanced document filter chips to the complaint parser UI.
Backend expanded to return filter-ready fields from JSONB; frontend
replaces the single status dropdown with a chip-based filter bar
supporting multi-select dropdowns for station, type, language, BNS
section, completeness, and status.

## Preflight

| Item              | Value                                                  |
|-------------------|--------------------------------------------------------|
| Branch            | `main`                                                 |
| Commit            | `67337dd` feat: add document filter chips              |
| Python            | 3.10.11                                                |
| Docker            | unavailable (cloud-only deploy)                        |
| gcloud            | 561.0.0, `vk@adssoftek.com`                           |
| Project           | `policing-apps`                                        |
| Region            | `asia-southeast1`                                      |
| Service           | `police-complaints`                                    |

## Env Audit

All required env vars present on the Cloud Run service. No missing or orphan config.

## Build Verification

- `py_compile` on `app.py`, `complaint_parsing.py`, `database.py`: PASS
- 49/49 unit tests: PASS

## Cloud Build

- Image: `asia-southeast1-docker.pkg.dev/policing-apps/policing-apps/police-complaints:latest`
- Build ID: `4a4f9189-fd82-4348-b79c-3aa4cf34fed3`
- Duration: 1m 43s
- Status: SUCCESS

## Deployment

- New revision: `police-complaints-00024-t6z`
- Serving: 100% traffic
- Service URL: https://police-complaints-809677427844.asia-southeast1.run.app

## Smoke Tests

| Test                        | Expected | Actual | Status |
|-----------------------------|----------|--------|--------|
| `GET /health`               | 200      | 200    | PASS   |
| `GET /`                     | HTML     | HTML   | PASS   |
| `POST /api/parse` (no auth) | 401      | 401    | PASS   |
| `GET /api/history` (no auth)| 401      | 401    | PASS   |

## Rollback

Previous revision: `police-complaints-00023-t8w`

```bash
gcloud run services update-traffic police-complaints \
  --to-revisions=police-complaints-00023-t8w=100 \
  --region asia-southeast1 --project policing-apps
```

## Verdict

**READY** — all checks passed, service healthy, filters deployed.
