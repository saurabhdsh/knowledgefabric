"""Schema-aware LLM analysis (Phase 2 Layer 1)."""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm.llm_router import llm_router

logger = logging.getLogger(__name__)

SCHEMA_ANALYSIS_PROMPT = """
Analyze this database schema and respond with a single JSON object (no markdown):
{
  "entities": [{"name": "string", "normalized_name": "string", "definition": "string", "primary_key_columns": ["col"], "confidence": 0.0-1.0}],
  "relationships": [{"name": "string", "source_entity": "string", "target_entity": "string", "source_columns": ["col"], "target_columns": ["col"], "cardinality": "1:1|1:n|n:m", "confidence": 0.0-1.0}],
  "attributes": [{"entity": "string", "name": "string", "normalized_name": "string", "data_type": "string", "required": false, "confidence": 0.0-1.0}]
}
Infer entities from tables, relationships from FK-like column patterns, and attributes from columns.
"""


class SchemaAnalyzer:
    def build_profile_from_fabric(self, fabric: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not fabric:
            return None
        conn = fabric.get("connection_info") or {}
        tables = conn.get("tables") or conn.get("schema_tables")
        if tables:
            return {"tables": tables, "source": "connection_info"}
        if conn.get("type") in ("csv_upload", "database"):
            return {
                "tables": [{
                    "name": conn.get("database_profile") or fabric.get("name") or "dataset",
                    "columns": conn.get("columns") or [],
                    "sample_rows": conn.get("sample_rows") or [],
                }],
                "source": "fabric_metadata",
            }
        return None

    def analyze(self, schema_profile: Dict[str, Any]) -> Dict[str, Any]:
        llm_result = self._llm_analyze(schema_profile)
        rule_result = self._rule_analyze(schema_profile)
        return self._merge(llm_result, rule_result)

    def _rule_analyze(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        attributes: List[Dict[str, Any]] = []
        tables = profile.get("tables") or []

        for table in tables:
            tname = str(table.get("name") or "Table")
            norm = self._normalize(tname)
            cols = table.get("columns") or []
            if isinstance(cols, list) and cols and isinstance(cols[0], str):
                col_objs = [{"name": c, "type": "string"} for c in cols]
            else:
                col_objs = cols
            pk_cols = [c["name"] for c in col_objs if self._looks_like_pk(c["name"])]
            entities.append({
                "id": f"ent_{uuid.uuid4().hex[:8]}",
                "name": tname,
                "normalized_name": norm,
                "definition": f"Entity inferred from table {tname}",
                "primary_key_columns": pk_cols,
                "confidence": 0.75,
                "extraction_source": "rule_based",
                "source_table": tname,
            })
            for col in col_objs:
                cname = col.get("name") or ""
                attributes.append({
                    "id": f"attr_{uuid.uuid4().hex[:8]}",
                    "entity": norm,
                    "name": cname,
                    "normalized_name": self._normalize(cname),
                    "data_type": col.get("type") or "string",
                    "required": bool(col.get("required", False)),
                    "confidence": 0.7,
                    "extraction_source": "rule_based",
                    "source_table": tname,
                    "source_column": cname,
                })
                fk_target = self._fk_target(cname, [t.get("name") for t in tables])
                if fk_target:
                    relationships.append({
                        "id": f"rel_{uuid.uuid4().hex[:8]}",
                        "name": f"references_{fk_target}",
                        "source_entity": norm,
                        "target_entity": self._normalize(fk_target),
                        "source_columns": [cname],
                        "target_columns": [],
                        "cardinality": "n:1",
                        "confidence": 0.65,
                        "extraction_source": "rule_based",
                        "tabular_binding": True,
                    })
        return {"entities": entities, "relationships": relationships, "attributes": attributes}

    def _llm_analyze(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        if not llm_router.is_provider_ready(llm_router.ontology_provider()):
            return {"entities": [], "relationships": [], "attributes": []}

        payload = json.dumps(profile, default=str)[:12000]
        try:
            provider = llm_router.ontology_provider()
            model = (
                settings.BEDROCK_ONTOLOGY_MODEL_ID or settings.BEDROCK_MODEL_ID
                if provider == "bedrock"
                else settings.ONTOLOGY_LLM_MODEL
            )
            raw = llm_router.chat_completion(
                provider=provider,
                messages=[
                    {"role": "system", "content": SCHEMA_ANALYSIS_PROMPT},
                    {"role": "user", "content": payload},
                ],
                model=model,
                max_tokens=3000,
                temperature=settings.ONTOLOGY_LLM_TEMPERATURE,
            )
            parsed = self._parse_json(raw)
            if not parsed:
                return {"entities": [], "relationships": [], "attributes": []}
            return self._normalize_llm(parsed)
        except Exception as exc:
            logger.warning("Schema LLM analysis failed: %s", exc)
            return {"entities": [], "relationships": [], "attributes": []}

    def _merge(self, llm: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        entities = {e["normalized_name"]: e for e in rules.get("entities", [])}
        for e in llm.get("entities", []):
            key = e.get("normalized_name") or e.get("name")
            if key and key not in entities:
                entities[key] = e
        rels = rules.get("relationships", []) + llm.get("relationships", [])
        attrs = rules.get("attributes", []) + llm.get("attributes", [])
        return {"entities": list(entities.values()), "relationships": rels, "attributes": attrs}

    def _normalize(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip())
        parts = [p.capitalize() for p in cleaned.split("_") if p]
        return "".join(parts) or "Entity"

    def _looks_like_pk(self, col: str) -> bool:
        c = col.lower()
        return c in ("id", "uuid", "pk") or c.endswith("_id") or c.endswith("key")

    def _fk_target(self, col: str, tables: List[Any]) -> Optional[str]:
        c = col.lower()
        if not c.endswith("_id"):
            return None
        base = c[:-3]
        for t in tables:
            tname = str(t).lower()
            if base in tname or tname.startswith(base):
                return str(t)
        return base.replace("_", " ").title() if base else None

    def _parse_json(self, raw: str) -> Optional[Dict[str, Any]]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            if start >= 0:
                try:
                    return json.loads(raw[start:])
                except json.JSONDecodeError:
                    return None
        return None

    def _normalize_llm(self, data: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, List[Dict[str, Any]]] = {"entities": [], "relationships": [], "attributes": []}
        for e in data.get("entities") or []:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            norm = (e.get("normalized_name") or self._normalize(name))
            out["entities"].append({
                "id": f"ent_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "normalized_name": norm,
                "definition": e.get("definition"),
                "primary_key_columns": e.get("primary_key_columns") or [],
                "confidence": float(e.get("confidence", 0.6)),
                "extraction_source": "llm",
            })
        for r in data.get("relationships") or []:
            name = (r.get("name") or "relates_to").strip()
            src = r.get("source_entity") or r.get("source")
            tgt = r.get("target_entity") or r.get("target")
            if not src or not tgt:
                continue
            out["relationships"].append({
                "id": f"rel_llm_{uuid.uuid4().hex[:8]}",
                "name": name,
                "source_entity": src,
                "target_entity": tgt,
                "source_columns": r.get("source_columns") or [],
                "target_columns": r.get("target_columns") or [],
                "cardinality": r.get("cardinality"),
                "confidence": float(r.get("confidence", 0.5)),
                "extraction_source": "llm",
                "tabular_binding": True,
            })
        for a in data.get("attributes") or []:
            entity = a.get("entity")
            name = (a.get("name") or "").strip()
            if not entity or not name:
                continue
            out["attributes"].append({
                "id": f"attr_llm_{uuid.uuid4().hex[:8]}",
                "entity": entity,
                "name": name,
                "normalized_name": a.get("normalized_name") or self._normalize(name),
                "data_type": a.get("data_type") or "string",
                "required": bool(a.get("required", False)),
                "confidence": float(a.get("confidence", 0.5)),
                "extraction_source": "llm",
            })
        return out


schema_analyzer = SchemaAnalyzer()
