"""SQLAlchemy 2.0 ORM models for the IQW platform.

Defines all 19 domain entities with UUID primary keys, audit fields,
soft-delete support, and portable enum handling.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    type_annotation_map = {
        dict: sa.JSON,
        list: sa.JSON,
        Any: sa.JSON,
    }


from sqlalchemy import event  # noqa: E402


@event.listens_for(Base, "init", propagate=True)
def _apply_column_defaults(target: Any, args: Any, kwargs: dict) -> None:
    """Apply column-level defaults that SQLAlchemy skips when
    ``from __future__ import annotations`` is active (PEP 563)."""
    mapper = sa.inspect(type(target))
    for attr in mapper.column_attrs:
        key = attr.key
        if key not in kwargs:
            col = attr.columns[0]
            if col.default is not None:
                if col.default.is_scalar:
                    kwargs[key] = col.default.arg
                elif col.default.is_callable:
                    kwargs[key] = col.default.arg(None)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    IO = "IO"
    Clerk = "Clerk"
    AI_Admin = "AI_Admin"
    System_Admin = "System_Admin"


class CaseType(str, Enum):
    FIR = "FIR"
    Petition = "Petition"
    Suo_Motu = "Suo_Motu"


class CaseStatus(str, Enum):
    Open = "Open"
    Under_Investigation = "Under_Investigation"
    Charge_Sheet_Filed = "Charge_Sheet_Filed"
    Closed = "Closed"
    Transferred = "Transferred"


class CCTNSSyncStatus(str, Enum):
    Synced = "Synced"
    Pending = "Pending"
    Failed = "Failed"
    Not_Applicable = "Not_Applicable"


class DocumentType(str, Enum):
    Petition = "Petition"
    FIR = "FIR"
    Witness_Statement = "Witness_Statement"
    Charge_Sheet = "Charge_Sheet"
    Medical_Report = "Medical_Report"
    FSL_Report = "FSL_Report"
    Seizure_Memo = "Seizure_Memo"
    Arrest_Memo = "Arrest_Memo"
    Remand_Note = "Remand_Note"
    Confession = "Confession"
    CDR = "CDR"
    Other = "Other"


class OCRStatus(str, Enum):
    Not_Required = "Not_Required"
    Pending = "Pending"
    Processing = "Processing"
    Completed = "Completed"
    Failed = "Failed"


class OCRConfidence(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


class AnalysisType(str, Enum):
    Quality_Check = "Quality_Check"
    Section_Recommendation = "Section_Recommendation"
    Congruence_Detection = "Congruence_Detection"
    SOP_Generation = "SOP_Generation"
    Judgment_Analysis = "Judgment_Analysis"
    Ingredient_Mapping = "Ingredient_Mapping"


class ConfidenceLevel(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


class AlertType(str, Enum):
    Contradiction = "Contradiction"
    Timeline_Inconsistency = "Timeline_Inconsistency"
    Role_Mismatch = "Role_Mismatch"
    Medical_Narrative_Discrepancy = "Medical_Narrative_Discrepancy"
    Missing_Carry_Forward = "Missing_Carry_Forward"


class AlertSeverity(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


class DismissReasonCode(str, Enum):
    Typographical_Error = "Typographical_Error"
    Context_Difference = "Context_Difference"
    Intentional_Variation = "Intentional_Variation"
    Other = "Other"


class ActName(str, Enum):
    IPC = "IPC"
    BNS = "BNS"
    CrPC = "CrPC"
    BNSS = "BNSS"
    IT_Act = "IT_Act"
    NDPS = "NDPS"
    POCSO = "POCSO"
    SC_ST_Act = "SC_ST_Act"
    Other = "Other"


class DocumentCategory(str, Enum):
    FSL_Communication = "FSL_Communication"
    Evidence_Certificate = "Evidence_Certificate"
    Legal_Notice = "Legal_Notice"
    Legal_Draft = "Legal_Draft"


class SignatureStatus(str, Enum):
    Unsigned = "Unsigned"
    Signed = "Signed"
    Signature_Failed = "Signature_Failed"


class KBEntryType(str, Enum):
    Checklist = "Checklist"
    SOP = "SOP"
    Template = "Template"
    Legal_Reference = "Legal_Reference"


class KBEntryStatus(str, Enum):
    Draft = "Draft"
    Staging = "Staging"
    Production = "Production"
    Deprecated = "Deprecated"


class ActionTypeEnum(str, Enum):
    Upload = "Upload"
    Edit = "Edit"
    Delete = "Delete"
    AI_Analysis = "AI_Analysis"
    Document_Generation = "Document_Generation"
    Sign = "Sign"
    Export = "Export"
    Login = "Login"
    Logout = "Logout"
    Config_Change = "Config_Change"
    KB_Update = "KB_Update"
    Promote = "Promote"
    Rollback = "Rollback"


class TaskPriority(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


class TaskStatus(str, Enum):
    Pending = "Pending"
    Overdue = "Overdue"
    Completed = "Completed"


class TaskSource(str, Enum):
    Statutory = "Statutory"
    SOP = "SOP"
    Manual = "Manual"


class UploadMethod(str, Enum):
    Drag_Drop = "Drag_Drop"
    Bulk_Upload = "Bulk_Upload"
    Offline_Queue = "Offline_Queue"
    Scanner = "Scanner"


# ---------------------------------------------------------------------------
# Mixin for common audit + soft-delete columns
# ---------------------------------------------------------------------------

class AuditMixin:
    """Provides created_at, updated_at, created_by, updated_by and
    soft-delete columns (is_deleted, deleted_at) to every model that
    inherits this mixin."""

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        onupdate=sa.text("now()"),
        server_default=None,
        nullable=True,
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        sa.String, nullable=True,
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        sa.String, nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )


# ---------------------------------------------------------------------------
# Helper: reusable UUID primary-key column
# ---------------------------------------------------------------------------

def _pk_uuid() -> Mapped[str]:
    return mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# 1. PoliceStation
# ---------------------------------------------------------------------------

class PoliceStation(AuditMixin, Base):
    __tablename__ = "police_stations"

    id: Mapped[str] = _pk_uuid()
    station_code: Mapped[str] = mapped_column(
        sa.String, unique=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String, nullable=False)
    district: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.text("true"), nullable=False,
    )

    # relationships
    users: Mapped[List[User]] = relationship(back_populates="police_station")
    cases: Mapped[List[Case]] = relationship(back_populates="police_station")


# ---------------------------------------------------------------------------
# 2. OffenceType
# ---------------------------------------------------------------------------

class OffenceType(AuditMixin, Base):
    __tablename__ = "offence_types"

    id: Mapped[str] = _pk_uuid()
    name: Mapped[str] = mapped_column(sa.String, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    bns_section: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    ipc_section: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.text("true"), nullable=False,
    )

    # relationships
    primary_cases: Mapped[List[Case]] = relationship(back_populates="primary_offence_type")


# ---------------------------------------------------------------------------
# 3. User
# ---------------------------------------------------------------------------

class User(AuditMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = _pk_uuid()
    employee_id: Mapped[str] = mapped_column(
        sa.String, unique=True, nullable=False,
    )
    full_name: Mapped[str] = mapped_column(sa.String, nullable=False)
    rank: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    police_station_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("police_stations.id"), nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(UserRole, name="userrole", create_constraint=True, native_enum=False),
        nullable=False,
    )
    email: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.text("true"), nullable=False,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )

    # relationships
    police_station: Mapped[Optional[PoliceStation]] = relationship(
        back_populates="users",
    )
    io_cases: Mapped[List[Case]] = relationship(
        back_populates="io", foreign_keys="[Case.io_id]",
    )
    case_activities: Mapped[List[CaseActivity]] = relationship(
        back_populates="user",
    )
    audit_logs: Mapped[List[AuditLog]] = relationship(
        back_populates="user",
    )
    notifications: Mapped[List[Notification]] = relationship(
        back_populates="user",
    )
    usage_events: Mapped[List[UsageEvent]] = relationship(
        back_populates="user",
    )


# ---------------------------------------------------------------------------
# 4. Case
# ---------------------------------------------------------------------------

class Case(AuditMixin, Base):
    __tablename__ = "cases"

    id: Mapped[str] = _pk_uuid()
    crime_no: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    petition_no: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    case_type: Mapped[CaseType] = mapped_column(
        sa.Enum(CaseType, name="casetype", create_constraint=True, native_enum=False),
        nullable=False,
    )
    offence_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    police_station_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("police_stations.id"), nullable=True,
    )
    io_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    status: Mapped[CaseStatus] = mapped_column(
        sa.Enum(CaseStatus, name="casestatus", create_constraint=True, native_enum=False),
        default=CaseStatus.Open,
        nullable=False,
    )
    cctns_sync_status: Mapped[CCTNSSyncStatus] = mapped_column(
        sa.Enum(CCTNSSyncStatus, name="cctnssyncstatus", create_constraint=True, native_enum=False),
        default=CCTNSSyncStatus.Not_Applicable,
        nullable=False,
    )
    cctns_case_id: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    date_of_occurrence: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )
    date_of_registration: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )
    brief_facts: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    primary_offence_type_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("offence_types.id"), nullable=True,
    )
    secondary_offence_type_ids: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )

    # relationships
    police_station: Mapped[Optional[PoliceStation]] = relationship(
        back_populates="cases",
    )
    io: Mapped[Optional[User]] = relationship(
        back_populates="io_cases", foreign_keys=[io_id],
    )
    primary_offence_type: Mapped[Optional[OffenceType]] = relationship(
        back_populates="primary_cases",
    )
    documents: Mapped[List[CaseDocument]] = relationship(
        back_populates="case",
    )
    activities: Mapped[List[CaseActivity]] = relationship(
        back_populates="case",
    )
    ai_analysis_results: Mapped[List[AIAnalysisResult]] = relationship(
        back_populates="case",
    )
    congruence_alerts: Mapped[List[CongruenceAlert]] = relationship(
        back_populates="case",
    )
    generated_documents: Mapped[List[GeneratedDocument]] = relationship(
        back_populates="case",
    )
    investigation_plan: Mapped[Optional[InvestigationPlan]] = relationship(
        back_populates="case", uselist=False,
    )
    action_tracker_tasks: Mapped[List[ActionTrackerTask]] = relationship(
        back_populates="case",
    )


# ---------------------------------------------------------------------------
# 5. CaseDocument
# ---------------------------------------------------------------------------

class CaseDocument(AuditMixin, Base):
    __tablename__ = "case_documents"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        sa.Enum(DocumentType, name="documenttype", create_constraint=True, native_enum=False),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(sa.String, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    sha256_hash: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    upload_method: Mapped[Optional[UploadMethod]] = mapped_column(
        sa.Enum(UploadMethod, name="uploadmethod", create_constraint=True, native_enum=False),
        nullable=True,
    )
    file_bytes: Mapped[Optional[bytes]] = mapped_column(
        sa.LargeBinary, nullable=True,
    )
    ocr_status: Mapped[OCRStatus] = mapped_column(
        sa.Enum(OCRStatus, name="ocrstatus", create_constraint=True, native_enum=False),
        default=OCRStatus.Not_Required,
        nullable=False,
    )
    ocr_extracted_text: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    ocr_confidence: Mapped[Optional[OCRConfidence]] = mapped_column(
        sa.Enum(OCRConfidence, name="ocrconfidence", create_constraint=True, native_enum=False),
        nullable=True,
    )
    language_detected: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    version: Mapped[int] = mapped_column(
        sa.Integer, default=1, server_default=sa.text("1"), nullable=False,
    )
    is_latest_version: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.text("true"), nullable=False,
    )
    parsed_output: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)

    # relationships
    case: Mapped[Case] = relationship(back_populates="documents")
    ai_analysis_results: Mapped[List[AIAnalysisResult]] = relationship(
        back_populates="document",
    )
    citations_as_source: Mapped[List[Citation]] = relationship(
        back_populates="source_document",
    )
    congruence_alerts_as_a: Mapped[List[CongruenceAlert]] = relationship(
        back_populates="document_a",
        foreign_keys="[CongruenceAlert.document_a_id]",
    )
    congruence_alerts_as_b: Mapped[List[CongruenceAlert]] = relationship(
        back_populates="document_b",
        foreign_keys="[CongruenceAlert.document_b_id]",
    )


# ---------------------------------------------------------------------------
# 6. CaseActivity
# ---------------------------------------------------------------------------

class CaseActivity(AuditMixin, Base):
    __tablename__ = "case_activities"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(sa.String, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    entity_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)

    # relationships
    case: Mapped[Case] = relationship(back_populates="activities")
    user: Mapped[Optional[User]] = relationship(back_populates="case_activities")


# ---------------------------------------------------------------------------
# 7. AIAnalysisResult
# ---------------------------------------------------------------------------

class AIAnalysisResult(AuditMixin, Base):
    __tablename__ = "ai_analysis_results"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), nullable=False,
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("case_documents.id"), nullable=True,
    )
    analysis_type: Mapped[AnalysisType] = mapped_column(
        sa.Enum(AnalysisType, name="analysistype", create_constraint=True, native_enum=False),
        nullable=False,
    )
    model_name: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    input_text_hash: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    confidence_score: Mapped[Optional[ConfidenceLevel]] = mapped_column(
        sa.Enum(ConfidenceLevel, name="confidencelevel", create_constraint=True, native_enum=False),
        nullable=True,
    )
    has_uncertainty_flag: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    uncertainty_tags: Mapped[Optional[list]] = mapped_column(sa.JSON, nullable=True)
    io_reviewed: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    io_review_action: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    io_review_notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)

    # relationships
    case: Mapped[Case] = relationship(back_populates="ai_analysis_results")
    document: Mapped[Optional[CaseDocument]] = relationship(
        back_populates="ai_analysis_results",
    )
    citations: Mapped[List[Citation]] = relationship(
        back_populates="analysis",
    )
    section_recommendations: Mapped[List[SectionRecommendation]] = relationship(
        back_populates="analysis",
    )


# ---------------------------------------------------------------------------
# 8. Citation
# ---------------------------------------------------------------------------

class Citation(AuditMixin, Base):
    __tablename__ = "citations"

    id: Mapped[str] = _pk_uuid()
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis_results.id"), nullable=False,
    )
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("case_documents.id"), nullable=False,
    )
    excerpt_text: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    char_offset_start: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    char_offset_end: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    citation_purpose: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)

    # relationships
    analysis: Mapped[AIAnalysisResult] = relationship(back_populates="citations")
    source_document: Mapped[CaseDocument] = relationship(
        back_populates="citations_as_source",
    )


# ---------------------------------------------------------------------------
# 9. CongruenceAlert
# ---------------------------------------------------------------------------

class CongruenceAlert(AuditMixin, Base):
    __tablename__ = "congruence_alerts"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), nullable=False,
    )
    document_a_id: Mapped[str] = mapped_column(
        ForeignKey("case_documents.id"), nullable=False,
    )
    document_b_id: Mapped[str] = mapped_column(
        ForeignKey("case_documents.id"), nullable=False,
    )
    alert_type: Mapped[AlertType] = mapped_column(
        sa.Enum(AlertType, name="alerttype", create_constraint=True, native_enum=False),
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        sa.Enum(AlertSeverity, name="alertseverity", create_constraint=True, native_enum=False),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    excerpt_doc_a: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    excerpt_doc_b: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    dismiss_reason_code: Mapped[Optional[DismissReasonCode]] = mapped_column(
        sa.Enum(DismissReasonCode, name="dismissreasoncode", create_constraint=True, native_enum=False),
        nullable=True,
    )
    dismiss_notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    dismissed_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )
    feeds_model_refinement: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )

    # relationships
    case: Mapped[Case] = relationship(back_populates="congruence_alerts")
    document_a: Mapped[CaseDocument] = relationship(
        back_populates="congruence_alerts_as_a",
        foreign_keys=[document_a_id],
    )
    document_b: Mapped[CaseDocument] = relationship(
        back_populates="congruence_alerts_as_b",
        foreign_keys=[document_b_id],
    )
    dismissed_by_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[dismissed_by],
    )


# ---------------------------------------------------------------------------
# 10. SectionRecommendation
# ---------------------------------------------------------------------------

class SectionRecommendation(AuditMixin, Base):
    __tablename__ = "section_recommendations"

    id: Mapped[str] = _pk_uuid()
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis_results.id"), nullable=False,
    )
    section_code: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    act_name: Mapped[ActName] = mapped_column(
        sa.Enum(ActName, name="actname", create_constraint=True, native_enum=False),
        nullable=False,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    legal_reasoning: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    supporting_ingredients: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    missing_ingredients: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    is_alternative: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    disclaimer_text: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    # relationships
    analysis: Mapped[AIAnalysisResult] = relationship(
        back_populates="section_recommendations",
    )


# ---------------------------------------------------------------------------
# 11. GeneratedDocument
# ---------------------------------------------------------------------------

class GeneratedDocument(AuditMixin, Base):
    __tablename__ = "generated_documents"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), nullable=False,
    )
    template_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("document_templates.id"), nullable=True,
    )
    document_category: Mapped[DocumentCategory] = mapped_column(
        sa.Enum(DocumentCategory, name="documentcategory", create_constraint=True, native_enum=False),
        nullable=False,
    )
    document_subtype: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    generated_content: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    auto_filled_fields: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    io_edited: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    export_format: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    digital_signature_status: Mapped[SignatureStatus] = mapped_column(
        sa.Enum(SignatureStatus, name="signaturestatus", create_constraint=True, native_enum=False),
        default=SignatureStatus.Unsigned,
        nullable=False,
    )
    signed_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    signed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )

    # relationships
    case: Mapped[Case] = relationship(back_populates="generated_documents")
    template: Mapped[Optional[DocumentTemplate]] = relationship(
        back_populates="generated_documents",
    )
    signed_by_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[signed_by],
    )


# ---------------------------------------------------------------------------
# 12. DocumentTemplate
# ---------------------------------------------------------------------------

class DocumentTemplate(AuditMixin, Base):
    __tablename__ = "document_templates"

    id: Mapped[str] = _pk_uuid()
    template_name: Mapped[str] = mapped_column(sa.String, nullable=False)
    category: Mapped[DocumentCategory] = mapped_column(
        sa.Enum(DocumentCategory, name="documentcategory", create_constraint=True, native_enum=False),
        nullable=False,
    )
    template_body: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    placeholders: Mapped[Optional[list]] = mapped_column(sa.JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.text("true"), nullable=False,
    )
    version: Mapped[int] = mapped_column(
        sa.Integer, default=1, server_default=sa.text("1"), nullable=False,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )

    # relationships
    generated_documents: Mapped[List[GeneratedDocument]] = relationship(
        back_populates="template",
    )
    approved_by_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[approved_by],
    )


# ---------------------------------------------------------------------------
# 13. InvestigationPlan
# ---------------------------------------------------------------------------

class InvestigationPlan(AuditMixin, Base):
    __tablename__ = "investigation_plans"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), unique=True, nullable=False,
    )
    offence_type_detected: Mapped[Optional[str]] = mapped_column(
        sa.String, nullable=True,
    )
    investigation_steps: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    evidence_to_collect: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    documents_to_generate: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    statutory_deadlines: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    is_editable: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.text("true"), nullable=False,
    )

    # relationships
    case: Mapped[Case] = relationship(back_populates="investigation_plan")


# ---------------------------------------------------------------------------
# 14. JudgmentAnalysis
# ---------------------------------------------------------------------------

class JudgmentAnalysis(AuditMixin, Base):
    __tablename__ = "judgment_analyses"

    id: Mapped[str] = _pk_uuid()
    uploaded_file_id: Mapped[str] = mapped_column(
        ForeignKey("case_documents.id"), nullable=False,
    )
    case_facts: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    issues_raised: Mapped[Optional[list]] = mapped_column(sa.JSON, nullable=True)
    verdict: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    reasons_for_verdict: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    investigation_lapses: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    evidence_quality_observations: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    investigation_lessons: Mapped[Optional[str]] = mapped_column(
        sa.Text, nullable=True,
    )
    avoidable_errors: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    proposed_checklist_updates: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    checklist_update_status: Mapped[Optional[str]] = mapped_column(
        sa.String, nullable=True,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )

    # relationships
    uploaded_file: Mapped[CaseDocument] = relationship(
        foreign_keys=[uploaded_file_id],
    )
    approved_by_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[approved_by],
    )


# ---------------------------------------------------------------------------
# 15. KnowledgeBaseEntry
# ---------------------------------------------------------------------------

class KnowledgeBaseEntry(AuditMixin, Base):
    __tablename__ = "knowledge_base_entries"

    id: Mapped[str] = _pk_uuid()
    entry_type: Mapped[KBEntryType] = mapped_column(
        sa.Enum(KBEntryType, name="kbentrytype", create_constraint=True, native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(sa.String, nullable=False)
    content: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    applicable_offence_types: Mapped[Optional[list]] = mapped_column(
        sa.JSON, nullable=True,
    )
    version: Mapped[int] = mapped_column(
        sa.Integer, default=1, server_default=sa.text("1"), nullable=False,
    )
    status: Mapped[KBEntryStatus] = mapped_column(
        sa.Enum(KBEntryStatus, name="kbentrystatus", create_constraint=True, native_enum=False),
        default=KBEntryStatus.Draft,
        nullable=False,
    )
    promoted_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    promoted_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )
    previous_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("knowledge_base_entries.id"), nullable=True,
    )

    # relationships
    promoted_by_user: Mapped[Optional[User]] = relationship(
        foreign_keys=[promoted_by],
    )
    previous_version: Mapped[Optional[KnowledgeBaseEntry]] = relationship(
        remote_side="KnowledgeBaseEntry.id",
        foreign_keys=[previous_version_id],
    )


# ---------------------------------------------------------------------------
# 16. AuditLog  (append-only, immutable -- no updated_at, no soft-delete)
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """Append-only audit log. Does NOT use AuditMixin because this table
    is immutable: no updated_at and no is_deleted columns."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = _pk_uuid()
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    action_type: Mapped[ActionTypeEnum] = mapped_column(
        sa.Enum(ActionTypeEnum, name="actiontypeenum", create_constraint=True, native_enum=False),
        nullable=False,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    action_details: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    created_by: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)

    # relationships
    user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")


