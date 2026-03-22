# Compliant Parser App

This app ingests police complaint PDFs, runs OCR through Google Document AI, identifies the complaint language, optionally translates the OCR text into English, and extracts the complaint using the `5W + 1H` structure:

- `Who`
- `What`
- `When`
- `Where`
- `Why`
- `How`

The current parser is designed for English, Hindi, and Telugu complaints, including handwritten complaints if your OCR processor supports them.

## 1. Install dependencies

```bash
cd /Users/n15318/compliant-parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure credentials, OCR, and translation

Create `.env` with:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your-service-account.json
DOC_AI_PROJECT_ID=your-gcp-project-id
DOC_AI_LOCATION=eu
DOC_AI_PROCESSOR_ID=your-ocr-or-handwriting-processor-id
DOC_AI_MIME_TYPE=application/pdf
DOC_AI_FIELD_MASK=text
TRANSLATION_ENABLED=true
TRANSLATION_PROJECT_ID=your-gcp-project-id
TRANSLATION_LOCATION=global
TRANSLATION_TARGET_LANGUAGE=en
```

Optional:

```bash
MAX_PARSE_UPLOAD_BYTES=15728640  # 15 MB
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
```

Note: if you run Docker with `--env-file`, keep values unquoted.

Notes:

- Use a Google Document AI OCR / handwriting-capable processor, not the old fund-specific processor.
- Translation is only needed for non-English complaints. If translation is unavailable, the output will flag that in `gaps.pipeline_flags`.

## 3. Run the app

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open: `http://127.0.0.1:8000`

## 4. Run with Docker

This repository includes a production-oriented Dockerfile that:
- installs dependencies from `requirements.txt` (no `--no-deps` install shortcuts),
- copies app code and `credentials/` into the image,
- listens on Cloud Run compatible `PORT` (default `8080`).

Place the service account key at:

```bash
credentials/your-service-account.json
```

Build image:

```bash
docker build -t compliant-parser:local .
```

Run container:

```bash
docker run --rm \
  -p 8080:8080 \
  -e PORT=8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/your-service-account.json \
  -e DOC_AI_PROJECT_ID=your-gcp-project-id \
  -e DOC_AI_LOCATION=eu \
  -e DOC_AI_PROCESSOR_ID=your-ocr-or-handwriting-processor-id \
  -e DOC_AI_MIME_TYPE=application/pdf \
  -e DOC_AI_FIELD_MASK=text \
  -e TRANSLATION_ENABLED=true \
  -e TRANSLATION_PROJECT_ID=your-gcp-project-id \
  -e TRANSLATION_LOCATION=global \
  -e TRANSLATION_TARGET_LANGUAGE=en \
  compliant-parser:local
```

Health check:

```bash
curl http://127.0.0.1:8080/health
```

## 5. Use the app

1. Upload one or more police complaint PDFs.
2. Start the bulk run.
3. For each complaint, review:
   - detected language
   - translation status
   - OCR text preview
   - English text preview
   - extracted `Who / What / When / Where / Why / How`
   - gap analysis showing missing or uncertain fields
4. Download the combined JSON when you want a file-level complaint coverage export.

## 6. Cloud push targets

- Google Cloud Storage:
  - target format: `gs://bucket/path/file.json`
  - credentials: `GOOGLE_APPLICATION_CREDENTIALS` (already used for Document AI) with Storage write access
- Azure Blob Storage:
  - target format: `container/path/file.json`
  - credentials: `AZURE_STORAGE_CONNECTION_STRING`

## 7. Runtime API endpoints

- `GET /` - Upload UI
- `POST /api/parse` - Parse uploaded PDF bytes and return complaint JSON
- `POST /api/push-combined-json` - Push a combined JSON payload to GCS or Azure Blob
- `GET /health` - Runtime config health check, including translation settings
