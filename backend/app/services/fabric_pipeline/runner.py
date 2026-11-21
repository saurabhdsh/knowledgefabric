"""Pipeline run: stages, job record and saved manifest (Release 2.0, Phase 1).

Every fabric is built by the same six stages:

    Profile -> Parse -> Model -> Index -> Validate -> Publish

A run owns the fabric record for the duration of the build (``building`` ->
``active`` or ``failed``), a ``fabric_ingest`` job record for progress, and a
manifest file that records what each stage did, how long it took, and every
warning. A fabric is only published when all stages complete; a failure leaves
a ``failed`` fabric with the reason, never a half-built ``active`` one.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.core.config import settings
from app.services.platform.fabric_store import fabric_store
from app.services.platform.job_service import job_service
from app.services.platform.progress_store import progress_store
from app.utils.json_sanitize import sanitize_for_json

logger = logging.getLogger(__name__)

PIPELINE_VERSION = 2
STAGES = ("profile", "parse", "model", "index", "validate", "publish")
_STAGE_END_PERCENT = {"profile": 15, "parse": 35, "model": 50, "index": 85, "validate": 95, "publish": 100}
_STAGE_LABEL = {
    "profile": "Profiling the source",
    "parse": "Parsing and loading",
    "model": "Modelling structure",
    "index": "Embedding and indexing",
    "validate": "Validating the fabric",
    "publish": "Publishing",
}


class PipelineError(RuntimeError):
    """A fabric build failed. ``stage`` names where; ``fabric_id`` the failed fabric."""

    def __init__(self, message: str, *, stage: Optional[str] = None, fabric_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.fabric_id = fabric_id


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def manifest_dir() -> str:
    os.makedirs(settings.FABRIC_MANIFEST_DIR, exist_ok=True)
    return settings.FABRIC_MANIFEST_DIR


def manifest_path(fabric_id: str) -> str:
    safe = re.sub(r"[^0-9a-zA-Z_.-]", "_", fabric_id)
    return os.path.join(manifest_dir(), f"{safe}.json")


_manifest_cache: Dict[str, Any] = {}


def load_manifest(fabric_id: str) -> Optional[Dict[str, Any]]:
    path = manifest_path(fabric_id)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    cached = _manifest_cache.get(fabric_id)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        logger.warning("Manifest for %s unreadable: %s", fabric_id, exc)
        return None
    _manifest_cache[fabric_id] = (mtime, data)
    return data


def load_profile(fabric_id: str) -> Optional[Dict[str, Any]]:
    """Tabular profile saved with a fabric's manifest, if it has one."""
    manifest = load_manifest(fabric_id)
    return (manifest or {}).get("profile") or None


def delete_manifest(fabric_id: str) -> None:
    _manifest_cache.pop(fabric_id, None)
    try:
        os.remove(manifest_path(fabric_id))
    except OSError:
        pass


