from __future__ import annotations

import os
import json
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from complaint_parsing import (
    get_translation_config,
    load_dotenv,
    parse_document,
    process_document_bytes,
)

load_dotenv()

app = FastAPI(title="Compliant Parser", version="1.0.0")


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _get_env(key: str, default: str | None = None) -> str | None:
    value = _clean_env_value(os.getenv(key))
    if value is None or value == "":
        return default
    return value


def _get_max_upload_bytes(default_bytes: int = 15 * 1024 * 1024) -> int:
    raw_value = _get_env("MAX_PARSE_UPLOAD_BYTES")
    if not raw_value:
        return default_bytes
    try:
        return int(raw_value)
    except ValueError:
        return default_bytes


MAX_PARSE_UPLOAD_BYTES = _get_max_upload_bytes()


def get_doc_ai_config() -> dict:
    config = {
        "GOOGLE_APPLICATION_CREDENTIALS": _get_env("GOOGLE_APPLICATION_CREDENTIALS"),
        "DOC_AI_PROJECT_ID": _get_env("DOC_AI_PROJECT_ID"),
        "DOC_AI_LOCATION": _get_env("DOC_AI_LOCATION"),
        "DOC_AI_PROCESSOR_ID": _get_env("DOC_AI_PROCESSOR_ID"),
        "DOC_AI_MIME_TYPE": _get_env("DOC_AI_MIME_TYPE", "application/pdf"),
        "DOC_AI_FIELD_MASK": _get_env("DOC_AI_FIELD_MASK", "text"),
    }

    missing = [
        key
        for key in (
            "DOC_AI_PROJECT_ID",
            "DOC_AI_LOCATION",
            "DOC_AI_PROCESSOR_ID",
        )
        if not config.get(key)
    ]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    creds_path = config["GOOGLE_APPLICATION_CREDENTIALS"]
    if creds_path:
        resolved_creds_path = Path(creds_path).expanduser()
        if not resolved_creds_path.is_absolute():
            resolved_creds_path = (Path(__file__).resolve().parent / resolved_creds_path).resolve()
        if not resolved_creds_path.exists():
            raise RuntimeError(
                f"Credentials file not found: {creds_path}. "
                "Update GOOGLE_APPLICATION_CREDENTIALS in .env."
            )
        config["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved_creds_path)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config["GOOGLE_APPLICATION_CREDENTIALS"]

    return config


def _split_bucket_target(target: str, prefix: str) -> tuple[str, str]:
    value = target.strip()
    if value.startswith(prefix):
        value = value[len(prefix) :]
    value = value.lstrip("/")
    bucket, _, key = value.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid target `{target}`. Expected format: {prefix}bucket/path/file.json")
    return bucket, key


def _split_container_target(target: str) -> tuple[str, str]:
    value = target.strip()
    if value.startswith("az://"):
        value = value[len("az://") :]
    value = value.lstrip("/")
    container, _, blob_name = value.partition("/")
    if not container or not blob_name:
        raise ValueError(
            f"Invalid Azure target `{target}`. Expected format: container/path/file.json"
        )
    return container, blob_name


def _push_json_to_gcs(target: str, payload_json: str) -> dict:
    bucket_name, blob_name = _split_bucket_target(target, "gs://")
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed. Install it with `pip install google-cloud-storage`."
        ) from exc

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(payload_json, content_type="application/json")
    return {"provider": "gcs", "destination": f"gs://{bucket_name}/{blob_name}"}


def _push_json_to_azure(target: str, payload_json: str) -> dict:
    connection_string = _get_env("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING is not set for Azure pushes."
        )

    container_name, blob_name = _split_container_target(target)
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise RuntimeError(
            "azure-storage-blob is not installed. Install it with `pip install azure-storage-blob`."
        ) from exc

    service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = service_client.get_blob_client(container=container_name, blob=blob_name)
    blob_client.upload_blob(
        payload_json.encode("utf-8"),
        overwrite=True,
    )
    return {"provider": "azure", "destination": f"{container_name}/{blob_name}"}


