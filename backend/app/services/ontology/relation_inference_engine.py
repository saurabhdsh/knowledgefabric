"""Infer relationships between entities from text and structure.

A relationship is kept only when the text names both ends. Nothing is attached
to a default entity, and a relationship the text does not support is left out
and counted in ``last_dropped`` so the run log can say how many were refused.
"""
import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.models.ontology import OntologyEvidence, ExtractionSourceType
from app.services.ontology.text_match import (
    entity_names,
    find_mentions,
    mentions,
    name_pattern,
    quote_in_text,
    resolve_name,
    sentence_around,
)

# Confidence is assigned from the kind of evidence, not reported by a model.
QUOTED_SENTENCE_CONFIDENCE = 0.75   # subject, verb and object all in one quoted sentence
SENTENCE_ORDER_CONFIDENCE = 0.5     # verb pattern with a named entity on each side
_PASSIVE_BY = re.compile(r"^\s+by\b", re.I)
_HAS_OBJECT = re.compile(r"^(has|have)\s+(?:an?\s+)?\w+$", re.I)


class RelationInferenceEngine:
    """Bind source -> relationship -> target from sentences that name both ends."""

    def __init__(self) -> None:
        self.last_dropped: List[Dict[str, Any]] = []

    def infer_relationships(
        self,
        entities: List[Dict[str, Any]],
        relationship_candidates: List[Dict[str, Any]],
        text_chunks: List[Dict[str, Any]],
        evidence_factory: Optional[Callable[..., OntologyEvidence]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Produce list of {source_class_id, relationship_name, target_class_id, confidence, evidence}.

        Two kinds of candidate are accepted:
        - a triple (subject, predicate, object, quote): kept when the quote is
          in the source text and names both the subject and the object;
        - a verb phrase with a text snippet: kept when the sentence around the
          verb names one entity before it and a different one after it.
        Everything else is dropped.
        """
        self.last_dropped = []
        names = entity_names(entities)
        corpus = " ".join(str(c.get("content") or "") for c in (text_chunks or []))
        best: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        triples = [c for c in relationship_candidates if c.get("subject") and c.get("object")]
        phrases = [c for c in relationship_candidates if not (c.get("subject") and c.get("object"))]
        for cand in triples + phrases[:40]:
            if cand.get("subject") and cand.get("object"):
                one, reason = self._bind_triple(cand, names, corpus)
                bound_list = [one] if one else []
            else:
                bound_list, reason = self._bind_by_sentence_order(cand, names)
            if not bound_list:
                self.last_dropped.append({
                    "relationship_name": cand.get("normalized_name") or cand.get("name") or "",
                    "reason": reason,
                })
                continue
            for bound in bound_list:
                key = (bound["source_class_id"], bound["relationship_name"].lower(), bound["target_class_id"])
                if key not in best or bound["confidence"] > best[key]["confidence"]:
                    best[key] = bound
        return list(best.values())

    def _bind_triple(
        self, cand: Dict[str, Any], names: Dict[str, str], corpus: str
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        subject = str(cand.get("subject") or "").strip()
        obj = str(cand.get("object") or "").strip()
        quote = str(cand.get("quote") or cand.get("evidence_snippet") or "").strip()
        name = str(cand.get("predicate") or cand.get("normalized_name") or cand.get("name") or "").strip()
        if not name:
            return None, "no verb"
        if not quote:
            return None, "no quoted sentence"
        if corpus.strip():
            if not quote_in_text(quote, corpus):
                return None, "quoted sentence is not in the source text"
        elif not cand.get("quote_verified"):
            return None, "quoted sentence could not be checked against the source text"
        if not (mentions(subject, quote) and mentions(obj, quote)):
            return None, "quoted sentence does not name both ends"
        source_id = resolve_name(subject, names)
        target_id = resolve_name(obj, names)
        if not source_id or not target_id:
            return None, "subject or object is not a discovered entity"
        if source_id == target_id:
            return None, "subject and object are the same entity"
        return {
            "id": cand.get("id") or f"rel_inf_{uuid.uuid4().hex[:8]}",
            "source_class_id": source_id,
            "relationship_name": name,
            "target_class_id": target_id,
            "definition": cand.get("definition"),
            "evidence_snippet": quote[:300],
            "evidence": {"basis": "quoted_sentence", "detail": quote[:300]},
            "confidence": QUOTED_SENTENCE_CONFIDENCE,
            "extraction_source": ExtractionSourceType.LLM,
            "artifact_type": cand.get("artifact_type") or "document",
            "artifact_id": cand.get("artifact_id") or "",
        }, ""

    def _bind_by_sentence_order(
        self, cand: Dict[str, Any], names: Dict[str, str]
    ) -> Tuple[List[Dict[str, Any]], str]:
        name = str(cand.get("normalized_name") or cand.get("name") or "").strip()
        snippets = [cand.get("evidence_snippet") or ""] + list(cand.get("evidence_snippets") or [])
        if not name:
            return [], "no verb"
        bound: List[Dict[str, Any]] = []
        verb_text = str(cand.get("name") or name)
        verb = name_pattern(verb_text.split()[0]) if verb_text.split() else None
        phrase = re.compile(
            r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(w) for w in verb_text.split()) + r"(?![A-Za-z0-9])",
            re.I,
        )
        for snippet in snippets:
            snippet = str(snippet or "")
            if not snippet.strip():
                continue
            match = phrase.search(snippet) or (verb.search(snippet) if verb else None)
            if not match:
                continue
            sentence, offset = sentence_around(snippet, match.start(), match.end())
            verb_start = match.start() - offset
            head_end = verb_start + len(verb_text.split()[0])
            found = find_mentions(sentence, names)
            before = [m for m in found if m[1] <= verb_start]
            after = [m for m in found if m[0] >= head_end]
            if not before or not after:
                continue
            subject, obj = before[-1], after[0]
            if subject[2] == obj[2]:
                continue
            source_id, target_id = subject[2], obj[2]
            if _PASSIVE_BY.match(sentence[match.end() - offset:]):
                source_id, target_id = target_id, source_id
            rel_name = re.sub(r"^(is|are)\s+", "", verb_text.strip(), flags=re.I).lower()
            if _HAS_OBJECT.match(verb_text):
                rel_name = verb_text.split()[0].lower()
            bound.append({
                "id": f"rel_inf_{uuid.uuid4().hex[:8]}",
                "source_class_id": source_id,
                "relationship_name": rel_name,
                "target_class_id": target_id,
                "definition": None,
                "evidence_snippet": sentence.strip()[:300],
                "evidence": {"basis": "sentence_order", "detail": sentence.strip()[:300]},
                "confidence": min(float(cand.get("confidence", SENTENCE_ORDER_CONFIDENCE)), SENTENCE_ORDER_CONFIDENCE),
                "extraction_source": ExtractionSourceType.RULE_BASED,
                "artifact_type": cand.get("artifact_type") or "document",
                "artifact_id": cand.get("artifact_id") or "",
            })
        return bound, ("" if bound else "no sentence names an entity on each side of the verb")

    def bind_tabular_relationship_candidates(
        self,
        entities: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Resolve FK-style tabular relationships using inferred entity display names."""
        by_display: Dict[str, str] = {}
        for e in entities:
            for key in (
                (e.get("normalized_name") or "").strip(),
                (e.get("name") or "").strip(),
            ):
                if key:
                    by_display[key.lower()] = e.get("id")

        result: List[Dict[str, Any]] = []
        for r in candidates:
            if not r.get("tabular_binding"):
                continue
            sn = (r.get("source_entity_normalized") or "").strip()
            tn = (r.get("target_entity_normalized") or "").strip()
            sid = by_display.get(sn.lower())
            tid = by_display.get(tn.lower())
            if not sid or not tid or sid == tid:
                continue
            nm = r.get("relationship_name") or r.get("name") or "references"
            evidence = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
            snippet = r.get("evidence_snippet") or evidence.get("detail") or ""
            card = r.get("cardinality_if_detected") or r.get("cardinality")
            src_cols = [str(c) for c in (r.get("source_columns") or []) if c]
            tgt_cols = [str(c) for c in (r.get("target_columns") or []) if c]
            result.append({
                "id": r.get("id") or f"rel_tab_{uuid.uuid4().hex[:8]}",
                "source_class_id": sid,
                "relationship_name": nm,
                "target_class_id": tid,
                "definition": None,
                "evidence_snippet": str(snippet)[:500],
                "evidence": evidence or None,
                "confidence": float(r.get("confidence", 0.8)),
                "extraction_source": ExtractionSourceType.COMBINED,
                "cardinality_if_detected": card,
                "source_columns": src_cols,
                "target_columns": tgt_cols,
                "tabular_binding": {
                    "source_entity": sn,
                    "target_entity": tn,
                    "source_columns": src_cols,
                    "target_columns": tgt_cols,
                    "overlap": evidence.get("overlap") if evidence else r.get("overlap"),
                    "basis": evidence.get("basis") if evidence else "tabular_fk",
                },
                "artifact_type": "profile",
                "artifact_id": f"profile:{sn}->{tn}",
            })
        return result