class StageHandle:
    def __init__(self, record: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        self._record = record
        self._manifest = manifest

    def metrics(self, **values: Any) -> None:
        self._record["metrics"].update(values)

    def warn(self, message: str) -> None:
        if message and message not in self._record["warnings"]:
            self._record["warnings"].append(message)
            self._manifest["warnings"].append({"stage": self._record["name"], "message": message})


class PipelineRun:
    def __init__(
        self,
        fabric_id: str,
        kind: str,
        record: Dict[str, Any],
        *,
        inputs: Optional[Dict[str, Any]] = None,
        progress_id: Optional[str] = None,
    ) -> None:
        self.fabric_id = fabric_id
        self.kind = kind
        self.record = record
        self.progress_id = progress_id
        self._current_stage: Optional[str] = None
        self.manifest: Dict[str, Any] = {
            "manifest_version": 1,
            "pipeline_version": PIPELINE_VERSION,
            "fabric_id": fabric_id,
            "fabric_name": record.get("name"),
            "kind": kind,
            "status": "running",
            "started_at": _now(),
            "finished_at": None,
            "inputs": inputs or {},
            "stages": [],
            "warnings": [],
            "embedding": None,
            "error": None,
        }
        # The fabric exists from the first moment so the build is visible, and
        # so the job record can reference it.
        record.update({
            "id": fabric_id,
            "status": "building",
            "model_status": "indexing",
            "pipeline_version": PIPELINE_VERSION,
        })
        record.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        record["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        fabric_store.save(record)
        self.job_id: Optional[str] = None
        try:
            self.job_id = job_service.start_running(
                "fabric_ingest", fabric_id, {"kind": kind, "pipeline_version": PIPELINE_VERSION}
            )
        except Exception as exc:  # the job record is bookkeeping; never block a build on it
            logger.warning("Could not create fabric_ingest job for %s: %s", fabric_id, exc)
        self.manifest["job_id"] = self.job_id
        self.save()

    # ----------------------------------------------------------------- state

    def save(self) -> None:
        path = manifest_path(self.fabric_id)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(sanitize_for_json(self.manifest), fh, indent=2, default=str)
        os.replace(tmp, path)
        _manifest_cache.pop(self.fabric_id, None)

    def _report(self, percent: float, message: str, status: str = "processing") -> None:
        if self.job_id:
            try:
                job_service.update(self.job_id, progress_percent=float(percent))
            except Exception:
                logger.debug("Job progress update failed", exc_info=True)
        if self.progress_id:
            try:
                progress_store[self.progress_id] = {
                    "status": status,
                    "progress": percent,
                    "message": message,
                    "stage": self._current_stage or "",
                    "fabric_id": self.fabric_id,
                    "job_id": self.job_id,
                }
            except Exception:
                logger.debug("Progress store update failed", exc_info=True)

    @contextmanager
    def stage(self, name: str) -> Iterator[StageHandle]:
        if name not in STAGES:
            raise ValueError(f"Unknown stage '{name}'")
        record: Dict[str, Any] = {
            "name": name,
            "status": "running",
            "started_at": _now(),
            "seconds": None,
            "metrics": {},
            "warnings": [],
        }
        self.manifest["stages"].append(record)
        self._current_stage = name
        previous = STAGES.index(name) - 1
        start_percent = _STAGE_END_PERCENT[STAGES[previous]] if previous >= 0 else 0
        self._report(start_percent, _STAGE_LABEL[name])
        started = time.time()
        try:
            yield StageHandle(record, self.manifest)
            record["status"] = "completed"
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            raise
        finally:
            record["seconds"] = round(time.time() - started, 3)
            self.save()
        self._report(_STAGE_END_PERCENT[name], f"{_STAGE_LABEL[name]} — done")

    def summary(self) -> Dict[str, Any]:
        """Compact view of the run stored on the fabric record."""
        return {
            "version": PIPELINE_VERSION,
            "kind": self.kind,
            "status": self.manifest["status"],
            "job_id": self.job_id,
            "started_at": self.manifest["started_at"],
            "finished_at": self.manifest["finished_at"],
            "stages": [
                {"name": s["name"], "status": s["status"], "seconds": s["seconds"]}
                for s in self.manifest["stages"]
            ],
            "warnings": len(self.manifest["warnings"]),
            "error": self.manifest["error"],
        }

    # ------------------------------------------------------------- outcomes

    def publish(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Mark the fabric active. Call inside the ``publish`` stage."""
        self.manifest["status"] = "completed"
        self.manifest["finished_at"] = _now()
        self.record.update(updates)
        self.record.update({
            "status": "active",
            "model_status": "indexed",
            "last_indexed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": None,
        })
        if self.manifest.get("embedding"):
            self.record["embedding"] = self.manifest["embedding"]
        # The publish stage is still open while the record is written; show it closed.
        self.record["pipeline"] = self.summary()
        for stage in self.record["pipeline"]["stages"]:
            if stage["name"] == "publish":
                stage["status"] = "completed"
        saved = fabric_store.save(self.record)
        self.record.update(saved)
        try:
            from app.services.enterprise.ops import on_publish

            on_publish(self.record, change="publish")
            fabric_store.save(self.record)
        except Exception:
            logger.debug("Phase 5 publish stamp failed for %s", self.fabric_id, exc_info=True)
        return self.record

    def complete(self) -> None:
        """Close the job after the publish stage has ended."""
        self.save()
        if self.job_id:
            try:
                job_service.update(
                    self.job_id, status="ready", progress_percent=100.0, result=self.summary()
                )
            except Exception:
                logger.debug("Job completion update failed", exc_info=True)
        self._report(100, "Fabric ready", status="completed")

    def fail(self, exc: BaseException) -> PipelineError:
        """Record the failure, mark the fabric failed, and return the error to raise."""
        stage = self._current_stage
        message = str(exc) or type(exc).__name__
        self.manifest["status"] = "failed"
        self.manifest["finished_at"] = _now()
        self.manifest["error"] = {"stage": stage, "message": message, "type": type(exc).__name__}
        try:
            self.save()
        except Exception:
            logger.exception("Could not save failure manifest for %s", self.fabric_id)
        self.record.update({
            "status": "failed",
            "model_status": "failed",
            "error": f"{stage}: {message}" if stage else message,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pipeline": self.summary(),
        })
        try:
            fabric_store.save(self.record)
        except Exception:
            logger.exception("Could not mark fabric %s failed", self.fabric_id)
        if self.job_id:
            try:
                job_service.update(
                    self.job_id,
                    status="failed",
                    error_payload={"stage": stage, "message": message},
                    result=self.summary(),
                )
            except Exception:
                logger.debug("Job failure update failed", exc_info=True)
        self._report(0, message, status="error")
        logger.error("Fabric %s failed at stage %s: %s", self.fabric_id, stage, message)
        return PipelineError(message, stage=stage, fabric_id=self.fabric_id)


def reconcile_interrupted_runs() -> int:
    """Mark builds that were cut off by a server restart as failed.

    Builds run inside the API process, so any ``fabric_ingest`` job still
    ``running`` when the process starts was interrupted.
    """
    count = 0
    try:
        for job in job_service.list_running("fabric_ingest"):
            fabric_id = job.get("fabric_id")
            message = "The build was interrupted by a server restart. Create the fabric again."
            job_service.update(job["id"], status="failed", error_payload={"message": message})
            fabric = fabric_store.get(fabric_id) if fabric_id else None
            if fabric and fabric.get("status") == "building":
                fabric.update({"status": "failed", "model_status": "failed", "error": message})
                fabric_store.save(fabric)
            manifest = load_manifest(fabric_id) if fabric_id else None
            if manifest and manifest.get("status") == "running":
                manifest["status"] = "failed"
                manifest["finished_at"] = _now()
                manifest["error"] = {"stage": None, "message": message, "type": "Interrupted"}
                with open(manifest_path(fabric_id), "w", encoding="utf-8") as fh:
                    json.dump(manifest, fh, indent=2, default=str)
                _manifest_cache.pop(fabric_id, None)
            count += 1
    except Exception as exc:
        logger.warning("Could not reconcile interrupted fabric builds: %s", exc)
    return count
