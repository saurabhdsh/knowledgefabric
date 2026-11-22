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
        # Prefer the full Release 2.0 measured profile from the table-store manifest.
        fabric_id = str(fabric.get("id") or "")
        if fabric_id:
            try:
                from app.services.fabric_pipeline.runner import load_profile
                from app.services.fabric_pipeline.table_store import table_store
                from app.services.fabric_pipeline.pipelines import _schema_tables

                if table_store.exists(fabric_id):
                    full = load_profile(fabric_id)
                    if full and full.get("tables"):
                        return {
                            "tables": _schema_tables(full),
                            "foreign_keys": full.get("foreign_keys") or [],
                            "summary": full.get("summary") or {},
                            "source": "data_profile",
                        }
            except Exception as exc:
                logger.warning("Could not load measured profile for %s: %s", fabric_id, exc)

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
        rule_result = self._rule_analyze(schema_profile)
        # Measured profile FKs already carry evidence + confidence — skip LLM
        # to avoid truncating the full profile and inventing duplicate edges.
        has_measured = (
            schema_profile.get("source") == "data_profile"
            or any(isinstance(t.get("foreign_keys"), list) for t in (schema_profile.get("tables") or []))
        )
        if has_measured and rule_result.get("relationships"):
            return rule_result
        llm_result = self._llm_analyze(schema_profile)
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
            # Release 2.0 fabrics carry a measured profile: the key was verified
            # unique on the data and foreign keys were found by value overlap.
            # Older fabrics have column names only, so those are still guessed.
            profiled = isinstance(table.get("foreign_keys"), list)
            if profiled:
                pk_cols = [str(c) for c in (table.get("primary_key") or [])]
            else:
                pk_cols = [c["name"] for c in col_objs if self._looks_like_pk(c["name"])]
            entity: Dict[str, Any] = {
                "id": f"ent_{uuid.uuid4().hex[:8]}",
                "name": tname,
                "normalized_name": norm,
                "definition": f"Entity inferred from table {tname}",
                "primary_key_columns": pk_cols,
                "confidence": 0.75,
                "extraction_source": "rule_based",
                "source_table": tname,
            }
            if profiled:
                rows = table.get("row_count")
                entity["definition"] = (
                    f"{str(table.get('kind') or 'table').capitalize()} table {tname}"
                    + (f" ({rows:,} rows)" if isinstance(rows, int) else "")
                    + (f"; key {', '.join(pk_cols)} verified unique" if pk_cols else "; no unique key found")
                )
                entity["confidence"] = 0.95 if pk_cols else 0.7
                entity["evidence"] = {"basis": "data_profile", "row_count": rows, "kind": table.get("kind")}
            entities.append(entity)
            if profiled:
                # Two links to the same table are two different facts
                # (provider_id and pcp_provider_id), so each gets its own name.
                targets = [str(fk.get("references_table") or "") for fk in table.get("foreign_keys") or []]
                targets += [str(fk.get("references_table") or "") for fk in table.get("composite_foreign_keys") or []]
                repeated = {t for t in targets if t and targets.count(t) > 1}
                for fk in table.get("foreign_keys") or []:
                    target = str(fk.get("references_table") or "")
                    if not target:
                        continue
                    card_raw = str(fk.get("cardinality") or "")
                    if card_raw in ("1:1", "1:n", "n:1", "n:m"):
                        card = card_raw
                    elif card_raw in ("one-to-one", "1-1"):
                        card = "1:1"
                    else:
                        card = "n:1"
                    overlap = fk.get("overlap")
                    evidence_basis = fk.get("evidence") or "value-inclusion"
                    detail = (
                        f"{float(overlap or 0):.0%} of the distinct values of "
                        f"{tname}.{fk.get('column')} exist in {target}.{fk.get('references_column')}"
                        + (f" ({evidence_basis})" if evidence_basis else "")
                    )
                    if fk.get("distinct_values") is not None:
                        detail += f"; {fk.get('matched_values')} of {fk.get('distinct_values')} distinct values"
                    if fk.get("support") == "low":
                        detail += "; few values, so the column name carries this link"
                    if fk.get("status") == "accepted_by_review":
                        detail += "; accepted by a reviewer"
                    if fk.get("parent_is_sample"):
                        detail += f"; {target} is a sample of its source"
                    rel_name = f"references_{target}"
                    if target in repeated:
                        rel_name = f"references_{target}_via_{fk.get('column')}"
                    relationships.append({
                        "id": f"rel_{uuid.uuid4().hex[:8]}",
                        "name": rel_name,
                        "source_entity": norm,
                        "target_entity": self._normalize(target),
                        "source_columns": [c for c in [fk.get("column")] if c],
                        "target_columns": [c for c in [fk.get("references_column")] if c],
                        "cardinality": card,
                        "confidence": float(fk.get("confidence") or 0.0),
                        "extraction_source": "rule_based",
                        "tabular_binding": True,
                        "evidence_snippet": detail,
                        "evidence": {
                            "basis": evidence_basis if isinstance(evidence_basis, str) else "value_overlap",
                            "overlap": overlap,
                            "matched_values": fk.get("matched_values"),
                            "orphan_values": fk.get("orphan_values"),
                            "name_affinity": fk.get("name_affinity"),
                            "distinct_values": fk.get("distinct_values"),
                            "value_confidence": fk.get("value_confidence"),
                            "support": fk.get("support"),
                            "status": fk.get("status") or "accepted",
                            "detail": detail,
                        },
                    })
                for fk in table.get("composite_foreign_keys") or []:
                    target = str(fk.get("references_table") or "")
                    cols = [str(c) for c in fk.get("columns") or []]
                    ref_cols = [str(c) for c in fk.get("references_columns") or []]
                    if not target or len(cols) != len(ref_cols) or not cols:
                        continue
                    card_raw = str(fk.get("cardinality") or "")
                    card = "1:1" if card_raw in ("one-to-one", "1:1", "1-1") else "n:1"
                    overlap = fk.get("overlap")
                    detail = (
                        f"{float(overlap or 0):.0%} of the distinct ({', '.join(cols)}) pairs of {tname} "
                        f"exist as ({', '.join(ref_cols)}) in {target} (two-column key)"
                    )
                    rel_name = f"references_{target}"
                    if target in repeated:
                        rel_name = f"references_{target}_via_{'_'.join(cols)}"
                    relationships.append({
                        "id": f"rel_{uuid.uuid4().hex[:8]}",
                        "name": rel_name,
                        "source_entity": norm,
                        "target_entity": self._normalize(target),
                        "source_columns": cols,
                        "target_columns": ref_cols,
                        "cardinality": card,
                        "confidence": float(fk.get("confidence") or 0.0),
                        "extraction_source": "rule_based",
                        "tabular_binding": True,
                        "evidence_snippet": detail,
                        "evidence": {
                            "basis": str(fk.get("evidence") or "pair-inclusion"),
                            "overlap": overlap,
                            "matched_values": fk.get("matched_values"),
                            "orphan_values": fk.get("orphan_values"),
                            "distinct_values": fk.get("distinct_values"),
                            "status": fk.get("status") or "accepted",
                            "detail": detail,
                        },
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
                fk_target = None if profiled else self._fk_target(cname, [t.get("name") for t in tables])
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
        self.infer_parent_classes(entities)
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


    def infer_parent_classes(self, entities: List[Dict[str, Any]]) -> None:
        """When one entity name is a proper prefix of another, the shorter is the parent.

        ``Claim`` becomes the parent of ``ClaimLine``. Names that only share a
        short stem (``Plan`` / ``Plant``) are left alone.
        """
        from app.services.ontology.text_match import canonical_key

        keyed = [(canonical_key(e.get("normalized_name") or e.get("name") or ""), e) for e in entities]
        keyed = [(k, e) for k, e in keyed if k]
        for child_key, child in keyed:
            parents = [
                (parent_key, parent)
                for parent_key, parent in keyed
                if parent is not child
                and len(parent_key) >= 4
                and child_key != parent_key
                and (child_key.startswith(parent_key + " ") or child_key.startswith(parent_key))
            ]
            if len(parents) != 1:
                continue
            # Prefer the longest proper parent when several match.
            parents.sort(key=lambda item: -len(item[0]))
            child["parent_class_id"] = parents[0][1].get("id")

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
