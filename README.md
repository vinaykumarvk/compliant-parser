# Intellect Document Parser App

This app lets you upload PDFs, process them through Google Document AI, and view parsed JSON with a PDF preview in the browser.

## 1. Install dependencies

```bash
cd /Users/n15318/ta_doc_parser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure credentials and Document AI settings

Create `.env` with:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/Users/n15318/Downloads/wealth-report-0f38071f8483.json
DOC_AI_PROJECT_ID=wealth-report
DOC_AI_LOCATION=eu
DOC_AI_PROCESSOR_ID=70b690b94894b43
DOC_AI_MIME_TYPE=application/pdf
DOC_AI_FIELD_MASK=text,entities,fund name, amount
```

Optional:

```bash
MAX_PARSE_UPLOAD_BYTES=15728640  # 15 MB
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
```

Note: if you run Docker with `--env-file`, keep values unquoted.

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
credentials/wealth-report-0f38071f8483.json
```

Build image:

```bash
docker build -t intellect-document-parser:local .
```

Run container:

```bash
docker run --rm \
  -p 8080:8080 \
  -e PORT=8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/wealth-report-0f38071f8483.json \
  -e DOC_AI_PROJECT_ID=wealth-report \
  -e DOC_AI_LOCATION=eu \
  -e DOC_AI_PROCESSOR_ID=70b690b94894b43 \
  -e DOC_AI_MIME_TYPE=application/pdf \
  -e DOC_AI_FIELD_MASK="text,entities,fund name, amount" \
  intellect-document-parser:local
```

Health check:

```bash
curl http://127.0.0.1:8080/health
```

## 5. Use the app

1. In **Single File** mode (default):
   - Choose one local PDF file.
   - Click **Parse Document**.
   - View parsed JSON output and PDF preview.
2. In **Bulk Processing** mode:
   - Select multiple PDF files (up to 20 files, max 15 MB each).
   - Click **Start Bulk Run**.
   - Monitor per-file status (`Queued`, `Processing`, `Success`, `Failed`) and retry failed items if needed.
   - Select any processed file to inspect:
     - extracted JSON on the left,
     - source PDF preview on the right.
   - Download all successful bulk results as one **combined JSON** file.
   - Use **Push to GCS/Azure** to upload the combined JSON to cloud storage.

## 6. Cloud push targets

- Google Cloud Storage:
  - target format: `gs://bucket/path/file.json`
  - credentials: `GOOGLE_APPLICATION_CREDENTIALS` (already used for Document AI) with Storage write access
- Azure Blob Storage:
  - target format: `container/path/file.json`
  - credentials: `AZURE_STORAGE_CONNECTION_STRING`

## 7. Runtime API endpoints

- `GET /` - Upload UI
- `POST /api/parse` - Parse uploaded PDF bytes and return parsed JSON
- `POST /api/push-combined-json` - Push a combined JSON payload to GCS or Azure Blob
- `GET /health` - Runtime config health check
