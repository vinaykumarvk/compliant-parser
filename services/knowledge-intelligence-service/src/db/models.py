from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    updated_by: Mapped[Optional[str]] = mapped_column(String(128))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Domain(Base, AuditMixin):
    __tablename__ = "kis_domains"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ServicePrincipal(Base, AuditMixin):
    __tablename__ = "kis_service_principals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class DomainMembership(Base, AuditMixin):
    __tablename__ = "kis_domain_memberships"
    __table_args__ = (UniqueConstraint("domain_id", "principal_id", name="uq_kis_domain_principal"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_domains.id"), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class KnowledgeBase(Base, AuditMixin):
    __tablename__ = "kis_knowledge_bases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_domains.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    retrieval_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DomainTemplate(Base, AuditMixin):
    __tablename__ = "kis_domain_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LLMProviderConfig(Base, AuditMixin):
    __tablename__ = "kis_llm_provider_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_domains.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_models: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LLMCredential(Base, AuditMixin):
    __tablename__ = "kis_llm_credentials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_domains.id"), nullable=False, index=True)
    provider_config_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_llm_provider_configs.id"), nullable=False)
    secret_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_secret_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class PromptTemplate(Base, AuditMixin):
    __tablename__ = "kis_prompt_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_domains.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)


class PolicyRule(Base, AuditMixin):
    __tablename__ = "kis_policy_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_domains.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditEvent(Base):
    __tablename__ = "kis_audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ReviewTask(Base, AuditMixin):
    __tablename__ = "kis_review_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LegalHold(Base, AuditMixin):
    __tablename__ = "kis_legal_holds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DeletionRequest(Base, AuditMixin):
    __tablename__ = "kis_deletion_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="requested", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)


class IdempotencyRecord(Base):
    __tablename__ = "kis_idempotency_records"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    domain_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class KISStateSnapshot(Base):
    __tablename__ = "kis_state_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