# ---------------------------------------------------------------------------
# 17. Notification
# ---------------------------------------------------------------------------

class Notification(AuditMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[str] = _pk_uuid()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False,
    )
    type: Mapped[str] = mapped_column(sa.String, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.text("false"), nullable=False,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)

    # relationships
    user: Mapped[User] = relationship(back_populates="notifications")


# ---------------------------------------------------------------------------
# 18. ActionTrackerTask
# ---------------------------------------------------------------------------

class ActionTrackerTask(AuditMixin, Base):
    __tablename__ = "action_tracker_tasks"

    id: Mapped[str] = _pk_uuid()
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"), nullable=False,
    )
    task_name: Mapped[str] = mapped_column(sa.String, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        sa.Enum(TaskPriority, name="taskpriority", create_constraint=True, native_enum=False),
        default=TaskPriority.Medium,
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        sa.Enum(TaskStatus, name="taskstatus", create_constraint=True, native_enum=False),
        default=TaskStatus.Pending,
        nullable=False,
    )
    source: Mapped[Optional[TaskSource]] = mapped_column(
        sa.Enum(TaskSource, name="tasksource", create_constraint=True, native_enum=False),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True,
    )

    # relationships
    case: Mapped[Case] = relationship(back_populates="action_tracker_tasks")


# ---------------------------------------------------------------------------
# 19. UsageEvent
# ---------------------------------------------------------------------------

class UsageEvent(AuditMixin, Base):
    __tablename__ = "usage_events"

    id: Mapped[str] = _pk_uuid()
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True,
    )
    event_type: Mapped[str] = mapped_column(sa.String, nullable=False)
    module: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )

    # relationships
    user: Mapped[Optional[User]] = relationship(back_populates="usage_events")
