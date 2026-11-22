"""Whole-word matching used to tie ontology elements to the text that states them.

Nothing here guesses. A name counts as mentioned only when it appears as a
whole word (singular or plural), and a quote counts as found only when the
same words appear in the source in the same order.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

_SENTENCE_BREAK = re.compile(r"[.!?;\n]")
_QUOTE_CHARS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ",
})


def singular(word: str) -> str:
    """Naive English singular: claims -> claim, policies -> policy, addresses -> address."""
    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("sses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def canonical_key(name: str) -> str:
    """Case, spacing and plural-insensitive key for comparing names."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", str(name or "")) if w]
    return " ".join(singular(w) for w in words)


def normalize_text(text: str) -> str:
    """Lower-case, straighten quotes and dashes, collapse whitespace."""
    cleaned = str(text or "").translate(_QUOTE_CHARS).lower()
    return re.sub(r"\s+", " ", cleaned).strip()


def quote_in_text(quote: str, text: str, *, min_words: int = 3) -> bool:
    """True when ``quote`` appears word for word in ``text``.

    Whitespace, case, and surrounding punctuation are ignored. Very short
    quotes are refused because two or three words can match by accident.
    """
    q = normalize_text(quote).strip(" .,:;!?\"'()[]")
    if len(q.split()) < min_words:
        return False
    return q in normalize_text(text)


def name_pattern(name: str) -> Optional[re.Pattern]:
    """Regex that matches ``name`` as whole words, singular or plural."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", str(name or "").lower()) if w]
    if not words:
        return None
    parts: List[str] = []
    for i, word in enumerate(words):
        base = singular(word) if i == len(words) - 1 else word
        if i == len(words) - 1:
            if base.endswith("y") and len(base) > 2:
                parts.append(re.escape(base[:-1]) + r"(?:y|ies)")
            else:
                parts.append(re.escape(base) + r"(?:s|es)?")
        else:
            parts.append(re.escape(base))
    body = r"[\s_\-]+".join(parts)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.I)


def find_mentions(text: str, names_to_ids: Dict[str, str]) -> List[Tuple[int, int, str]]:
    """Whole-word mentions of the given names in ``text``.

    Returns ``(start, end, id)`` in reading order. When two names overlap
    ("Care Plan" and "Plan"), the longer one wins.
    """
    hits: List[Tuple[int, int, str]] = []
    for name, ident in names_to_ids.items():
        pattern = name_pattern(name)
        if pattern is None:
            continue
        for m in pattern.finditer(text or ""):
            hits.append((m.start(), m.end(), ident))
    hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
    chosen: List[Tuple[int, int, str]] = []
    for hit in hits:
        if any(hit[0] < c[1] and c[0] < hit[1] for c in chosen):
            continue
        chosen.append(hit)
    chosen.sort(key=lambda h: h[0])
    return chosen


def mentions(name: str, text: str) -> bool:
    pattern = name_pattern(name)
    return bool(pattern and pattern.search(text or ""))


def sentence_around(text: str, start: int, end: int) -> Tuple[str, int]:
    """The sentence containing ``text[start:end]`` and the offset where it begins."""
    left = 0
    for m in _SENTENCE_BREAK.finditer(text, 0, start):
        left = m.end()
    right_match = _SENTENCE_BREAK.search(text, end)
    right = right_match.start() if right_match else len(text)
    return text[left:right], left


def entity_names(entities: Iterable[dict]) -> Dict[str, str]:
    """name -> id for every name and alias an entity is known by."""
    out: Dict[str, str] = {}
    for e in entities:
        ident = e.get("id")
        if not ident:
            continue
        for raw in [e.get("normalized_name"), e.get("name"), *(e.get("aliases") or [])]:
            name = str(raw or "").strip()
            if name and name.lower() not in out:
                out[name.lower()] = ident
    return out


def resolve_name(name: str, names_to_ids: Dict[str, str]) -> Optional[str]:
    """Id of the entity called ``name`` (plural and case-insensitive), or None."""
    wanted = canonical_key(name)
    if not wanted:
        return None
    for known, ident in names_to_ids.items():
        if canonical_key(known) == wanted:
            return ident
    return None
