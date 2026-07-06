"""RDF / Stardog export adapter (Phase 3c)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services.graph.graph_store import graph_store

logger = logging.getLogger(__name__)

WEAVE_NS = "http://weave.ai/ontology#"


class RdfAdapter:
    def export_fabric_graph(
        self,
        fabric_id: str,
        ontology_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = graph_store.get_graph_payload(fabric_id, ontology_version_id)
        ttl = self._to_turtle(fabric_id, payload)
        json_ld = self._to_json_ld(fabric_id, payload)
        return {
            "status": "generated",
            "format": "turtle",
            "turtle": ttl,
            "json_ld": json_ld,
            "node_count": payload.get("node_count", 0),
            "edge_count": payload.get("edge_count", 0),
        }

    def push_to_stardog(
        self,
        fabric_id: str,
        ontology_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not settings.STARDOG_ENDPOINT or not settings.STARDOG_DATABASE:
            return {"status": "skipped", "reason": "STARDOG_ENDPOINT/STARDOG_DATABASE not configured"}

        export = self.export_fabric_graph(fabric_id, ontology_version_id)
        url = (
            f"{settings.STARDOG_ENDPOINT.rstrip('/')}/"
            f"{settings.STARDOG_DATABASE}/data?graph-uri=weave:{fabric_id}"
        )
        auth = None
        if settings.STARDOG_USERNAME and settings.STARDOG_PASSWORD:
            auth = (settings.STARDOG_USERNAME, settings.STARDOG_PASSWORD)
        try:
            resp = httpx.post(
                url,
                content=export["turtle"],
                headers={"Content-Type": "text/turtle"},
                auth=auth,
                timeout=60.0,
            )
            resp.raise_for_status()
            return {"status": "uploaded", "url": url, "response_code": resp.status_code}
        except Exception as exc:
            logger.warning("Stardog upload failed: %s", exc)
            return {"status": "failed", "error": str(exc), "turtle_preview": export["turtle"][:500]}

    def _to_turtle(self, fabric_id: str, payload: Dict[str, Any]) -> str:
        lines = [
            f"@prefix weave: <{WEAVE_NS}> .",
            f"@prefix fabric: <{WEAVE_NS}fabric/{fabric_id}/> .",
            "",
        ]
        for n in payload.get("nodes") or []:
            uri = f"fabric:node/{n['id']}"
            lines.append(f"{uri} a weave:Entity ;")
            lines.append(f'  weave:label "{self._esc(n["label"])}" ;')
            lines.append(f'  weave:normalizedName "{self._esc(n["normalized_name"])}" .')
            lines.append("")
        for e in payload.get("edges") or []:
            src = f"fabric:node/{e['source']}"
            tgt = f"fabric:node/{e['target']}"
            pred = self._pred(e["relationship_type"])
            lines.append(f"{src} {pred} {tgt} .")
        return "\n".join(lines)

    def _to_json_ld(self, fabric_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        graph = []
        for n in payload.get("nodes") or []:
            graph.append({
                "@id": f"{WEAVE_NS}fabric/{fabric_id}/node/{n['id']}",
                "@type": "Entity",
                "label": n["label"],
                "normalizedName": n["normalized_name"],
            })
        for e in payload.get("edges") or []:
            graph.append({
                "@id": f"{WEAVE_NS}fabric/{fabric_id}/edge/{e['id']}",
                "@type": "Relationship",
                "source": f"{WEAVE_NS}fabric/{fabric_id}/node/{e['source']}",
                "target": f"{WEAVE_NS}fabric/{fabric_id}/node/{e['target']}",
                "relationshipType": e["relationship_type"],
            })
        return {"@context": {"weave": WEAVE_NS}, "@graph": graph}

    def _pred(self, rel: str) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in rel)
        return f"weave:{safe}"

    def _esc(self, value: str) -> str:
        return (value or "").replace('"', '\\"')


rdf_adapter = RdfAdapter()
