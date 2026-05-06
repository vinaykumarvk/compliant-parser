# Deploy Readiness: Knowledge Intelligence Service

Date: 2026-05-05

## Target

- App: `services/knowledge-intelligence-service`
- Cloud Run service: `knowledge-intelligence-service`
- Project: `policing-apps`
- Region: `asia-southeast1`
- Cloud SQL: `policing-apps:asia-southeast1:policing-db-v2`
- Database: `police_kb`
- Runtime URL: `https://knowledge-intelligence-service-ik2uvb7epq-as.a.run.app`
- Complaint parser URL: `https://police-complaints-ik2uvb7epq-as.a.run.app`

## Confirmed Infrastructure

- Existing Cloud SQL secret `police-kb-database-url` points to database `police_kb` on `policing-apps:asia-southeast1:policing-db-v2`.
- Secret Manager contains `openai-api-key`.
- KIS secrets created or verified: `kis-api-keys`, `kis-compliant-parser-api-key`, and `kis-secret-key`.
- Secret access granted to Cloud Run service account `809677427844-compute@developer.gserviceaccount.com`.
- KIS deployment uses `KIS_ALLOW_LLM_STUBS=false`, `KIS_AUTH_DISABLED=false`, and live OpenAI provider configuration.

## Changes Completed

- Added standalone KIS Dockerfile and `.dockerignore`.
- KIS accepts deployed `DATABASE_URL` and normalizes `postgresql://` to `postgresql+asyncpg://`.
- KIS supports real self-hosted/OpenAI/Gemini provider calls behind PII masking and provider governance.
- KIS persists/hydrates state from Cloud SQL and auto-migrates the service tables.
- Hardened BNS reasoning with OpenAI structured outputs, canonical `BNS-###` code validation, legacy-shape coercion, and BNS legal-reference context pinning.
- Updated wiki quality gates so PII mask tokens such as `[[PII_PHONE_0001]]` are not treated as broken wiki links.
- Indexed live complaint-parser history uploads into KIS as masked source documents with vectors, graph facts, and source-backed wiki articles.
- Added automatic compliant-parser post-parse KIS indexing with idempotent source creation, deterministic fact/graph/wiki enrichment, and admin re-index support.
- Added KIS admin status and snapshot publish APIs under `/api/v1/admin/kis/*`.
- Added candidate-only LLM fact extraction with strict structured output and PII masking.
- Deployed compliant-parser with KIS adapter configuration and Secret Manager API key binding.

## Local Verification

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest services/knowledge-intelligence-service/tests -q
# 53 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_kis_client.py tests/test_ai_workflows.py tests/test_external_interfaces.py -q
# 11 passed

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_kis_client.py tests/test_kis_admin.py tests/test_external_interfaces.py tests/test_app.py::AppEndpointTests -q
# 29 passed
```

## KIS Deployment

Command executed:

```bash
gcloud run deploy knowledge-intelligence-service \
  --project=policing-apps \
  --region=asia-southeast1 \
  --source=services/knowledge-intelligence-service \
  --allow-unauthenticated \
  --add-cloudsql-instances=policing-apps:asia-southeast1:policing-db-v2 \
  --memory=1Gi \
  --cpu=1 \
  --set-env-vars=KIS_REQUIRE_DATABASE=true,KIS_AUTO_MIGRATE=true,KIS_AUTH_DISABLED=false,KIS_ALLOW_LLM_STUBS=false,KIS_DEFAULT_PROVIDER=openai,KIS_OPENAI_BASE_URL=https://api.openai.com/v1 \
  --set-secrets=DATABASE_URL=police-kb-database-url:latest,OPENAI_API_KEY=openai-api-key:latest,KIS_API_KEYS=kis-api-keys:latest,KIS_SECRET_KEY=kis-secret-key:latest \
  --quiet
```

Result:

- Latest revision after remediation: `knowledge-intelligence-service-00008-kvj`
- Traffic: 100 percent
- Status: deployed

Seeded live KIS state:

- Domain: `police-iqw`
- Knowledge base: `kb_0873ac3ae2b14e8d`
- Provider: `openai`
- Source: `src_e25c50b1aba84a13`
- Wiki article: `wiki_ecf280a9b2c84891`
- Published snapshot: `snap_284e1a22949b48c9`

## KIS Cloud Smoke

Executed live smoke against `https://knowledge-intelligence-service-ik2uvb7epq-as.a.run.app`.

