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
    "embedding_reindex",
)


# Jobs stuck longer than this are treated as dead so Run Discovery can start fresh.
_STALE_QUEUED_SECONDS = 90
_STALE_RUNNING_SECONDS = {
    "codebase_analysis": 45,
    "ontology_discovery": 1800,
    "graph_build": 900,
    "graph_export": 600,
    "embedding_reindex": 900,
    "fabric_ingest": 1800,
}
_DEFAULT_STALE_RUNNING_SECONDS = 900


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

    @staticmethod
    def _age_seconds(job: FabricJobRecord, now: datetime) -> float:
        started = job.started_at or job.created_at
        if not started:
            return 0.0
        return max(0.0, (now - started).total_seconds())

    def _is_stale(self, job: FabricJobRecord, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        age = self._age_seconds(job, now)
        if job.status == "queued":
            return age >= _STALE_QUEUED_SECONDS
        if job.status == "running":
            limit = _STALE_RUNNING_SECONDS.get(job.job_type or "", _DEFAULT_STALE_RUNNING_SECONDS)
            return age >= limit
        return False

    def _fail_stale(self, job: FabricJobRecord, now: Optional[datetime] = None) -> None:
        now = now or datetime.utcnow()
        age = int(self._age_seconds(job, now))
        prior = job.status or "unknown"
        logger.warning(
            "Failing stale job %s type=%s status=%s age=%ss",
            job.id,
            job.job_type,
            prior,
            age,
        )
        job.status = "failed"
        job.completed_at = now
        job.error_payload = {
            "message": f"Job timed out while {prior} ({age}s). Start discovery again.",
        }

    def find_active(
        self,
        job_type: str,
        fabric_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a queued or running job for this fabric and project, if one exists.

        Stale jobs are marked failed so a later enqueue_once can start fresh.
        """
        session = get_session_factory()()
        try:
            query = session.query(FabricJobRecord).filter(
                FabricJobRecord.job_type == job_type,
                FabricJobRecord.status.in_(("queued", "running")),
            )
            if fabric_id:
                query = query.filter(FabricJobRecord.fabric_id == fabric_id)
            jobs = query.order_by(FabricJobRecord.created_at.desc()).all()
            now = datetime.utcnow()
            dirty = False
            for job in jobs:
                cfg = job.config or {}
                if project_id and str(cfg.get("project_id") or "") != str(project_id):
                    continue
                if self._is_stale(job, now):
                    self._fail_stale(job, now)
                    dirty = True
                    continue
                if dirty:
                    session.commit()
                return self._to_dict(job)
            if dirty:
                session.commit()
            return None
        finally:
            session.close()

    def enqueue_once(
        self,
        job_type: str,
        fabric_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Enqueue unless the same fabric and project already have this job in flight."""
        cfg = config or {}
        existing = self.find_active(job_type, fabric_id, cfg.get("project_id"))
        if existing:
            logger.info(
                "Reusing in-flight job %s type=%s fabric=%s status=%s progress=%s",
                existing["id"],
                job_type,
                fabric_id,
                existing.get("status"),
                existing.get("progress_percent"),
            )
            return existing["id"]
        return self.enqueue(job_type, fabric_id, cfg)

    def start_running(
        self,
        job_type: str,
        fabric_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a job that runs in the caller (not picked up by the worker)."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        with db_session() as session:
            session.add(
                FabricJobRecord(
                    id=job_id,
                    fabric_id=fabric_id,
                    job_type=job_type,
                    status="running",
                    progress_percent=0.0,
                    config=config or {},
                    started_at=datetime.utcnow(),
                )
            )
        return job_id

    def list_running(self, job_type: str) -> List[Dict[str, Any]]:
        session = get_session_factory()()
        try:
            jobs = (
                session.query(FabricJobRecord)
                .filter(FabricJobRecord.status == "running", FabricJobRecord.job_type == job_type)
                .all()
            )
            return [self._to_dict(j) for j in jobs]
        finally:
            session.close()

    def claim_next(self) -> Optional[Dict[str, Any]]:
        session = get_session_factory()()
        try:
            # Reclaim / fail jobs stuck after a worker restart or hang so the queue moves.
            candidates = (
                session.query(FabricJobRecord)
                .filter(FabricJobRecord.status.in_(("queued", "running")))
                .order_by(FabricJobRecord.created_at.asc())
                .all()
            )
            now = datetime.utcnow()
            dirty = False
            for job in candidates:
                if not self._is_stale(job, now):
                    continue
                dirty = True
                if job.status == "running" and (job.job_type or "") == "codebase_analysis":
                    logger.warning("Re-queueing stale running job %s", job.id)
                    job.status = "queued"
                    job.started_at = None
                    job.progress_percent = 0.0
                else:
                    self._fail_stale(job, now)
            if dirty:
                session.commit()

            job = (
                session.query(FabricJobRecord)
                .filter(FabricJobRecord.status == "queued")
                .order_by(FabricJobRecord.created_at.asc())
                .first()
            )
            if not job:
                return None
            # Only one worker may take a queued job. A second claim sees zero rows.
            taken = (
                session.query(FabricJobRecord)
                .filter(FabricJobRecord.id == job.id, FabricJobRecord.status == "queued")
                .update(
                    {"status": "running", "started_at": datetime.utcnow()},
                    synchronize_session=False,
                )
            )
            session.commit()
            if not taken:
                return None
            session.expire_all()
            claimed = session.get(FabricJobRecord, job.id)
            return self._to_dict(claimed) if claimed else None
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
