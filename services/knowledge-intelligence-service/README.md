# Knowledge Intelligence Service

Standalone reusable KIS MVP service for domain-scoped knowledge bases, graph/wiki/vector retrieval, governed LLM execution, and BNS reasoning.

## Local Run

```bash
cd services/knowledge-intelligence-service
cp .env.example .env
uvicorn src.main:app --reload --port 8090
```

The service starts without external providers. `/api/v1/health` is liveness-only; `/api/v1/ready` reports database configuration/readiness without returning secrets.

## Database

For the policing-apps Cloud SQL instance, keep KIS in the separate `police_kb` logical database:

```env
KIS_CLOUD_SQL_CONNECTION_NAME=policing-apps:asia-southeast1:policing-db-v2
KIS_DB_NAME=police_kb
KIS_DB_USER=puda
KIS_DB_PASSWORD=...
KIS_DB_IAM_AUTH=false
KIS_AUTO_MIGRATE=true
KIS_REQUIRE_DATABASE=true
```

The existing Cloud Run deployment uses Secret Manager secret `police-kb-database-url` as `DATABASE_URL`, which points to `police_kb` on `policing-apps:asia-southeast1:policing-db-v2` using DB user `puda`. KIS accepts either `KIS_DATABASE_URL` or `DATABASE_URL`; `postgresql://` and `postgres://` URLs are normalized to `postgresql+asyncpg://` at startup.

Use `KIS_DATABASE_URL=postgresql+asyncpg://...` when running through a local Cloud SQL proxy or local Postgres.

## LLM Providers

Provider configs and allowlisted models are managed per domain. Runtime API credentials can come from domain credential maintenance or from environment variables:

```env
KIS_SELF_HOSTED_LLM_URL=http://llm-gateway.internal
KIS_SELF_HOSTED_LLM_API_KEY=
KIS_OPENAI_API_KEY=
KIS_GEMINI_API_KEY=
KIS_ALLOW_LLM_STUBS=false
```

All prompt payloads are PII-masked before outbound provider calls.

## Auth

Set `KIS_API_KEYS` to a JSON object keyed by API key. Each value may include `principal_id`, `domain_id`, and `scopes`.

```json
{
  "local-dev-key": {
    "principal_id": "local-admin",
    "domain_id": "police-iqw",
    "scopes": ["domain:admin", "kb:write", "kb:read", "llm:execute"]
  }
}
```

Pass API keys as `X-API-Key`. For local-only tests, `KIS_AUTH_DISABLED=true` permits anonymous dev requests.
