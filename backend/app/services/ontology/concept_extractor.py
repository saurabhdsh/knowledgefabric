"""Rule-based extraction of entity/relationship/attribute/business-rule candidates."""
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.models.ontology import OntologyEvidence, ExtractionSourceType


# Labels that strongly suggest attributes (domain-agnostic)
ATTRIBUTE_LIKE_LABELS = {
    "id", "name", "date", "code", "type", "status", "amount", "category",
    "description", "value", "number", "identifier", "title", "version",
    "created_at", "updated_at", "timestamp", "key", "ref", "reference",
    "quantity", "price", "total", "count", "flag", "enabled", "active",
}

# Data-warehouse / star-schema naming conventions. A column whose name ends with
# one of these is almost always a foreign reference to a separate entity table.
ENTITY_REF_SUFFIXES: Tuple[str, ...] = (
    "Dim", "Fact", "Bridge", "Lookup", "Mapping",
)

# Prefix tokens that are NOT entities even if many columns share them — these are
# temporal / boolean / comparator words that just describe other attributes.
PREFIX_BLOCKLIST: set = {
    "is", "has", "was", "will", "had", "do", "does",
    "total", "min", "max", "avg", "mean", "sum", "count", "num",
    "first", "last", "next", "prev", "current", "previous",
    "new", "old", "created", "updated", "modified", "deleted",
    "actual", "expected", "target", "planned",
    "original", "final", "default", "primary", "secondary",
    "start", "end", "from", "to",
    "affected", "related",  # related_X handled specially below
    "short", "detailed", "long", "full",
    "data", "raw", "clean", "valid", "invalid",
    "work", "before", "after",
}

# Short tokens we want to keep as ACRONYMS (rather than Title-case) when they
# show up as a snake_case prefix in lowercase form.
SHORT_ACRONYM_PREFIXES: set = {
    "ai", "ci", "ip", "ui", "ux", "ml", "qa", "hr", "it", "pr",
    "rx", "kb", "qa", "ar", "ap", "id",
}


