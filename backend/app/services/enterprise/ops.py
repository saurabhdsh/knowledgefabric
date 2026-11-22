"""Enterprise operations for a Knowledge Fabric (Release 2.0 Phase 5).

Logical order on every publish:
1. Classify PII columns from names and the active domain pack.
2. Append a lineage version (what changed, parent version, fingerprints).
3. Ensure the owner is on the access list.
4. Write an audit event.

Incremental sync compares incoming rows to the stored table by primary key.
A column-set change is a full rebuild, not a silent partial update.
Vector indexes are isolated per fabric so one fabric's chunks cannot be
retrieved from another's collection.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.core.user_context import get_current_user_id

_PII_EXACT = {
    "ssn", "social_security", "dob", "date_of_birth", "birth_date", "email",
    "phone", "mobile", "address", "street", "member_name", "patient_name",
    "full_name", "first_name", "last_name",
}
_PII_FRAGMENTS = ("ssn", "dob", "email", "phone", "address", "passport")


class AccessDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lineage_path(fabric_id: str) -> str:
    root = os.path.join(settings.DATA_DIR, "fabric_lineage")
    os.makedirs(root, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", fabric_id)[:80]
    return os.path.join(root, f"{safe}.json")


def _audit_path() -> str:
    root = os.path.join(settings.DATA_DIR, "fabric_audit")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "events.jsonl")


def _load_lineage(fabric_id: str) -> Dict[str, Any]:
    path = _lineage_path(fabric_id)
    if not os.path.isfile(path):
        return {"fabric_id": fabric_id, "versions": []}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("versions", [])
    return data


def _save_lineage(fabric_id: str, data: Dict[str, Any]) -> None:
    path = _lineage_path(fabric_id)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, default=str)


def fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def isolated_collection_name(fabric_id: str) -> str:
    """Chroma collection dedicated to one fabric (3–63 chars, stable)."""
    digest = hashlib.sha1(str(fabric_id).encode("utf-8")).hexdigest()[:20]
    return f"kf_f_{digest}"


def classify_pii(column_names: Sequence[str], *, extra_sensitive: Optional[Iterable[str]] = None) -> List[Dict[str, str]]:
    """Tag columns as phi, pii, or none. Domain-pack keywords count as phi."""
    sensitive = {str(s).lower() for s in (extra_sensitive or [])}
    try:
        from app.services.domain_packs import detect_packs

        for pack in detect_packs(list(column_names)):
            sensitive.update(str(k).lower() for k in (pack.sensitive_keywords or []))
    except Exception:
        pass
    out: List[Dict[str, str]] = []
    for name in column_names:
        key = str(name or "").strip().lower()
        if not key:
            continue
        if key in sensitive or any(frag in key for frag in _PII_FRAGMENTS) or key in _PII_EXACT:
            kind = "phi" if key in sensitive or key in {"member_id", "member_name", "dob", "ssn"} else "pii"
            out.append({"column": str(name), "sensitivity": kind, "reason": "name_or_domain_pack"})
        else:
            out.append({"column": str(name), "sensitivity": "none", "reason": ""})
    return out


def _columns_from_fabric(fabric: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    conn = fabric.get("connection_info") or {}
    tables = conn.get("tables") or conn.get("schema_tables") or []
    if isinstance(tables, list):
        for table in tables:
            if isinstance(table, dict):
                for col in table.get("columns") or []:
                    if isinstance(col, dict) and col.get("name"):
                        names.append(str(col["name"]))
                    elif isinstance(col, str):
                        names.append(col)
    return names


def ensure_owner_acl(fabric: Dict[str, Any]) -> Dict[str, Any]:
    access = dict(fabric.get("access") or {})
    owner = access.get("owner_id") or fabric.get("owner_id") or get_current_user_id()
    grants = list(access.get("grants") or [])
    if owner and not any(g.get("user_id") == owner for g in grants):
        grants.append({"user_id": owner, "role": "owner"})
    access["owner_id"] = owner
    access["grants"] = grants
    fabric["access"] = access
    return access


def authorize(fabric: Dict[str, Any], action: str) -> str:
    """Return the caller's role. Raise AccessDenied when a known user is outside the ACL.

    No signed-in user means local/system use and is allowed as role ``system``.
    ``export`` requires analyst or owner. ``query`` allows viewer.
    """
    user = get_current_user_id()
    access = fabric.get("access") or {}
    grants = {g.get("user_id"): g.get("role") for g in (access.get("grants") or [])}
    owner = access.get("owner_id") or fabric.get("owner_id")
    if not user:
        role = "system"
    elif user == owner or grants.get(user) == "owner":
        role = "owner"
    elif user in grants:
        role = str(grants[user] or "viewer")
    elif owner and not grants:
        # Fabric has an owner but this user is not them and no grants exist.
        raise AccessDenied("Not allowed to access this fabric")
    elif owner and user != owner:
        raise AccessDenied("Not allowed to access this fabric")
    else:
        role = "owner"
    if action == "export" and role == "viewer":
        raise AccessDenied("Viewer role cannot export this fabric")
    if action not in ("query", "export", "sync", "admin"):
        raise AccessDenied(f"Unknown action '{action}'")
    if action in ("sync", "admin") and role not in ("owner", "system"):
        raise AccessDenied("Only the fabric owner can change this fabric")
    return role


def record_audit(
    fabric_id: str,
    action: str,
    *,
    actor: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = {
        "id": f"aud_{uuid.uuid4().hex[:12]}",
        "fabric_id": fabric_id,
        "action": action,
        "actor": actor or get_current_user_id() or "system",
        "at": _now(),
        "detail": detail or {},
    }
    with open(_audit_path(), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, default=str) + "\n")
    return event


def list_audit(fabric_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    path = _audit_path()
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if fabric_id and event.get("fabric_id") != fabric_id:
                continue
            rows.append(event)
    return rows[-limit:]


def record_grant(fabric: Dict[str, Any], user_id: str, role: str) -> Dict[str, Any]:
    if role not in ("owner", "analyst", "viewer"):
        raise ValueError("role must be owner, analyst, or viewer")
    authorize(fabric, "admin")
    ensure_owner_acl(fabric)
    grants = [g for g in fabric["access"]["grants"] if g.get("user_id") != user_id]
    grants.append({"user_id": user_id, "role": role})
    fabric["access"]["grants"] = grants
    record_audit(str(fabric.get("id")), "grant", detail={"user_id": user_id, "role": role})
    return fabric["access"]


def on_publish(fabric: Dict[str, Any], *, change: str = "publish") -> Dict[str, Any]:
    """Stamp PII, lineage, and ACL onto a fabric that just finished a pipeline."""
    columns = _columns_from_fabric(fabric)
    pii = classify_pii(columns)
    fabric["pii"] = {
        "classified_at": _now(),
        "sensitive": [c for c in pii if c["sensitivity"] != "none"],
        "column_count": len(pii),
    }
    ensure_owner_acl(fabric)
    summary = {
        "tables": sorted(
            str(t.get("name"))
            for t in ((fabric.get("connection_info") or {}).get("tables") or [])
            if isinstance(t, dict) and t.get("name")
        ),
        "row_count": fabric.get("row_count"),
        "table_count": fabric.get("table_count"),
        "pipeline_version": (fabric.get("pipeline") or {}).get("version"),
    }
    book = _load_lineage(str(fabric["id"]))
    parent = book["versions"][-1]["id"] if book["versions"] else None
    version = {
        "id": f"flv_{uuid.uuid4().hex[:12]}",
        "at": _now(),
        "change": change,
        "parent_id": parent,
        "fingerprint": fingerprint(summary),
        "summary": summary,
        "sensitive_columns": [c["column"] for c in fabric["pii"]["sensitive"]],
        "index_collection": isolated_collection_name(str(fabric["id"])),
    }
    book["versions"].append(version)
    _save_lineage(str(fabric["id"]), book)
    fabric["lineage_version_id"] = version["id"]
    fabric["index_collection"] = version["index_collection"]
    record_audit(str(fabric["id"]), change, detail={"lineage_version_id": version["id"], "fingerprint": version["fingerprint"]})
    return version


def list_lineage(fabric_id: str) -> Dict[str, Any]:
    return _load_lineage(fabric_id)


def _row_key(row: Dict[str, Any], key_columns: Sequence[str]) -> Tuple[str, ...]:
    return tuple("" if row.get(col) is None else str(row.get(col)) for col in key_columns)


def _row_hash(row: Dict[str, Any]) -> str:
    stable = {k: v for k, v in row.items() if not str(k).startswith("__")}
    return fingerprint(stable)


def plan_row_sync(
    current_rows: Sequence[Dict[str, Any]],
    incoming_rows: Sequence[Dict[str, Any]],
    *,
    key_columns: Sequence[str],
    current_columns: Optional[Sequence[str]] = None,
    incoming_columns: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Diff one table. Schema changes force a full rebuild."""
    if not key_columns:
        return {"mode": "full_rebuild", "reason": "no primary key", "added": [], "changed": [], "removed": []}
    cur_cols = set(current_columns or [])
    inc_cols = set(incoming_columns or [])
    if cur_cols and inc_cols and cur_cols != inc_cols:
        return {
            "mode": "full_rebuild",
            "reason": "column set changed",
            "added": [],
            "changed": [],
            "removed": [],
        }
    current = {_row_key(r, key_columns): r for r in current_rows}
    incoming = {_row_key(r, key_columns): r for r in incoming_rows}
    added = [incoming[k] for k in incoming.keys() - current.keys()]
    removed = [current[k] for k in current.keys() - incoming.keys()]
    changed = [
        incoming[k]
        for k in incoming.keys() & current.keys()
        if _row_hash(current[k]) != _row_hash(incoming[k])
    ]
    return {
        "mode": "incremental",
        "reason": "primary key diff",
        "added": added,
        "changed": changed,
        "removed": removed,
        "added_count": len(added),
        "changed_count": len(changed),
        "removed_count": len(removed),
    }


