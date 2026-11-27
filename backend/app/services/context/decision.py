"""Deterministic Context Layer adjudication over retrieved fabric facts.

Prompted LLMs still narrate; this module locks ``## DECISION`` from structured
evidence so the same fabric + context + claim does not flip between routes.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Common chronic codes in the Databricks claims_demo seed + Cost of Care CSNP set.
_CHRONIC_DX = {
    "I10",
    "E11.9",
    "E11.65",
    "F32.9",
    "K21.9",
    "J44.9",
    "J44.1",
    "J44.0",
    "N18.3",
    "N18.4",
    "N18.5",
    "N18.6",
    "I50.9",
    "I25.10",
}

_PAID = {"paid", "approved"}
_DENIED = {"denied"}
_HOLD_STATUS = {"pending", "under review", "under_review", "in review"}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_upper(value: Any) -> str:
    return _norm(value).upper()


def _is_csnp_plan(plan_id: str) -> bool:
    p = plan_id.upper().replace(" ", "")
    return "CSNP" in p or p.startswith("PLN-CSNP") or p.startswith("PLN_CSNP")


def _is_chronic(dx: str, chronic_flag: Optional[bool]) -> Optional[bool]:
    if chronic_flag is not None:
        return bool(chronic_flag)
    code = _norm_upper(dx)
    if not code:
        return None
    if code in _CHRONIC_DX:
        return True
    # Unknown code → undetermined (do not invent chronic=true)
    return False if code else None


def _row_get(row: Dict[str, Any], *names: str) -> Any:
    if not isinstance(row, dict):
        return None
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower and lower[name.lower()] not in (None, ""):
            return lower[name.lower()]
    return None


def extract_adjudication_facts(
    *,
    query: str,
    entities: Optional[List[Dict[str, Any]]] = None,
    entity_rows: Optional[List[Dict[str, Any]]] = None,
    answer: str = "",
) -> Dict[str, Any]:
    """Pull claim/member/plan/dx facts from entity rows and answer text."""
    facts: Dict[str, Any] = {
        "claim_id": None,
        "member_id": None,
        "plan_id": None,
        "claim_status": None,
        "diagnosis_code": None,
        "chronic": None,
        "denial_reason": None,
        "claim_row_found": False,
        "sources": [],
    }

    q = query or ""
    for m in re.finditer(r"\b(CLM[-_]?\d+)\b", q, re.I):
        facts["claim_id"] = facts["claim_id"] or m.group(1).upper().replace("-", "_")
    for m in re.finditer(r"\b((?:MBR|MEM)[-_]?\d+)\b", q, re.I):
        facts["member_id"] = facts["member_id"] or m.group(1).upper().replace("-", "_")
    for m in re.finditer(r"\b(PLN[-_][A-Z0-9]+(?:[-_][A-Z0-9]+)?)\b", q, re.I):
        facts["plan_id"] = facts["plan_id"] or m.group(1).upper()

    rows: List[Dict[str, Any]] = []
    for item in entity_rows or []:
        if isinstance(item, dict) and isinstance(item.get("row"), dict):
            rows.append(item)
        elif isinstance(item, dict) and item.get("table"):
            rows.append({"table": item.get("table"), "row": item})

    # Lightweight entities list from API (no full row) — still capture ids.
    for ent in entities or []:
        if not isinstance(ent, dict):
            continue
        table = str(ent.get("table") or "").lower()
        col = str(ent.get("column") or ent.get("matched_column") or "").lower()
        val = _norm(ent.get("value") or ent.get("matched_value"))
        if not val:
            continue
        if "claim" in table and "claim_id" in col:
            facts["claim_id"] = facts["claim_id"] or val
            facts["claim_row_found"] = True
            facts["sources"].append("entity:claim_id")
        if "member" in table and "member_id" in col:
            facts["member_id"] = facts["member_id"] or val
            facts["sources"].append("entity:member_id")
        if "plan" in table and "plan_id" in col:
            facts["plan_id"] = facts["plan_id"] or val
            facts["sources"].append("entity:plan_id")

    for item in rows:
        table = str(item.get("table") or "").lower()
        row = item.get("row") or {}
        if "claim" in table and "line" not in table and "event" not in table:
            facts["claim_row_found"] = True
            facts["claim_id"] = facts["claim_id"] or _norm(_row_get(row, "claim_id"))
            facts["member_id"] = facts["member_id"] or _norm(_row_get(row, "member_id"))
            facts["plan_id"] = facts["plan_id"] or _norm(_row_get(row, "plan_id"))
            facts["claim_status"] = facts["claim_status"] or _norm(
                _row_get(row, "claim_status", "status")
            )
            facts["diagnosis_code"] = facts["diagnosis_code"] or _norm(
                _row_get(row, "diagnosis_code", "dx", "primary_diagnosis", "icd10")
            )
            facts["denial_reason"] = facts["denial_reason"] or _norm(
                _row_get(row, "denial_reason", "deny_reason")
            )
            facts["sources"].append("row:claims")
        if "member" in table:
            facts["member_id"] = facts["member_id"] or _norm(_row_get(row, "member_id"))
            facts["plan_id"] = facts["plan_id"] or _norm(_row_get(row, "plan_id"))
            facts["sources"].append("row:members")
        if table in {"plans", "plan"} or table.endswith(".plans"):
            facts["plan_id"] = facts["plan_id"] or _norm(_row_get(row, "plan_id"))
            facts["sources"].append("row:plans")
        if "diagnosis" in table:
            code = _norm(_row_get(row, "diagnosis_code", "code", "icd10"))
            if code:
                facts["diagnosis_code"] = facts["diagnosis_code"] or code
            flag = _row_get(row, "chronic", "is_chronic")
            if flag is not None:
                facts["chronic"] = bool(flag) if not isinstance(flag, str) else flag.lower() in {
                    "true",
                    "1",
                    "yes",
                }
            facts["sources"].append("row:diagnosis")

        for rel_key in ("parents", "children"):
            for rel in item.get(rel_key) or []:
                if not isinstance(rel, dict):
                    continue
                rtable = str(rel.get("table") or "").lower()
                rrow = rel.get("row") or {}
                if "diagnosis" in rtable:
                    code = _norm(_row_get(rrow, "diagnosis_code", "code", "icd10"))
                    if code:
                        facts["diagnosis_code"] = facts["diagnosis_code"] or code
                    flag = _row_get(rrow, "chronic", "is_chronic")
                    if flag is not None and facts["chronic"] is None:
                        facts["chronic"] = (
                            bool(flag)
                            if not isinstance(flag, str)
                            else flag.lower() in {"true", "1", "yes"}
                        )

    # Fallback: scrape model evidence text when table_store rows were thin.
    text = answer or ""
    if not facts["claim_status"]:
        m = re.search(
            r"claim[_\s-]*status\s*[:=]\s*([A-Za-z ]+)",
            text,
            re.I,
        ) or re.search(r"\bstatus\s*[:=]\s*(Paid|Denied|Pending|Approved|Under Review)\b", text, re.I)
        if m:
            facts["claim_status"] = m.group(1).strip()
            facts["sources"].append("answer:status")
    if not facts["diagnosis_code"]:
        m = re.search(r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b", text)
        if m:
            facts["diagnosis_code"] = m.group(1)
            facts["sources"].append("answer:dx")
    if facts["claim_id"] and re.search(re.escape(str(facts["claim_id"])), text, re.I):
        facts["claim_row_found"] = facts["claim_row_found"] or bool(facts["claim_status"])

    facts["chronic"] = _is_chronic(str(facts["diagnosis_code"] or ""), facts.get("chronic"))
    return facts


def resolve_decision(
    profile: Dict[str, Any],
    facts: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a locked decision dict from profile playbook + structured facts."""
    playbook = profile.get("playbook") or {}
    routes = [str(r).strip().lower() for r in (playbook.get("routes") or []) if str(r).strip()]
    if not routes:
        routes = ["pay", "deny", "hold", "human_review"]
    default = str(playbook.get("default_route") or "human_review").strip().lower()
    if default not in routes:
        default = "human_review" if "human_review" in routes else routes[-1]

    schema = profile.get("decision_schema") or {}
    thr = schema.get("human_review_if_confidence_below")
    try:
        thr_f = float(thr) if thr is not None else None
    except (TypeError, ValueError):
        thr_f = None

    claim_found = bool(facts.get("claim_row_found") or facts.get("claim_status"))
    status = _norm(facts.get("claim_status")).lower()
    plan_id = _norm(facts.get("plan_id"))
    dx = _norm(facts.get("diagnosis_code"))
    chronic = facts.get("chronic")
    denial = _norm(facts.get("denial_reason"))

    evidence_fields: List[str] = []
    for key in ("claim_id", "member_id", "plan_id", "claim_status", "diagnosis_code"):
        if facts.get(key):
            evidence_fields.append(key)
    if facts.get("chronic") is not None:
        evidence_fields.append("chronic")
    if denial:
        evidence_fields.append("denial_reason")

    def _ok(route: str) -> str:
        return route if route in routes else default

    # Fail closed: no claim evidence → human_review
    if not claim_found and not status:
        return {
            "decision": _ok("human_review"),
            "confidence_0_1": 0.35,
            "evidence_fields": evidence_fields or ["none"],
            "reasoning_one_line": "Exact claim row missing from evidence — fail closed to human_review.",
            "resolver": "deterministic",
            "facts": facts,
        }

    if status in _DENIED:
        if denial or "denial_reason" in evidence_fields:
            return {
                "decision": _ok("deny"),
                "confidence_0_1": 0.92,
                "evidence_fields": evidence_fields,
                "reasoning_one_line": f"Claim status Denied"
                + (f" ({denial})" if denial else "")
                + ".",
                "resolver": "deterministic",
                "facts": facts,
            }
        return {
            "decision": _ok("human_review"),
            "confidence_0_1": 0.55,
            "evidence_fields": evidence_fields,
            "reasoning_one_line": "Claim is Denied but denial_reason is missing — human_review.",
            "resolver": "deterministic",
            "facts": facts,
        }

    if status in _HOLD_STATUS:
        return {
            "decision": _ok("hold"),
            "confidence_0_1": 0.9,
            "evidence_fields": evidence_fields,
            "reasoning_one_line": f"Claim status is {facts.get('claim_status')} — hold pending review.",
            "resolver": "deterministic",
            "facts": facts,
        }

    # CSNP chronic alignment (Databricks + Cost of Care demos)
    if _is_csnp_plan(plan_id):
        if chronic is False:
            return {
                "decision": _ok("hold"),
                "confidence_0_1": 0.95,
                "evidence_fields": evidence_fields,
                "reasoning_one_line": (
                    f"Plan {plan_id} is CSNP but diagnosis {dx or 'n/a'} is not chronic — hold."
                ),
                "resolver": "deterministic",
                "facts": facts,
            }
        if chronic is True and status in _PAID:
            return {
                "decision": _ok("pay"),
                "confidence_0_1": 0.96,
                "evidence_fields": evidence_fields,
                "reasoning_one_line": (
                    f"CSNP plan {plan_id} with chronic diagnosis {dx} and status "
                    f"{facts.get('claim_status')} — pay."
                ),
                "resolver": "deterministic",
                "facts": facts,
            }
        if chronic is None and status in _PAID:
            # Status paid but chronic unknown → hold, not human_review (more specific rule)
            return {
                "decision": _ok("hold"),
                "confidence_0_1": 0.7,
                "evidence_fields": evidence_fields,
                "reasoning_one_line": (
                    f"CSNP plan {plan_id} lacks chronic-alignment evidence for {dx or 'diagnosis'} — hold."
                ),
                "resolver": "deterministic",
                "facts": facts,
            }

    if status in _PAID:
        return {
            "decision": _ok("pay"),
            "confidence_0_1": 0.9,
            "evidence_fields": evidence_fields,
            "reasoning_one_line": f"Claim status is {facts.get('claim_status')} — pay.",
            "resolver": "deterministic",
            "facts": facts,
        }

    # Incomplete structured status with claim id present
    decision = _ok(default)
    confidence = 0.45
    if thr_f is not None and confidence < thr_f and "human_review" in routes:
        decision = "human_review"
    return {
        "decision": decision,
        "confidence_0_1": confidence,
        "evidence_fields": evidence_fields or ["claim_id"],
        "reasoning_one_line": "Claim identifiers present but status incomplete — default route applied.",
        "resolver": "deterministic",
        "facts": facts,
    }


