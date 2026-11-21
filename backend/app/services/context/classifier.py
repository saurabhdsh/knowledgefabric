"""Decide where a correction belongs before it is saved.

Ambiguous corrections stay fabric memory, which is the path the queue already
had. A session phrase stays on the session. A later episode that negates the
same statement discards it. An alias or a rule is proposed onto the ontology
draft and does not change answers until that version is approved.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

_SESSION = re.compile(
    r"\b(this session|this conversation|only for now|just this chat|only this chat)\b",
    re.I,
)
_ALIAS = re.compile(
    r"^[\"'“”]?(.+?)[\"'“”]?\s+(?:means|is short for|stands for|refers to)\s+[\"'“”]?(.+?)[\"'“”]?\.?$",
    re.I,
)
_RULE = re.compile(r"\b(when|if|must|should|always|whenever|within\s+\d+)\b", re.I)
_NEGATION = re.compile(r"\b(not|no longer|ignore|incorrect|do not|don't|never)\b", re.I)
_TOKEN = re.compile(r"[a-z0-9]{3,}")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "when", "should",
    "must", "always", "means", "not", "longer", "ignore", "incorrect",
}


def _norm(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _tokens(text: str) -> set:
    return {tok for tok in _TOKEN.findall((text or "").lower()) if tok not in _STOP}


def contradicts(later: str, earlier: str) -> bool:
    """A later statement drops an earlier one when it negates a shared subject."""
    if not later or not earlier or not _NEGATION.search(later):
        return False
    shared = _tokens(later) & _tokens(earlier)
    return len(shared) >= 2


def _class_tokens(name: str) -> List[str]:
    raw = re.sub(r"([a-z])([A-Z])", r"\1 \2", name or "")
    raw = raw.replace("_", " ")
    return [tok for tok in _tokens(raw) if len(tok) >= 4]


def _match_name(text: str, names: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    hay = _norm(text)
    best = None
    best_len = 0
    for item in names:
        name = str(item.get("name") or "")
        tokens = _class_tokens(name) or ([_norm(name)] if len(_norm(name)) >= 4 else [])
        for token in tokens:
            if token and token in hay and len(token) > best_len:
                best = item
                best_len = len(token)
    return best


def classify_correction(
    text: str,
    *,
    classes: Optional[Sequence[Dict[str, Any]]] = None,
    attributes: Optional[Sequence[Dict[str, Any]]] = None,
    columns: Optional[Sequence[str]] = None,
    later_texts: Optional[Sequence[str]] = None,
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Return destination, reason, and the ontology target when one was found."""
    statement = (text or "").strip()
    classes = list(classes or [])
    attributes = list(attributes or [])
    columns = list(columns or [])
    forced = (scope or "").strip().lower()
    if forced in {"memory", "ontology_alias", "ontology_constraint", "session", "discard"}:
        return {
            "destination": forced,
            "reason": "Scope was set on the correction.",
            "alias": None,
            "attribute_name": None,
            "related_entity": None,
        }

    if not statement:
        return {
            "destination": "memory",
            "reason": "No correction text; the answer was marked incorrect, so it stays a memory candidate.",
            "alias": None,
            "attribute_name": None,
            "related_entity": None,
        }

    if _SESSION.search(statement):
        return {
            "destination": "session",
            "reason": "The correction is limited to this conversation.",
            "alias": None,
            "attribute_name": None,
            "related_entity": None,
        }

    for later in later_texts or []:
        if contradicts(later, statement):
            return {
                "destination": "discard",
                "reason": "A later episode contradicts this correction.",
                "alias": None,
                "attribute_name": None,
                "related_entity": None,
            }

    alias_match = _ALIAS.match(statement)
    if alias_match:
        left, right = alias_match.group(1).strip(), alias_match.group(2).strip()
        attribute = _match_name(right, attributes) or _match_name(left, attributes)
        if attribute:
            alias = left if _norm(left) != _norm(str(attribute.get("name") or "")) else right
            return {
                "destination": "ontology_alias",
                "reason": f"'{alias}' is a name for the attribute {attribute.get('name')}.",
                "alias": alias,
                "attribute_name": attribute.get("name"),
                "related_entity": attribute.get("class_name"),
            }

    if _RULE.search(statement):
        matched = _match_name(statement, classes)
        if matched:
            return {
                "destination": "ontology_constraint",
                "reason": f"The correction states a rule over {matched.get('name')}.",
                "alias": None,
                "attribute_name": None,
                "related_entity": matched.get("name"),
            }

    if _match_name(statement, [{"name": col} for col in columns]):
        return {
            "destination": "memory",
            "reason": "The correction names a value in a table column, so it overrides answers until the source changes.",
            "alias": None,
            "attribute_name": None,
            "related_entity": None,
        }

    return {
        "destination": "memory",
        "reason": "The correction does not name an ontology alias or rule, so it stays fabric memory.",
        "alias": None,
        "attribute_name": None,
        "related_entity": None,
    }