def push_combined_json_to_cloud(provider: str, target: str, payload: dict) -> dict:
    provider_normalized = (provider or "").strip().lower()
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    if provider_normalized == "gcs":
        return _push_json_to_gcs(target, payload_json)
    if provider_normalized == "azure":
        return _push_json_to_azure(target, payload_json)

    raise ValueError(
        f"Unsupported provider `{provider}`. Use one of: gcs, azure."
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Compliant Parser</title>
  <style>
    :root {
      color-scheme: light;
      --space-1: 0.25rem;
      --space-2: 0.5rem;
      --space-3: 0.75rem;
      --space-4: 1rem;
      --space-5: 1.25rem;
      --space-6: 1.5rem;
      --space-8: 2rem;
      --radius-sm: 0.5rem;
      --radius-md: 0.75rem;
      --radius-lg: 1rem;
      --radius-xl: 1.25rem;
      --color-bg: #eef3f9;
      --color-bg-accent: #dce8f8;
      --color-surface: #ffffff;
      --color-surface-alt: #f6f9ff;
      --color-border: #c8d6ea;
      --color-text: #111827;
      --color-text-muted: #4b5563;
      --color-primary: #2563eb;
      --color-primary-hover: #1d4ed8;
      --color-primary-contrast: #ffffff;
      --color-success: #0f766e;
      --color-error: #b42318;
      --color-info: #334155;
      --focus-ring: 0 0 0 3px rgba(37, 99, 235, 0.3);
      --shadow-soft: 0 8px 24px rgba(15, 23, 42, 0.08);
      --shadow-strong: 0 18px 40px rgba(15, 23, 42, 0.16);
      --font-body: "Space Grotesk", "Segoe UI", "Avenir Next", sans-serif;
      --font-mono: "IBM Plex Mono", "SF Mono", "Menlo", monospace;
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --color-bg: #0b1220;
      --color-bg-accent: #17213a;
      --color-surface: #111b2f;
      --color-surface-alt: #0f1729;
      --color-border: #334155;
      --color-text: #e5edf8;
      --color-text-muted: #b2c0d4;
      --color-primary: #60a5fa;
      --color-primary-hover: #3b82f6;
      --color-primary-contrast: #08111f;
      --color-success: #2dd4bf;
      --color-error: #fda4af;
      --color-info: #bfdbfe;
      --focus-ring: 0 0 0 3px rgba(96, 165, 250, 0.35);
      --shadow-soft: 0 10px 24px rgba(0, 0, 0, 0.28);
      --shadow-strong: 0 22px 44px rgba(0, 0, 0, 0.4);
    }
    * {
      box-sizing: border-box;
    }
    html,
    body {
      width: 100%;
      height: 100%;
    }
    body {
      margin: 0;
      color: var(--color-text);
      background:
        radial-gradient(circle at 0% 0%, var(--color-bg-accent), transparent 44%),
        radial-gradient(circle at 100% 100%, rgba(37, 99, 235, 0.12), transparent 38%),
        var(--color-bg);
      font-family: var(--font-body);
      line-height: 1.5;
    }
    body.has-fullscreen-surface {
      overflow: hidden;
    }
    body.has-fullscreen-surface::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(2, 6, 23, 0.56);
      z-index: 1100;
    }
    .login-screen {
      min-height: 100dvh;
      display: grid;
      place-items: center;
      padding: clamp(1rem, 2vw + 0.5rem, 2rem);
    }
    .login-card {
      width: min(28rem, 100%);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-xl);
      background: color-mix(in srgb, var(--color-surface) 96%, transparent);
      box-shadow: var(--shadow-strong);
      padding: clamp(1rem, 1.6vw + 0.75rem, 1.6rem);
      display: grid;
      gap: var(--space-4);
    }
    .login-card h2 {
      margin: 0;
      font-size: clamp(1.05rem, 0.7vw + 0.95rem, 1.4rem);
      line-height: 1.2;
    }
    .login-card p {
      margin: 0;
      color: var(--color-text-muted);
      font-size: 0.92rem;
    }
    .login-heading {
      display: grid;
      gap: var(--space-2);
    }
    .login-form {
      display: grid;
      gap: var(--space-3);
    }
    .text-field {
      display: grid;
      gap: var(--space-2);
      min-width: 0;
    }
    .text-field input {
      width: 100%;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      min-height: 2.75rem;
      padding: 0.62rem 0.78rem;
      background: var(--color-surface-alt);
      color: var(--color-text);
      font: inherit;
      font-size: 0.9rem;
    }
    .text-field input:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
      border-color: var(--color-primary);
    }
    .input-with-action {
      position: relative;
      display: flex;
      align-items: center;
    }
    .input-with-action input {
      padding-right: 4.25rem;
    }
    .input-inline-btn {
      position: absolute;
      right: 0.35rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      background: var(--color-surface);
      color: var(--color-text-muted);
      font: inherit;
      font-size: 0.8rem;
      font-weight: 700;
      min-height: 2.75rem;
      padding: 0.36rem 0.62rem;
      cursor: pointer;
    }
    .input-inline-btn:hover {
      color: var(--color-text);
      border-color: color-mix(in srgb, var(--color-primary) 35%, var(--color-border));
    }
    .input-inline-btn:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
    }
    .login-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-2);
      flex-wrap: wrap;
    }
    .login-check {
      display: inline-flex;
      align-items: center;
      justify-content: flex-start;
      gap: var(--space-2);
      min-height: 2.75rem;
      min-width: 10.5rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 0.5rem 0.68rem;
      background: var(--color-surface-alt);
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--color-text);
      cursor: pointer;
    }
    .login-check[aria-checked="true"] {
      border-color: color-mix(in srgb, var(--color-primary) 45%, var(--color-border));
      background: color-mix(in srgb, var(--color-primary) 10%, var(--color-surface-alt));
    }
    .login-check .check-indicator {
      width: 1.18rem;
      height: 1.18rem;
      border: 2px solid color-mix(in srgb, var(--color-primary) 60%, var(--color-border));
      border-radius: 0.3rem;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
    }
    .login-check .check-indicator::after {
      content: "";
      width: 0.55rem;
      height: 0.55rem;
      border-radius: 0.12rem;
      background: transparent;
      transition: background 120ms ease;
    }
    .login-check[aria-checked="true"] .check-indicator::after {
      background: var(--color-primary);
    }
    .login-link {
      border: 1px solid transparent;
      border-radius: var(--radius-md);
      background: transparent;
      color: var(--color-primary);
      font: inherit;
      font-size: 0.88rem;
      font-weight: 600;
      min-height: 2.75rem;
      padding: 0.4rem 0.62rem;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      text-decoration: underline;
      text-underline-offset: 0.16em;
    }
    .login-link:hover {
      color: var(--color-primary-hover);
    }
    .login-link:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
      border-radius: var(--radius-sm);
    }
    .login-footer {
      margin-top: calc(-1 * var(--space-2));
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-2);
      flex-wrap: wrap;
    }
    .login-error {
      margin: 0;
      min-height: 1.2rem;
      color: var(--color-error);
      font-size: 0.85rem;
    }
    .app {
      min-height: 100dvh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-4);
      padding: clamp(0.875rem, 1vw + 0.5rem, 1.25rem) clamp(1rem, 2vw + 0.5rem, 2rem);
      border-bottom: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface) 92%, transparent);
      backdrop-filter: blur(8px);
    }
    .brand {
      min-width: 0;
    }
    .brand h1 {
      margin: 0;
      font-size: clamp(1.1rem, 1.2vw + 0.9rem, 1.8rem);
      line-height: 1.2;
      letter-spacing: 0.01em;
    }
    .brand p {
      margin: var(--space-1) 0 0;
      font-size: clamp(0.84rem, 0.6vw + 0.72rem, 1rem);
      color: var(--color-text-muted);
    }
    .icon-btn {
      border: 1px solid var(--color-border);
      border-radius: 999px;
      background: var(--color-surface);
      color: var(--color-text);
      min-height: 2.75rem;
      padding: 0.62rem 0.95rem;
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      font-size: 0.84rem;
      font-weight: 600;
      cursor: pointer;
      box-shadow: var(--shadow-soft);
      transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;
      white-space: nowrap;
    }
    .icon-btn:hover {
      transform: translateY(-1px);
      border-color: color-mix(in srgb, var(--color-primary) 45%, var(--color-border));
    }
    .icon-btn:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
    }
    .icon-btn svg {
      width: 1rem;
      height: 1rem;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .icon-sun {
      display: none;
    }
    :root[data-theme="dark"] .icon-moon {
      display: none;
    }
    :root[data-theme="dark"] .icon-sun {
      display: block;
    }
    .main {
      padding: clamp(0.9rem, 0.9vw + 0.65rem, 1.6rem) clamp(1rem, 2vw + 0.5rem, 2rem);
      display: grid;
      grid-template-rows: auto 1fr;
      gap: var(--space-4);
      min-height: 0;
    }
    .status-banner {
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      background: var(--color-surface);
      color: var(--color-info);
      padding: 0.7rem 0.85rem;
      font-size: 0.95rem;
      box-shadow: var(--shadow-soft);
    }
    .status-info {
      border-color: color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
      color: var(--color-info);
    }
    .status-success {
      border-color: color-mix(in srgb, var(--color-success) 40%, var(--color-border));
      color: var(--color-success);
    }
    .status-error {
      border-color: color-mix(in srgb, var(--color-error) 50%, var(--color-border));
      color: var(--color-error);
    }
    .mode-view {
      min-height: 0;
    }
    .mode-hidden {
      display: none !important;
    }
    .panel {
      min-height: 0;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-xl);
      background: var(--color-surface);
      box-shadow: var(--shadow-strong);
      padding: clamp(0.9rem, 1vw + 0.6rem, 1.4rem);
      display: flex;
      flex-direction: column;
      gap: var(--space-4);
    }
    .panel-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--space-4);
      flex-wrap: wrap;
    }
    .panel-header h2 {
      margin: 0;
      font-size: clamp(1rem, 0.75vw + 0.92rem, 1.3rem);
      line-height: 1.2;
    }
    .panel-header p {
      margin: var(--space-1) 0 0;
      color: var(--color-text-muted);
      font-size: 0.91rem;
    }
    .fullscreen-btn {
      min-width: 7.5rem;
    }
    .fullscreen-btn.is-active {
      border-color: var(--color-primary);
      background: color-mix(in srgb, var(--color-primary) 18%, var(--color-surface-alt));
    }
    .fullscreen-fab {
      position: absolute;
      top: var(--space-2);
      right: var(--space-2);
      z-index: 3;
      min-width: 8.4rem;
      box-shadow: var(--shadow-soft);
    }
    .file-field {
      display: grid;
      gap: var(--space-2);
      min-width: 0;
    }
    .field-label {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--color-text-muted);
    }
    .file-field input[type="file"] {
      width: 100%;
      border: 1px dashed var(--color-border);
      border-radius: var(--radius-md);
      padding: 0.6rem 0.65rem;
      background: var(--color-surface-alt);
      color: var(--color-text);
      font: inherit;
      cursor: pointer;
    }
    .file-field input[type="file"]:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
      border-color: var(--color-primary);
    }
    .action-group {
      display: flex;
      gap: var(--space-2);
      flex-wrap: wrap;
      align-items: center;
    }
    .push-processing-wrap {
      position: relative;
      display: inline-flex;
    }
    .push-processing-wrap[data-tooltip]:hover::after {
      content: attr(data-tooltip);
      position: absolute;
      bottom: calc(100% + 6px);
      left: 50%;
      transform: translateX(-50%);
      background: var(--color-surface-alt);
      color: var(--color-text-muted);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      padding: 0.28rem 0.6rem;
      font-size: 0.72rem;
      white-space: nowrap;
      pointer-events: none;
      z-index: 10;
    }
    .btn {
      border: 1px solid transparent;
      border-radius: var(--radius-md);
      min-height: 2.75rem;
      padding: 0.64rem 0.95rem;
      font-size: 0.92rem;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--space-2);
      cursor: pointer;
      transition: transform 120ms ease, background 120ms ease, border-color 120ms ease;
      white-space: nowrap;
    }
    .btn:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
    }
    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }
    .btn:not(:disabled):hover {
      transform: translateY(-1px);
    }
    .btn-primary {
      background: var(--color-primary);
      border-color: var(--color-primary);
      color: var(--color-primary-contrast);
      box-shadow: var(--shadow-soft);
    }
    .btn-primary:not(:disabled):hover {
      background: var(--color-primary-hover);
      border-color: var(--color-primary-hover);
    }
    .btn-secondary {
      background: var(--color-surface-alt);
      border-color: var(--color-border);
      color: var(--color-text);
    }
    .btn-secondary.is-active {
      border-color: var(--color-primary);
      background: color-mix(in srgb, var(--color-primary) 14%, var(--color-surface-alt));
      color: var(--color-text);
    }
    .btn-secondary:not(:disabled):hover {
      border-color: color-mix(in srgb, var(--color-primary) 35%, var(--color-border));
    }
    .btn svg {
      width: 1rem;
      height: 1rem;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
      flex: 0 0 auto;
    }
    .spinner {
      width: 0.95rem;
      height: 0.95rem;
      border-radius: 999px;
      border: 2px solid color-mix(in srgb, currentColor 32%, transparent);
      border-top-color: currentColor;
      animation: spin 760ms linear infinite;
      display: none;
    }
    .btn.is-loading .spinner {
      display: inline-block;
    }
    .btn.is-loading .btn-icon {
      display: none;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
    .output-pre {
      margin: 0;
      flex: 1;
      min-height: 16rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      background: var(--color-surface-alt);
      color: var(--color-text);
      padding: var(--space-4);
      overflow: auto;
      white-space: pre;
      line-height: 1.55;
      font-size: 0.86rem;
      font-family: var(--font-mono);
    }
    .json-output-shell {
      position: relative;
      min-height: 0;
      flex: 1;
      display: flex;
    }
    .json-editor {
      width: 100%;
      min-height: 16rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      background: var(--color-surface-alt);
      color: var(--color-text);
      padding: var(--space-4);
      overflow: auto;
      line-height: 1.55;
      font-size: 0.86rem;
      font-family: var(--font-mono);
      resize: vertical;
    }
    .json-editor:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
      border-color: var(--color-primary);
    }
    .data-table-shell {
      margin: 0;
      flex: 1;
      min-height: 16rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      background: var(--color-surface-alt);
      color: var(--color-text);
      padding: var(--space-3);
      overflow: auto;
      display: grid;
      gap: var(--space-3);
      align-content: start;
    }
    .data-table-section {
      display: grid;
      gap: var(--space-2);
    }
    .data-table-title {
      margin: 0;
      font-size: 0.84rem;
      color: var(--color-text-muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }
    .data-table-wrap {
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      overflow: auto;
      background: var(--color-surface);
    }
    .data-table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 0.8rem;
      min-width: 22rem;
    }
    .data-table th,
    .data-table td {
      text-align: left;
      vertical-align: top;
      padding: 0.48rem 0.56rem;
      border-bottom: 1px solid var(--color-border);
      color: var(--color-text);
      line-height: 1.4;
      word-break: break-word;
    }
    .data-table th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: color-mix(in srgb, var(--color-surface-alt) 88%, var(--color-surface));
      color: var(--color-text-muted);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      font-size: 0.72rem;
      white-space: nowrap;
    }
    .data-table th[data-col="confidence_score"],
    .data-table th[data-col="requires_review"],
    .data-table th[data-col="who"],
    .data-table th[data-col="what"],
    .data-table th[data-col="when"],
    .data-table th[data-col="where"],
    .data-table th[data-col="why"],
    .data-table th[data-col="how"],
    .data-table th[data-col="status"] {
      white-space: normal;
      min-width: 80px;
    }
    .data-table th[data-col="value"],
    .data-table td[data-col="value"],
    .data-table th[data-col="preview"],
    .data-table td[data-col="preview"],
    .data-table th[data-col="evidence"],
    .data-table td[data-col="evidence"],
    .data-table th[data-col="missing_fields"],
    .data-table td[data-col="missing_fields"],
    .data-table th[data-col="uncertain_fields"],
    .data-table td[data-col="uncertain_fields"] {
      min-width: 200px;
    }
    .data-table th[data-col="amount"],
    .data-table td[data-col="amount"] {
      min-width: 130px;
      white-space: nowrap;
    }
    .data-table tbody tr:last-child td {
      border-bottom: none;
    }
    .data-table-empty {
      margin: 0;
      border: 1px dashed var(--color-border);
      border-radius: var(--radius-md);
      padding: 0.64rem 0.7rem;
      color: var(--color-text-muted);
      font-size: 0.84rem;
      background: var(--color-surface);
    }
    .preview-shell {
      position: relative;
      flex: 1;
      min-height: 18rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      overflow: hidden;
      background: var(--color-surface-alt);
    }
    .pdf-preview {
      width: 100%;
      height: 100%;
      border: 0;
      display: none;
      background: #ffffff;
    }
    .preview-placeholder {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      padding: var(--space-6);
      text-align: center;
      font-size: 0.95rem;
      color: var(--color-text-muted);
    }
    .fullscreen-target {
      min-width: 0;
    }
    .fullscreen-target.is-fullscreen {
      position: fixed !important;
      inset: clamp(0.5rem, 1.2vw, 1rem);
      z-index: 1200;
      margin: 0 !important;
      width: auto !important;
      height: auto !important;
      max-height: none !important;
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-strong);
      padding: clamp(0.75rem, 0.7vw + 0.45rem, 1.1rem);
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
      overflow: hidden;
    }
    .fullscreen-target.is-fullscreen .json-output-shell,
    .fullscreen-target.is-fullscreen .bulk-result-shell,
    .fullscreen-target.is-fullscreen .preview-shell {
      flex: 1;
      min-height: 0;
    }
    .fullscreen-target.is-fullscreen .output-pre,
    .fullscreen-target.is-fullscreen .json-editor,
    .fullscreen-target.is-fullscreen .data-table-shell,
    .fullscreen-target.is-fullscreen .pdf-preview {
      min-height: 0;
      height: 100%;
      flex: 1;
    }
    .fullscreen-target.is-fullscreen .preview-placeholder {
      min-height: 0;
    }
    .bulk-panel {
      gap: var(--space-5);
    }
    .bulk-controls {
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--space-3);
      align-items: end;
    }
    .field-help {
      margin: 0;
      font-size: 0.82rem;
      color: var(--color-text-muted);
    }
    .field-error {
      margin: 0;
      min-height: 1.1rem;
      font-size: 0.82rem;
      color: var(--color-error);
    }
    .summary-strip {
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      background: var(--color-surface-alt);
      color: var(--color-text-muted);
      padding: 0.62rem 0.78rem;
      font-size: 0.86rem;
      line-height: 1.45;
    }
    .bulk-grid {
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--space-4);
    }
    .bulk-review-grid {
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr;
      gap: var(--space-4);
    }
    .bulk-queue-shell {
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      background: var(--color-surface-alt);
      overflow: auto;
      max-height: 38vh;
    }
    .bulk-table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      min-width: 42rem;
      font-size: 0.82rem;
    }
    .bulk-table th,
    .bulk-table td {
      text-align: left;
      vertical-align: top;
      padding: 0.58rem 0.62rem;
      border-bottom: 1px solid var(--color-border);
      color: var(--color-text);
    }
    .bulk-table th {
      position: sticky;
      top: 0;
      background: color-mix(in srgb, var(--color-surface-alt) 90%, var(--color-surface));
      z-index: 1;
      font-size: 0.78rem;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      color: var(--color-text-muted);
    }
    .bulk-table tbody tr:last-child td {
      border-bottom: none;
    }
    .bulk-table tr.is-selected td {
      background: color-mix(in srgb, var(--color-primary) 11%, var(--color-surface-alt));
    }
    .bulk-file-name {
      margin: 0;
      font-size: 0.84rem;
      font-weight: 600;
      line-height: 1.35;
      word-break: break-word;
    }
    .bulk-file-meta {
      margin: var(--space-1) 0 0;
      font-size: 0.75rem;
      color: var(--color-text-muted);
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 0.2rem 0.52rem;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .status-pill.is-queued {
      color: var(--color-info);
      border-color: color-mix(in srgb, var(--color-info) 35%, var(--color-border));
      background: color-mix(in srgb, var(--color-info) 8%, var(--color-surface-alt));
    }
    .status-pill.is-processing {
      color: var(--color-primary);
      border-color: color-mix(in srgb, var(--color-primary) 40%, var(--color-border));
      background: color-mix(in srgb, var(--color-primary) 10%, var(--color-surface-alt));
    }
    .status-pill.is-success {
      color: var(--color-success);
      border-color: color-mix(in srgb, var(--color-success) 40%, var(--color-border));
      background: color-mix(in srgb, var(--color-success) 10%, var(--color-surface-alt));
    }
    .status-pill.is-failed {
      color: var(--color-error);
      border-color: color-mix(in srgb, var(--color-error) 42%, var(--color-border));
      background: color-mix(in srgb, var(--color-error) 10%, var(--color-surface-alt));
    }
    .bulk-message {
      margin: 0;
      font-size: 0.76rem;
      color: var(--color-text-muted);
      line-height: 1.3;
      max-width: 22ch;
      word-break: break-word;
    }
    .bulk-actions {
      display: flex;
      gap: var(--space-1);
      flex-wrap: wrap;
    }
    .btn-compact {
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      background: var(--color-surface);
      color: var(--color-text);
      font-size: 0.72rem;
      font-weight: 700;
      min-height: 2.75rem;
      padding: 0.32rem 0.66rem;
      cursor: pointer;
      white-space: nowrap;
    }
    .btn-compact:focus-visible {
      outline: none;
      box-shadow: var(--focus-ring);
    }
    .btn-compact:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .btn-compact:not(:disabled):hover {
      border-color: color-mix(in srgb, var(--color-primary) 35%, var(--color-border));
      transform: translateY(-1px);
    }
    .bulk-result-pre {
      min-height: 14rem;
    }
    .bulk-result-shell {
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
    }
    .bulk-result-controls {
      justify-content: flex-end;
    }
    .visually-hidden {
      position: absolute !important;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    @media (min-width: 720px) {
      .bulk-controls {
        grid-template-columns: 1fr auto;
      }
    }
    @media (min-width: 1024px) {
      .panel {
        max-height: 100%;
      }
      .preview-shell,
      .output-pre {
        min-height: 0;
      }
      .bulk-grid {
        grid-template-columns: 1fr;
      }
      .bulk-review-grid {
        grid-template-columns: minmax(22rem, 1fr) minmax(22rem, 1fr);
      }
    }
    @media (max-width: 719px) {
      .action-group {
        width: 100%;
      }
      .action-group .btn {
        flex: 1 1 calc(50% - var(--space-2));
      }
      .bulk-controls .btn-primary {
        width: 100%;
      }
      .icon-btn #themeToggleText {
        display: none;
      }
      .bulk-table {
        min-width: 35rem;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      * {
        animation: none !important;
        transition: none !important;
      }
    }
  </style>
</head>
<body>
  <div id="loginScreen" class="login-screen">
    <section class="login-card" aria-labelledby="loginTitle">
      <div class="login-heading">
        <h2 id="loginTitle">Compliant Parser</h2>
        <p>Sign in to continue to your police complaint analysis workspace.</p>
      </div>
      <form id="loginForm" class="login-form">
        <label class="text-field" for="loginUser">
          <span class="field-label">User ID</span>
          <input id="loginUser" type="text" autocomplete="username" required aria-describedby="loginError" aria-invalid="false" />
        </label>
        <label class="text-field" for="loginPassword">
          <span class="field-label">Password</span>
          <span class="input-with-action">
            <input id="loginPassword" type="password" autocomplete="current-password" required aria-describedby="loginError" aria-invalid="false" />
            <button id="togglePasswordBtn" class="input-inline-btn" type="button" aria-label="Show password">Show</button>
          </span>
        </label>
        <div class="login-row">
          <button id="loginRemember" class="login-check" type="button" role="checkbox" aria-checked="false">
            <span class="check-indicator" aria-hidden="true"></span>
            <span>Remember me</span>
          </button>
          <button id="forgotPasswordBtn" class="login-link" type="button">Forgot password?</button>
        </div>
        <button id="loginBtn" class="btn btn-primary" type="submit" disabled>
          <span>Login</span>
        </button>
      </form>
      <div class="login-footer">
        <button id="createAccountBtn" class="login-link" type="button">Create account</button>
        <button id="helpCenterBtn" class="login-link" type="button">Need help?</button>
      </div>
      <p id="loginError" class="login-error" role="alert" aria-live="assertive"></p>
    </section>
  </div>
  <div id="appShell" class="app mode-hidden">
    <header class="topbar">
      <div class="brand">
        <h1>Compliant Parser</h1>
        <p>Upload, translate, and review police complaints from one full-screen workspace.</p>
      </div>
      <button id="themeToggle" class="icon-btn" type="button" aria-label="Toggle color theme" aria-pressed="false">
        <svg class="icon-moon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"></path>
        </svg>
        <svg class="icon-sun" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4"></circle>
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path>
        </svg>
        <span id="themeToggleText">Dark mode</span>
      </button>
    </header>
    <main class="main">
      <div id="offlineBanner" class="status-banner status-error mode-hidden" role="status" aria-live="polite">
        Offline mode detected. Parsing and cloud push are paused until connection is restored.
      </div>
      <section id="bulkView" class="mode-view">
        <article class="panel bulk-panel">
          <div class="panel-header">
            <div>
              <h2>File Selection</h2>
            </div>
          </div>
          <div class="bulk-controls">
            <label class="file-field" for="bulkFileInput">
              <span class="field-label">Complaint PDFs</span>
              <input id="bulkFileInput" type="file" accept=".pdf,application/pdf" multiple />
            </label>
          </div>
          <div class="action-group">
            <button id="bulkStartBtn" class="btn btn-primary" type="button">
              <span class="spinner" aria-hidden="true"></span>
              <svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 3h10l4 4v14H5z"></path>
                <path d="M15 3v4h4"></path>
                <path d="m10 10 5 2-5 2z"></path>
              </svg>
              <span class="btn-label">Start</span>
            </button>
            <button id="bulkStopBtn" class="btn btn-secondary" type="button">Stop After Current</button>
            <button id="bulkRetryFailedBtn" class="btn btn-secondary" type="button">Retry Failed</button>
            <button id="bulkDownloadBtn" class="btn btn-secondary" type="button">Download Combined JSON</button>
            <span class="push-processing-wrap" data-tooltip="Destination not configured">
              <button class="btn btn-secondary" type="button" disabled aria-disabled="true">Push for Processing</button>
            </span>
          </div>
          <div id="bulkSummary" class="summary-strip">No files queued yet.</div>
          <div class="bulk-grid">
            <div class="bulk-queue-shell">
              <table class="bulk-table" aria-label="File selection queue">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">File</th>
                    <th scope="col">Status</th>
                    <th scope="col">Attempts</th>
                    <th scope="col">Details</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody id="bulkTableBody">
                  <tr>
                    <td colspan="6">No files selected yet.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="bulk-review-grid">
              <div id="bulkResultShell" class="bulk-result-shell fullscreen-target">
                <div class="action-group bulk-result-controls">
                  <button id="bulkSelectedSourceBtn" class="btn btn-secondary is-active" type="button">Selected File</button>
                  <button id="bulkCombinedSourceBtn" class="btn btn-secondary" type="button">Combined JSON</button>
                  <button id="bulkJsonViewBtn" class="btn btn-secondary is-active" type="button">JSON View</button>
                  <button id="bulkTableViewBtn" class="btn btn-secondary" type="button">Table View</button>
                  <button id="bulkEditBtn" class="btn btn-secondary" type="button">Edit JSON</button>
                  <button id="bulkSaveBtn" class="btn btn-secondary mode-hidden" type="button">Save JSON</button>
                  <button id="bulkCancelBtn" class="btn btn-secondary mode-hidden" type="button">Cancel Edit</button>
                  <button id="bulkResultExpandBtn" class="btn btn-secondary fullscreen-btn" type="button" data-fullscreen-target="bulkResultShell" aria-expanded="false">Expand</button>
                </div>
                <div class="json-output-shell">
                  <pre id="bulkResultOutput" class="output-pre bulk-result-pre">{\n  "message": "Select a file row to inspect individual output."\n}</pre>
                  <textarea id="bulkResultEditor" class="json-editor bulk-result-pre mode-hidden" spellcheck="false" aria-label="Editable bulk parsed JSON"></textarea>
                  <div id="bulkResultTableView" class="data-table-shell bulk-result-pre mode-hidden" aria-live="polite"></div>
                </div>
              </div>
              <div id="bulkPdfShell" class="preview-shell fullscreen-target">
                <button id="bulkPdfExpandBtn" class="btn btn-secondary fullscreen-fab" type="button" data-fullscreen-target="bulkPdfShell" aria-expanded="false">Expand</button>
                <iframe id="bulkPdfPreview" class="pdf-preview" title="Bulk selected PDF preview"></iframe>
                <div id="bulkPdfPlaceholder" class="preview-placeholder">Select a file row to preview the corresponding PDF.</div>
              </div>
            </div>
          </div>
        </article>
      </section>
    </main>
  </div>

  <script>
    const THEME_KEY = "compliant_parser_theme";
    const APP_STATE_KEY = "compliant_parser_ui_state_v2";
    const LOGIN_REMEMBERED_USER_KEY = "compliant_parser_demo_user";
    const DEMO_USER_ID = "user123";
    const DEMO_PASSWORD = "password123";
    const BULK_MAX_FILES = 20;
    const BULK_MAX_FILE_SIZE = 15 * 1024 * 1024;
    const LOW_CONFIDENCE_THRESHOLD = 0.8;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    let statePersistenceReady = false;

    const loginScreen = document.getElementById("loginScreen");
    const appShell = document.getElementById("appShell");
    const loginForm = document.getElementById("loginForm");
    const loginUser = document.getElementById("loginUser");
    const loginPassword = document.getElementById("loginPassword");
    const loginRemember = document.getElementById("loginRemember");
    const loginBtn = document.getElementById("loginBtn");
    const togglePasswordBtn = document.getElementById("togglePasswordBtn");
    const forgotPasswordBtn = document.getElementById("forgotPasswordBtn");
    const createAccountBtn = document.getElementById("createAccountBtn");
    const helpCenterBtn = document.getElementById("helpCenterBtn");
    const loginError = document.getElementById("loginError");

    const themeToggle = document.getElementById("themeToggle");
    const themeToggleText = document.getElementById("themeToggleText");
    const offlineBanner = document.getElementById("offlineBanner");

    const bulkFileInput = document.getElementById("bulkFileInput");
    const bulkStartBtn = document.getElementById("bulkStartBtn");
    const bulkStopBtn = document.getElementById("bulkStopBtn");
    const bulkRetryFailedBtn = document.getElementById("bulkRetryFailedBtn");
    const bulkDownloadBtn = document.getElementById("bulkDownloadBtn");
    const bulkSummary = document.getElementById("bulkSummary");
    const bulkTableBody = document.getElementById("bulkTableBody");
    const bulkResultOutput = document.getElementById("bulkResultOutput");
    const bulkResultEditor = document.getElementById("bulkResultEditor");
    const bulkResultTableView = document.getElementById("bulkResultTableView");
    const bulkEditBtn = document.getElementById("bulkEditBtn");
    const bulkSaveBtn = document.getElementById("bulkSaveBtn");
    const bulkCancelBtn = document.getElementById("bulkCancelBtn");
    const bulkSelectedSourceBtn = document.getElementById("bulkSelectedSourceBtn");
    const bulkCombinedSourceBtn = document.getElementById("bulkCombinedSourceBtn");
    const bulkJsonViewBtn = document.getElementById("bulkJsonViewBtn");
    const bulkTableViewBtn = document.getElementById("bulkTableViewBtn");
    const bulkPdfPreview = document.getElementById("bulkPdfPreview");
    const bulkPdfPlaceholder = document.getElementById("bulkPdfPlaceholder");
    const fullscreenButtons = Array.prototype.slice.call(
      document.querySelectorAll("[data-fullscreen-target]")
    );

    const state = {
      bulkPreviewUrl: null,
      bulkPreviewJobId: null,
      lastStatus: {
        message: "Select police complaint PDFs and click Start.",
        kind: "info"
      },
      network: {
        isOnline: navigator.onLine
      },
      rememberUser: false,
      bulk: {
        jobs: [],
        isRunning: false,
        cancelRequested: false,
        selectedJobId: null,
        editingJobId: null,
        resultViewMode: "json",
        resultSource: "selected"
      },
      fullscreen: {
        activeTargetId: null
      }
    };

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function setStatus(message, kind) {
      state.lastStatus = {
        message: message || "",
        kind: kind || "info"
      };
    }

    function persistUiState() {
      if (!statePersistenceReady) {
        return;
      }
      try {
        const payload = {
          rememberUser: state.rememberUser,
          lastStatus: state.lastStatus,
          bulkResultViewMode: state.bulk.resultViewMode,
          bulkResultSource: state.bulk.resultSource,
          bulkSelectedJobId: state.bulk.selectedJobId,
          bulkJobs: state.bulk.jobs.map((job) => ({
            id: job.id,
            name: job.name,
            size: job.size,
            status: job.status,
            message: job.message,
            attempts: job.attempts,
            result: job.result,
            error: job.error
          }))
        };
        localStorage.setItem(APP_STATE_KEY, JSON.stringify(payload));
      } catch (_err) {
        // Ignore storage limits and private mode restrictions.
      }
    }

    function restorePersistedState() {
      let payload = null;
      try {
        const raw = localStorage.getItem(APP_STATE_KEY);
        payload = raw ? JSON.parse(raw) : null;
      } catch (_err) {
        payload = null;
      }
      if (!payload || typeof payload !== "object") {
        return;
      }

      if (payload.lastStatus && typeof payload.lastStatus === "object") {
        const message = String(payload.lastStatus.message || "");
        const kind = String(payload.lastStatus.kind || "info");
        if (message) {
          state.lastStatus = { message: message, kind: kind };
        }
      }

      if (payload.bulkResultViewMode === "table" || payload.bulkResultViewMode === "json") {
        state.bulk.resultViewMode = payload.bulkResultViewMode;
      }
      if (payload.bulkResultSource === "combined" || payload.bulkResultSource === "selected") {
        state.bulk.resultSource = payload.bulkResultSource;
      }
      if (Array.isArray(payload.bulkJobs)) {
        state.bulk.jobs = payload.bulkJobs.map((job, index) => {
          const statusValue = job && typeof job.status === "string" ? job.status : "failed";
          const requiresRequeue = statusValue === "queued" || statusValue === "processing";
          return {
            id: Number(job && job.id) || index + 1,
            file: null,
            name: String((job && job.name) || ("restored_file_" + (index + 1) + ".pdf")),
            size: Number(job && job.size) || 0,
            status: requiresRequeue ? "failed" : statusValue,
            message: requiresRequeue
              ? "Session restored. Re-upload this file to process again."
              : String((job && job.message) || "Restored from previous session."),
            attempts: Number(job && job.attempts) || 0,
            result: job ? job.result || null : null,
            error: requiresRequeue
              ? "File bytes are not retained after reload."
              : (job ? job.error || null : null)
          };
        });
      }

      if (payload.bulkSelectedJobId) {
        state.bulk.selectedJobId = Number(payload.bulkSelectedJobId) || null;
      }
      if (!state.bulk.selectedJobId && state.bulk.jobs.length) {
        state.bulk.selectedJobId = state.bulk.jobs[0].id;
      }
      if (typeof payload.rememberUser === "boolean") {
        setLoginRememberState(payload.rememberUser);
      }

      setStatus(state.lastStatus.message, state.lastStatus.kind);
      renderBulkState();
    }

    function setLoginFieldsInvalid(isInvalid) {
      const invalid = Boolean(isInvalid);
      loginUser.setAttribute("aria-invalid", String(invalid));
      loginPassword.setAttribute("aria-invalid", String(invalid));
    }

    function setLoginRememberState(isChecked) {
      state.rememberUser = Boolean(isChecked);
      loginRemember.setAttribute("aria-checked", String(state.rememberUser));
      loginRemember.classList.toggle("is-checked", state.rememberUser);
    }

    function setLoginMessage(message) {
      const text = message || "";
      loginError.textContent = text;
      setLoginFieldsInvalid(Boolean(text));
      persistUiState();
    }

    function updateLoginActionState() {
      const hasUser = (loginUser.value || "").trim().length > 0;
      const hasPassword = (loginPassword.value || "").trim().length > 0;
      loginBtn.disabled = !(hasUser && hasPassword);
    }

    function loadRememberedUser() {
      let rememberedUser = "";
      try {
        rememberedUser = localStorage.getItem(LOGIN_REMEMBERED_USER_KEY) || "";
      } catch (_err) {
        rememberedUser = "";
      }
      if (rememberedUser) {
        loginUser.value = rememberedUser;
        setLoginRememberState(true);
      } else {
        setLoginRememberState(false);
      }
      updateLoginActionState();
    }

    function saveRememberedUser(userValue, rememberUser) {
      try {
        if (rememberUser) {
          localStorage.setItem(LOGIN_REMEMBERED_USER_KEY, userValue);
        } else {
          localStorage.removeItem(LOGIN_REMEMBERED_USER_KEY);
        }
      } catch (_err) {
        // Ignore browser storage restrictions in demo mode.
      }
      persistUiState();
    }

    function updateConnectivityUI() {
      const offline = !state.network.isOnline;
      offlineBanner.classList.toggle("mode-hidden", !offline);
      updateBulkActionStates();
    }

    function togglePasswordVisibility() {
      const showing = loginPassword.type === "text";
      loginPassword.type = showing ? "password" : "text";
      togglePasswordBtn.textContent = showing ? "Show" : "Hide";
      togglePasswordBtn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      loginPassword.focus();
    }

    function handleForgotPassword() {
      setLoginMessage("Password reset is not available in this demo.");
    }

    function handleCreateAccount() {
      setLoginMessage("Account creation is not available in this demo.");
    }

    function handleHelpCenter() {
      setLoginMessage("Support is unavailable in this demo. Please contact your admin.");
    }

    function setAppAuthenticated(isAuthenticated) {
      loginScreen.classList.toggle("mode-hidden", isAuthenticated);
      appShell.classList.toggle("mode-hidden", !isAuthenticated);
      if (isAuthenticated) {
        setLoginMessage("");
        updateLoginActionState();
      } else {
        loginUser.focus();
      }
      persistUiState();
    }

    function handleLoginSubmit(event) {
      event.preventDefault();
      const userValue = (loginUser.value || "").trim();
      const passwordValue = loginPassword.value || "";
      const rememberChecked = Boolean(state.rememberUser);
      if (userValue === DEMO_USER_ID && passwordValue === DEMO_PASSWORD) {
        saveRememberedUser(userValue, rememberChecked);
        setAppAuthenticated(true);
        setStatus("Login successful. Select police complaint PDFs and click Start.", "success");
        loginForm.reset();
        loginPassword.type = "password";
        togglePasswordBtn.textContent = "Show";
        togglePasswordBtn.setAttribute("aria-label", "Show password");
        if (rememberChecked) {
          loginUser.value = userValue;
          setLoginRememberState(true);
        } else {
          setLoginRememberState(false);
        }
        updateLoginActionState();
        bulkFileInput.focus();
        return;
      }
      setLoginMessage("Invalid user ID or password.");
      loginPassword.focus();
      loginPassword.select();
    }

    function getFullscreenTargetById(targetId) {
      if (!targetId) {
        return null;
      }
      const element = document.getElementById(targetId);
      if (!element || !element.classList.contains("fullscreen-target")) {
        return null;
      }
      return element;
    }

    function setFullscreenButtonState(targetId, isActive) {
      fullscreenButtons.forEach((button) => {
        const buttonTarget = button.getAttribute("data-fullscreen-target");
        if (buttonTarget !== targetId) {
          return;
        }
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-expanded", String(isActive));
        button.textContent = isActive ? "Collapse" : "Expand";
      });
    }

    function collapseActiveFullscreenTarget() {
      const activeTargetId = state.fullscreen.activeTargetId;
      if (!activeTargetId) {
        return;
      }
      const activeTarget = getFullscreenTargetById(activeTargetId);
      if (activeTarget) {
        activeTarget.classList.remove("is-fullscreen");
      }
      setFullscreenButtonState(activeTargetId, false);
      state.fullscreen.activeTargetId = null;
      document.body.classList.remove("has-fullscreen-surface");
    }

    function toggleFullscreenTarget(targetId) {
      const target = getFullscreenTargetById(targetId);
      if (!target) {
        return;
      }
      if (state.fullscreen.activeTargetId === targetId) {
        collapseActiveFullscreenTarget();
        return;
      }
      collapseActiveFullscreenTarget();
      target.classList.add("is-fullscreen");
      state.fullscreen.activeTargetId = targetId;
      document.body.classList.add("has-fullscreen-surface");
      setFullscreenButtonState(targetId, true);
    }

    function setBulkLoading(isLoading) {
      bulkStartBtn.classList.toggle("is-loading", isLoading);
      bulkStartBtn.setAttribute("aria-busy", String(isLoading));
      persistUiState();
    }

    function applyTheme(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      const darkEnabled = theme === "dark";
      themeToggle.setAttribute("aria-pressed", String(darkEnabled));
      themeToggleText.textContent = darkEnabled ? "Light mode" : "Dark mode";
    }

    function getPreferredTheme() {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") {
        return saved;
      }
      return mediaQuery.matches ? "dark" : "light";
    }

    function initTheme() {
      applyTheme(getPreferredTheme());
    }

    function isPdfFile(file) {
      if (!file) {
        return false;
      }
      const type = (file.type || "").toLowerCase();
      const name = (file.name || "").toLowerCase();
      return type.includes("pdf") || name.endsWith(".pdf");
    }

    function clearBulkPdfPreview(message) {
      if (state.bulkPreviewUrl) {
        URL.revokeObjectURL(state.bulkPreviewUrl);
        state.bulkPreviewUrl = null;
      }
      state.bulkPreviewJobId = null;
      bulkPdfPreview.removeAttribute("src");
      bulkPdfPreview.style.display = "none";
      bulkPdfPlaceholder.textContent = message;
      bulkPdfPlaceholder.style.display = "grid";
    }

    function setBulkPdfPreview(file, jobId) {
      if (state.bulkPreviewUrl && state.bulkPreviewJobId === jobId) {
        return;
      }
      if (state.bulkPreviewUrl) {
        URL.revokeObjectURL(state.bulkPreviewUrl);
      }
      state.bulkPreviewUrl = URL.createObjectURL(file);
      state.bulkPreviewJobId = jobId;
      bulkPdfPreview.src = state.bulkPreviewUrl + "#view=FitH";
      bulkPdfPlaceholder.style.display = "none";
      bulkPdfPreview.style.display = "block";
    }

    function normalizePdfName(fileName) {
      return (fileName || "parsed_output.pdf").replace(/\\.[Pp][Dd][Ff]$/, "");
    }

    function formatBytes(value) {
      const bytes = Number(value) || 0;
      if (bytes < 1024) {
        return bytes + " B";
      }
      const kb = bytes / 1024;
      if (kb < 1024) {
        return kb.toFixed(1) + " KB";
      }
      return (kb / 1024).toFixed(1) + " MB";
    }

    function downloadJsonPayload(payload, fileName) {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const downloadUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(downloadUrl);
    }

    function buildApiUrlCandidates(endpointPath) {
      const cleanEndpoint = String(endpointPath || "")
        .replace(/^\\/+/, "")
        .replace(/\\/+/g, "/");
      if (!cleanEndpoint) {
        return ["/"];
      }

      const locationPath = String(window.location.pathname || "/");
      const basePath = locationPath.endsWith("/")
        ? locationPath
        : (locationPath.slice(0, locationPath.lastIndexOf("/") + 1) || "/");
      const baseSegments = basePath
        .split("/")
        .filter(Boolean);

      const prefixes = [];
      for (let index = baseSegments.length; index >= 0; index -= 1) {
        const joined = "/" + baseSegments.slice(0, index).join("/");
        prefixes.push(joined === "/" ? "" : joined);
      }

      const endpointVariants = [cleanEndpoint];
      if (cleanEndpoint.startsWith("api/")) {
        endpointVariants.push(cleanEndpoint.slice(4));
      } else {
        endpointVariants.push("api/" + cleanEndpoint);
      }

      const candidates = [];
      prefixes.forEach((prefix) => {
        endpointVariants.forEach((variant) => {
          if (!variant) {
            return;
          }
          candidates.push((prefix || "") + "/" + variant);
        });
      });

      return Array.from(new Set(candidates));
    }

    async function fetchWithApiFallback(endpointPath, options) {
      const candidates = buildApiUrlCandidates(endpointPath);
      let lastResponse = null;
      let lastError = null;

      for (let index = 0; index < candidates.length; index += 1) {
        const url = candidates[index];
        try {
          const response = await fetch(url, options);
          if (response.status !== 404) {
            return response;
          }
          lastResponse = response;
        } catch (err) {
          lastError = err;
        }
      }

      if (lastError) {
        throw lastError;
      }
      if (lastResponse) {
        return lastResponse;
      }
      throw new Error("No reachable API endpoint found.");
    }

    function formatCellValue(value) {
      if (value === null || value === undefined || value === "") {
        return "-";
      }
      if (Array.isArray(value)) {
        return value.length ? value.join(", ") : "-";
      }
      if (typeof value === "object") {
        try {
          return JSON.stringify(value);
        } catch (_err) {
          return String(value);
        }
      }
      return String(value);
    }

    function formatColumnLabel(columnName) {
      return String(columnName)
        .replace(/_/g, " ")
        .replace(/\\s+/g, " ")
        .trim();
    }

    function toReadableMetricLabel(metricPath) {
      if (!metricPath) {
        return "-";
      }
      const rawParts = String(metricPath)
        .split(".")
        .map((part) => part.trim())
        .filter(Boolean);
      if (!rawParts.length) {
        return String(metricPath);
      }

      const parts = rawParts;
      const labelParts = parts.map((part) => {
        const normalized = part.toLowerCase();
        if (normalized === "grand_total_amount") {
          return "Grand Total Amount";
        }
        if (normalized === "total_amount") {
          return "Total Amount";
        }
        if (normalized === "total_units") {
          return "Total Units";
        }
        if (normalized === "transaction_count") {
          return "Transaction Count";
        }
        return part
          .replace(/_/g, " ")
          .replace(/\\s+/g, " ")
          .trim()
          .replace(/\\b\\w/g, (char) => char.toUpperCase());
      });

      return labelParts.join(" ");
    }

    function buildDataTableHtml(rows, preferredColumns, emptyMessage) {
      if (!Array.isArray(rows) || !rows.length) {
        return "<p class=\\"data-table-empty\\">" + escapeHtml(emptyMessage || "No rows available.") + "</p>";
      }
      const columnSet = new Set();
      rows.forEach((row) => {
        if (row && typeof row === "object") {
          Object.keys(row).forEach((key) => columnSet.add(key));
        }
      });

      const columns = [];
      (preferredColumns || []).forEach((column) => {
        if (columnSet.has(column)) {
          columns.push(column);
          columnSet.delete(column);
        }
      });
      Array.from(columnSet)
        .sort()
        .forEach((column) => columns.push(column));

      const headerHtml = columns
        .map((column) => "<th scope=\\"col\\" data-col=\\"" + escapeHtml(column) + "\\">" + escapeHtml(formatColumnLabel(column)) + "</th>")
        .join("");
      const bodyHtml = rows
        .map((row) => {
          const cells = columns
            .map((column) => "<td data-col=\\"" + escapeHtml(column) + "\\">" + escapeHtml(formatCellValue(row && row[column])) + "</td>")
            .join("");
          return "<tr>" + cells + "</tr>";
        })
        .join("");

      return (
        "<div class=\\"data-table-wrap\\">" +
          "<table class=\\"data-table\\">" +
            "<thead><tr>" + headerHtml + "</tr></thead>" +
            "<tbody>" + bodyHtml + "</tbody>" +
          "</table>" +
        "</div>"
      );
    }

    function buildSectionTableHtml(title, rows, preferredColumns, emptyMessage) {
      return (
        "<section class=\\"data-table-section\\">" +
          "<p class=\\"data-table-title\\">" + escapeHtml(title) + "</p>" +
          buildDataTableHtml(rows, preferredColumns, emptyMessage) +
        "</section>"
      );
    }

    function flattenObjectToRows(input, prefix) {
      if (!input || typeof input !== "object" || Array.isArray(input)) {
        return [];
      }
      const rows = [];
      Object.keys(input).forEach((key) => {
        const value = input[key];
        const fieldName = prefix ? prefix + "." + key : key;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          rows.push.apply(rows, flattenObjectToRows(value, fieldName));
        } else {
          rows.push({ metric: fieldName, value: value });
        }
      });
      return rows;
    }

    function formatScoreValue(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return value === undefined || value === null || value === "" ? "-" : String(value);
      }
      return numeric.toFixed(2);
    }

    function toYesNoValue(value) {
      if (value === true) {
        return "Yes";
      }
      if (value === false) {
        return "No";
      }
      return value === undefined || value === null || value === "" ? "-" : String(value);
    }

    function truncateText(value, maxLength) {
      const text = value === undefined || value === null ? "" : String(value).trim();
      if (!text) {
        return null;
      }
      if (text.length <= maxLength) {
        return text;
      }
      return text.slice(0, maxLength - 1) + "…";
    }

    function getComplaintField(parsedOutput, fieldName) {
      const complaint = parsedOutput && typeof parsedOutput.complaint === "object"
        ? parsedOutput.complaint
        : {};
      const field = complaint && typeof complaint[fieldName] === "object"
        ? complaint[fieldName]
        : {};
      return field || {};
    }

    function buildComplaintCoverageRow(parsedOutput, extraFields) {
      const language = parsedOutput && typeof parsedOutput.language === "object"
        ? parsedOutput.language
        : {};
      const gaps = parsedOutput && typeof parsedOutput.gaps === "object"
        ? parsedOutput.gaps
        : {};
      const confidence = parsedOutput && typeof parsedOutput.confidence === "object"
        ? parsedOutput.confidence
        : {};
      const row = {
        detected_language: language.detected_name || language.detected || "-",
        translation_status: language.translation_status || "-",
        who: getComplaintField(parsedOutput, "who").status || "missing",
        what: getComplaintField(parsedOutput, "what").status || "missing",
        when: getComplaintField(parsedOutput, "when").status || "missing",
        where: getComplaintField(parsedOutput, "where").status || "missing",
        why: getComplaintField(parsedOutput, "why").status || "missing",
        how: getComplaintField(parsedOutput, "how").status || "missing",
        missing_fields: Array.isArray(gaps.missing_fields) ? gaps.missing_fields : [],
        uncertain_fields: Array.isArray(gaps.uncertain_fields) ? gaps.uncertain_fields : [],
        completeness_score: formatScoreValue(gaps.completeness_score),
        average_confidence: formatScoreValue(confidence.average_score),
        requires_review: toYesNoValue(gaps.requires_review)
      };
      if (extraFields && typeof extraFields === "object") {
        Object.keys(extraFields).forEach((key) => {
          row[key] = extraFields[key];
        });
      }
      return row;
    }

    function extractComplaintFieldRows(parsedOutput) {
      return ["who", "what", "when", "where", "why", "how"].map((fieldName) => {
        const field = getComplaintField(parsedOutput, fieldName);
        return {
          field: toReadableMetricLabel(fieldName),
          status: field.status || "missing",
          value: field.value || null,
          confidence_score: formatScoreValue(field.confidence_score),
          evidence: Array.isArray(field.evidence) ? field.evidence : []
        };
      });
    }

    function extractWhoComponentRows(parsedOutput) {
      const whoField = getComplaintField(parsedOutput, "who");
      const components = whoField && typeof whoField.components === "object"
        ? whoField.components
        : {};
      return ["complainant", "victim", "accused", "witnesses"].map((role) => {
        const component = components && typeof components[role] === "object"
          ? components[role]
          : {};
        return {
          role: toReadableMetricLabel(role),
          status: component.status || "missing",
          values: Array.isArray(component.values) ? component.values : [],
          inferred: component.inferred === true
            ? "Yes"
            : component.inferred === false
              ? "No"
              : "-"
        };
      });
    }

    function extractWhenComponentRows(parsedOutput) {
      const whenField = getComplaintField(parsedOutput, "when");
      const components = whenField && typeof whenField.components === "object"
        ? whenField.components
        : {};
      return ["date", "time"].map((part) => {
        const component = components && typeof components[part] === "object"
          ? components[part]
          : {};
        return {
          component: toReadableMetricLabel(part),
          status: component.status || "missing",
          value: component.value || null
        };
      });
    }

    function buildGapRows(parsedOutput) {
      const gaps = parsedOutput && typeof parsedOutput.gaps === "object"
        ? parsedOutput.gaps
        : {};
      const language = parsedOutput && typeof parsedOutput.language === "object"
        ? parsedOutput.language
        : {};
      return [
        { metric: "Available Fields", value: Array.isArray(gaps.available_fields) ? gaps.available_fields : [] },
        { metric: "Missing Fields", value: Array.isArray(gaps.missing_fields) && gaps.missing_fields.length ? gaps.missing_fields : "None" },
        { metric: "Uncertain Fields", value: Array.isArray(gaps.uncertain_fields) && gaps.uncertain_fields.length ? gaps.uncertain_fields : "None" },
        { metric: "Pipeline Flags", value: Array.isArray(gaps.pipeline_flags) && gaps.pipeline_flags.length ? gaps.pipeline_flags : "None" },
        { metric: "Completeness Score", value: formatScoreValue(gaps.completeness_score) },
        { metric: "Requires Review", value: toYesNoValue(gaps.requires_review) },
        { metric: "Gap Summary", value: gaps.summary || "-" },
        { metric: "Translation Error", value: language.translation_error || "None" }
      ];
    }

    function buildTextPreviewRows(parsedOutput) {
      const text = parsedOutput && typeof parsedOutput.text === "object"
        ? parsedOutput.text
        : {};
      return [
        { source: "OCR Text", preview: truncateText(text.ocr_text, 320) || "-" },
        { source: "English Text", preview: truncateText(text.english_text, 320) || "-" }
      ];
    }

    function buildSelectedComplaintSummaryRows(selected, payload) {
      const language = payload && typeof payload.language === "object"
        ? payload.language
        : {};
      const gaps = payload && typeof payload.gaps === "object"
        ? payload.gaps
        : {};
      const confidence = payload && typeof payload.confidence === "object"
        ? payload.confidence
        : {};
      const meta = payload && typeof payload.meta === "object"
        ? payload.meta
        : {};
      const assessment = meta && typeof meta.complaint_assessment === "object"
        ? meta.complaint_assessment
        : {};
      return [
        { field: "File Name", value: selected.name },
        { field: "Status", value: selected.status },
        { field: "Attempts", value: selected.attempts },
        { field: "Document Type", value: payload.document_type || "-" },
        { field: "Detected Language", value: language.detected_name || language.detected || "-" },
        { field: "Translation Status", value: language.translation_status || "-" },
        { field: "Translation Provider", value: language.translation_provider || "-" },
        { field: "Completeness Score", value: formatScoreValue(gaps.completeness_score) },
        { field: "Avg. Field Confidence", value: formatScoreValue(confidence.average_score) },
        { field: "Requires Review", value: toYesNoValue(gaps.requires_review) },
        { field: "Likely Police Complaint", value: toYesNoValue(assessment.likely_police_complaint) }
      ];
    }

    function renderBulkResultTableView() {
      if (state.bulk.resultSource === "combined") {
        const combinedPayload = buildCombinedBulkPayload();
        if (!combinedPayload) {
          bulkResultTableView.innerHTML = "<p class=\\"data-table-empty\\">No successful bulk results available yet.</p>";
          return;
        }
        const summaryRows = [
          { field: "Generated At", value: combinedPayload.generated_at || "-" },
          { field: "Total Files", value: combinedPayload.total_files || 0 },
          { field: "Total Results", value: combinedPayload.total_results || 0 },
          { field: "Failed Count", value: combinedPayload.failed_count || 0 }
        ];

        const resultItems = Array.isArray(combinedPayload.results) ? combinedPayload.results : [];
        const combinedRows = resultItems.map((item) => {
          const parsedOutput = item && item.parsed_output ? item.parsed_output : null;
          return buildComplaintCoverageRow(parsedOutput, {
            file_name: item ? item.file_name : null
          });
        });

        const completenessScores = combinedRows
          .map((row) => Number(row && row.completeness_score))
          .filter((value) => Number.isFinite(value));
        const confidenceScores = combinedRows
          .map((row) => Number(row && row.average_confidence))
          .filter((value) => Number.isFinite(value));
        summaryRows.push(
          {
            field: "Avg. Completeness Score",
            value: completenessScores.length
              ? (completenessScores.reduce((acc, value) => acc + value, 0) / completenessScores.length).toFixed(2)
              : "-"
          },
          {
            field: "Avg. Field Confidence",
            value: confidenceScores.length
              ? (confidenceScores.reduce((acc, value) => acc + value, 0) / confidenceScores.length).toFixed(2)
              : "-"
          }
        );

        const failedRows = Array.isArray(combinedPayload.failed_files) ? combinedPayload.failed_files : [];
        bulkResultTableView.innerHTML =
          buildSectionTableHtml("Combined Summary", summaryRows, ["field", "value"], "No summary available.") +
          buildSectionTableHtml(
            "Complaint Coverage",
            combinedRows,
            ["file_name", "detected_language", "translation_status", "who", "what", "when", "where", "why", "how", "missing_fields", "uncertain_fields", "completeness_score", "average_confidence", "requires_review"],
            "No complaint analysis available in combined output."
          ) +
          buildSectionTableHtml("Failed Files", failedRows, ["file_name", "error"], "No failed files.");
        return;
      }

      const selected = getBulkJobById(state.bulk.selectedJobId);
      if (!selected) {
        bulkResultTableView.innerHTML = "<p class=\\"data-table-empty\\">Select a file row to view table output.</p>";
        return;
      }
      if (selected.status !== "success" || !selected.result) {
        bulkResultTableView.innerHTML = "<p class=\\"data-table-empty\\">Selected file does not have parsed output yet.</p>";
        return;
      }

      const payload = selected.result;
      const summaryRows = buildSelectedComplaintSummaryRows(selected, payload);
      const complaintFieldRows = extractComplaintFieldRows(payload);
      const whoComponentRows = extractWhoComponentRows(payload);
      const whenComponentRows = extractWhenComponentRows(payload);
      const gapRows = buildGapRows(payload);
      const textPreviewRows = buildTextPreviewRows(payload);
      bulkResultTableView.innerHTML =
        buildSectionTableHtml("Selected File Summary", summaryRows, ["field", "value"], "No summary data.") +
        buildSectionTableHtml(
          "5W + 1H Fields",
          complaintFieldRows,
          ["field", "status", "value", "confidence_score", "evidence"],
          "No complaint fields available."
        ) +
        buildSectionTableHtml(
          "Who Components",
          whoComponentRows,
          ["role", "status", "values", "inferred"],
          "No identified people available."
        ) +
        buildSectionTableHtml(
          "When Components",
          whenComponentRows,
          ["component", "status", "value"],
          "No incident timing details available."
        ) +
        buildSectionTableHtml(
          "Gap Analysis",
          gapRows,
          ["metric", "value"],
          "No gap analysis available."
        ) +
        buildSectionTableHtml(
          "Text Preview",
          textPreviewRows,
          ["source", "preview"],
          "No text preview available."
        );
    }

    function setBulkResultSource(source) {
      const resolved = source === "combined" ? "combined" : "selected";
      if (resolved === "combined") {
        state.bulk.editingJobId = null;
      }
      state.bulk.resultSource = resolved;
      renderBulkDetails();
      persistUiState();
    }

    function setBulkResultViewMode(mode) {
      const resolved = mode === "table" ? "table" : "json";
      if (resolved === "table") {
        state.bulk.editingJobId = null;
      }
      state.bulk.resultViewMode = resolved;
      renderBulkDetails();
      persistUiState();
    }

    function getBulkJobById(jobId) {
      return state.bulk.jobs.find((job) => job.id === jobId) || null;
    }

    function updateBulkEditorState() {
      const selected = getBulkJobById(state.bulk.selectedJobId);
      const hasSelectedResult = Boolean(selected && selected.status === "success" && selected.result);
      const combinedPayload = buildCombinedBulkPayload();
      const hasCombinedResult = Boolean(combinedPayload);
      const isSelectedSource = state.bulk.resultSource === "selected";
      const isJsonView = state.bulk.resultViewMode === "json";
      const canEditSelected = Boolean(isSelectedSource && isJsonView && hasSelectedResult);
      const isEditingSelected = Boolean(
        canEditSelected &&
        selected &&
        state.bulk.editingJobId === selected.id
      );
      if (!isEditingSelected || !isSelectedSource || !isJsonView) {
        state.bulk.editingJobId = null;
      }

      bulkSelectedSourceBtn.classList.toggle("is-active", isSelectedSource);
      bulkCombinedSourceBtn.classList.toggle("is-active", !isSelectedSource);
      bulkJsonViewBtn.classList.toggle("is-active", isJsonView);
      bulkTableViewBtn.classList.toggle("is-active", !isJsonView);

      bulkSelectedSourceBtn.disabled = false;
      bulkCombinedSourceBtn.disabled = !hasCombinedResult;
      bulkJsonViewBtn.disabled = isSelectedSource ? !hasSelectedResult : !hasCombinedResult;
      bulkTableViewBtn.disabled = isSelectedSource ? !hasSelectedResult : !hasCombinedResult;

      const isTableView = !isJsonView;
      bulkResultTableView.classList.toggle("mode-hidden", !isTableView);
      bulkResultOutput.classList.toggle("mode-hidden", isTableView || isEditingSelected);
      bulkResultEditor.classList.toggle("mode-hidden", isTableView || !isEditingSelected);

      const showEditActions = isSelectedSource && isJsonView;
      bulkEditBtn.classList.toggle("mode-hidden", !showEditActions || isEditingSelected);
      bulkSaveBtn.classList.toggle("mode-hidden", !showEditActions || !isEditingSelected);
      bulkCancelBtn.classList.toggle("mode-hidden", !showEditActions || !isEditingSelected);
      bulkEditBtn.disabled = !canEditSelected || state.bulk.isRunning;
      bulkSaveBtn.disabled = !isEditingSelected;
      bulkCancelBtn.disabled = !isEditingSelected;
    }

    function getBulkCounts() {
      const counts = {
        total: state.bulk.jobs.length,
        queued: 0,
        processing: 0,
        success: 0,
        failed: 0
      };
      state.bulk.jobs.forEach((job) => {
        if (job.status === "queued") {
          counts.queued += 1;
        } else if (job.status === "processing") {
          counts.processing += 1;
        } else if (job.status === "success") {
          counts.success += 1;
        } else if (job.status === "failed") {
          counts.failed += 1;
        }
      });
      return counts;
    }

    function getBulkStatusLabel(status) {
      if (status === "queued") {
        return "Queued";
      }
      if (status === "processing") {
        return "Processing";
      }
      if (status === "success") {
        return "Success";
      }
      if (status === "failed") {
        return "Failed";
      }
      return "Unknown";
    }

    function renderBulkSummary() {
      const counts = getBulkCounts();
      const stateText = state.bulk.isRunning ? "Running" : "Idle";
      bulkSummary.textContent =
        "State: " + stateText +
        " | Total: " + counts.total +
        " | Queued: " + counts.queued +
        " | Processing: " + counts.processing +
        " | Success: " + counts.success +
        " | Failed: " + counts.failed;
    }

    function renderBulkDetails() {
      const selected = getBulkJobById(state.bulk.selectedJobId);
      if (!selected) {
        state.bulk.editingJobId = null;
        clearBulkPdfPreview("Select a file row to preview the corresponding PDF.");
        if (state.bulk.resultSource === "combined") {
          const combinedPayload = buildCombinedBulkPayload();
          if (combinedPayload) {
            bulkResultOutput.textContent = JSON.stringify(combinedPayload, null, 2);
          } else {
            bulkResultOutput.textContent = "{\\n  \\"message\\": \\"No successful bulk results available yet.\\"\\n}";
          }
        } else {
          bulkResultOutput.textContent = "{\\n  \\"message\\": \\"Select a file row to inspect individual output.\\"\\n}";
        }
        bulkResultEditor.value = "";
        renderBulkResultTableView();
        updateBulkEditorState();
        return;
      }
      if (selected.file && isPdfFile(selected.file)) {
        setBulkPdfPreview(selected.file, selected.id);
      } else {
        clearBulkPdfPreview("Selected row does not contain a previewable PDF.");
      }
      if (state.bulk.resultSource === "combined") {
        state.bulk.editingJobId = null;
        const combinedPayload = buildCombinedBulkPayload();
        if (combinedPayload) {
          bulkResultOutput.textContent = JSON.stringify(combinedPayload, null, 2);
        } else {
          bulkResultOutput.textContent = "{\\n  \\"message\\": \\"No successful bulk results available yet.\\"\\n}";
        }
        bulkResultEditor.value = "";
        renderBulkResultTableView();
        updateBulkEditorState();
        return;
      }
      if (selected.status === "success" && selected.result) {
        const rendered = JSON.stringify(selected.result, null, 2);
        if (state.bulk.editingJobId !== selected.id) {
          bulkResultOutput.textContent = rendered;
          bulkResultEditor.value = rendered;
        }
        renderBulkResultTableView();
        updateBulkEditorState();
        return;
      }
      state.bulk.editingJobId = null;
      if (selected.status === "failed") {
        bulkResultOutput.textContent = JSON.stringify({
          file_name: selected.name,
          status: selected.status,
          error: selected.error || selected.message || "Unknown error"
        }, null, 2);
        bulkResultEditor.value = "";
        renderBulkResultTableView();
        updateBulkEditorState();
        return;
      }
      bulkResultOutput.textContent = JSON.stringify({
        file_name: selected.name,
        status: selected.status,
        detail: selected.message || "Waiting"
      }, null, 2);
      bulkResultEditor.value = "";
      renderBulkResultTableView();
      updateBulkEditorState();
    }

    function renderBulkTable() {
      if (!state.bulk.jobs.length) {
        bulkTableBody.innerHTML = "<tr><td colspan=\\"6\\">No files selected yet.</td></tr>";
        return;
      }
      const rows = state.bulk.jobs.map((job, index) => {
        const isSelected = state.bulk.selectedJobId === job.id;
        const retryDisabled = state.bulk.isRunning || job.status !== "failed" ? "disabled" : "";
        const downloadDisabled = job.status === "success" ? "" : "disabled";
        const selectedClass = isSelected ? "is-selected" : "";
        return "" +
          "<tr class=\\"" + selectedClass + "\\" data-job-id=\\"" + job.id + "\\">" +
            "<td>" + (index + 1) + "</td>" +
            "<td>" +
              "<p class=\\"bulk-file-name\\">" + escapeHtml(job.name) + "</p>" +
              "<p class=\\"bulk-file-meta\\">" + escapeHtml(formatBytes(job.size)) + "</p>" +
            "</td>" +
            "<td><span class=\\"status-pill is-" + escapeHtml(job.status) + "\\">" + escapeHtml(getBulkStatusLabel(job.status)) + "</span></td>" +
            "<td>" + job.attempts + "</td>" +
            "<td><p class=\\"bulk-message\\">" + escapeHtml(job.message || "-") + "</p></td>" +
            "<td>" +
              "<div class=\\"bulk-actions\\">" +
                "<button type=\\"button\\" class=\\"btn-compact\\" data-action=\\"view\\" data-job-id=\\"" + job.id + "\\">View</button>" +
                "<button type=\\"button\\" class=\\"btn-compact\\" data-action=\\"retry\\" data-job-id=\\"" + job.id + "\\" " + retryDisabled + ">Retry</button>" +
                "<button type=\\"button\\" class=\\"btn-compact\\" data-action=\\"download\\" data-job-id=\\"" + job.id + "\\" " + downloadDisabled + ">Download</button>" +
              "</div>" +
            "</td>" +
          "</tr>";
      });
      bulkTableBody.innerHTML = rows.join("");
    }

    function updateBulkActionStates() {
      const counts = getBulkCounts();
      bulkStartBtn.disabled = !state.network.isOnline || state.bulk.isRunning || counts.queued === 0;
      bulkStopBtn.disabled = !state.bulk.isRunning;
      bulkRetryFailedBtn.disabled = !state.network.isOnline || state.bulk.isRunning || counts.failed === 0;
      bulkDownloadBtn.disabled = counts.success === 0;
      bulkFileInput.disabled = state.bulk.isRunning;
      updateBulkEditorState();
      persistUiState();
    }

    function renderBulkState() {
      renderBulkSummary();
      renderBulkTable();
      renderBulkDetails();
      updateBulkActionStates();
    }

    function startBulkJsonEdit() {
      if (state.bulk.isRunning) {
        setStatus("Wait for the bulk run to finish before editing JSON.", "error");
        return;
      }
      if (state.bulk.resultSource !== "selected" || state.bulk.resultViewMode !== "json") {
        setStatus("Switch to Selected File and JSON View to edit.", "error");
        return;
      }
      const selected = getBulkJobById(state.bulk.selectedJobId);
      if (!selected || selected.status !== "success" || !selected.result) {
        setStatus("Select a successful file result to edit JSON.", "error");
        return;
      }
      state.bulk.editingJobId = selected.id;
      bulkResultEditor.value = JSON.stringify(selected.result, null, 2);
      updateBulkEditorState();
      bulkResultEditor.focus();
      setStatus("Editing JSON for " + selected.name + ".", "info");
    }

    function saveBulkJsonEdit() {
      if (state.bulk.editingJobId === null) {
        return;
      }
      const job = getBulkJobById(state.bulk.editingJobId);
      if (!job || job.status !== "success" || !job.result) {
        state.bulk.editingJobId = null;
        renderBulkState();
        return;
      }
      let parsed = null;
      try {
        parsed = JSON.parse(bulkResultEditor.value);
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        setStatus("Invalid JSON: " + message, "error");
        return;
      }
      job.result = parsed;
      job.message = "Complaint parsed successfully (edited).";
      state.bulk.editingJobId = null;
      renderBulkState();
      setStatus("Saved JSON edits for " + job.name + ".", "success");
    }

    function cancelBulkJsonEdit() {
      if (state.bulk.editingJobId === null) {
        return;
      }
      const job = getBulkJobById(state.bulk.editingJobId);
      state.bulk.editingJobId = null;
      renderBulkDetails();
      setStatus("JSON edit canceled" + (job ? " for " + job.name : "") + ".", "info");
    }

    function buildCombinedBulkPayload() {
      const successfulJobs = state.bulk.jobs.filter((job) => job.status === "success" && job.result);
      const failedJobs = state.bulk.jobs.filter((job) => job.status === "failed");
      if (!successfulJobs.length) {
        return null;
      }
      return {
        generated_at: new Date().toISOString(),
        total_files: state.bulk.jobs.length,
        total_results: successfulJobs.length,
        failed_count: failedJobs.length,
        failed_files: failedJobs.map((job) => ({
          file_name: job.name,
          error: job.error || job.message || "Unknown error"
        })),
        results: successfulJobs.map((job) => ({
          file_name: job.name,
          parsed_output: job.result
        }))
      };
    }

    function downloadBulkResults() {
      const payload = buildCombinedBulkPayload();
      if (!payload) {
        setStatus("No successful bulk results available to download.", "error");
        return;
      }
      downloadJsonPayload(payload, "bulk_complaint_results.json");
      setStatus("Combined JSON downloaded for bulk results.", "success");
    }

    async function requestParseFile(file) {
      if (!state.network.isOnline) {
        throw new Error("Offline mode: reconnect before parsing.");
      }
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetchWithApiFallback("api/parse", {
        method: "POST",
        body: formData
      });

      let data = null;
      try {
        data = await response.json();
      } catch (_err) {
        data = null;
      }

      if (!response.ok) {
        const detail = data && data.detail ? data.detail : "Failed to parse document.";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      return data;
    }

    function queueFailedJobsForRetry() {
      if (state.bulk.isRunning) {
        return;
      }
      let retried = 0;
      state.bulk.jobs.forEach((job) => {
        if (job.status === "failed") {
          job.status = "queued";
          job.message = "Queued for retry.";
          job.error = null;
          job.result = null;
          retried += 1;
        }
      });
      renderBulkState();
      if (retried > 0) {
        setStatus("Queued " + retried + " failed file(s) for retry.", "info");
      } else {
        setStatus("No failed files available to retry.", "info");
      }
    }

    function selectBulkJob(jobId) {
      const job = getBulkJobById(jobId);
      if (!job) {
        return;
      }
      if (state.bulk.editingJobId !== null && state.bulk.editingJobId !== job.id) {
        state.bulk.editingJobId = null;
      }
      state.bulk.selectedJobId = job.id;
      renderBulkDetails();
      renderBulkTable();
    }

    function buildBulkJobs(files) {
      return files.map((file, index) => {
        let status = "queued";
        let message = "Ready to process.";
        if (!isPdfFile(file)) {
          status = "failed";
          message = "Only PDF files are supported.";
        } else if (!file.size) {
          status = "failed";
          message = "File is empty.";
        } else if (file.size > BULK_MAX_FILE_SIZE) {
          status = "failed";
          message = "File exceeds 15 MB size limit.";
        }
        return {
          id: index + 1,
          file: file,
          name: file.name,
          size: file.size,
          status: status,
          message: message,
          attempts: 0,
          result: null,
          error: null
        };
      });
    }

    function onBulkFilesSelected() {
      if (state.bulk.isRunning) {
        return;
      }
      let files = Array.prototype.slice.call(bulkFileInput.files || []);
      let truncated = false;
      if (!files.length) {
        state.bulk.jobs = [];
        state.bulk.selectedJobId = null;
        state.bulk.editingJobId = null;
        renderBulkState();
        setStatus("Bulk queue cleared.", "info");
        return;
      }
      if (files.length > BULK_MAX_FILES) {
        files = files.slice(0, BULK_MAX_FILES);
        truncated = true;
      }
      state.bulk.jobs = buildBulkJobs(files);
      state.bulk.selectedJobId = state.bulk.jobs.length ? state.bulk.jobs[0].id : null;
      state.bulk.editingJobId = null;
      renderBulkState();
      const counts = getBulkCounts();
      if (counts.failed > 0) {
        setStatus("Bulk queue created with " + counts.failed + " validation failure(s).", "error");
      } else if (truncated) {
        setStatus("Only the first " + BULK_MAX_FILES + " files were queued. Extra files were ignored.", "error");
      } else {
        setStatus("Bulk queue ready with " + counts.total + " file(s).", "info");
      }
    }

    async function runBulkQueue() {
      if (state.bulk.isRunning) {
        return;
      }
      const counts = getBulkCounts();
      if (counts.queued === 0) {
        setStatus("No queued files to process in bulk mode.", "error");
        return;
      }

      state.bulk.isRunning = true;
      state.bulk.cancelRequested = false;
      state.bulk.editingJobId = null;
      setBulkLoading(true);
      renderBulkState();
      setStatus("Bulk processing started for " + counts.queued + " queued file(s).", "info");

      for (let index = 0; index < state.bulk.jobs.length; index += 1) {
        if (state.bulk.cancelRequested) {
          break;
        }
        const job = state.bulk.jobs[index];
        if (!job || job.status !== "queued") {
          continue;
        }

        job.status = "processing";
        job.message = "Parsing in progress...";
        job.error = null;
        job.attempts += 1;
        state.bulk.selectedJobId = job.id;
        renderBulkState();

        try {
          const data = await requestParseFile(job.file);
          job.status = "success";
          job.result = data.parsed_output || data;
          job.message = "Complaint parsed successfully.";
        } catch (err) {
          const message = err && err.message ? err.message : String(err);
          job.status = "failed";
          job.result = null;
          job.error = message;
          job.message = message;
        }
        renderBulkState();
      }

      const stopped = state.bulk.cancelRequested;
      state.bulk.isRunning = false;
      state.bulk.cancelRequested = false;
      setBulkLoading(false);
      renderBulkState();

      const finalCounts = getBulkCounts();
      if (stopped) {
        setStatus(
          "Bulk run stopped. Success: " + finalCounts.success + ", Failed: " + finalCounts.failed + ", Queued: " + finalCounts.queued + ".",
          "info"
        );
      } else if (finalCounts.failed > 0) {
        setStatus(
          "Bulk run finished with partial failures. Success: " + finalCounts.success + ", Failed: " + finalCounts.failed + ".",
          "error"
        );
      } else {
        setStatus("Bulk run finished successfully for " + finalCounts.success + " file(s).", "success");
      }
    }

    function stopBulkQueueAfterCurrent() {
      if (!state.bulk.isRunning) {
        return;
      }
      state.bulk.cancelRequested = true;
      setStatus("Stop requested. Current file will finish before queue stops.", "info");
    }

    function handleNetworkOnline() {
      state.network.isOnline = true;
      updateConnectivityUI();
      setStatus("Connection restored. Online services are available.", "success");
    }

    function handleNetworkOffline() {
      state.network.isOnline = false;
      updateConnectivityUI();
      setStatus("You are offline. Parsing and cloud push are disabled until reconnection.", "error");
    }

    initTheme();
    renderBulkState();
    setLoginRememberState(false);
    loadRememberedUser();
    setAppAuthenticated(false);
    restorePersistedState();
    updateLoginActionState();
    updateConnectivityUI();
    statePersistenceReady = true;
    persistUiState();

    themeToggle.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const nextTheme = current === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, nextTheme);
      applyTheme(nextTheme);
      persistUiState();
    });

    const handleThemePreferenceChange = (event) => {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") {
        return;
      }
      applyTheme(event.matches ? "dark" : "light");
    };

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleThemePreferenceChange);
    } else if (typeof mediaQuery.addListener === "function") {
      mediaQuery.addListener(handleThemePreferenceChange);
    }

    loginForm.addEventListener("submit", handleLoginSubmit);
    loginUser.addEventListener("input", () => {
      setLoginMessage("");
      updateLoginActionState();
      persistUiState();
    });
    loginPassword.addEventListener("input", () => {
      setLoginMessage("");
      updateLoginActionState();
      persistUiState();
    });
    loginRemember.addEventListener("click", () => {
      setLoginRememberState(!state.rememberUser);
      persistUiState();
    });
    togglePasswordBtn.addEventListener("click", togglePasswordVisibility);
    forgotPasswordBtn.addEventListener("click", handleForgotPassword);
    createAccountBtn.addEventListener("click", handleCreateAccount);
    helpCenterBtn.addEventListener("click", handleHelpCenter);
    bulkFileInput.addEventListener("change", onBulkFilesSelected);
    bulkStartBtn.addEventListener("click", runBulkQueue);
    bulkStopBtn.addEventListener("click", stopBulkQueueAfterCurrent);
    bulkRetryFailedBtn.addEventListener("click", queueFailedJobsForRetry);
    bulkDownloadBtn.addEventListener("click", downloadBulkResults);
    bulkSelectedSourceBtn.addEventListener("click", () => setBulkResultSource("selected"));
    bulkCombinedSourceBtn.addEventListener("click", () => setBulkResultSource("combined"));
    bulkJsonViewBtn.addEventListener("click", () => setBulkResultViewMode("json"));
    bulkTableViewBtn.addEventListener("click", () => setBulkResultViewMode("table"));
    bulkEditBtn.addEventListener("click", startBulkJsonEdit);
    bulkSaveBtn.addEventListener("click", saveBulkJsonEdit);
    bulkCancelBtn.addEventListener("click", cancelBulkJsonEdit);

    bulkTableBody.addEventListener("click", (event) => {
      const clickedRow = event.target.closest("tr[data-job-id]");
      if (clickedRow) {
        const rowJobId = Number(clickedRow.getAttribute("data-job-id"));
        if (rowJobId) {
          selectBulkJob(rowJobId);
        }
      }
      const actionBtn = event.target.closest("button[data-action]");
      if (!actionBtn) {
        return;
      }
      const jobId = Number(actionBtn.getAttribute("data-job-id"));
      if (!jobId) {
        return;
      }
      const action = actionBtn.getAttribute("data-action");
      const job = getBulkJobById(jobId);
      if (!job) {
        return;
      }

      if (action === "view") {
        selectBulkJob(jobId);
        return;
      }

      if (action === "retry") {
        if (state.bulk.isRunning || job.status !== "failed") {
          return;
        }
        job.status = "queued";
        job.message = "Queued for retry.";
        job.error = null;
        job.result = null;
        selectBulkJob(jobId);
        renderBulkState();
        setStatus("File queued for retry: " + job.name, "info");
        return;
      }

      if (action === "download") {
        if (job.status !== "success" || !job.result) {
          return;
        }
        const outputName = normalizePdfName(job.name) + "_complaint_parsed.json";
        downloadJsonPayload(job.result, outputName);
        setStatus("Downloaded result for " + job.name + ".", "success");
      }
    });

    window.addEventListener("online", handleNetworkOnline);
    window.addEventListener("offline", handleNetworkOffline);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.fullscreen.activeTargetId) {
        event.preventDefault();
        collapseActiveFullscreenTarget();
      }
    });
    fullscreenButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const targetId = button.getAttribute("data-fullscreen-target");
        toggleFullscreenTarget(targetId);
      });
    });
    window.addEventListener("beforeunload", () => {
      collapseActiveFullscreenTarget();
      persistUiState();
      if (state.bulkPreviewUrl) {
        URL.revokeObjectURL(state.bulkPreviewUrl);
      }
    });
  </script>
