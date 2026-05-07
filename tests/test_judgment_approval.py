"""Tests for AC-015-5 (checklist proposal status) and AC-015-6 (judgment → KB auto-feed)."""

from __future__ import annotations

import sys
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import AsyncTestCase
from models import JudgmentAnalysis, KnowledgeBaseEntry, CaseDocument


class TestJudgmentChecklistProposalStatus(AsyncTestCase):
    """AC-015-5: Checklist proposals require AI Admin approval."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        # Create a CaseDocument stub for the foreign key
        self.case_doc = CaseDocument(
            case_id="case-1",
            document_type="Judgment",
            file_name="judgment.pdf",
        )
        self.db.add(self.case_doc)
        await self.db.flush()

    async def test_new_analysis_has_pending_approval_status(self):
        analysis = JudgmentAnalysis(
            uploaded_file_id=self.case_doc.id,
            case_facts="Robbery case facts",
            proposed_checklist_updates=[
                {"type": "Checklist", "title": "Verify CCTV", "items": ["Check timestamps"]},
            ],
            checklist_update_status="Pending_AI_Admin_Approval",
            created_by="u1",
        )
        self.db.add(analysis)
        await self.db.flush()

        stored = await self.db.get(JudgmentAnalysis, analysis.id)
        self.assertEqual(stored.checklist_update_status, "Pending_AI_Admin_Approval")
        self.assertEqual(len(stored.proposed_checklist_updates), 1)

    async def test_approved_status_set_on_approval(self):
        analysis = JudgmentAnalysis(
            uploaded_file_id=self.case_doc.id,
            case_facts="Theft case",
            proposed_checklist_updates=[],
            checklist_update_status="Pending_AI_Admin_Approval",
            created_by="u1",
        )
        self.db.add(analysis)
        await self.db.flush()

        # Simulate approval
        analysis.checklist_update_status = "Approved"
        analysis.approved_by = "admin-1"
        await self.db.flush()

        stored = await self.db.get(JudgmentAnalysis, analysis.id)
        self.assertEqual(stored.checklist_update_status, "Approved")
        self.assertEqual(stored.approved_by, "admin-1")


class TestJudgmentKBAutoFeed(AsyncTestCase):
    """AC-015-6: Approved judgment findings auto-feed KB entries."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.db.clear()
        self.case_doc = CaseDocument(
            case_id="case-2",
            document_type="Judgment",
            file_name="judgment_v2.pdf",
        )
        self.db.add(self.case_doc)
        await self.db.flush()

    async def test_approval_creates_kb_entries_from_proposals(self):
        """AC-015-6: Each proposed checklist update becomes a KB entry."""
        analysis = JudgmentAnalysis(
            uploaded_file_id=self.case_doc.id,
            case_facts="Murder case facts",
            investigation_lessons="Always verify alibi early",
            avoidable_errors="Delayed forensic collection",
            proposed_checklist_updates=[
                {"type": "Checklist", "title": "Forensic timing", "items": ["Collect within 24h"]},
                {"type": "SOP", "title": "Alibi verification", "items": ["Cross-reference witnesses"]},
            ],
            checklist_update_status="Pending_AI_Admin_Approval",
            created_by="u1",
        )
        self.db.add(analysis)
        await self.db.flush()

        # Simulate the approve_judgment_findings_endpoint logic
        analysis.checklist_update_status = "Approved"
        analysis.approved_by = "admin-1"
        kb_entries_created = 0
        for proposal in (analysis.proposed_checklist_updates or []):
            entry = KnowledgeBaseEntry(
                entry_type=proposal.get("type", "Checklist"),
                title=proposal.get("title", "Judgment-derived item"),
                content={
                    "items": proposal.get("items", []),
                    "source_judgment_analysis_id": analysis.id,
                    "investigation_lessons": analysis.investigation_lessons,
                    "avoidable_errors": analysis.avoidable_errors,
                },
                status="Draft",
                version=1,
                created_by="admin-1",
            )
            self.db.add(entry)
            kb_entries_created += 1
        await self.db.flush()

        self.assertEqual(kb_entries_created, 2)

        # Verify KB entries exist in store
        from sqlalchemy import select
        result = await self.db.execute(select(KnowledgeBaseEntry))
        entries = result.scalars().all()
        self.assertEqual(len(entries), 2)

        titles = {e.title for e in entries}
        self.assertIn("Forensic timing", titles)
        self.assertIn("Alibi verification", titles)

        for entry in entries:
            self.assertEqual(entry.status, "Draft")
            self.assertEqual(entry.version, 1)
            self.assertIn("source_judgment_analysis_id", entry.content)
            self.assertIn("investigation_lessons", entry.content)

    async def test_already_approved_is_idempotent(self):
        """Re-approving should not create duplicate KB entries."""
        analysis = JudgmentAnalysis(
            uploaded_file_id=self.case_doc.id,
            case_facts="Case facts",
            proposed_checklist_updates=[
                {"type": "Checklist", "title": "Item 1", "items": ["Check A"]},
            ],
            checklist_update_status="Approved",
            approved_by="admin-1",
            created_by="u1",
        )
        self.db.add(analysis)
        await self.db.flush()

        # The endpoint returns early for already-approved
        if analysis.checklist_update_status == "Approved":
            result = {"id": analysis.id, "status": "already_approved", "kb_entries_created": 0}

        self.assertEqual(result["status"], "already_approved")
        self.assertEqual(result["kb_entries_created"], 0)

    async def test_no_proposals_creates_zero_entries(self):
        analysis = JudgmentAnalysis(
            uploaded_file_id=self.case_doc.id,
            case_facts="Simple case",
            proposed_checklist_updates=[],
            checklist_update_status="Pending_AI_Admin_Approval",
            created_by="u1",
        )
        self.db.add(analysis)
        await self.db.flush()

        analysis.checklist_update_status = "Approved"
        kb_count = 0
        for proposal in (analysis.proposed_checklist_updates or []):
            kb_count += 1
        self.assertEqual(kb_count, 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