_DECISION_BLOCK_RE = re.compile(
    r"(?:^|\n)##\s*DECISION\b.*?(?=\n##\s+[A-Z]|\Z)",
    re.I | re.S,
)


def format_decision_block(resolved: Dict[str, Any]) -> str:
    fields = resolved.get("evidence_fields") or []
    if isinstance(fields, list):
        fields_s = ", ".join(str(f) for f in fields)
    else:
        fields_s = str(fields)
    return (
        "## DECISION\n"
        f"- decision: {resolved.get('decision')}\n"
        f"- confidence_0_1: {resolved.get('confidence_0_1')}\n"
        f"- evidence_fields: {fields_s}\n"
        f"- reasoning_one_line: {resolved.get('reasoning_one_line')}\n"
        f"- resolver: deterministic\n"
    )


def apply_decision_to_answer(answer: str, resolved: Dict[str, Any]) -> str:
    """Replace or append the locked ## DECISION block."""
    block = format_decision_block(resolved)
    text = answer or ""
    if _DECISION_BLOCK_RE.search(text):
        return _DECISION_BLOCK_RE.sub("\n\n" + block.strip() + "\n", text).strip() + "\n"
    return (text.rstrip() + "\n\n" + block).strip() + "\n"


def lock_context_decision(
    profile: Dict[str, Any],
    *,
    query: str,
    answer: str,
    entities: Optional[List[Dict[str, Any]]] = None,
    entity_rows: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    facts = extract_adjudication_facts(
        query=query,
        entities=entities,
        entity_rows=entity_rows,
        answer=answer,
    )
    resolved = resolve_decision(profile, facts)
    return apply_decision_to_answer(answer, resolved), resolved