class ConceptExtractor:
    """Extract candidate nouns (entities), verbs (relationships), labels (attributes), rules."""

    def __init__(self):
        self.attribute_labels = ATTRIBUTE_LIKE_LABELS

    def extract_from_text(
        self,
        text: str,
        evidence_list: Optional[List[OntologyEvidence]] = None,
        source_artifact_id: Optional[str] = None,
        page_number: Optional[int] = None,
        xml_path: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run rule-based extraction on text. Returns:
        entities, relationships, attributes, business_rules, enumerations
        """
        evidence = evidence_list or []
        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        attributes: List[Dict[str, Any]] = []
        business_rules: List[Dict[str, Any]] = []
        enumerations: List[Dict[str, Any]] = []

        # Nouns (capitalized or title-case phrases) as entity candidates
        noun_phrases = self._extract_noun_phrases(text)
        for np in noun_phrases:
            normalized = self._normalize_name(np)
            if len(normalized) < 2 or normalized.lower() in ("the", "a", "an"):
                continue
            entities.append({
                "id": f"ent_rb_{uuid.uuid4().hex[:8]}",
                "name": np,
                "normalized_name": normalized,
                "source": "rule_based",
                "evidence_snippet": self._snippet(text, np),
                "confidence": 0.5,
            })

        # Verb phrases as relationship candidates
        verb_phrases = self._extract_verb_phrases(text)
        for vp in verb_phrases:
            relationships.append({
                "id": f"rel_rb_{uuid.uuid4().hex[:8]}",
                "name": vp,
                "normalized_name": self._normalize_name(vp),
                "source": "rule_based",
                "evidence_snippet": self._snippet(text, vp),
                "confidence": 0.45,
            })

        # Attribute-like labels
        for label in self._extract_labels(text):
            if label.lower() in self.attribute_labels or self._looks_like_attribute(label):
                attributes.append({
                    "id": f"attr_rb_{uuid.uuid4().hex[:8]}",
                    "name": label,
                    "normalized_name": self._normalize_name(label),
                    "source": "rule_based",
                    "evidence_snippet": self._snippet(text, label),
                    "confidence": 0.7,
                })

        # Business rule indicators: must, required, mandatory, only if, cannot, should, depends on
        rule_patterns = [
            r"(?:must|shall|required|mandatory)\s+[^.]*?\.",
            r"(?:only\s+if|when|if\s+and\s+only\s+if)[^.]*?\.",
            r"(?:cannot|must\s+not|should\s+not)[^.]*?\.",
            r"(?:should|may|optional)[^.]*?\.",
            r"depends\s+on[^.]*?\.",
        ]
        for pat in rule_patterns:
            for m in re.finditer(pat, text, re.I | re.DOTALL):
                snippet = m.group(0).strip()[:400]
                business_rules.append({
                    "id": f"rule_rb_{uuid.uuid4().hex[:8]}",
                    "expression": snippet,
                    "source": "rule_based",
                    "confidence": 0.6,
                })

        return {
            "entities": entities,
            "relationships": relationships,
            "attributes": attributes,
            "business_rules": business_rules,
            "enumerations": enumerations,
        }

    def extract_from_xml_hierarchy(
        self,
        node_hierarchy: List[Dict[str, Any]],
        repeated_groups: List[str],
        evidence: List[OntologyEvidence],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Map XML structure to entity/attribute candidates."""
        entities: List[Dict[str, Any]] = []
        attributes: List[Dict[str, Any]] = []
        repeated_set = set(repeated_groups)
        path_to_evidence: Dict[str, OntologyEvidence] = {e.xml_path: e for e in evidence if e.xml_path}

        for node in node_hierarchy:
            path = node["path"]
            tag = node["tag"]
            is_leaf = node["is_leaf"]
            if tag.lower() == "fabricsource":
                continue
            norm = self._normalize_name(tag)
            ev = path_to_evidence.get(path)
            snippet = (node.get("text_sample") or path)[:200]
            conf = 0.85 if not is_leaf else 0.75

            if is_leaf:
                if tag.lower() == "chunk":
                    # Vector row text; real attributes come from tabular row parsing
                    continue
                attributes.append({
                    "id": f"attr_xml_{uuid.uuid4().hex[:8]}",
                    "name": tag,
                    "normalized_name": norm,
                    "source": "rule_based",
                    "xml_path": path,
                    "evidence_snippet": snippet,
                    "confidence": conf,
                })
            else:
                # Parent nodes as entity candidates; repeated groups get higher confidence
                conf_entity = 0.9 if path in repeated_set or any(path.endswith(r) for r in repeated_set) else 0.7
                entities.append({
                    "id": f"ent_xml_{uuid.uuid4().hex[:8]}",
                    "name": tag,
                    "normalized_name": norm,
                    "source": "rule_based",
                    "xml_path": path,
                    "evidence_snippet": snippet,
                    "confidence": conf_entity,
                })

        return {
            "entities": entities,
            "relationships": [],
            "attributes": attributes,
            "business_rules": [],
            "enumerations": [],
        }

    def extract_from_tabular_row_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_chunks: int = 120,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Infer entities, FK-style relationships, and attributes from database/CSV row text
        formatted as ``key: value | key: value`` (common for vectorized tabular rows).
        """
        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        attributes: List[Dict[str, Any]] = []

        sampled_texts: List[str] = []
        for c in chunks[:max_chunks]:
            text = (c.get("content") or "").strip()
            if len(text) < 8 or ":" not in text:
                continue
            if "|" not in text and text.count(":") < 2:
                continue
            sampled_texts.append(text)

        if not sampled_texts:
            return {
                "entities": entities,
                "relationships": relationships,
                "attributes": attributes,
                "enumerations": [],
            }

        pair_lists: List[List[Tuple[str, str]]] = []
        for text in sampled_texts:
            pairs = self._parse_kv_pipe_row(text)
            if len(pairs) >= 2:
                pair_lists.append(pairs)

        if not pair_lists:
            return {
                "entities": entities,
                "relationships": relationships,
                "attributes": attributes,
                "enumerations": [],
            }

        unique_keys: List[str] = []
        seen_k = set()
        for pairs in pair_lists:
            for k, _ in pairs:
                lk = k.lower()
                if lk not in seen_k:
                    seen_k.add(lk)
                    unique_keys.append(k)

        root_display = self._infer_root_entity_from_keys(unique_keys)
        entity_names_added: set = set()

        def add_entity(display_name: str, confidence: float = 0.82) -> None:
            norm = self._normalize_name(display_name)
            key = norm.lower()
            if not norm or key in entity_names_added:
                return
            entity_names_added.add(key)
            entities.append({
                "id": f"ent_tab_{key.replace(' ', '_')[:28]}",
                "name": display_name,
                "normalized_name": norm,
                "source": "tabular_fabric",
                "evidence_snippet": (
                    f"{display_name} inferred from tabular columns: "
                    + ", ".join(unique_keys[:16])
                    + ("..." if len(unique_keys) > 16 else "")
                ),
                "confidence": confidence,
            })

        add_entity(root_display)

        # Pre-compute which columns look like references to other entities, so we
        # can both create the target entity and the relationship in a single pass
        # and (importantly) skip them when emitting attributes.
        root_lower = root_display.lower()
        reference_columns: List[Tuple[str, str, str, float]] = []  # (col, entity_name, rel_name, confidence)
        for k in unique_keys:
            entity_name, kind = self._classify_reference_column(k)
            if not entity_name:
                continue
            if entity_name.lower() == root_lower:
                continue
            rel_name = self._relationship_name_for_reference(k, kind)
            confidence = {
                "id_suffix": 0.82,
                "dw_suffix": 0.80,
                "camel_entity": 0.72,
                "related_prefix": 0.74,
            }.get(kind, 0.7)
            reference_columns.append((k, entity_name, rel_name, confidence))

        # Phase B: prefix-group detection. When ≥2 columns share a snake_case
        # prefix and the prefix isn't a generic comparator/temporal word, the
        # prefix usually IS an entity (e.g. caller_id/caller_name/caller_email
        # → Caller entity).
        seen_entity_lower = {e.lower() for _, e, _, _ in reference_columns}
        seen_entity_lower.add(root_lower)
        for prefix, cols in self._extract_prefix_groups(unique_keys):
            entity_name = self._prefix_to_entity_name(prefix)
            if not entity_name:
                continue
            if entity_name.lower() in seen_entity_lower:
                continue
            seen_entity_lower.add(entity_name.lower())
            rel_name = self._relationship_name_for_reference(prefix, "prefix_group")
            reference_columns.append((prefix, entity_name, rel_name, 0.70))

        reference_column_set = {c[0] for c in reference_columns}

        for _, entity_name, _, _ in reference_columns:
            add_entity(entity_name, 0.78)

        for col, entity_name, rel_name, confidence in reference_columns:
            relationships.append({
                "id": f"rel_tab_{uuid.uuid4().hex[:8]}",
                "name": rel_name,
                "normalized_name": rel_name,
                "relationship_name": rel_name,
                "source": "tabular_fabric",
                "tabular_binding": True,
                "source_entity_normalized": root_display,
                "target_entity_normalized": entity_name,
                "evidence_snippet": (
                    f"{root_display} row links to {entity_name} via column {col}"
                ),
                "confidence": confidence,
            })

        for k in unique_keys:
            if k in reference_column_set:
                continue
            norm_attr = self._normalize_name(k.replace("_", " "))
            attributes.append({
                "id": f"attr_tab_{uuid.uuid4().hex[:8]}",
                "name": k,
                "normalized_name": norm_attr,
                "source": "tabular_fabric",
                "evidence_snippet": f"{root_display} record field {k}",
                "confidence": 0.74,
            })

        return {
            "entities": entities,
            "relationships": relationships,
            "attributes": attributes,
            "enumerations": [],
        }

    def _classify_reference_column(self, col: str) -> Tuple[str, str]:
        """
        Decide whether a column name points to another entity, and return
        (entity_display_name, kind) where kind is one of:
          - "id_suffix"     → claim_id, member_id, CLAIM_ID, claimId ...
          - "dw_suffix"     → MemberDim, MEMBER_DIM, member_dim, ClaimFact,
                              CLAIM_FACT, condition_lookup, ICD_MAPPING ...
          - "camel_entity"  → Diagnosis, Enrollment, BenefitPackage ...
        Returns ("", "") when the column should stay an attribute. Matching is
        case-insensitive and tolerates snake_case, SCREAMING_SNAKE_CASE,
        CamelCase, camelCase, and kebab-case across all supported connectors.
        """
        if not col:
            return ("", "")
        base = col.strip().replace("-", "_")
        lower = base.lower()

        if lower in ATTRIBUTE_LIKE_LABELS:
            return ("", "")

        # ITSM-style convention: related_change / related_problem / related_request
        # → reference to entity Change / Problem / Request.
        if lower.startswith("related_") and len(lower) > len("related_"):
            rest = base[len("related_"):].strip("_")
            if rest:
                entity = self._normalize_mixed_token(rest) or rest.title()
                return (entity, "related_prefix")

        if lower.endswith("_id") and len(lower) > 3:
            entity = self._column_base_entity_name(base)
            return (entity, "id_suffix") if entity else ("", "")

        # Postgres / Databricks camelCase ID pattern: claimId, memberId.
        camel_id_match = re.match(r"^([a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)*)Id$", base)
        if camel_id_match:
            entity = self._column_base_entity_name(camel_id_match.group(1))
            return (entity, "id_suffix") if entity else ("", "")

        # Star-schema suffix in any casing. We try to peel the suffix off
        # whether the column is CamelCase (MemberDim), snake_case (member_dim),
        # or SCREAMING_SNAKE (MEMBER_DIM / CLAIM_FACT).
        for suf in ENTITY_REF_SUFFIXES:
            suf_l = suf.lower()
            if not lower.endswith(suf_l):
                continue
            if len(lower) <= len(suf_l):
                continue
            # Reject if the suffix is glued onto a non-boundary word (e.g. 'random' ends in 'm'
            # but not a real suffix). We require either a separator or a casing boundary
            # in the original token immediately before the suffix start.
            cut = len(base) - len(suf_l)
            boundary_ok = (
                "_" in base
                or base[cut - 1].islower() and base[cut].isupper()
                or base[cut - 1].isupper() and base[cut].isupper()
            )
            if not boundary_ok and cut > 0 and base[cut - 1] == base[cut]:
                continue
            stripped_raw = base[:cut].rstrip("_")
            if not stripped_raw:
                continue
            return (self._normalize_mixed_token(stripped_raw), "dw_suffix")

        # CamelCase noun column (no spaces, no underscores, starts capital, length > 2).
        if (
            "_" not in base
            and " " not in base
            and len(base) > 2
            and base[0].isupper()
            and base.isalpha()
            and not self._looks_like_attribute(base)
        ):
            return (self._normalize_camel_token(base), "camel_entity")

        return ("", "")

    def _relationship_name_for_reference(self, col: str, kind: str) -> str:
        """Pick a readable verb for the relationship based on the column kind."""
        if kind == "id_suffix":
            # Strip whichever id-marker is present without assuming length=3.
            base = col
            lower = col.lower()
            if lower.endswith("_id"):
                base = col[:-3]
            elif col.endswith("Id") or col.endswith("ID") or col.endswith("iD"):
                base = col[:-2]
            base = base.rstrip("_")
            slug = self._snake_case_camel(base).replace(" ", "_").strip("_") or base.lower()
            return f"references_{slug}"
        if kind == "related_prefix":
            slug = col.lower()
            return f"has_{slug}"
        if kind == "prefix_group":
            # col here is the prefix itself, not a real column.
            return f"has_{col.lower()}"
        # Normalize any casing/separator into clean snake_case.
        if "_" in col:
            slug = col.lower().strip("_")
        else:
            slug = self._snake_case_camel(col)
        slug = slug.replace(" ", "_").replace("__", "_")
        return f"has_{slug}"

    def _snake_case_camel(self, token: str) -> str:
        """
        Convert CamelCase to snake_case, keeping consecutive uppercase runs
        together: 'HRASurvey' → 'hra_survey', 'ICDMapping' → 'icd_mapping',
        'MemberDim' → 'member_dim'.
        """
        if not token:
            return ""
        # Boundary 1: an uppercase letter preceded by a lowercase letter or digit ("aB" / "9B").
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", token)
        # Boundary 2: end of an uppercase run followed by an uppercase + lowercase ("ABc"  → "A_Bc"),
        # which splits 'HRASurvey' into 'HRA_Survey' but leaves 'ICD' alone.
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
        return s.lower().replace("__", "_")

    def _extract_prefix_groups(self, unique_keys: List[str]) -> List[Tuple[str, List[str]]]:
        """
        Group columns by their first snake_case token. Returns prefix groups
        worth treating as entities (i.e. blocklist-filtered and large enough).

        Heuristic: prefix length ≥ 3 needs ≥ 2 columns; prefix length 2 needs ≥ 3
        columns (so noisy 2-char tokens don't generate spurious entities).
        """
        groups: Dict[str, List[str]] = {}
        for k in unique_keys:
            if "_" not in k:
                continue
            prefix = k.split("_", 1)[0]
            if not prefix or not prefix.replace("-", "").isalnum():
                continue
            prefix_lower = prefix.lower()
            if prefix_lower in PREFIX_BLOCKLIST:
                continue
            if prefix_lower in ATTRIBUTE_LIKE_LABELS:
                continue
            groups.setdefault(prefix_lower, []).append(k)

        out: List[Tuple[str, List[str]]] = []
        for prefix, cols in groups.items():
            if len(prefix) >= 3 and len(cols) >= 2:
                out.append((prefix, cols))
            elif len(prefix) == 2 and len(cols) >= 3:
                out.append((prefix, cols))
        return out

    def _prefix_to_entity_name(self, prefix: str) -> str:
        """Convert a snake_case prefix into a human-friendly entity name."""
        p = prefix.strip().lower()
        if not p:
            return ""
        if p in SHORT_ACRONYM_PREFIXES:
            return p.upper()
        if len(p) <= 3 and p.isalpha():
            return p.upper()
        return p[:1].upper() + p[1:]

    def _normalize_mixed_token(self, token: str) -> str:
        """
        Turn a token coming from any casing convention into a friendly title
        with acronyms preserved.

        Examples:
          'MemberDim'        → 'Member'
          'MEMBER_DIM'       → 'Member'
          'member_dim'       → 'Member'
          'icd_mapping'      → 'ICD Mapping'   (short tokens stay upper)
          'social_engagement'→ 'Social Engagement'
        """
        if not token:
            return ""
        if "_" in token:
            parts = [p for p in token.split("_") if p]
            words: List[str] = []
            for p in parts:
                if len(p) <= 4 and p.isupper():
                    words.append(p)
                elif p.isupper():
                    words.append(p.capitalize())
                else:
                    words.append(self._normalize_camel_token(p))
            return " ".join(words)
        if token.isupper() and len(token) > 4:
            return token.capitalize()
        return self._normalize_camel_token(token)

    def _normalize_camel_token(self, token: str) -> str:
        """
        Turn a CamelCase identifier into a human-friendly display string while
        preserving consecutive uppercase acronyms.

        Examples:
          'MemberCare'  → 'Member Care'
          'ICDMapping'  → 'ICD Mapping'
          'HRASurvey'   → 'HRA Survey'
        """
        if not token:
            return ""
        spaced = self._snake_case_camel(token).replace("_", " ")
        # Re-capitalize each word; keep acronym uppercase if the original word was all-caps.
        words = []
        for w in spaced.split():
            # Find original casing by re-walking token? Simpler: if the snake step kept it
            # together (e.g. 'icd', 'hra'), restore upper-case for short tokens of <=4 chars
            # that map back to a fully-uppercase slice of the original.
            if len(w) <= 4 and w.upper() in token:
                words.append(w.upper())
            else:
                words.append(w.capitalize())
        return " ".join(words) or token

    def _parse_kv_pipe_row(self, text: str) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []
        for segment in re.split(r"\s*\|\s*", text):
            segment = segment.strip()
            if ":" not in segment:
                continue
            key, _, rest = segment.partition(":")
            key, rest = key.strip(), rest.strip()
            if key:
                pairs.append((key, rest))
        return pairs

    def _infer_root_entity_from_keys(self, keys: List[str]) -> str:
        kl = [k.lower() for k in keys]
        priority = [
            ("claim", "Claim"),
            ("incident", "Incident"),
            ("ticket", "Ticket"),
            ("change", "Change"),
            ("problem", "Problem"),
            ("request", "Request"),
            ("member", "Member"),
            ("patient", "Patient"),
            ("provider", "Provider"),
            ("prescription", "Prescription"),
            ("order", "Order"),
            ("invoice", "Invoice"),
            ("policy", "Policy"),
            ("customer", "Customer"),
            ("user", "User"),
        ]

        # Strongest signal: the FIRST column is almost always the row grain.
        # Recognize three flavors:
        #   1. A *Dim / *Fact / *Lookup / *Bridge / *Mapping column
        #      (MemberDim, MEMBER_DIM, member_dim) → root = Member
        #   2. A *_id or *Id column (member_id, memberId, MEMBER_ID) → root = Member
        #   3. Otherwise fall through to the heuristics below.
        def _matches_priority(name: str) -> Optional[str]:
            lname = name.lower()
            for hint, label in priority:
                if hint in lname:
                    return label
            return None

        if keys:
            first = keys[0]
            first_lower = first.lower().replace("-", "_")
            for suf in ENTITY_REF_SUFFIXES:
                suf_l = suf.lower()
                if first_lower.endswith(suf_l) and len(first_lower) > len(suf_l):
                    stripped = first[: len(first) - len(suf_l)].rstrip("_")
                    if stripped:
                        derived = self._normalize_mixed_token(stripped) or stripped
                        return _matches_priority(derived) or derived
            # *_id / *ID / *_number / *_no — first column is row primary key.
            for marker in ("_id", "_number", "_no", "_uid", "_pk"):
                if first_lower.endswith(marker) and len(first_lower) > len(marker):
                    derived = self._column_base_entity_name(first[: len(first) - len(marker)])
                    if derived:
                        return _matches_priority(derived) or derived
            # *Id / *Number (camelCase)
            for marker_re in (r"^([a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)*)Id$",
                              r"^([a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)*)Number$"):
                camel_match = re.match(marker_re, first)
                if camel_match:
                    derived = self._column_base_entity_name(camel_match.group(1))
                    if derived:
                        return _matches_priority(derived) or derived

        for hint, label in priority:
            if any(k.endswith("_id") and hint in k for k in kl):
                return label

        for hint, label in priority:
            for k in keys:
                lower = k.lower()
                if hint in lower and any(lower.endswith(suf.lower()) for suf in ENTITY_REF_SUFFIXES):
                    return label

        for k in keys:
            lk = k.lower()
            if lk.endswith("_id"):
                guessed = self._column_base_entity_name(k)
                if guessed:
                    return guessed

        for k in keys:
            lower = k.lower()
            for suf in ENTITY_REF_SUFFIXES:
                suf_l = suf.lower()
                if lower.endswith(suf_l) and len(lower) > len(suf_l):
                    stripped = k[: len(k) - len(suf_l)].rstrip("_")
                    if stripped:
                        return self._normalize_mixed_token(stripped) or stripped

        return "Record"

    def _column_base_entity_name(self, col: str) -> str:
        base = col.strip()
        if base.lower().endswith("_id"):
            base = base[:-3]
        base = base.replace("-", "_")
        parts = [p for p in base.split("_") if p]
        if not parts:
            return ""
        return "".join(p.title() for p in parts)

    def _extract_noun_phrases(self, text: str) -> List[str]:
        # Simple: capitalized words and short title-case phrases
        seen = set()
        result: List[str] = []
        # Words that look like nouns (Capitalized, not at sentence start - simplified: take all Cap phrases)
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
            phrase = m.group(1).strip()
            if phrase not in seen and 2 <= len(phrase) <= 60:
                seen.add(phrase)
                result.append(phrase)
        return result[:80]  # cap

    def _extract_verb_phrases(self, text: str) -> List[str]:
        # Simple verb patterns: "has a", "belongs to", "contains", "references"
        patterns = [
            r"\b(has\s+(?:a\s+)?\w+)",
            r"\b(belongs\s+to)\b",
            r"\b(contains?)\b",
            r"\b(references?)\b",
            r"\b(associated\s+with)\b",
            r"\b(related\s+to)\b",
            r"\b(identifies?)\b",
            r"\b(links?\s+to)\b",
            r"\b(consists\s+of)\b",
        ]
        seen = set()
        result: List[str] = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.I):
                phrase = m.group(1).strip()
                if phrase not in seen:
                    seen.add(phrase)
                    result.append(phrase)
        return result[:30]

    def _extract_labels(self, text: str) -> List[str]:
        # Labels: "Label:" or "Label -" or table header tokens
        seen = set()
        result: List[str] = []
        for m in re.finditer(r"(?:^|\n)\s*([A-Za-z][A-Za-z0-9_\s]{0,40}?)\s*[:\-]\s*", text):
            label = m.group(1).strip()
            if label and label not in seen:
                seen.add(label)
                result.append(label)
        return result

    def _looks_like_attribute(self, label: str) -> bool:
        lower = label.lower().replace(" ", "_")
        return any(kw in lower for kw in ["_id", "_name", "_date", "_code", "_type", "_status", "_amount"])

    def _normalize_name(self, name: str) -> str:
        s = re.sub(r"[^\w\s]", " ", name)
        s = re.sub(r"\s+", " ", s).strip()
        return s.title() if s else name

    def _snippet(self, text: str, phrase: str, window: int = 80) -> str:
        idx = text.find(phrase)
        if idx < 0:
            return phrase[:window]
        start = max(0, idx - 20)
        end = min(len(text), idx + len(phrase) + 60)
        return text[start:end]
