"""SQLAlchemy models for Weave enterprise platform."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    allowed_features: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FabricRecord(Base):
    __tablename__ = "fabrics"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="unknown")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    model_status: Mapped[str] = mapped_column(String(32), default="not_trained")
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    weave_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    connection_info: Mapped[dict] = mapped_column(JSON, default=dict)
    guardrails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    ontology_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    approved_ontology_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ontology_waiver: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs: Mapped[list["FabricJobRecord"]] = relationship(back_populates="fabric", cascade="all, delete-orphan")


class FabricJobRecord(Base):
    __tablename__ = "fabric_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    fabric_id: Mapped[str | None] = mapped_column(String(128), ForeignKey("fabrics.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    error_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    fabric: Mapped["FabricRecord | None"] = relationship(back_populates="jobs")


class OntologyProjectRecord(Base):
    __tablename__ = "ontology_projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fabric_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions: Mapped[list["OntologyVersionRecord"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class OntologyVersionRecord(Base):
    __tablename__ = "ontology_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("ontology_projects.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(64), default="draft")
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["OntologyProjectRecord"] = relationship(back_populates="versions")


class OntologyAuditRecord(Base):
    __tablename__ = "ontology_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GraphNodeRecord(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    fabric_id: Mapped[str] = mapped_column(String(128), index=True)
    ontology_class_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ontology_version_id: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(512))
    normalized_name: Mapped[str] = mapped_column(String(512), index=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    source_table: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_column: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GraphEdgeRecord(Base):
    __tablename__ = "graph_edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    fabric_id: Mapped[str] = mapped_column(String(128), index=True)
    source_node_id: Mapped[str] = mapped_column(String(64), ForeignKey("graph_nodes.id"), index=True)
    target_node_id: Mapped[str] = mapped_column(String(64), ForeignKey("graph_nodes.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(256), index=True)
    ontology_version_id: Mapped[str] = mapped_column(String(64), index=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GraphBuildRunRecord(Base):
    __tablename__ = "graph_build_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    fabric_id: Mapped[str] = mapped_column(String(128), index=True)
    ontology_version_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    storage_backend: Mapped[str] = mapped_column(String(32), default="postgres")
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)
    export_uris: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_graph_nodes_fabric_version", GraphNodeRecord.fabric_id, GraphNodeRecord.ontology_version_id)
Index("ix_graph_edges_fabric_version", GraphEdgeRecord.fabric_id, GraphEdgeRecord.ontology_version_id)
