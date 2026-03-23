# Compliant Parser App

This service ingests police complaint PDFs, runs OCR through Google Document AI, optionally translates the OCR text into English, extracts `Who / What / When / Where / Why / How`, and stores parse history plus the source PDF in Postgres / Cloud SQL.

The web UI supports:

- authenticated sign-in
- single-document parsing
- parse history browse, load, delete, and clear
- JSON / summary / table result review
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
- Document AI:
  - `DOC_AI_PROJECT_ID`
  - `DOC_AI_LOCATION`
  - `DOC_AI_PROCESSOR_ID`
- Database:
  - local / proxy: `DATABASE_URL`
  - or Cloud Run / IAM auth: `CLOUD_SQL_CONNECTION_NAME`, `DB_USER`, `DB_NAME`

Optional runtime groups:

- `GOOGLE_APPLICATION_CREDENTIALS` for local development only
- translation settings
- `MAX_PARSE_UPLOAD_BYTES`
- `CORS_ALLOWED_ORIGINS`
- `RATE_LIMIT_RPM`
- `APP_SESSION_HTTPS_ONLY=true` when running behind HTTPS

Example:

```bash
APP_ADMIN_USERNAME=operator
APP_ADMIN_PASSWORD=change-me
APP_SESSION_SECRET=replace-with-a-long-random-secret

DOC_AI_PROJECT_ID=your-gcp-project-id
DOC_AI_LOCATION=eu
DOC_AI_PROCESSOR_ID=your-ocr-or-handwriting-processor-id
DOC_AI_MIME_TYPE=application/pdf
DOC_AI_FIELD_MASK=text

TRANSLATION_ENABLED=true
TRANSLATION_PROVIDER=auto
TRANSLATION_FALLBACK_PROVIDER=openai
TRANSLATION_PROJECT_ID=your-gcp-project-id
TRANSLATION_LOCATION=global
TRANSLATION_TARGET_LANGUAGE=en
OPENAI_TRANSLATION_ENABLED=true
OPENAI_TRANSLATION_MODEL=gpt-5.2
OPENAI_TRANSLATION_REASONING_EFFORT=none
OPENAI_API_KEY=sk-...

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/police_complaints
MAX_PARSE_UPLOAD_BYTES=15728640
```

Notes:

- The app creates the `parse_records` table automatically at startup if it does not already exist.
- For Cloud Run, prefer an attached service account over a local `GOOGLE_APPLICATION_CREDENTIALS` file.
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
  -e DOC_AI_PROJECT_ID=your-gcp-project-id \
  -e DOC_AI_LOCATION=eu \
  -e DOC_AI_PROCESSOR_ID=your-ocr-or-handwriting-processor-id \
  -e DOC_AI_MIME_TYPE=application/pdf \
  -e DOC_AI_FIELD_MASK=text \
  -e TRANSLATION_ENABLED=true \
  -e TRANSLATION_PROVIDER=auto \
  -e TRANSLATION_FALLBACK_PROVIDER=openai \
  -e TRANSLATION_PROJECT_ID=your-gcp-project-id \
  -e TRANSLATION_LOCATION=global \
  -e TRANSLATION_TARGET_LANGUAGE=en \
  -e OPENAI_TRANSLATION_ENABLED=true \
  -e OPENAI_TRANSLATION_MODEL=gpt-5.2 \
  -e OPENAI_TRANSLATION_REASONING_EFFORT=none \
  -e OPENAI_API_KEY=sk-... \
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
