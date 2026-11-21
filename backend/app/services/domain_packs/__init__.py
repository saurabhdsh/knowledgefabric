"""Phase 2 domain packs — configurable rules extracted from endpoint heuristics."""
from app.services.domain_packs.base import DomainPack
from app.services.domain_packs.registry import (
    all_packs,
    cost_of_care_collections,
    detect_packs,
    detect_primary_pack,
    get_pack,
    id_hints_for,
    infer_collections_from_packs,
    short_instance_label_from_packs,
)

__all__ = [
    "DomainPack",
    "all_packs",
    "cost_of_care_collections",
    "detect_packs",
    "detect_primary_pack",
    "get_pack",
    "id_hints_for",
    "infer_collections_from_packs",
    "short_instance_label_from_packs",
]
