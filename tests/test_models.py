"""Tests for Phase 1: Data Model & API Infrastructure (async ORM version).

Most tests here verify enum values and model instantiation, which are
purely synchronous operations.  They are still wrapped in AsyncTestCase
for consistency with the rest of the test suite.
"""

from __future__ import annotations

import sys
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import AsyncTestCase

from models import (
    ActionTrackerTask,
    ActionTypeEnum,
    ActName,
    AIAnalysisResult,
    AlertSeverity,
    AlertType,
    AnalysisType,
    AuditLog,
    Base,
    Case,
    CaseActivity,
    CaseDocument,
    CaseStatus,
    CaseType,
    CCTNSSyncStatus,
    Citation,
    ConfidenceLevel,
    CongruenceAlert,
    DismissReasonCode,
    DocumentCategory,
    DocumentTemplate,
    DocumentType,
    GeneratedDocument,
    InvestigationPlan,
    JudgmentAnalysis,
    KBEntryStatus,
    KBEntryType,
    KnowledgeBaseEntry,
    Notification,
    OCRConfidence,
    OCRStatus,
    OffenceType,
    PoliceStation,
    SectionRecommendation,
    SignatureStatus,
    TaskPriority,
    TaskSource,
    TaskStatus,
    UploadMethod,
    UsageEvent,
    User,
    UserRole,
)
from api_v1 import ErrorCode, raise_api_error, check_rate_limit, APIErrorResponse


class TestEnums(AsyncTestCase):
    """Verify all enum values match BRD specifications."""

    async def test_user_roles(self):
        self.assertEqual(
            set(r.value for r in UserRole),
            {"Senior_Command", "Zone_Officer", "SHO", "IO", "Clerk", "AI_Admin", "System_Admin"},
        )

    async def test_case_types(self):
        self.assertEqual(set(t.value for t in CaseType), {"FIR", "Petition", "Suo_Motu"})

    async def test_case_statuses(self):
        expected = {
            "Complaint_Received", "FIR_Registered", "Under_Investigation",
            "Charge_Sheet_Filed", "Closure_Report_Filed", "Court_Proceedings",
            "Transferred", "Disposed", "Closed_No_FIR",
        }
        self.assertEqual(set(s.value for s in CaseStatus), expected)

    async def test_cctns_sync_statuses(self):
        expected = {"Synced", "Pending", "Failed", "Not_Applicable"}
        self.assertEqual(set(s.value for s in CCTNSSyncStatus), expected)

    async def test_document_types(self):
        expected = {
            "Petition", "FIR", "Witness_Statement", "Charge_Sheet",
            "Medical_Report", "FSL_Report", "Seizure_Memo", "Arrest_Memo",
            "Remand_Note", "Confession", "CDR", "Other",
        }
        self.assertEqual(set(t.value for t in DocumentType), expected)

    async def test_analysis_types(self):
        expected = {
            "Quality_Check", "Section_Recommendation", "Congruence_Detection",
            "SOP_Generation", "Judgment_Analysis", "Ingredient_Mapping",
        }
        self.assertEqual(set(t.value for t in AnalysisType), expected)

    async def test_alert_types(self):
        expected = {
            "Contradiction", "Timeline_Inconsistency", "Role_Mismatch",
            "Medical_Narrative_Discrepancy", "Missing_Carry_Forward",
        }
        self.assertEqual(set(t.value for t in AlertType), expected)

    async def test_document_categories(self):
        expected = {"FSL_Communication", "Evidence_Certificate", "Legal_Notice", "Legal_Draft"}
        self.assertEqual(set(c.value for c in DocumentCategory), expected)

    async def test_kb_entry_statuses(self):
        expected = {"Draft", "Staging", "Production", "Deprecated"}
        self.assertEqual(set(s.value for s in KBEntryStatus), expected)

    async def test_action_type_enum(self):
        expected = {
            "Upload", "Edit", "Delete", "AI_Analysis", "Document_Generation",
            "Sign", "Export", "Login", "Logout", "Config_Change",
            "KB_Update", "Promote", "Rollback",
        }
        self.assertEqual(set(a.value for a in ActionTypeEnum), expected)

    async def test_task_priority(self):
        self.assertEqual(set(p.value for p in TaskPriority), {"High", "Medium", "Low"})

    async def test_signature_status(self):
        self.assertEqual(set(s.value for s in SignatureStatus), {"Unsigned", "Signed", "Signature_Failed"})


