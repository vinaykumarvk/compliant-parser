from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import AuditMixin, Base, _uuid


class OntologyType(Base, AuditMixin):
    __tablename__ = "kis_ontology_types"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ExtractedFact(Base, AuditMixin):
    __tablename__ = "kis_extracted_facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    object_value: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(64))
    citation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class GraphNode(Base, AuditMixin):
    __tablename__ = "kis_graph_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    type_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class GraphEdge(Base, AuditMixin):
    __tablename__ = "kis_graph_edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    citation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WikiArticle(Base, AuditMixin):
    __tablename__ = "kis_wiki_articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    broken_links: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class EvaluationSet(Base, AuditMixin):
    __tablename__ = "kis_evaluation_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cases: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)


class EvaluationRun(Base, AuditMixin):
    __tablename__ = "kis_evaluation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evaluation_set_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FeedbackItem(Base, AuditMixin):
    __tablename__ = "kis_feedback_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)


class KnowledgeSnapshot(Base, AuditMixin):
    __tablename__ = "kis_knowledge_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
