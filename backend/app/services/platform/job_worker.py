"""Background job worker and handlers."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.platform.fabric_store import fabric_store
from app.services.platform.job_service import job_service
from app.services.ontology.ontology_access import register_project_owner

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if not settings.ENABLE_JOB_WORKER or self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="weave-job-worker", daemon=True)
        self._thread.start()
        logger.info("Job worker started")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            job = job_service.claim_next()
            if not job:
                time.sleep(settings.JOB_POLL_INTERVAL_SECONDS)
                continue
            try:
                self._dispatch(job)
            except Exception as exc:
                logger.exception("Job %s failed: %s", job["id"], exc)
                job_service.update(
                    job["id"],
                    status="failed",
                    error_payload={"message": str(exc)},
                )

    def _dispatch(self, job: Dict[str, Any]) -> None:
        handlers = {
            "ontology_discovery": self._handle_ontology_discovery,
            "graph_build": self._handle_graph_build,
            "graph_export": self._handle_graph_export,
        }
        handler = handlers.get(job["job_type"])
        if not handler:
            job_service.update(job["id"], status="failed", error_payload={"message": "Unknown job type"})
            return
        handler(job)

    def _handle_ontology_discovery(self, job: Dict[str, Any]) -> None:
        from app.services.ontology.discovery_orchestrator import DiscoveryOrchestrator
        from app.services.ontology.ontology_db_repository import ontology_db_repository
        from app.services.ontology.schema_analyzer import schema_analyzer

        config = job.get("config") or {}
        fabric_id = job.get("fabric_id")
        project_id = config.get("project_id")
        if not project_id:
            project_id = f"proj_{uuid.uuid4().hex[:12]}"
            project_name = config.get("project_name") or f"Fabric {fabric_id}"
            ontology_db_repository.ensure_project(
                project_id,
                name=project_name,
                fabric_id=fabric_id,
            )
            fabric = fabric_store.get(fabric_id) if fabric_id else None
            register_project_owner(
                project_id,
                project_name,
                owner_id=fabric.get("owner_id") if fabric else None,
            )
        job_service.update(job["id"], progress_percent=10.0)

        schema_profile = config.get("schema_profile")
        if not schema_profile and fabric_id:
            fabric = fabric_store.get(fabric_id)
            schema_profile = schema_analyzer.build_profile_from_fabric(fabric)

        run_id = ontology_db_repository.create_discovery_run(project_id, config)
        job_service.update(job["id"], progress_percent=20.0, result={"run_id": run_id})

        orchestrator = DiscoveryOrchestrator()
        if schema_profile:
            version_id = orchestrator.run_schema_discovery(
                run_id=run_id,
                project_id=project_id,
                schema_profile=schema_profile,
            )
        else:
            from app.services.ontology.fabric_artifact_bridge import (
                artifact_paths_for_discovery,
                resolve_artifacts_for_fabric,
            )

            artifact_ids = config.get("artifact_ids") or []
            if not artifact_ids and fabric_id:
                bridged = resolve_artifacts_for_fabric(fabric_id, project_id)
                artifact_ids = artifact_paths_for_discovery(bridged)
            version_id = orchestrator.run_discovery(
                run_id=run_id,
                project_id=project_id,
                artifact_ids=artifact_ids,
                use_llm=config.get("use_llm", True),
            )

        if not version_id:
            job_service.update(job["id"], status="failed", error_payload={"message": "Discovery failed"})
            return

        if fabric_id:
            fabric_store.link_ontology(fabric_id, project_id)
        job_service.update(
            job["id"],
            status="ready",
            progress_percent=100.0,
            result={"run_id": run_id, "version_id": version_id, "project_id": project_id},
        )

    def _handle_graph_build(self, job: Dict[str, Any]) -> None:
        from app.services.graph.graph_materialization_service import graph_materialization_service

        config = job.get("config") or {}
        fabric_id = job.get("fabric_id")
        version_id = config.get("ontology_version_id")
        if not fabric_id or not version_id:
            job_service.update(job["id"], status="failed", error_payload={"message": "Missing fabric or version"})
            return

        job_service.update(job["id"], progress_percent=30.0)
        result = graph_materialization_service.materialize(
            fabric_id=fabric_id,
            ontology_version_id=version_id,
            storage_backend=config.get("storage_backend") or settings.GRAPH_STORAGE_BACKEND,
        )
        job_service.update(job["id"], status="ready", progress_percent=100.0, result=result)

    def _handle_graph_export(self, job: Dict[str, Any]) -> None:
        from app.services.graph.adapters.neo4j_adapter import neo4j_adapter
        from app.services.graph.adapters.rdf_adapter import rdf_adapter

        config = job.get("config") or {}
        fabric_id = job.get("fabric_id")
        version_id = config.get("ontology_version_id")
        targets = config.get("targets") or ["rdf"]
        exports: Dict[str, Any] = {}
        if "neo4j" in targets:
            exports["neo4j"] = neo4j_adapter.export_fabric_graph(fabric_id, version_id)
        if "rdf" in targets or "stardog" in targets:
            exports["rdf"] = rdf_adapter.export_fabric_graph(fabric_id, version_id)
            if "stardog" in targets:
                exports["stardog"] = rdf_adapter.push_to_stardog(fabric_id, version_id)
        job_service.update(job["id"], status="ready", progress_percent=100.0, result=exports)


job_worker = JobWorker()
