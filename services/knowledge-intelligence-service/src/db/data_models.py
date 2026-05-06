from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import AuditMixin, Base, _uuid


class SourceConnector(Base, AuditMixin):
    __tablename__ = "kis_source_connectors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SourceDocument(Base, AuditMixin):
    __tablename__ = "kis_source_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_uri: Mapped[Optional[str]] = mapped_column(String(1024))
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="indexed", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DocumentChunk(Base, AuditMixin):
    __tablename__ = "kis_document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(64), ForeignKey("kis_source_documents.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    privacy_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class VectorNamespace(Base, AuditMixin):
    __tablename__ = "kis_vector_namespaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(nullable=False)


class RetrievalQuery(Base):
    __tablename__ = "kis_retrieval_queries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    redacted_query: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    result_count: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class RetrievalResult(Base):
    __tablename__ = "kis_retrieval_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    retrieval_query_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    citation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LLMUsageEvent(Base):
    __tablename__ = "kis_llm_usage_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class IngestionJob(Base, AuditMixin):
    __tablename__ = "kis_ingestion_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
