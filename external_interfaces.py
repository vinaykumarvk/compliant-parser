from __future__ import annotations

"""External service interfaces and live adapters.

This module keeps government-system, OCR, signing, storage, notification, and
LLM boundaries explicit.  Live adapters read credentials from environment
variables; stub adapters are intentionally no-op/test doubles and never embed
secrets in source.
"""

import json
import os
import ssl
import asyncio
import urllib.error
import urllib.request
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from complaint_parsing import process_document_bytes
from privacy import PIIProtectionError, protect_for_llm


class ExternalServiceError(RuntimeError):
    """Raised when a configured external service call fails."""


class ExternalServiceUnavailable(ExternalServiceError):
    """Raised when an external adapter is not configured for live use."""


class HRMSClient(Protocol):
    async def authenticate(self, employee_id: str, password: str) -> Optional[dict[str, Any]]:
        ...


class CCTNSClient(Protocol):
    async def sync_case(self, case_payload: dict[str, Any]) -> dict[str, Any]:
        ...


class DSCClient(Protocol):
    async def sign_document(self, document_bytes: bytes, pin: str) -> dict[str, Any]:
        ...


class NotificationGateway(Protocol):
    async def send(self, recipient: str, message: str, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        ...


class ObjectStorageClient(Protocol):
    async def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        ...

    async def get_bytes(self, uri: str) -> bytes:
        ...

    async def delete(self, uri: str) -> None:
        ...


@dataclass(frozen=True)
class OCRResult:
    text: str
    provider: str
    page_count: Optional[int] = None
    confidence: Optional[float] = None


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    provider: str
    model: str
    privacy: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectStorageResult:
    uri: str
    provider: str
    encryption_key_ref: Optional[str] = None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _is_true(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _is_external_ai_provider(provider: str) -> bool:
    return provider.lower() in {
        "google",
        "google_document_ai",
        "openai",
        "gemini",
    }


def _external_ai_approval_required() -> bool:
    if _is_true("IQW_REQUIRE_EXTERNAL_AI_APPROVAL", False):
        return True
    return _is_production_runtime()


def _external_ai_approval_status() -> dict[str, Any]:
    return {
        "approved": _is_true("EXTERNAL_AI_API_APPROVED", False),
        "approval_id": _env("EXTERNAL_AI_APPROVAL_ID"),
        "approved_by": _env("EXTERNAL_AI_APPROVED_BY"),
        "expires_on": _env("EXTERNAL_AI_APPROVAL_EXPIRES_ON"),
        "scope": _env("EXTERNAL_AI_APPROVAL_SCOPE"),
        "required": _external_ai_approval_required(),
    }


def require_external_ai_approval(provider: str, purpose: str) -> None:
    """Enforce written-approval metadata for external AI/OCR providers.

    The BRD/RFQ requires sensitive case data to remain inside the organisation
    boundary unless written approval exists. Development and tests can opt into
    this check with IQW_REQUIRE_EXTERNAL_AI_APPROVAL=true; production always
    requires it.
    """
    if not _is_external_ai_provider(provider) or not _external_ai_approval_required():
        return
    status = _external_ai_approval_status()
    if not status["approved"] or not status["approval_id"] or not status["approved_by"]:
        raise ExternalServiceUnavailable(
            f"{provider} {purpose} requires written external-AI approval. "
            "Set EXTERNAL_AI_API_APPROVED=true, EXTERNAL_AI_APPROVAL_ID, and "
            "EXTERNAL_AI_APPROVED_BY, or configure the self-hosted provider."
        )


def _resolve_service_account_credentials(path_value: Optional[str]) -> Any:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (Path(__file__).resolve().parent / path).resolve()
    if not path.exists():
        return None
    from google.oauth2 import service_account

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(path)
    return service_account.Credentials.from_service_account_file(str(path))


def infer_mime_type(file_name: str, content_type: Optional[str] = None) -> str:
    if content_type and content_type not in {"application/octet-stream", "binary/octet-stream"}:
        return content_type
    lower = (file_name or "").lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


def is_document_ai_supported_mime(mime_type: str) -> bool:
    return mime_type in {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/gif",
    }


def run_google_document_ai_ocr(
    content: bytes,
    *,
    file_name: str = "",
    mime_type: Optional[str] = None,
) -> OCRResult:
    """Run Google Document AI OCR using DOC_AI_* environment variables."""
    require_external_ai_approval("google_document_ai", "OCR")
    project_id = _env("DOC_AI_PROJECT_ID")
    location = _env("DOC_AI_LOCATION")
    processor_id = _env("DOC_AI_PROCESSOR_ID")
    if not project_id or not location or not processor_id:
        raise ExternalServiceUnavailable(
            "Google Document AI is not configured. Set DOC_AI_PROJECT_ID, DOC_AI_LOCATION, and DOC_AI_PROCESSOR_ID."
        )

    detected_mime = infer_mime_type(file_name, mime_type)
    if not is_document_ai_supported_mime(detected_mime):
        raise ExternalServiceUnavailable(f"Google Document AI OCR does not support MIME type {detected_mime}.")

    credentials = _resolve_service_account_credentials(
        _env("DOC_AI_CREDENTIALS_PATH") or _env("GOOGLE_APPLICATION_CREDENTIALS")
    )
    try:
        response = process_document_bytes(
            project_id=project_id,
            location=location,
            processor_id=processor_id,
            content=content,
            mime_type=detected_mime,
            field_mask=_env("DOC_AI_FIELD_MASK", "text"),
            processor_version_id=_env("DOC_AI_PROCESSOR_VERSION_ID"),
            credentials=credentials,
        )
    except Exception as exc:
        raise ExternalServiceError(f"Google Document AI OCR failed: {exc}") from exc

    document = response.document
    page_count = len(getattr(document, "pages", []) or [])
    return OCRResult(
        text=getattr(document, "text", "") or "",
        provider="google_document_ai",
        page_count=page_count or None,
    )


def _json_post(url: str, payload: dict[str, Any], headers: Optional[dict[str, str]] = None, timeout: int = 120) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    urlopen_kwargs: dict[str, Any] = {"timeout": timeout}
    if url.lower().startswith("https://"):
        urlopen_kwargs["context"] = _build_ssl_context()
    with urllib.request.urlopen(request, **urlopen_kwargs) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def run_self_hosted_ocr(
    content: bytes,
    *,
    file_name: str = "",
    mime_type: Optional[str] = None,
) -> OCRResult:
    """Run OCR through an internal/self-hosted OCR gateway."""
    url = _env("IQW_SELF_HOSTED_OCR_URL")
    if not url:
        raise ExternalServiceUnavailable("IQW_SELF_HOSTED_OCR_URL is not configured.")
    detected_mime = infer_mime_type(file_name, mime_type)
    payload = {
        "file_name": file_name,
        "mime_type": detected_mime,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }
    headers = {}
    api_key = _env("IQW_SELF_HOSTED_OCR_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        data = _json_post(url, payload, headers=headers, timeout=int(_env("IQW_SELF_HOSTED_OCR_TIMEOUT", "120") or "120"))
    except Exception as exc:
        raise ExternalServiceError(f"Self-hosted OCR failed: {exc}") from exc
    text = data.get("text") or data.get("extracted_text") or ""
    return OCRResult(
        text=text,
        provider="self_hosted",
        page_count=data.get("page_count"),
        confidence=data.get("confidence"),
    )


def run_configured_ocr(
    content: bytes,
    *,
    file_name: str = "",
    mime_type: Optional[str] = None,
) -> OCRResult:
    """Run OCR using the configured BRD/RFQ-compliant provider order."""
    provider = (_env("IQW_OCR_PROVIDER") or "auto").lower().replace("-", "_")
    if provider == "auto":
        provider = "self_hosted" if _env("IQW_SELF_HOSTED_OCR_URL") else "google_document_ai"
    if provider in {"self_hosted", "internal"}:
        try:
            return run_self_hosted_ocr(content, file_name=file_name, mime_type=mime_type)
        except ExternalServiceUnavailable:
            fallback = (_env("IQW_OCR_FALLBACK_PROVIDER") or "").lower().replace("-", "_")
            if fallback not in {"google", "google_document_ai"}:
                raise
    if provider in {"google", "google_document_ai"} or (_env("IQW_OCR_FALLBACK_PROVIDER") or "").lower().replace("-", "_") in {"google", "google_document_ai"}:
        return run_google_document_ai_ocr(content, file_name=file_name, mime_type=mime_type)
    raise ExternalServiceUnavailable(f"Unsupported OCR provider '{provider}'.")


class StubExternalClient:
    """Base no-op adapter for dependencies that are unavailable in local tests."""

    service_name = "external"

    async def authenticate(self, employee_id: str, password: str) -> Optional[dict[str, Any]]:
        return None

    async def sync_case(self, case_payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "Pending", "queued": True, "service": self.service_name}

    async def sign_document(self, document_bytes: bytes, pin: str) -> dict[str, Any]:
        raise ExternalServiceUnavailable(f"{self.service_name} signing is not configured.")

    async def send(self, recipient: str, message: str, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return {"sent": False, "recipient": recipient, "queued": True}

    async def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        return f"stub://{key}"

    async def get_bytes(self, uri: str) -> bytes:
        raise ExternalServiceUnavailable(f"{self.service_name} object storage is not configured.")

    async def delete(self, uri: str) -> None:
        return None


class LocalObjectStorageClient:
    """Filesystem object storage for local development and deterministic tests."""

    provider = "local"

    def __init__(self) -> None:
        root = _env("OBJECT_STORAGE_LOCAL_DIR", ".object-storage")
        self.root = Path(root).expanduser()
        if not self.root.is_absolute():
            self.root = (Path(__file__).resolve().parent / self.root).resolve()

    def _path_for_key(self, key: str) -> Path:
        safe_parts = [part for part in key.split("/") if part and part not in {".", ".."}]
        path = (self.root / Path(*safe_parts)).resolve()
        if self.root not in path.parents and path != self.root:
            raise ExternalServiceError("Object storage key escapes storage root.")
        return path

    def _path_for_uri(self, uri: str) -> Path:
        key = uri.removeprefix("local://")
        return self._path_for_key(key)

    async def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        path = self._path_for_key(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(write)
        return f"local://{key}"

    async def get_bytes(self, uri: str) -> bytes:
        path = self._path_for_uri(uri)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise ExternalServiceError(f"Stored object not found: {uri}") from exc

    async def delete(self, uri: str) -> None:
        path = self._path_for_uri(uri)

        def remove() -> None:
            try:
                path.unlink()
            except FileNotFoundError:
                return

        await asyncio.to_thread(remove)


class GCSObjectStorageClient:
    """Google Cloud Storage object adapter for production document binaries."""

    provider = "gcs"

    def __init__(self) -> None:
        bucket = _env("OBJECT_STORAGE_BUCKET") or _env("GCS_BUCKET")
        if not bucket:
            raise ExternalServiceUnavailable("OBJECT_STORAGE_BUCKET or GCS_BUCKET must be configured for GCS storage.")
        self.bucket_name = bucket
        self.encryption_key_ref = _env("OBJECT_STORAGE_KMS_KEY") or _env("GCS_KMS_KEY")
        credentials = _resolve_service_account_credentials(
            _env("OBJECT_STORAGE_CREDENTIALS_PATH")
            or _env("DOC_AI_CREDENTIALS_PATH")
            or _env("GOOGLE_APPLICATION_CREDENTIALS")
        )
        from google.cloud import storage

        self.client = storage.Client(credentials=credentials)

    async def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        def upload() -> None:
            blob = self.client.bucket(self.bucket_name).blob(key)
            if self.encryption_key_ref:
                blob.kms_key_name = self.encryption_key_ref
            blob.upload_from_string(data, content_type=content_type or "application/octet-stream")

        await asyncio.to_thread(upload)
        return f"gs://{self.bucket_name}/{key}"

    async def get_bytes(self, uri: str) -> bytes:
        prefix = f"gs://{self.bucket_name}/"
        if not uri.startswith(prefix):
            raise ExternalServiceError(f"Stored object URI does not belong to configured bucket: {uri}")
        key = uri[len(prefix):]

        def download() -> bytes:
            return self.client.bucket(self.bucket_name).blob(key).download_as_bytes()

        return await asyncio.to_thread(download)

    async def delete(self, uri: str) -> None:
        prefix = f"gs://{self.bucket_name}/"
        if not uri.startswith(prefix):
            return
        key = uri[len(prefix):]

        def remove() -> None:
            self.client.bucket(self.bucket_name).blob(key).delete()

        await asyncio.to_thread(remove)


class S3ObjectStorageClient:
    """S3-compatible object adapter for on-prem MinIO deployments."""

    provider = "s3"

    def __init__(self) -> None:
        bucket = _env("S3_BUCKET") or _env("MINIO_BUCKET") or _env("OBJECT_STORAGE_BUCKET")
        if not bucket:
            raise ExternalServiceUnavailable("S3_BUCKET, MINIO_BUCKET, or OBJECT_STORAGE_BUCKET must be configured for S3/MinIO storage.")
        self.bucket_name = bucket
        self.endpoint_url = _env("S3_ENDPOINT_URL") or _env("MINIO_ENDPOINT")
        self.encryption_key_ref = _env("OBJECT_STORAGE_KMS_KEY") or _env("S3_SSE_KMS_KEY_ID") or _env("MINIO_KMS_KEY_ID")
        access_key = _env("AWS_ACCESS_KEY_ID") or _env("MINIO_ACCESS_KEY")
        secret_key = _env("AWS_SECRET_ACCESS_KEY") or _env("MINIO_SECRET_KEY")
        region = _env("AWS_REGION", "us-east-1")

        import boto3

        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": region,
        }
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key
        self.client = boto3.client(**kwargs)

    def _key_from_uri(self, uri: str) -> str:
        prefix = f"s3://{self.bucket_name}/"
        if not uri.startswith(prefix):
            raise ExternalServiceError(f"Stored object URI does not belong to configured S3 bucket: {uri}")
        return uri[len(prefix):]

    async def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        def upload() -> None:
            extra_args: dict[str, Any] = {
                "ContentType": content_type or "application/octet-stream",
                "ServerSideEncryption": "AES256",
            }
            if self.encryption_key_ref:
                extra_args["ServerSideEncryption"] = "aws:kms"
                extra_args["SSEKMSKeyId"] = self.encryption_key_ref
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                **extra_args,
            )

        await asyncio.to_thread(upload)
        return f"s3://{self.bucket_name}/{key}"

    async def get_bytes(self, uri: str) -> bytes:
        key = self._key_from_uri(uri)

        def download() -> bytes:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()

        return await asyncio.to_thread(download)

    async def delete(self, uri: str) -> None:
        key = self._key_from_uri(uri)

        def remove() -> None:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)

        await asyncio.to_thread(remove)


def _is_production_runtime() -> bool:
    value = (_env("APP_ENV") or _env("ENVIRONMENT") or _env("IQW_ENV") or "").lower()
    return value in {"prod", "production"}


def get_object_storage_client() -> ObjectStorageClient:
    provider = (_env("OBJECT_STORAGE_PROVIDER") or "auto").lower()
    has_s3_config = bool(_env("S3_ENDPOINT_URL") or _env("MINIO_ENDPOINT") or _env("S3_BUCKET") or _env("MINIO_BUCKET"))
    has_gcs_bucket = bool(_env("GCS_BUCKET")) or bool(_env("OBJECT_STORAGE_BUCKET") and not has_s3_config)
    if provider in {"s3", "minio", "s3_compatible"} or (provider == "auto" and has_s3_config):
        return S3ObjectStorageClient()
    if provider in {"gcs", "google", "google_cloud_storage"} or (provider == "auto" and has_gcs_bucket):
        return GCSObjectStorageClient()
    if _is_production_runtime() and provider != "local":
        raise ExternalServiceUnavailable("Production document storage requires S3/MinIO or GCS configuration.")
    return LocalObjectStorageClient()


async def put_object_bytes(key: str, data: bytes, content_type: Optional[str] = None) -> ObjectStorageResult:
    client = get_object_storage_client()
    uri = await client.put_bytes(key, data, content_type)
    encryption_key_ref = getattr(client, "encryption_key_ref", None)
    return ObjectStorageResult(uri=uri, provider=getattr(client, "provider", "object_storage"), encryption_key_ref=encryption_key_ref)


async def get_object_bytes(uri: str) -> bytes:
    if uri.startswith("local://"):
        return await LocalObjectStorageClient().get_bytes(uri)
    if uri.startswith("gs://"):
        return await GCSObjectStorageClient().get_bytes(uri)
    if uri.startswith("s3://"):
        return await S3ObjectStorageClient().get_bytes(uri)
    raise ExternalServiceUnavailable(f"Unsupported stored object URI scheme: {uri}")


async def delete_object(uri: str) -> None:
    if uri.startswith("local://"):
        await LocalObjectStorageClient().delete(uri)
        return
    if uri.startswith("gs://"):
        await GCSObjectStorageClient().delete(uri)
        return
    if uri.startswith("s3://"):
        await S3ObjectStorageClient().delete(uri)


def _extract_openai_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    fragments: list[str] = []
    for output in payload.get("output", []) or []:
        for item in output.get("content", []) or []:
            text = item.get("text") or item.get("output_text")
            if text:
                fragments.append(text)
    return "\n".join(fragments).strip()


def _extract_openai_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(item.get("text") or "") for item in content if isinstance(item, dict)).strip()
    return _extract_openai_text(payload)


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    fragments: list[str] = []
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if text:
                fragments.append(text)
    return "\n".join(fragments).strip()


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


class LiveLLMClient:
    """Provider-neutral structured JSON LLM adapter."""

    def __init__(self) -> None:
        provider = (_env("IQW_LLM_PROVIDER") or "auto").lower()
        if provider == "auto":
            provider = (
                "self_hosted"
                if _env("IQW_SELF_HOSTED_LLM_URL")
                else "openai"
                if _env("OPENAI_API_KEY")
                else "gemini"
                if _env("GEMINI_API_KEY")
                else "stub"
            )
        provider = provider.replace("-", "_")
        self.provider = provider
        self.self_hosted_url = (_env("IQW_SELF_HOSTED_LLM_URL", "") or "").rstrip("/")
        self.self_hosted_key = _env("IQW_SELF_HOSTED_LLM_API_KEY")
        self.self_hosted_model = _env("IQW_SELF_HOSTED_LLM_MODEL") or "llama3-legal-local"
        self.openai_key = _env("OPENAI_API_KEY")
        self.openai_base_url = (_env("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
        self.openai_model = _env("IQW_LLM_MODEL") or _env("OPENAI_MODEL") or "gpt-5.2"
        self.gemini_key = _env("GEMINI_API_KEY")
        self.gemini_base_url = (_env("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta") or "").rstrip("/")
        self.gemini_model = _env("IQW_GEMINI_MODEL") or _env("GEMINI_MODEL") or "gemini-2.5-flash"

    def generate_json(self, system_prompt: str, user_prompt: str, *, timeout: int = 120) -> LLMResult:
        def _call_with_privacy(callable_json) -> LLMResult:
            try:
                protected_system, protected_user, privacy_context = protect_for_llm(system_prompt, user_prompt)
            except PIIProtectionError as exc:
                raise ExternalServiceError(str(exc)) from exc
            result = callable_json(protected_system, protected_user)
            return LLMResult(
                data=privacy_context.restore_json(result.data),
                provider=result.provider,
                model=result.model,
                privacy=privacy_context.metadata(),
            )

        if self.provider in {"self_hosted", "vllm", "tgi", "internal"}:
            return _call_with_privacy(
                lambda protected_system, protected_user: self._self_hosted_json(
                    protected_system, protected_user, timeout=timeout
                )
            )
        if self.provider == "openai":
            require_external_ai_approval("openai", "LLM")
            return _call_with_privacy(
                lambda protected_system, protected_user: self._openai_json(
                    protected_system, protected_user, timeout=timeout
                )
            )
        if self.provider == "gemini":
            require_external_ai_approval("gemini", "LLM")
            return _call_with_privacy(
                lambda protected_system, protected_user: self._gemini_json(
                    protected_system, protected_user, timeout=timeout
                )
            )
        raise ExternalServiceUnavailable(
            "No live LLM API is configured. Set IQW_SELF_HOSTED_LLM_URL, OPENAI_API_KEY, or GEMINI_API_KEY."
        )

    def _self_hosted_json(self, system_prompt: str, user_prompt: str, *, timeout: int) -> LLMResult:
        if not self.self_hosted_url:
            raise ExternalServiceUnavailable("IQW_SELF_HOSTED_LLM_URL is not configured.")
        endpoint = self.self_hosted_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint.rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.self_hosted_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {}
        if self.self_hosted_key:
            headers["Authorization"] = f"Bearer {self.self_hosted_key}"
        try:
            response_payload = _json_post(endpoint, payload, headers=headers, timeout=timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ExternalServiceError(f"Self-hosted LLM request failed: {body[:500]}") from exc
        except Exception as exc:
            raise ExternalServiceError(f"Self-hosted LLM request failed: {exc}") from exc
        text = _extract_openai_chat_text(response_payload)
        return LLMResult(data=_json_from_text(text), provider="self_hosted", model=self.self_hosted_model)

    def _openai_json(self, system_prompt: str, user_prompt: str, *, timeout: int) -> LLMResult:
        if not self.openai_key:
            raise ExternalServiceUnavailable("OPENAI_API_KEY is not configured.")
        payload = {
            "model": self.openai_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        request = urllib.request.Request(
            f"{self.openai_base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=_build_ssl_context()) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ExternalServiceError(f"OpenAI LLM request failed: {body[:500]}") from exc
        except Exception as exc:
            raise ExternalServiceError(f"OpenAI LLM request failed: {exc}") from exc
        text = _extract_openai_text(response_payload)
        return LLMResult(data=_json_from_text(text), provider="openai", model=self.openai_model)

    def _gemini_json(self, system_prompt: str, user_prompt: str, *, timeout: int) -> LLMResult:
        if not self.gemini_key:
            raise ExternalServiceUnavailable("GEMINI_API_KEY is not configured.")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nReturn JSON only.\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            f"{self.gemini_base_url}/models/{self.gemini_model}:generateContent?key={self.gemini_key}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=_build_ssl_context()) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ExternalServiceError(f"Gemini LLM request failed: {body[:500]}") from exc
        except Exception as exc:
            raise ExternalServiceError(f"Gemini LLM request failed: {exc}") from exc
        text = _extract_gemini_text(response_payload)
        return LLMResult(data=_json_from_text(text), provider="gemini", model=self.gemini_model)


def get_live_llm_client() -> LiveLLMClient:
    return LiveLLMClient()


def external_interface_registry() -> dict[str, str]:
    """Human-readable external boundary inventory for reviews and health checks."""
    return {
        "hrms": "HRMS REST/LDAP authentication and profile sync",
        "cctns": "CCTNS case metadata sync and retry queue",
        "dsc": "Digital Signature Certificate bridge",
        "ocr": "Self-hosted OCR gateway with approved Google Document AI fallback",
        "llm": "Self-hosted structured JSON LLM gateway with approved OpenAI/Gemini fallback",
        "translation": "Google Translate/OpenAI/Gemini translation adapters",
        "object_storage": "Evidence/document object storage",
        "search": "OpenSearch case/evidence search index",
        "vector_store": "pgvector embeddings in private Postgres",
        "knowledge_intelligence_service": "Reusable KIS hybrid retrieval and governed BNS reasoning service",
        "job_queue": "Redis/Celery or Temporal background workflow backplane",
        "notification": "In-app/external notification gateway",
    }


def ai_boundary_status() -> dict[str, Any]:
    """Return non-secret AI boundary configuration for admin readiness checks."""
    llm_provider = (_env("IQW_LLM_PROVIDER") or "auto").lower().replace("-", "_")
    if llm_provider == "auto":
        llm_provider = (
            "self_hosted"
            if _env("IQW_SELF_HOSTED_LLM_URL")
            else "openai"
            if _env("OPENAI_API_KEY")
            else "gemini"
            if _env("GEMINI_API_KEY")
            else "stub"
        )
    ocr_provider = (_env("IQW_OCR_PROVIDER") or "auto").lower().replace("-", "_")
    if ocr_provider == "auto":
        ocr_provider = "self_hosted" if _env("IQW_SELF_HOSTED_OCR_URL") else "google_document_ai"
    return {
        "llm_provider": llm_provider,
        "llm_self_hosted_configured": bool(_env("IQW_SELF_HOSTED_LLM_URL")),
        "ocr_provider": ocr_provider,
        "ocr_self_hosted_configured": bool(_env("IQW_SELF_HOSTED_OCR_URL")),
        "external_ai_approval": _external_ai_approval_status(),
        "kis": {
            "enabled": _is_true("IQW_KIS_ENABLED", False),
            "configured": bool(
                _env("IQW_KIS_BASE_URL")
                and _env("IQW_KIS_API_KEY")
                and _env("IQW_KIS_DOMAIN")
                and _env("IQW_KIS_KB")
            ),
            "base_url_configured": bool(_env("IQW_KIS_BASE_URL")),
            "credential_configured": bool(_env("IQW_KIS_API_KEY")),
            "domain_id": _env("IQW_KIS_DOMAIN"),
            "knowledge_base_id": _env("IQW_KIS_KB"),
        },
        "production_runtime": _is_production_runtime(),
    }
