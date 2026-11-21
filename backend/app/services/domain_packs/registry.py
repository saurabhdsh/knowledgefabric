"""Resolve which domain pack(s) apply to a fabric or column set."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from app.services.domain_packs.base import DomainPack
from app.services.domain_packs.healthcare_cost_of_care import healthcare_cost_of_care_pack
from app.services.domain_packs.itsm_servicenow import itsm_servicenow_pack

_PACKS: List[DomainPack] = [
    healthcare_cost_of_care_pack,
    itsm_servicenow_pack,
]

_BY_ID: Dict[str, DomainPack] = {p.id: p for p in _PACKS}


def all_packs() -> List[DomainPack]:
    return list(_PACKS)


def get_pack(pack_id: str) -> Optional[DomainPack]:
    return _BY_ID.get(pack_id)


def detect_packs(columns: Sequence[str], *, tags: Optional[Sequence[str]] = None) -> List[DomainPack]:
    """Return packs that match column names or fabric tags (order preserved)."""
    found: List[DomainPack] = []
    tag_set = {str(t).lower() for t in (tags or [])}
    for pack in _PACKS:
        tagged = any(
            pack.id in t or pack.id.replace("_", "-") in t or pack.id.split("_")[0] in t
            for t in tag_set
        )
        if tagged or pack.matches_columns(columns):
            found.append(pack)
    return found


def detect_primary_pack(columns: Sequence[str], *, tags: Optional[Sequence[str]] = None) -> Optional[DomainPack]:
    packs = detect_packs(columns, tags=tags)
    return packs[0] if packs else None


def infer_collections_from_packs(
    columns: Sequence[str],
    *,
    rows_imported: int = 0,
    tags: Optional[Sequence[str]] = None,
) -> List[dict]:
    """Merge logical collections from all matching packs (first wins on name)."""
    seen = set()
    out: List[dict] = []
    for pack in detect_packs(columns, tags=tags):
        for coll in pack.infer_collections(columns, rows_imported=rows_imported):
            name = coll.get("name")
            if name and name not in seen:
                seen.add(name)
                out.append(coll)
    return out


def short_instance_label_from_packs(
    collection: str,
    fields: Dict[str, str],
    fallback: str,
    *,
    columns: Optional[Sequence[str]] = None,
    tags: Optional[Sequence[str]] = None,
) -> Optional[str]:
    packs = detect_packs(columns or list(fields.keys()), tags=tags)
    # Prefer pack that owns this collection
    for pack in packs:
        if collection.lower() in pack.collections or any(collection.lower() in c for c in pack.collections):
            label = pack.short_label(collection, fields, fallback)
            if label:
                return label
    for pack in packs or _PACKS:
        label = pack.short_label(collection, fields, fallback)
        if label:
            return label
    return None


def cost_of_care_collections() -> set:
    return set(healthcare_cost_of_care_pack.collections)


def id_hints_for(collection: str) -> Sequence[str]:
    for pack in _PACKS:
        hints = pack.id_hints.get(collection) or pack.id_hints.get(collection.lower())
        if hints:
            return hints
    return ()
