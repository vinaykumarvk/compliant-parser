# KIS Local Deployment

## Start

```bash
cd /Users/n15318/compliant-parser/services/knowledge-intelligence-service
cp .env.example .env
uvicorn src.main:app --reload --port 8090
```

For the shared policing Cloud SQL instance, use the separate KIS database:

```env
KIS_CLOUD_SQL_CONNECTION_NAME=policing-apps:asia-southeast1:policing-db-v2
KIS_DB_NAME=police_kb
KIS_DB_USER=puda
KIS_DB_PASSWORD=<from secret manager or operator vault>
KIS_DB_IAM_AUTH=false
KIS_REQUIRE_DATABASE=true
```

If an IAM DB user is created later, omit `KIS_DB_PASSWORD` and set `KIS_DB_IAM_AUTH=true`.

The current Cloud Run deployment `police-kb` uses Secret Manager secret `police-kb-database-url` for `DATABASE_URL`. KIS accepts that deployment convention as a fallback to `KIS_DATABASE_URL`. The secret points to database `police_kb` on `policing-apps:asia-southeast1:policing-db-v2`, with password configured in the secret. Do not copy the password into source files.

## Smoke Flow

1. Create a domain with the `police_iqw_bns` template.
2. Create or confirm a knowledge base from the template.
3. Configure a domain-scoped provider allowlist.
4. Ingest BNS source text.
5. Compile a cited wiki article.
6. Create and publish a snapshot.
7. Run `/search/hybrid`.
8. Run `/reasoning/bns-mapping`.

## Test Command

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest services/knowledge-intelligence-service/tests -q
```

Use `IQW_KIS_ENABLED=true` in the compliant-parser `.env` only after the KIS service URL, API key, domain, and knowledge base are configured.

## Automatic Complaint Indexing

When `IQW_KIS_ENABLED=true`, compliant-parser queues each successfully persisted parse record for KIS indexing after `/api/parse` or `/api/parse/stream` completes.

Required compliant-parser variables:

```env
IQW_KIS_ENABLED=true
IQW_KIS_BASE_URL=http://127.0.0.1:8090
IQW_KIS_API_KEY=<service-api-key>
IQW_KIS_DOMAIN=police-iqw
IQW_KIS_KB=<knowledge-base-id>
IQW_KIS_PROVIDER=openai
IQW_KIS_MODEL=gpt-5.1
IQW_KIS_FALLBACK_ON_ERROR=true
IQW_KIS_BACKGROUND_INDEXING=true
IQW_KIS_WORKER_POLL_SECONDS=5
IQW_KIS_WORKER_LOCK_SECONDS=900
IQW_KIS_MAX_RETRIES=5
IQW_KIS_RETRY_BASE_SECONDS=60
IQW_KIS_RETRY_MAX_SECONDS=3600
IQW_KIS_AUTO_PUBLISH_SNAPSHOT=false
```

The parse endpoint saves the parse record, marks KIS indexing `pending`, and returns without waiting for KIS when `IQW_KIS_BACKGROUND_INDEXING=true`. A DB-backed worker claims due records, masks parsed complaint content before KIS source ingestion, stores the parse record ID as idempotency metadata, creates deterministic non-PII facts, promotes approved deterministic facts into the graph, compiles one source-backed wiki article, and runs KIS quality gates. Failed attempts are retried with exponential backoff until `IQW_KIS_MAX_RETRIES` is reached.

Compliant-parser persists per-record KIS status on `parse_records` (`pending`, `running`, `indexed`, `failed`, or `disabled`) with source, wiki, quality, count, privacy, retry, lock, and error summary fields. Snapshot publishing remains an explicit admin action unless `IQW_KIS_AUTO_PUBLISH_SNAPSHOT=true`.

Admin operations:

- `GET /api/v1/admin/kis/status` returns non-secret KIS health, latest snapshot, quality gates, graph counts, wiki count, fact count, and recent indexing summary when the app DB is reachable.
- `GET /api/v1/admin/kis/indexing-records` returns recent parse records with persisted KIS indexing state.
- `POST /api/v1/admin/kis/reindex/{record_id}` re-indexes one parse history record.
- `POST /api/v1/admin/kis/indexing:retry-failed` requeues failed records for background retry.
- `POST /api/v1/admin/kis/snapshots:publish` creates and publishes a new KIS snapshot only when quality gates pass.
- `GET /api/v1/admin/kis/facts?status=candidate` lists candidate KIS facts for review.
- `POST /api/v1/admin/kis/facts/{fact_id}:approve` approves and promotes a fact to the graph.
- `POST /api/v1/admin/kis/facts/{fact_id}:reject` rejects a candidate fact.

## Provider Configuration

Configure at least one domain provider allowlist and credential source before production reasoning:

```env
KIS_SELF_HOSTED_LLM_URL=http://llm-gateway.internal
KIS_OPENAI_API_KEY=
KIS_GEMINI_API_KEY=
KIS_ALLOW_LLM_STUBS=false
```

Stubs are only for tests/local dry runs. Production should leave `KIS_ALLOW_LLM_STUBS=false`.
