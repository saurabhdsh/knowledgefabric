"""ServiceNow / ITSM domain pack."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from app.services.domain_packs.base import DomainPack


def _add(
    out: List[Dict[str, Any]],
    name: str,
    cols: Sequence[str],
    relevant: List[str],
    rows_imported: int,
) -> None:
    out.append({
        "name": name,
        "documents_imported": int(rows_imported or 0),
        "columns": relevant[:40] or list(cols)[:40],
    })


class ItsmServiceNowPack(DomainPack):
    def __init__(self) -> None:
        super().__init__(
            id="itsm_servicenow",
            label="ITSM — ServiceNow",
            detect_columns={
                "incident_number", "incident_id", "short_description",
                "cmdb_ci_id", "ci_name", "assignment_group_id",
            },
            collections={
                "incidents", "cmdb_cis", "business_services", "assignment_groups",
                "problems", "change_requests", "users",
            },
            label_fields={
                "incidents": ["incident_number", "incident_id", "short_description", "priority", "_id"],
                "cmdb_cis": ["cmdb_ci_name", "ci_name", "cmdb_ci_id", "ci_id", "name", "_id"],
                "business_services": ["business_service", "service_name", "business_service_id", "service_id", "name"],
                "assignment_groups": ["assignment_group", "group_name", "assignment_group_id", "group_id"],
                "users": ["caller_name", "name", "caller_user_id", "user_id", "email"],
                "problems": ["related_problem_id", "problem_id", "title", "name"],
                "change_requests": ["related_change_id", "change_id", "change_type", "title"],
            },
            id_hints={
                "incidents": ("incident_number", "incident_id"),
                "cmdb_cis": ("cmdb_ci_id", "ci_id"),
                "business_services": ("business_service_id", "service_id"),
                "assignment_groups": ("assignment_group_id", "group_id"),
                "users": ("caller_user_id", "user_id"),
                "problems": ("related_problem_id", "problem_id"),
                "change_requests": ("related_change_id", "change_id"),
            },
            synonyms={
                "incident": ["ticket", "case"],
                "cmdb_ci": ["configuration_item", "ci", "asset"],
            },
            sensitive_keywords={"caller_name", "user_id", "email", "phone"},
        )

    def infer_collections(
        self,
        columns: Sequence[str],
        *,
        rows_imported: int = 0,
    ) -> List[Dict[str, Any]]:
        cols = [str(c) for c in columns if str(c).strip()]
        lower = {c.lower() for c in cols}
        out: List[Dict[str, Any]] = []

        if {"incident_number", "incident_id"} & lower or "short_description" in lower:
            _add(out, "incidents", cols, [c for c in cols if c.lower().startswith("incident") or c.lower() in {
                "short_description", "description", "priority", "state", "category",
                "subcategory", "urgency", "impact", "opened_at", "resolved_at",
                "close_code", "close_notes", "sla_id", "sla_name", "sla_breach_status",
                "business_rule_text", "relationship_summary",
                "cmdb_ci_id", "business_service_id", "assignment_group_id",
                "caller_user_id", "related_problem_id", "related_change_id",
            } or c.lower().endswith("_id")], rows_imported)
        if any(c.startswith("cmdb_ci") or c in {"ci_id", "ci_name", "ci_class"} for c in lower):
            _add(out, "cmdb_cis", cols, [c for c in cols if "cmdb_ci" in c.lower() or c.lower().startswith("ci_")], rows_imported)
        if {"business_service_id", "business_service", "service_id", "service_name"} & lower:
            _add(out, "business_services", cols, [c for c in cols if "service" in c.lower()], rows_imported)
        if {"assignment_group_id", "assignment_group", "group_id"} & lower:
            _add(out, "assignment_groups", cols, [c for c in cols if "assignment_group" in c.lower() or c.lower() in {
                "group_id", "group_name",
            }], rows_imported)
        if {"related_problem_id", "problem_id"} & lower:
            _add(out, "problems", cols, [c for c in cols if "problem" in c.lower()], rows_imported)
        if {"related_change_id", "change_id", "change_type"} & lower:
            _add(out, "change_requests", cols, [c for c in cols if "change" in c.lower()], rows_imported)
        if {"caller_user_id", "caller_name", "user_id"} & lower:
            _add(out, "users", cols, [c for c in cols if c.lower().startswith("caller") or c.lower().startswith("user")], rows_imported)
        return out


itsm_servicenow_pack = ItsmServiceNowPack()
