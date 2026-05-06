# Local Deployment Report

Date: 2026-03-22
Target: `police-complaints`
Status: `READY-FOR-MANUAL-TEST`

## What I Started

Command:

```bash
env -u GOOGLE_APPLICATION_CREDENTIALS \
    -u OPENAI_API_KEY \
    -u OPENAI_TRANSLATION_API_KEY \
    -u DOC_AI_PROJECT_ID \
    -u DOC_AI_PROCESSOR_ID \
    -u TRANSLATION_PROJECT_ID \
    -u TRANSLATION_PROVIDER \
    -u TRANSLATION_FALLBACK_PROVIDER \
    python3 -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Running URL:

```text
http://127.0.0.1:8000
```

Server session id: `60464`

## Preconditions Verified

- `.env` loads a valid Document AI configuration
- local credentials file exists at `credentials/wealth-report-sa.json`
- OpenAI translation key is present
- port `8000` was free before startup

## Smoke Checks Passed

- `GET /health` returned `200 OK`
- health payload reported:
  - `translation_provider=openai`
  - `translation_fallback_provider=google`
  - `openai_translation_model=gpt-5.2`
- root HTML served correctly and includes:
  - `Compliant Parser`
  - `Upload, translate, and review police complaints from one full-screen workspace.`
  - `Download Combined JSON`
- `POST /parse` with `complaints/complaint-1-hindi-handwritten.pdf` returned `200 OK`
- live parse result from local app reported:
  - `detected_language=hi`
  - `translation_status=translated`
  - `translation_provider=openai_responses`
  - `translation_model=gpt-5.2`

## Front-End Notes

- The app is serving the bulk upload UI on the root route.
- The front-end is wired to the working local backend on the same origin.
- Bulk review UI, JSON/table view toggles, PDF preview shell, and combined JSON download controls are present in the served page.

## Caveats

- Your shell has stale exported variables from the older `ta_doc_parser` setup. If you start the app manually from that shell without unsetting them, `.env` values may not take effect because `load_dotenv()` only sets missing variables.
- Local Python is `3.10.11`. It works, but Google client libraries now warn that 3.10 support ends on 2026-10-04. Move to Python 3.11+ for longer-term local stability.

## Cleanup

To stop the local server, terminate session `60464` or press `Ctrl+C` in the terminal running Uvicorn.
