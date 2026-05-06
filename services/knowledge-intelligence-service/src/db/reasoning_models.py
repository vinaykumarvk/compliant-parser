from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import AuditMixin, Base, _uuid


class ReasoningPattern(Base, AuditMixin):
    __tablename__ = "kis_reasoning_patterns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    prompt_name: Mapped[str] = mapped_column(String(128), nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReasoningRun(Base, AuditMixin):
    __tablename__ = "kis_reasoning_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    domain_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    pattern_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    context_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    llm_usage: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    privacy_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