_SECRET_KEYS = {
    "password", "passwd", "secret", "token", "api_key", "apikey", "client_secret",
    "access_key", "private_key", "connection_string",
}


def scrub_fabric_secrets(fabric: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy safe to send to a browser or partner.

    Connector passwords and other secrets are dropped. Existing fabrics that
    already stored them are scrubbed on read so the catalog never re-leaks them.
    """
    out = dict(fabric or {})
    out.pop("connection_data", None)
    conn = out.get("connection_info")
    if isinstance(conn, dict):
        cleaned = {}
        for key, value in conn.items():
            if str(key).lower() in _SECRET_KEYS:
                continue
            if isinstance(value, dict):
                cleaned[key] = {
                    k: ("[redacted]" if str(k).lower() in _SECRET_KEYS else v)
                    for k, v in value.items()
                }
            else:
                cleaned[key] = value
        out["connection_info"] = cleaned
    return out


def can_view_fabric(fabric: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """Whether ``user_id`` may see this fabric in the catalog.

    Owner, anyone on the grant list, and admins (role checked by the caller via
    ``user_is_admin``) are allowed. With no signed-in user the system path is
    allowed so background jobs keep working.
    """
    user = user_id if user_id is not None else get_current_user_id()
    if not user:
        return True
    access = fabric.get("access") or {}
    owner = access.get("owner_id") or fabric.get("owner_id")
    if owner and owner == user:
        return True
    grants = access.get("grants") or []
    if any(g.get("user_id") == user for g in grants):
        return True
    # Legacy rows with no owner are hidden from signed-in users (same as before).
    if not owner:
        return False
    return False


def redact_row(row: Dict[str, Any], sensitive_columns: Sequence[str]) -> Dict[str, Any]:

    hidden = {c.lower() for c in sensitive_columns}
    out = dict(row)
    for key in list(out):
        if str(key).lower() in hidden:
            out[key] = "[restricted]"
    return out
