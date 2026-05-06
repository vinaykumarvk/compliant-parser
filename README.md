# Compliant Parser App

This service ingests police complaint PDFs, runs OCR through Google Document AI, optionally translates the OCR text into English, extracts `Who / What / When / Where / Why / How`, and stores parse history plus the source PDF in Postgres / Cloud SQL.

The web UI supports:

- authenticated sign-in
- single-document parsing
- parse history browse, load, delete, and clear
- JSON / summary / table result review
- side-by-side document review with tabs for same-language OCR text, raw English translation, and refined English translation
- compare mode using fresh uploads or saved history

## 1. Install dependencies

```bash
cd /Users/n15318/compliant-parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure the environment

Create `.env` using `.env.example` as the template.

Required runtime groups:

- Operator auth:
  - `APP_ADMIN_USERNAME`
  - `APP_ADMIN_PASSWORD`
  - `APP_SESSION_SECRET`
  - `JWT_SECRET_KEY`
- OCR / AI boundary:
  - RFQ/on-prem: `IQW_OCR_PROVIDER=self_hosted`, `IQW_SELF_HOSTED_OCR_URL`
  - RFQ/on-prem: `IQW_LLM_PROVIDER=self_hosted`, `IQW_SELF_HOSTED_LLM_URL`
  - LLM privacy: `IQW_PII_ENCRYPTION_KEY`, `IQW_LLM_PRIVACY_STRICT=true`
  - Approved external fallback: `DOC_AI_PROJECT_ID`, `DOC_AI_LOCATION`, `DOC_AI_PROCESSOR_ID`, `OPENAI_API_KEY` or `GEMINI_API_KEY`
- Database:
  - local / proxy: `DATABASE_URL`
  - or Cloud Run / IAM auth: `CLOUD_SQL_CONNECTION_NAME`, `DB_USER`, `DB_NAME`

Optional runtime groups:

- `GOOGLE_APPLICATION_CREDENTIALS` for local development only
- object storage settings (`OBJECT_STORAGE_PROVIDER=minio`, `MINIO_ENDPOINT`, `MINIO_BUCKET`, or `OBJECT_STORAGE_BUCKET` / `GCS_BUCKET`, optional KMS key)
- on-prem backplanes: `OPENSEARCH_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `TEMPORAL_ADDRESS`, and pgvector-enabled Postgres
- Knowledge Intelligence Service: `IQW_KIS_ENABLED=true`, `IQW_KIS_BASE_URL`, `IQW_KIS_API_KEY`, `IQW_KIS_DOMAIN`, and `IQW_KIS_KB`
- translation settings
- external AI approval metadata (`EXTERNAL_AI_API_APPROVED`, `EXTERNAL_AI_APPROVAL_ID`, `EXTERNAL_AI_APPROVED_BY`) when Google/OpenAI/Gemini process case data in production
- `MAX_PARSE_UPLOAD_BYTES`
- `CORS_ALLOWED_ORIGINS`
- `RATE_LIMIT_RPM`
- `APP_SESSION_HTTPS_ONLY=true` when running behind HTTPS

Example:

```bash
APP_ADMIN_USERNAME=operator
APP_ADMIN_PASSWORD=change-me
APP_SESSION_SECRET=replace-with-a-long-random-secret
JWT_SECRET_KEY=replace-with-a-separate-long-random-jwt-secret

IQW_OCR_PROVIDER=self_hosted
IQW_SELF_HOSTED_OCR_URL=http://ocr-gateway.internal/ocr
IQW_LLM_PROVIDER=self_hosted
IQW_SELF_HOSTED_LLM_URL=http://llm-gateway.internal
IQW_PII_ENCRYPTION_KEY=replace-with-long-random-secret-or-fernet-key
IQW_LLM_PRIVACY_STRICT=true

# External fallback only with written approval.
DOC_AI_PROJECT_ID=your-gcp-project-id
DOC_AI_LOCATION=eu
DOC_AI_PROCESSOR_ID=your-ocr-or-handwriting-processor-id
DOC_AI_MIME_TYPE=application/pdf
DOC_AI_FIELD_MASK=text
EXTERNAL_AI_API_APPROVED=false
EXTERNAL_AI_APPROVAL_ID=
EXTERNAL_AI_APPROVED_BY=

TRANSLATION_ENABLED=true
TRANSLATION_PROVIDER=auto
TRANSLATION_FALLBACK_PROVIDER=openai
TRANSLATION_PROJECT_ID=your-gcp-project-id
TRANSLATION_LOCATION=global
TRANSLATION_TARGET_LANGUAGE=en
OPENAI_TRANSLATION_ENABLED=true
OPENAI_TRANSLATION_MODEL=gpt-5.2
OPENAI_TRANSLATION_REASONING_EFFORT=none
TRANSLATION_REFINEMENT_ENABLED=true
TRANSLATION_REFINEMENT_PROVIDER=openai
TRANSLATION_REFINEMENT_REASONING_EFFORT=medium
OPENAI_API_KEY=sk-...

IQW_KIS_ENABLED=false
IQW_KIS_BASE_URL=http://127.0.0.1:8090
IQW_KIS_DOMAIN=police-iqw
IQW_KIS_KB=
IQW_KIS_PROVIDER=self_hosted
IQW_KIS_MODEL=llama3-legal-local
IQW_KIS_BACKGROUND_INDEXING=true
IQW_KIS_MAX_RETRIES=5

OBJECT_STORAGE_PROVIDER=auto
MINIO_ENDPOINT=http://localhost:9000
MINIO_BUCKET=iqw-documents
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
OBJECT_STORAGE_KMS_KEY=onprem-hsm-key-ref
OPENSEARCH_URL=http://localhost:9200
REDIS_URL=redis://localhost:6379/0

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/police_complaints
MAX_PARSE_UPLOAD_BYTES=15728640
```

