"""Domain pack protocol — pluggable rules that augment (never replace) profile evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set


@dataclass
class DomainPack:
    """Configurable rules for a business domain (healthcare, ITSM, …)."""

    id: str
    label: str
    # Column-name signals used to auto-detect this pack from a schema.
    detect_columns: Set[str] = field(default_factory=set)
    # Logical collection name → preferred label columns (first match wins).
    label_fields: Dict[str, List[str]] = field(default_factory=dict)
    # Logical collection name → natural id columns that identify a row.
    id_hints: Dict[str, Sequence[str]] = field(default_factory=dict)
    # Collection names that belong to this domain (multi-file CSV packs).
    collections: Set[str] = field(default_factory=set)
    # Synonyms used by ontology enrichment (optional).
    synonyms: Dict[str, List[str]] = field(default_factory=dict)
    # Sensitive / PHI-ish field name fragments.
    sensitive_keywords: Set[str] = field(default_factory=set)

    def matches_columns(self, columns: Sequence[str]) -> bool:
        lower = {str(c).lower() for c in columns if str(c).strip()}
        return bool(self.detect_columns & lower)

    def infer_collections(
        self,
        columns: Sequence[str],
        *,
        rows_imported: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return logical collection stubs derived from column names. Override in packs."""
        return []

    def short_label(self, collection: str, fields: Dict[str, str], fallback: str) -> Optional[str]:
        coll = (collection or "").lower()
        preferred = list(self.label_fields.get(coll) or [])
        if not preferred:
            for key, vals in self.label_fields.items():
                if key in coll or coll in key:
                    preferred = list(vals)
                    break
        for key in preferred:
            for fk, fv in fields.items():
                if fk.lower() != key.lower():
                    continue
                text = fv
                if text.startswith("{") and len(text) > 80:
                    text = text[:80] + "…"
                if len(text) > 64:
                    text = text[:61] + "…"
                return text
        return None

    def business_rules(self) -> List[Dict[str, Any]]:
        """Return domain business rules for ontology constraints.

        Each rule dict supports:
          expression, confidence, related_entity (table/class name),
          constraint_type (optional; defaults to business_rule).
        """
        return []
