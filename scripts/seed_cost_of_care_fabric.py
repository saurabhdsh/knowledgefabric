#!/usr/bin/env python3
"""Create the Cost of Care (Lisa COPD) fabric and finish ontology + graph.

Usage (local Docker or EC2):
  python scripts/seed_cost_of_care_fabric.py
  python scripts/seed_cost_of_care_fabric.py --base-url https://cuweave.com
  python scripts/seed_cost_of_care_fabric.py --username Saurabh --password admin123
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def _request(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 600,
) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> {exc.code}: {detail}") from exc


def login(base: str, username: str, password: str) -> str:
    payload = _request(
        "POST",
        f"{base}/api/v1/auth/login",
        body={"username": username, "password": password},
        timeout=60,
    )
    token = (payload.get("data") or {}).get("access_token") or payload.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {payload}")
    return token


def wait_job(base: str, token: str, job_id: str, timeout_s: int = 900) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        payload = _request("GET", f"{base}/api/v1/platform/jobs/{job_id}", token=token, timeout=60)
        job = payload.get("data") or {}
        status = str(job.get("status") or "").lower()
        print(f"  job {job_id}: {status} ({job.get('progress_percent')}%)")
        if status in ("ready", "completed", "success"):
            return job
        if status in ("failed", "error"):
            raise RuntimeError(f"Job failed: {job}")
        time.sleep(5)
    raise TimeoutError(f"Job {job_id} timed out")


def latest_version(base: str, token: str, project_id: str) -> Optional[str]:
    payload = _request(
        "GET",
        f"{base}/api/v1/ontology/projects/{project_id}/versions",
        token=token,
        timeout=60,
    )
    versions = payload.get("data") or []
    if not versions:
        return None
    versions = sorted(versions, key=lambda v: str(v.get("created_at") or ""), reverse=True)
    return versions[0].get("id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Cost of Care Lisa COPD fabric")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="Saurabh")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--skip-graph", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(f"Logging in to {base} as {args.username}...")
    token = login(base, args.username, args.password)

    print("Creating Cost of Care fabric (500+ members, Lisa COPD)...")
    created = _request(
        "POST",
        f"{base}/api/v1/knowledge/create-cost-of-care-fabric",
        token=token,
        body={},
        timeout=900,
    )
    if not created.get("success"):
        raise RuntimeError(created)
    data = created.get("data") or {}
    fabric_id = data.get("fabric_id") or data.get("source_id")
    project_id = data.get("ontology_project_id")
    print(json.dumps(data, indent=2))

    # Find ontology discovery job for this fabric
    print("Waiting for ontology discovery...")
    jobs_payload = _request(
        "GET",
        f"{base}/api/v1/platform/fabrics/{fabric_id}/jobs",
        token=token,
        timeout=60,
    )
    jobs = jobs_payload.get("data") or []
    discovery_jobs = [j for j in jobs if j.get("job_type") == "ontology_discovery"]
    if not discovery_jobs:
        # Trigger explicitly if auto-enqueue missed
        trig = _request(
            "POST",
            f"{base}/api/v1/platform/fabrics/{fabric_id}/discover-ontology?use_llm=true",
            token=token,
            timeout=60,
        )
        job_id = (trig.get("data") or {}).get("job_id")
        if job_id:
            wait_job(base, token, job_id)
    else:
        wait_job(base, token, discovery_jobs[0]["id"])

    # Refresh fabric for project id
    fab = _request("GET", f"{base}/api/v1/knowledge/{fabric_id}", token=token, timeout=60)
    fabric = fab.get("data") or {}
    project_id = fabric.get("ontology_project_id") or project_id
    if not project_id:
        raise RuntimeError("No ontology_project_id on fabric after discovery")

    version_id = latest_version(base, token, project_id)
    if not version_id:
        # Platform discovery may store versions differently; try ontology list
        raise RuntimeError(f"No ontology version found for project {project_id}")
    print(f"Approving ontology version {version_id}...")
    approved = _request(
        "POST",
        f"{base}/api/v1/graph/ontology/versions/{version_id}/approve",
        token=token,
        body={"approved_by": "cost_of_care_seed", "trigger_graph_build": not args.skip_graph},
        timeout=120,
    )
    print(json.dumps(approved.get("data") or approved, indent=2))
    graph_job = (approved.get("data") or {}).get("graph_build_job_id")
    if graph_job and not args.skip_graph:
        print("Waiting for graph build...")
        wait_job(base, token, graph_job)

    print("\nDone.")
    print(f"  Fabric ID : {fabric_id}")
    print(f"  Project   : {project_id}")
    print(f"  Version   : {version_id}")
    print("  Open Catalog / Test with LLM / Knowledge Graph to explore Lisa COPD.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