</body>
</html>"""


@app.get("/health")
@app.get("/api/health")
def health() -> JSONResponse:
    try:
        config = get_doc_ai_config()
    except RuntimeError as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(exc)},
        )

    translation_config = get_translation_config()

    return JSONResponse(
        content={
            "status": "ok",
            "parser_mode": "police_complaint",
            "project_id": config["DOC_AI_PROJECT_ID"],
            "location": config["DOC_AI_LOCATION"],
            "processor_id": config["DOC_AI_PROCESSOR_ID"],
            "field_mask": config["DOC_AI_FIELD_MASK"],
            "translation_enabled": translation_config["enabled"],
            "translation_project_id": translation_config["project_id"],
            "translation_location": translation_config["location"],
            "translation_target_language": translation_config["target_language"],
        }
    )


@app.post("/api/parse")
@app.post("/parse")
async def parse_uploaded_pdf(file: UploadFile = File(...)) -> JSONResponse:
    filename = file.filename or ""
    content_type = file.content_type or ""

    if not filename.lower().endswith(".pdf") and "pdf" not in content_type.lower():
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_PARSE_UPLOAD_BYTES:
        max_mb = MAX_PARSE_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds the {max_mb} MB size limit.",
        )

    try:
        config = get_doc_ai_config()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        result = process_document_bytes(
            project_id=config["DOC_AI_PROJECT_ID"],
            location=config["DOC_AI_LOCATION"],
            processor_id=config["DOC_AI_PROCESSOR_ID"],
            content=content,
            mime_type=config["DOC_AI_MIME_TYPE"],
            field_mask=config["DOC_AI_FIELD_MASK"],
        )
        raw_text = result.document.text or ""
        parsed_output = parse_document(raw_text)
        detected_format = (
            parsed_output.get("meta", {}).get("detected_format")
            if isinstance(parsed_output, dict)
            else None
        )
        response_payload = {
            "file_name": Path(filename).name,
            "document_format": detected_format or "UNKNOWN",
            "raw_text_length": len(raw_text),
            "parsed_output": parsed_output,
        }
        return JSONResponse(content=response_payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {exc}",
        ) from exc


@app.post("/api/push-combined-json")
@app.post("/push-combined-json")
async def push_combined_json_endpoint(request: dict = Body(...)) -> JSONResponse:
    provider = request.get("provider")
    target = request.get("target")
    payload = request.get("payload")

    if not provider:
        raise HTTPException(status_code=400, detail="`provider` is required.")
    if not target:
        raise HTTPException(status_code=400, detail="`target` is required.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="`payload` must be a JSON object.")

    try:
        result = push_combined_json_to_cloud(
            provider=provider,
            target=target,
            payload=payload,
        )
        return JSONResponse(
            content={
                "status": "ok",
                "provider": result["provider"],
                "destination": result["destination"],
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Push failed: {exc}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(_get_env("PORT", "8080") or "8080"),
        reload=False,
    )