Results:

- `/api/v1/health`: 200, service `knowledge-intelligence-service`, version `0.1.0`
- `/api/v1/ready`: 200, database status `ok`, connection `direct_url`, database `police_kb`, OpenAI configured `true`
- `/search/hybrid`: 200, 10 results, source counts `vector=10`, `fact=10`, `wiki=10`, `graph=0`
- `/reasoning/bns-mapping`: 200, run `completed`, provider `openai`, model `gpt-5.1`, mode `live`, result source `llm`, raw PII sent to LLM `false`, primary section `BNS-303`
- Reasoning context includes pinned BNS legal reference context: `legal_reference=1`

## Uploaded Document Indexing

Processed live complaint-parser history uploads into KIS:

- History records seen: 15
- Indexed source documents added: 15
- Total KIS source documents after indexing: 16
- Total vector chunks after indexing: 218
- Facts promoted into graph: 74
- Graph manifest: 28 nodes
- Wiki articles after indexing: 16
- Published indexed snapshot: `snap_6dda64110a6a447e`
- Snapshot quality gates: pass

Quality checks:

- `citation_coverage`: pass
- `broken_wiki_links`: pass
- `low_confidence_graph_edges`: pass
- `active_fact_contradictions`: pass
- `required_evaluation_set`: pass

## Complaint Parser Wiring

Command executed:

```bash
gcloud run deploy police-complaints \
  --project=policing-apps \
  --region=asia-southeast1 \
  --source=. \
  --allow-unauthenticated \
  --service-account=809677427844-compute@developer.gserviceaccount.com \
  --add-cloudsql-instances=policing-apps:asia-southeast1:policing-db,policing-apps:asia-southeast1:policing-db-v2 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300 \
  --update-env-vars=IQW_KIS_ENABLED=true,IQW_KIS_BASE_URL=https://knowledge-intelligence-service-ik2uvb7epq-as.a.run.app,IQW_KIS_DOMAIN=police-iqw,IQW_KIS_KB=kb_0873ac3ae2b14e8d,IQW_KIS_PROVIDER=openai,IQW_KIS_MODEL=gpt-5.1,IQW_KIS_TIMEOUT_SECONDS=30,IQW_KIS_FALLBACK_ON_ERROR=true \
  --update-secrets=IQW_KIS_API_KEY=kis-compliant-parser-api-key:latest \
  --quiet
```

Result:

- Revision: `police-complaints-00035-txz`
- Traffic: 100 percent
- Status: deployed

## Complaint Parser Cloud Smoke

Results:

- `/health`: 200, database status `ok`, Document AI status `ok`
- `/api/v1/health`: 200
- `/api/v1/auth/login`: 200 with configured admin credential
- `/api/v1/admin/external-interfaces`: 200
- Admin AI boundary reports KIS `enabled=true`, `configured=true`, `domain_id=police-iqw`, `knowledge_base_id=kb_0873ac3ae2b14e8d`
- Admin external status reports OpenAI LLM configured `true` and Google Document AI configured `true`

## Automated Enrichment Smoke

Live smoke after automated enrichment deployment:

- `/api/v1/admin/kis/status`: 200, available `true`, quality gates `passed=true`
- Admin KIS status reported latest snapshot `snap_6dda64110a6a447e`, graph `28` nodes and `74` edges, wiki article count `16`, fact count `74`
- `/api/v1/admin/kis/reindex/{record_id}`: 200, indexed `true`, idempotent replay `true`, source `src_676b48d316254f42`
- Re-index response created deterministic enrichment summary: `fact_count=5`, wiki article `wiki_7d31c33882b447bf`
- `/reasoning/fact-extraction`: 200, live mode, candidate fact count `2`, raw PII sent to LLM `false`
- `/search/hybrid`: 200, source counts `vector=10`, `fact=10`, `wiki=10`, `graph=0`
- `/reasoning/bns-mapping`: 200, result source `llm`, mode `live`, primary section `BNS-303`, context includes `legal_reference=1`, raw PII sent to LLM `false`

## Verdict

Release readiness: `PASS`

KIS is deployed as a standalone Cloud Run service with Cloud SQL persistence, live OpenAI reasoning calls, PII masking, API-key authentication, seeded BNS knowledge, and compliant-parser integration enabled in production.
