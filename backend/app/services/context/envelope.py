"""One context envelope per agent turn.

The envelope is the packet the agent was allowed to use. Each line has a kind,
the text that was shown, a source id, and a confidence. Ontology and memory
text rendered from the lines matches the strings the query path already injects,
so the prompt stays the same when the source text is in the canonical form.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

KINDS = ("ontology", "table", "passage", "graph", "session", "memory")
_ONTOLOGY_PREFIX = "Domain ontology (approved):"
_MEMORY_HEADER = "APPROVED FABRIC MEMORY (these corrections override earlier answers):"
_SESSION_HEADER = "RECENT CONVERSATION (short-term session memory):"


def _line(kind: str, text: str, source_id: Optional[str], confidence: Optional[float]) -> Dict[str, Any]:
    return {
        "kind": kind,
        "text": text,
        "source_id": source_id,
        "confidence": confidence,
    }


def _parse_ontology(ontology_context: str, ontology_version_id: Optional[str]) -> List[Dict[str, Any]]:
    text = ontology_context or ""
    if not text.strip():
        return []
    lines: List[Dict[str, Any]] = []
    in_facts = False
    for raw in text.splitlines():
        if raw.startswith(_ONTOLOGY_PREFIX):
            in_facts = False
            summary = raw[len(_ONTOLOGY_PREFIX):].strip()
            lines.append(_line("ontology", summary, ontology_version_id or "approved", None))
        elif raw.strip() == "Graph facts:":
            in_facts = True
        elif raw.startswith("Linked entity:"):
            in_facts = False
            lines.append(_line("graph", raw.strip(), None, None))
        elif in_facts and raw.startswith("- "):
            lines.append(_line("graph", raw[2:].strip(), None, None))
        elif raw.strip():
            in_facts = False
            lines.append(_line("ontology", raw.strip(), ontology_version_id or "approved", None))
    return lines


def _render_ontology_lines(lines: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    facts: List[str] = []
    linked: List[str] = []
    for line in lines:
        kind = line.get("kind")
        text = str(line.get("text") or "")
        if kind == "ontology":
            parts.append(f"{_ONTOLOGY_PREFIX} {text}".rstrip())
        elif kind == "graph" and text.startswith("Linked entity:"):
            linked.append(text)
        elif kind == "graph":
            facts.append(text)
    if facts:
        parts.append("Graph facts:")
        parts.extend(f"- {fact}" for fact in facts)
    parts.extend(linked)
    return "\n".join(parts)


def _parse_memory(memory_context: str) -> List[Dict[str, Any]]:
    text = memory_context or ""
    if not text.strip():
        return []
    lines: List[Dict[str, Any]] = []
    section = ""
    for raw in text.splitlines():
        if raw.startswith(_MEMORY_HEADER):
            section = "memory"
            continue
        if raw.startswith(_SESSION_HEADER):
            section = "session"
            continue
        if section == "memory" and raw.startswith("- "):
            lines.append(_line("memory", raw[2:].strip(), "fabric_memory", 1.0))
        elif section == "session" and (raw.startswith("User: ") or raw.startswith("Assistant: ")):
            lines.append(_line("session", raw.strip(), "session", None))
        elif raw.strip() and section == "memory":
            lines.append(_line("memory", raw.strip(), "fabric_memory", 1.0))
        elif raw.strip() and section == "session":
            lines.append(_line("session", raw.strip(), "session", None))
    if not lines and text.strip():
        lines.append(_line("memory", text.strip(), "fabric_memory", 1.0))
    return lines


def _render_memory_lines(lines: List[Dict[str, Any]]) -> str:
    memory = [str(line.get("text") or "") for line in lines if line.get("kind") == "memory"]
    session = [str(line.get("text") or "") for line in lines if line.get("kind") == "session"]
    parts: List[str] = []
    if memory:
        parts.append("\n".join([_MEMORY_HEADER, *[f"- {fact}" for fact in memory]]))
    if session:
        parts.append("\n".join([_SESSION_HEADER, *session]))
    return "\n\n".join(parts)


def begin_envelope(
    memory_context: str = "",
    ontology_context: str = "",
    ontology_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse the two existing context strings into envelope lines."""
    ontology_lines = _parse_ontology(ontology_context, ontology_version_id)
    memory_lines = _parse_memory(memory_context)
    rendered_ontology = _render_ontology_lines(ontology_lines)
    rendered_memory = _render_memory_lines(memory_lines)
    envelope: Dict[str, Any] = {
        "version": 1,
        "route": None,
        "ontology_version_id": ontology_version_id,
        "confidence": None,
        "confidence_basis": None,
        "measurement": None,
        "lines": ontology_lines + memory_lines,
    }
    # Keep the original string only when a round-trip would change the prompt.
    if (ontology_context or "") and rendered_ontology != ontology_context:
        envelope["prompt_ontology"] = ontology_context
    if (memory_context or "") and rendered_memory != memory_context:
        envelope["prompt_memory"] = memory_context
    return envelope


def render_ontology(envelope: Dict[str, Any]) -> str:
    if envelope.get("prompt_ontology"):
        return str(envelope["prompt_ontology"])
    return _render_ontology_lines(envelope.get("lines") or [])


def render_memory(envelope: Dict[str, Any]) -> str:
    if envelope.get("prompt_memory"):
        return str(envelope["prompt_memory"])
    return _render_memory_lines(envelope.get("lines") or [])


def finish_envelope(
    envelope: Dict[str, Any],
    *,
    route: Optional[str] = None,
    confidence: Optional[float] = None,
    confidence_basis: Optional[str] = None,
    measurement: Optional[Dict[str, Any]] = None,
    sql: Optional[str] = None,
    table_text: str = "",
    entities: Optional[List[Dict[str, Any]]] = None,
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Copy the envelope and attach the evidence lines used for this answer."""
    lines = [dict(line) for line in (envelope.get("lines") or [])]
    if table_text:
        lines.append(_line("table", table_text, (sql or route or "table")[:500], 1.0 if route in {"sql", "rules"} else confidence))
    for entity in entities or []:
        table = entity.get("table") or ""
        column = entity.get("column") or ""
        value = entity.get("value")
        lines.append(_line("table", f"{table}.{column} = {value}", f"{table}.{column}", 1.0))
    for chunk in chunks or []:
        meta = chunk.get("metadata") or {}
        score = chunk.get("rerank_score")
        if score is None:
            score = chunk.get("similarity_score")
        confidence_value = float(score) if isinstance(score, (int, float)) else None
        source = str(chunk.get("id") or meta.get("chunk_id") or "")
        lines.append(_line("passage", str(chunk.get("content") or "")[:4000], source or None, confidence_value))
    finished = dict(envelope)
    finished["route"] = route
    finished["confidence"] = confidence
    finished["confidence_basis"] = confidence_basis
    finished["measurement"] = measurement
    finished["lines"] = lines
    return finished
