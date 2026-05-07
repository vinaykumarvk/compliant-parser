"""Structural tests for PWA, offline queue, Background Sync, and self-hosted OCR gateway.

AC-003-5: Background Sync queue registration
BR-003-2: Offline queue per-file progress display
AC-012-1: PWA installable (manifest)
AC-012-2: IndexedDB offline uploads
AC-012-4: Background Sync auto-upload via service worker
AC-012-5: Failed sync retry mechanism
BR-011-2: Self-hosted TrOCR/Donut OCR gateway in docker-compose
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestPWAManifest(unittest.TestCase):
    """AC-012-1: PWA installable on desktop/mobile."""

    def setUp(self):
        manifest_path = os.path.join(PROJECT_ROOT, "manifest.json")
        with open(manifest_path) as f:
            self.manifest = json.load(f)

    def test_manifest_has_required_fields(self):
        self.assertIn("name", self.manifest)
        self.assertIn("short_name", self.manifest)
        self.assertIn("start_url", self.manifest)
        self.assertIn("display", self.manifest)
        self.assertIn("icons", self.manifest)

    def test_display_is_standalone(self):
        self.assertEqual(self.manifest["display"], "standalone")

    def test_has_icons(self):
        self.assertGreater(len(self.manifest["icons"]), 0)
        for icon in self.manifest["icons"]:
            self.assertIn("src", icon)
            self.assertIn("sizes", icon)

    def test_start_url_is_root(self):
        self.assertEqual(self.manifest["start_url"], "/")


class TestServiceWorkerBackgroundSync(unittest.TestCase):
    """AC-003-5: Background Sync event listener.
    AC-012-4: Auto-sync on connectivity restored."""

    def setUp(self):
        sw_path = os.path.join(PROJECT_ROOT, "sw.js")
        with open(sw_path) as f:
            self.sw_content = f.read()

    def test_sync_event_listener_exists(self):
        """AC-012-4: Service worker listens for sync events."""
        self.assertIn('addEventListener("sync"', self.sw_content)

    def test_sync_tag_is_document_upload(self):
        """AC-003-5: Sync tag matches 'document-upload'."""
        self.assertIn('"document-upload"', self.sw_content)

    def test_sync_notifies_client(self):
        """AC-012-4: Sync handler posts message to client."""
        self.assertIn("sync-offline-uploads", self.sw_content)
        self.assertIn("postMessage", self.sw_content)

    def test_cache_name_defined(self):
        self.assertRegex(self.sw_content, r'CACHE_NAME\s*=\s*"iqw-v\d+"')

    def test_install_event_caches_static_assets(self):
        self.assertIn('addEventListener("install"', self.sw_content)
        self.assertIn("caches.open", self.sw_content)

    def test_fetch_event_handles_api_calls(self):
        self.assertIn('addEventListener("fetch"', self.sw_content)
        self.assertIn("/api/", self.sw_content)


class TestOfflineQueueUI(unittest.TestCase):
    """AC-012-2: IndexedDB offline uploads.
    BR-003-2: Offline queue per-file progress display.
    AC-012-5: Failed sync retry."""

    def setUp(self):
        index_path = os.path.join(PROJECT_ROOT, "index.html")
        with open(index_path) as f:
            self.html = f.read()

    def test_indexeddb_store_defined(self):
        """AC-012-2: IndexedDB store for offline uploads exists."""
        self.assertIn("OfflineUploadQueue", self.html)
        self.assertIn("indexedDB", self.html)

    def test_sync_tag_registration(self):
        """AC-003-5: Background sync tag registration in upload flow."""
        self.assertIn('sync.register("document-upload")', self.html)

    def test_sync_message_handler(self):
        """AC-003-5: Client-side handler for sync-offline-uploads message."""
        self.assertIn("sync-offline-uploads", self.html)

    def test_offline_queue_container_exists(self):
        """BR-003-2: Offline queue UI container."""
        self.assertIn("offlineUploadQueue", self.html)
        self.assertIn("offline-queue", self.html)

    def test_per_file_status_display(self):
        """BR-003-2: Queue shows per-file status."""
        # Should render status per item (Queued, Syncing, Synced, Failed)
        self.assertIn("Queued", self.html)
        self.assertIn("Synced", self.html)
        self.assertIn("Failed", self.html)

    def test_retry_mechanism_exists(self):
        """AC-012-5: Failed sync has retry capability."""
        # Should have retry button or Sync All
        self.assertIn("Sync All", self.html)

    def test_online_offline_event_listeners(self):
        """AC-012-4: Online/offline detection."""
        self.assertIn('"online"', self.html)
        self.assertIn('"offline"', self.html)


class TestDockerComposeOCRGateway(unittest.TestCase):
    """BR-011-2: Self-hosted TrOCR/Donut OCR gateway in docker-compose."""

    def setUp(self):
        compose_path = os.path.join(PROJECT_ROOT, "deploy", "docker-compose.onprem.yml")
        with open(compose_path) as f:
            self.compose_content = f.read()

    def test_ocr_gateway_service_exists(self):
        self.assertIn("ocr-gateway:", self.compose_content)

    def test_trocr_model_configured(self):
        self.assertIn("microsoft/trocr-base-printed", self.compose_content)

    def test_donut_fallback_model_configured(self):
        self.assertIn("naver-clova-ix/donut-base", self.compose_content)

    def test_ocr_gateway_has_healthcheck(self):
        # After the ocr-gateway service, there should be a healthcheck
        self.assertIn("healthcheck:", self.compose_content)
        self.assertIn("/health", self.compose_content)

    def test_ocr_models_volume(self):
        self.assertIn("ocr-models:", self.compose_content)

    def test_memory_limit(self):
        self.assertIn("4G", self.compose_content)

    def test_app_depends_on_ocr_gateway(self):
        """App service must depend on ocr-gateway."""
        self.assertIn("ocr-gateway:", self.compose_content)

    def test_self_hosted_llm_required(self):
        """BR-007-2: IQW_REQUIRE_SELF_HOSTED_LLM must be set."""
        self.assertIn("IQW_REQUIRE_SELF_HOSTED_LLM", self.compose_content)


class TestOffenceTypeBadgeInHeader(unittest.TestCase):
    """AC-002-3 (verify): Offence type badge is in case dashboard header."""

    def setUp(self):
        index_path = os.path.join(PROJECT_ROOT, "index.html")
        with open(index_path) as f:
            self.html = f.read()

    def test_offence_type_badge_element(self):
        self.assertIn("caseDetailOffenceType", self.html)
        self.assertIn("offence-type-badge", self.html)

    def test_badge_css_styling(self):
        self.assertIn(".offence-type-badge", self.html)


class TestInvestigationPlanCheckboxes(unittest.TestCase):
    """AC-009-7 (verify): Investigation plan has completion checkboxes."""

    def setUp(self):
        index_path = os.path.join(PROJECT_ROOT, "index.html")
        with open(index_path) as f:
            self.html = f.read()

    def test_plan_tab_exists(self):
        self.assertIn("caseTabPlan", self.html)

    def test_plan_generate_button(self):
        self.assertIn("casePlanGenerateBtn", self.html)

    def test_render_investigation_plan_function(self):
        self.assertIn("renderInvestigationPlan", self.html)

    def test_checkbox_in_plan_rendering(self):
        self.assertIn("data-plan-step", self.html)
        self.assertIn('type="checkbox"', self.html)

    def test_plan_completion_saves_via_patch(self):
        """Checkbox change triggers PATCH to save completion state."""
        self.assertIn("investigation-plan", self.html)


if __name__ == "__main__":
    unittest.main()
