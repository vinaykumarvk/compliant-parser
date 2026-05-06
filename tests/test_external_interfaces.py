from __future__ import annotations

import json
import os
import re
import unittest
from unittest.mock import patch

from external_interfaces import (
    ExternalServiceUnavailable,
    LiveLLMClient,
    ai_boundary_status,
    get_object_storage_client,
    run_configured_ocr,
)


class _JsonResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class TestAIBoundary(unittest.TestCase):
    def test_auto_prefers_self_hosted_llm_when_configured(self):
        def fake_urlopen(request, timeout=0, context=None):
            self.assertTrue(request.full_url.endswith("/v1/chat/completions"))
            body = json.loads(request.data.decode("utf-8"))
            self.assertEqual(body["model"], "local-legal-model")
            return _JsonResponse({"choices": [{"message": {"content": "{\"ok\": true}"}}]})

        with patch.dict(
            os.environ,
            {
                "IQW_SELF_HOSTED_LLM_URL": "https://llm.internal",
                "IQW_SELF_HOSTED_LLM_MODEL": "local-legal-model",
            },
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = LiveLLMClient().generate_json("system", "{\"input\": true}")

        self.assertEqual(result.provider, "self_hosted")
        self.assertEqual(result.model, "local-legal-model")
        self.assertTrue(result.data["ok"])

    def test_llm_payload_masks_pii_and_restores_response(self):
        def fake_urlopen(request, timeout=0, context=None):
            body = json.loads(request.data.decode("utf-8"))
            serialized = json.dumps(body)
            self.assertNotIn("Rajesh Kumar", serialized)
            self.assertNotIn("9876543210", serialized)
            name_token = re.search(r"\[\[PII_PERSON_NAME_\d{4}\]\]", serialized).group(0)
            phone_token = re.search(r"\[\[PII_PHONE_\d{4}\]\]", serialized).group(0)
            return _JsonResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"complainant": name_token, "phone": phone_token}
                                )
                            }
                        }
                    ]
                }
            )

        with patch.dict(
            os.environ,
            {
                "IQW_SELF_HOSTED_LLM_URL": "https://llm.internal",
                "IQW_SELF_HOSTED_LLM_MODEL": "local-legal-model",
            },
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = LiveLLMClient().generate_json(
                "system",
                "{\"complaint_text\": \"I, Rajesh Kumar, phone 9876543210, report theft\"}",
            )

        self.assertEqual(result.data["complainant"], "Rajesh Kumar")
        self.assertEqual(result.data["phone"], "9876543210")
        self.assertTrue(result.privacy["pii_redacted_before_llm"])
        self.assertFalse(result.privacy["raw_pii_sent_to_llm"])

    def test_production_openai_requires_external_ai_approval(self):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "IQW_LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
            },
            clear=True,
        ):
            with self.assertRaises(ExternalServiceUnavailable) as ctx:
                LiveLLMClient().generate_json("system", "{}")

        self.assertIn("requires written external-AI approval", str(ctx.exception))

    def test_configured_ocr_uses_self_hosted_gateway(self):
        def fake_urlopen(request, timeout=0, context=None):
            self.assertEqual(request.full_url, "https://ocr.internal/process")
            body = json.loads(request.data.decode("utf-8"))
            self.assertEqual(body["file_name"], "scan.pdf")
            self.assertIn("content_base64", body)
            return _JsonResponse({"text": "recognized text", "page_count": 1, "confidence": 0.93})

        with patch.dict(
            os.environ,
            {
                "IQW_OCR_PROVIDER": "self_hosted",
                "IQW_SELF_HOSTED_OCR_URL": "https://ocr.internal/process",
            },
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = run_configured_ocr(b"file-bytes", file_name="scan.pdf", mime_type="application/pdf")

        self.assertEqual(result.provider, "self_hosted")
        self.assertEqual(result.text, "recognized text")
        self.assertEqual(result.page_count, 1)
        self.assertEqual(result.confidence, 0.93)

    def test_production_google_document_ai_requires_approval_before_call(self):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "IQW_OCR_PROVIDER": "google_document_ai",
                "DOC_AI_PROJECT_ID": "project",
                "DOC_AI_LOCATION": "eu",
                "DOC_AI_PROCESSOR_ID": "processor",
            },
            clear=True,
        ):
            with self.assertRaises(ExternalServiceUnavailable) as ctx:
                run_configured_ocr(b"file-bytes", file_name="scan.pdf", mime_type="application/pdf")

        self.assertIn("requires written external-AI approval", str(ctx.exception))

    def test_ai_boundary_status_is_non_secret(self):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "IQW_SELF_HOSTED_LLM_URL": "https://llm.internal",
                "IQW_SELF_HOSTED_OCR_URL": "https://ocr.internal",
                "EXTERNAL_AI_API_APPROVED": "true",
                "EXTERNAL_AI_APPROVAL_ID": "approval-1",
                "EXTERNAL_AI_APPROVED_BY": "commissioner",
            },
            clear=True,
        ):
            status = ai_boundary_status()

        self.assertEqual(status["llm_provider"], "self_hosted")
        self.assertTrue(status["llm_self_hosted_configured"])
        self.assertEqual(status["ocr_provider"], "self_hosted")
        self.assertTrue(status["ocr_self_hosted_configured"])
        self.assertTrue(status["external_ai_approval"]["approved"])
        self.assertNotIn("key", json.dumps(status).lower())

    def test_minio_storage_requires_bucket(self):
        with patch.dict(
            os.environ,
            {
                "OBJECT_STORAGE_PROVIDER": "minio",
                "MINIO_ENDPOINT": "http://minio:9000",
            },
            clear=True,
        ):
            with self.assertRaises(ExternalServiceUnavailable) as ctx:
                get_object_storage_client()

        self.assertIn("MINIO_BUCKET", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