Notes:

- The app creates the `parse_records` table automatically at startup if it does not already exist.
- Versioned schema migrations are applied at startup through the `schema_migrations` table.
- Uploaded file binaries are stored through the object-storage adapter; production should use GCS.
- For Cloud Run, prefer an attached service account over a local `GOOGLE_APPLICATION_CREDENTIALS` file.
- BRD/RFQ-aligned deployments should keep OCR and LLM providers self-hosted. If Google Document AI, OpenAI, or Gemini are used for case data in production, the app requires written approval metadata before those providers are called.
- Before any LLM request, the app masks detected PII with opaque `[[PII_*]]` tokens, keeps the token map encrypted in memory, sends only the tokenized prompt, and restores tokens after the response returns. Production deployments must set `IQW_PII_ENCRYPTION_KEY`.
- If you run Docker with `--env-file`, keep values unquoted.

## 3. Run the app locally

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

The login screen uses the server-side operator credentials from `APP_ADMIN_USERNAME` and `APP_ADMIN_PASSWORD`.

## 4. Run with Docker

The Docker image:

- installs dependencies from `requirements.txt`
- copies the application source and UI into the image
- runs as a non-root user
- listens on Cloud Run compatible `PORT` (default `8080`)

If you need a local service-account file inside the container, mount it instead of expecting the image to contain `credentials/`.

Build:

```bash
docker build -t compliant-parser:local .
```

Run:

```bash
docker run --rm \
  -p 8080:8080 \
  -e PORT=8080 \
  -e APP_ADMIN_USERNAME=operator \
  -e APP_ADMIN_PASSWORD=change-me \
  -e APP_SESSION_SECRET=replace-with-a-long-random-secret \
  -e JWT_SECRET_KEY=replace-with-a-separate-long-random-jwt-secret \
  -e IQW_OCR_PROVIDER=self_hosted \
  -e IQW_SELF_HOSTED_OCR_URL=http://ocr-gateway.internal/ocr \
  -e IQW_LLM_PROVIDER=self_hosted \
  -e IQW_SELF_HOSTED_LLM_URL=http://llm-gateway.internal \
  -e DOC_AI_PROJECT_ID=your-gcp-project-id \
  -e DOC_AI_LOCATION=eu \
  -e DOC_AI_PROCESSOR_ID=your-ocr-or-handwriting-processor-id \
  -e DOC_AI_MIME_TYPE=application/pdf \
  -e DOC_AI_FIELD_MASK=text \
  -e EXTERNAL_AI_API_APPROVED=false \
  -e TRANSLATION_ENABLED=true \
  -e TRANSLATION_PROVIDER=auto \
  -e TRANSLATION_FALLBACK_PROVIDER=openai \
  -e TRANSLATION_PROJECT_ID=your-gcp-project-id \
  -e TRANSLATION_LOCATION=global \
  -e TRANSLATION_TARGET_LANGUAGE=en \
  -e OPENAI_TRANSLATION_ENABLED=true \
  -e OPENAI_TRANSLATION_MODEL=gpt-5.2 \
  -e OPENAI_TRANSLATION_REASONING_EFFORT=none \
  -e TRANSLATION_REFINEMENT_ENABLED=true \
  -e TRANSLATION_REFINEMENT_PROVIDER=openai \
  -e TRANSLATION_REFINEMENT_REASONING_EFFORT=medium \
  -e OPENAI_API_KEY=sk-... \
  -e OBJECT_STORAGE_PROVIDER=minio \
  -e MINIO_ENDPOINT=http://host.docker.internal:9000 \
  -e MINIO_BUCKET=iqw-documents \
  -e MINIO_ACCESS_KEY=minioadmin \
  -e MINIO_SECRET_KEY=minioadmin \
  -e OPENSEARCH_URL=http://host.docker.internal:9200 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e DATABASE_URL=postgresql+asyncpg://postgres:password@host.docker.internal:5432/police_complaints \
  -v /absolute/path/to/service-account.json:/var/secrets/docai.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/docai.json \
  compliant-parser:local
```

Health check:

```bash
curl http://127.0.0.1:8080/health
```

`/health` returns `200` only when Document AI config and database readiness are both healthy.

## 5. Use the app

1. Sign in with the configured operator account.
2. Upload a complaint PDF and run parse.
3. Review the JSON, summary, or table output.
4. Use the history sidebar to reopen saved parses or delete records.
5. Use compare mode to compare a complaint against another upload or a saved history item.

## 6. Runtime API endpoints

- `GET /` - authenticated operator UI
- `GET /health`
- `GET /api/health`
- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/parse`
- `POST /parse`
- `GET /api/history`
- `GET /api/history/{record_id}`
- `GET /api/history/{record_id}/pdf`
- `DELETE /api/history/{record_id}`
- `DELETE /api/history`