class TestModelInstantiation(AsyncTestCase):
    """Verify all 19 models can be instantiated with minimal required fields."""

    async def test_police_station(self):
        obj = PoliceStation(station_code="PS_TEST", name="Test Station")
        self.assertEqual(obj.station_code, "PS_TEST")
        self.assertFalse(obj.is_deleted)

    async def test_offence_type(self):
        obj = OffenceType(name="Theft", category="Property", bns_section="303")
        self.assertEqual(obj.name, "Theft")

    async def test_user(self):
        obj = User(employee_id="EMP001", full_name="Test IO", role=UserRole.IO)
        self.assertEqual(obj.role, UserRole.IO)
        self.assertTrue(obj.is_active)

    async def test_case(self):
        obj = Case(case_type=CaseType.FIR, crime_no="0001/2026", status=CaseStatus.Complaint_Received)
        self.assertEqual(obj.status, CaseStatus.Complaint_Received)
        self.assertEqual(obj.cctns_sync_status, CCTNSSyncStatus.Not_Applicable)

    async def test_case_document(self):
        obj = CaseDocument(file_name="test.pdf", document_type=DocumentType.FIR)
        self.assertEqual(obj.document_type, DocumentType.FIR)
        self.assertEqual(obj.version, 1)
        self.assertTrue(obj.is_latest_version)

    async def test_case_activity(self):
        obj = CaseActivity(activity_type="Upload", description="Uploaded FIR")
        self.assertEqual(obj.activity_type, "Upload")

    async def test_ai_analysis_result(self):
        obj = AIAnalysisResult(analysis_type=AnalysisType.Quality_Check, model_name="test-v1")
        self.assertEqual(obj.analysis_type, AnalysisType.Quality_Check)
        self.assertFalse(obj.io_reviewed)

    async def test_citation(self):
        obj = Citation(excerpt_text="sample text", citation_purpose="test")
        self.assertEqual(obj.excerpt_text, "sample text")

    async def test_congruence_alert(self):
        obj = CongruenceAlert(alert_type=AlertType.Contradiction, severity=AlertSeverity.High)
        self.assertFalse(obj.is_dismissed)

    async def test_section_recommendation(self):
        obj = SectionRecommendation(section_code="303 BNS", act_name=ActName.BNS)
        self.assertEqual(obj.act_name, ActName.BNS)

    async def test_section_recommendation_enhanced_fields(self):
        obj = SectionRecommendation(
            section_code="303",
            act_name=ActName.BNS,
            applicability_rank=1,
            statutory_text="Whoever intending to take dishonestly...",
            ingredient_mapping=[{"ingredient": "taking", "status": "satisfied", "complaint_fact": "stolen"}],
        )
        self.assertEqual(obj.applicability_rank, 1)
        self.assertEqual(obj.statutory_text, "Whoever intending to take dishonestly...")
        self.assertEqual(len(obj.ingredient_mapping), 1)

    async def test_generated_document(self):
        obj = GeneratedDocument(document_category=DocumentCategory.Legal_Draft)
        self.assertEqual(obj.digital_signature_status, SignatureStatus.Unsigned)

    async def test_document_template(self):
        obj = DocumentTemplate(template_name="Test", category=DocumentCategory.FSL_Communication)
        self.assertTrue(obj.is_active)

    async def test_investigation_plan(self):
        obj = InvestigationPlan(offence_type_detected="Theft")
        self.assertTrue(obj.is_editable)

    async def test_judgment_analysis(self):
        obj = JudgmentAnalysis(case_facts="Facts", verdict="Conviction")
        self.assertEqual(obj.verdict, "Conviction")

    async def test_knowledge_base_entry(self):
        obj = KnowledgeBaseEntry(entry_type=KBEntryType.Checklist, title="Generic")
        self.assertEqual(obj.status, KBEntryStatus.Draft)
        self.assertEqual(obj.version, 1)

    async def test_audit_log(self):
        obj = AuditLog(action_type=ActionTypeEnum.Login, entity_type="User", entity_id="123")
        self.assertEqual(obj.action_type, ActionTypeEnum.Login)

    async def test_notification(self):
        obj = Notification(type="info", message="Test notification")
        self.assertFalse(obj.is_read)

    async def test_action_tracker_task(self):
        obj = ActionTrackerTask(task_name="File charge sheet", priority=TaskPriority.High)
        self.assertEqual(obj.status, TaskStatus.Pending)

    async def test_usage_event(self):
        obj = UsageEvent(event_type="page_view", module="cases")
        self.assertEqual(obj.module, "cases")


class TestBase(AsyncTestCase):
    """Verify Base metadata contains all expected tables."""

    async def test_table_count(self):
        tables = set(Base.metadata.tables.keys())
        expected = {
            "police_stations", "offence_types", "users", "cases",
            "case_documents", "case_activities", "ai_analysis_results",
            "citations", "congruence_alerts", "section_recommendations",
            "generated_documents", "document_templates", "investigation_plans",
            "judgment_analyses", "knowledge_base_entries", "audit_logs",
            "notifications", "action_tracker_tasks", "usage_events",
        }
        self.assertTrue(expected.issubset(tables), f"Missing tables: {expected - tables}")


class TestErrorFormat(AsyncTestCase):
    """Verify standard error format from api_v1.py."""

    async def test_error_codes_have_status(self):
        for code in ErrorCode:
            from api_v1 import _ERROR_STATUS
            self.assertIn(code, _ERROR_STATUS)

    async def test_raise_api_error(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            raise_api_error(ErrorCode.VALIDATION_ERROR, "Bad input", field="crime_no")
        exc = ctx.exception
        self.assertEqual(exc.status_code, 400)
        detail = exc.detail["error"]
        self.assertEqual(detail["code"], "VALIDATION_ERROR")
        self.assertEqual(detail["message"], "Bad input")
        self.assertEqual(detail["field"], "crime_no")
        self.assertIsNotNone(detail["request_id"])

    async def test_error_response_model(self):
        resp = APIErrorResponse(error={
            "code": "NOT_FOUND",
            "message": "Case not found",
            "field": None,
            "request_id": "abc12345",
        })
        self.assertEqual(resp.error.code, "NOT_FOUND")


if __name__ == "__main__":
    import unittest
    unittest.main()
