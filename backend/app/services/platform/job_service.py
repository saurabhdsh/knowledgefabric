"""Platform background jobs."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.models import FabricJobRecord
from app.db.session import db_session, get_session_factory

logger = logging.getLogger(__name__)

JOB_STATUSES = ("queued", "running", "indexing", "training", "ready", "failed")
JOB_TYPES = (
    "fabric_ingest",
    "ontology_discovery",
    "graph_build",
    "graph_export",
    "codebase_analysis",
)


class JobService:
    def enqueue(
        self,
        job_type: str,
        fabric_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        with db_session() as session:
            session.add(
                FabricJobRecord(
                    id=job_id,
                    fabric_id=fabric_id,
                    job_type=job_type,
                    status="queued",
                    progress_percent=0.0,
                    config=config or {},
                )
            )
        logger.info("Enqueued job %s type=%s fabric=%s", job_id, job_type, fabric_id)
        return job_id

    def claim_next(self) -> Optional[Dict[str, Any]]:
        session = get_session_factory()()
        try:
            job = (
                session.query(FabricJobRecord)
                .filter(FabricJobRecord.status == "queued")
                .order_by(FabricJobRecord.created_at.asc())
                .first()
            )
            if not job:
                return None
            job.status = "running"
            job.started_at = datetime.utcnow()
            session.commit()
            return self._to_dict(job)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress_percent: Optional[float] = None,
        error_payload: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        with db_session() as session:
            job = session.get(FabricJobRecord, job_id)
            if not job:
                return
            if status:
                job.status = status
            if progress_percent is not None:
                job.progress_percent = progress_percent
            if error_payload is not None:
                job.error_payload = error_payload
            if result is not None:
                job.result = result
            if status in ("ready", "failed"):
                job.completed_at = datetime.utcnow()

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        session = get_session_factory()()
        try:
            job = session.get(FabricJobRecord, job_id)
            return self._to_dict(job) if job else None
        finally:
            session.close()

    def list_for_fabric(self, fabric_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        session = get_session_factory()()
        try:
            jobs = (
                session.query(FabricJobRecord)
                .filter(FabricJobRecord.fabric_id == fabric_id)
                .order_by(FabricJobRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_dict(j) for j in jobs]
        finally:
            session.close()

    def _to_dict(self, job: FabricJobRecord) -> Dict[str, Any]:
        return {
            "id": job.id,
            "fabric_id": job.fabric_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "error_payload": job.error_payload,
            "result": job.result,
            "config": job.config or {},
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }


job_service = JobService()
