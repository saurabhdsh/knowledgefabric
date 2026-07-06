"""Durable fabric metadata store (PostgreSQL/SQLite with JSON fallback)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.user_context import get_current_user_id
from app.db.models import FabricRecord
from app.db.session import db_session, get_session_factory, init_db

logger = logging.getLogger(__name__)

FABRICS_JSON = os.path.join(settings.DATA_DIR, "fabrics.json")


class FabricStore:
    """Single source of truth for fabric metadata."""

    def __init__(self) -> None:
        self._cache: List[Dict[str, Any]] = []
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        init_db()
        self._migrate_json_if_needed()
        self._cache = self.list_all_dicts()
        self._initialized = True
        logger.info("FabricStore ready (%d fabrics)", len(self._cache))

    def _migrate_json_if_needed(self) -> None:
        if not os.path.exists(FABRICS_JSON):
            return
        session = get_session_factory()()
        try:
            count = session.query(FabricRecord).count()
            if count > 0:
                return
            with open(FABRICS_JSON, "r", encoding="utf-8") as f:
                fabrics = json.load(f)
            for fab in fabrics:
                self._upsert_record(session, fab)
            session.commit()
            logger.info("Migrated %d fabrics from JSON to database", len(fabrics))
        except Exception as exc:
            session.rollback()
            logger.warning("JSON migration skipped: %s", exc)
        finally:
            session.close()

    def _record_to_dict(self, rec: FabricRecord) -> Dict[str, Any]:
        data = dict(rec.payload or {})
        data.update({
            "id": rec.id,
            "owner_id": rec.owner_id,
            "name": rec.name,
            "source_type": rec.source_type,
            "description": rec.description,
            "status": rec.status,
            "model_status": rec.model_status,
            "document_count": rec.document_count,
            "total_chunks": rec.total_chunks,
            "weave_domain": rec.weave_domain,
            "tags": rec.tags or [],
            "connection_info": rec.connection_info or {},
            "guardrails": rec.guardrails,
            "ontology_project_id": rec.ontology_project_id,
            "approved_ontology_version_id": rec.approved_ontology_version_id,
            "ontology_waiver": rec.ontology_waiver,
        })
        return data

    def _upsert_record(self, session, fabric: Dict[str, Any]) -> FabricRecord:
        fid = fabric["id"]
        rec = session.get(FabricRecord, fid)
        if rec is None:
            rec = FabricRecord(id=fid, payload={})
            session.add(rec)
        rec.name = fabric.get("name") or fid
        owner_id = fabric.get("owner_id") or get_current_user_id()
        if owner_id:
            rec.owner_id = owner_id
        rec.source_type = fabric.get("source_type") or "unknown"
        rec.description = fabric.get("description")
        rec.status = fabric.get("status") or "active"
        rec.model_status = fabric.get("model_status") or "not_trained"
        rec.document_count = int(fabric.get("document_count") or 0)
        rec.total_chunks = int(fabric.get("total_chunks") or 0)
        rec.weave_domain = fabric.get("weave_domain")
        rec.tags = fabric.get("tags") or []
        rec.connection_info = fabric.get("connection_info") or {}
        rec.guardrails = fabric.get("guardrails")
        rec.ontology_project_id = fabric.get("ontology_project_id")
        rec.approved_ontology_version_id = fabric.get("approved_ontology_version_id")
        rec.ontology_waiver = bool(fabric.get("ontology_waiver", False))
        rec.payload = fabric
        rec.updated_at = datetime.utcnow()
        return rec

    def list_all_dicts(self) -> List[Dict[str, Any]]:
        owner_id = get_current_user_id()
        session = get_session_factory()()
        try:
            query = session.query(FabricRecord).order_by(FabricRecord.created_at.desc())
            if owner_id:
                query = query.filter(FabricRecord.owner_id == owner_id)
            records = query.all()
            if records:
                return [self._record_to_dict(r) for r in records]
        finally:
            session.close()
        if owner_id:
            return []
        if os.path.exists(FABRICS_JSON):
            try:
                with open(FABRICS_JSON, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def get(self, fabric_id: str) -> Optional[Dict[str, Any]]:
        owner_id = get_current_user_id()
        session = get_session_factory()()
        try:
            rec = session.get(FabricRecord, fabric_id)
            if rec:
                if owner_id and rec.owner_id and rec.owner_id != owner_id:
                    return None
                if owner_id and rec.owner_id is None:
                    return None
                return self._record_to_dict(rec)
        finally:
            session.close()
        cached = next((f for f in self._cache if f.get("id") == fabric_id), None)
        if cached and owner_id and cached.get("owner_id") != owner_id:
            return None
        return cached

    def save(self, fabric: Dict[str, Any]) -> Dict[str, Any]:
        with db_session() as session:
            self._upsert_record(session, fabric)
        self._write_json_backup()
        self._cache = self.list_all_dicts()
        return fabric

    def save_all(self, fabrics: List[Dict[str, Any]]) -> None:
        with db_session() as session:
            for fab in fabrics:
                self._upsert_record(session, fab)
        self._write_json_backup()
        self._cache = fabrics

    def delete(self, fabric_id: str) -> bool:
        owner_id = get_current_user_id()
        with db_session() as session:
            rec = session.get(FabricRecord, fabric_id)
            if not rec:
                return False
            if owner_id and rec.owner_id and rec.owner_id != owner_id:
                return False
            if owner_id and rec.owner_id is None:
                return False
            session.delete(rec)
        self._write_json_backup()
        self._cache = [f for f in self._cache if f.get("id") != fabric_id]
        return True

    def link_ontology(self, fabric_id: str, project_id: str, version_id: Optional[str] = None) -> bool:
        fabric = self.get(fabric_id)
        if not fabric:
            return False
        fabric["ontology_project_id"] = project_id
        if version_id:
            fabric["approved_ontology_version_id"] = version_id
        self.save(fabric)
        return True

    def _write_json_backup(self) -> None:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        fabrics = self.list_all_dicts()
        with open(FABRICS_JSON, "w", encoding="utf-8") as f:
            json.dump(fabrics, f, indent=2, default=str)


fabric_store = FabricStore()
