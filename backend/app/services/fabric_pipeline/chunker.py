"""Structure-aware chunking (Release 2.0, Phase 1).

Chunks follow the document: they never cross a heading, never cut a sentence,
keep a table together (splitting only between rows, repeating the header), and
carry the section path and real page range. Each chunk starts with a one-line
context header (document > section) so it stands on its own when retrieved.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.config import settings

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(\[]?[A-Z0-9])")
_ABBREVIATION_RE = re.compile(r"\b(?:e\.g|i\.e|etc|vs|Dr|Mr|Mrs|Ms|No|Fig|Sec|Inc|Ltd|Co|approx)\.$", re.I)
OVERLAP_MAX_CHARS = 220


def split_sentences(text: str) -> List[str]:
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    sentences: List[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if sentences and _ABBREVIATION_RE.search(sentences[-1]):
            sentences[-1] += " " + part
        else:
            sentences.append(part)
    return sentences


def _hard_split(text: str, max_chars: int) -> List[str]:
    out: List[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > max_chars:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
        while len(current) > max_chars:
            out.append(current[:max_chars])
            current = current[max_chars:]
    if current:
        out.append(current)
    return out


def _units(paragraph: str, max_chars: int) -> List[str]:
    """A paragraph as pieces no longer than ``max_chars``, cut at sentence ends."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    units: List[str] = []
    for sentence in split_sentences(paragraph):
        units.extend([sentence] if len(sentence) <= max_chars else _hard_split(sentence, max_chars))
    return units


def _split_table(markdown: str, max_chars: int) -> List[str]:
    lines = markdown.split("\n")
    if len(markdown) <= max_chars or len(lines) <= 3:
        return [markdown]
    header, rows = lines[:2], lines[2:]
    head_len = sum(len(l) + 1 for l in header)
    parts: List[str] = []
    current: List[str] = []
    size = head_len
    for row in rows:
        if current and size + len(row) + 1 > max_chars:
            parts.append("\n".join(header + current))
            current, size = [], head_len
        current.append(row)
        size += len(row) + 1
    if current:
        parts.append("\n".join(header + current))
    return parts


def chunk_document(parsed: Dict[str, Any], max_chars: Optional[int] = None) -> List[Dict[str, Any]]:
    """Turn parsed blocks into chunks with section path and page range.

    Each chunk: ``{content, body, section_path, page_start, page_end,
    block_type: text|table, ocr, file_name, chunk_index}``.
    """
    limit = int(max_chars or settings.FABRIC_CHUNK_MAX_CHARS)
    title = parsed["file_name"]
    chunks: List[Dict[str, Any]] = []
    headings: List[Dict[str, Any]] = []  # stack of {level, text}

    def _section_path() -> str:
        return " > ".join(h["text"] for h in headings)

    def _emit(body: str, block_type: str, pages: List[Optional[int]], ocr: bool, section: str) -> None:
        body = body.strip()
        if not body:
            return
        header = title if not section else f"{title} > {section}"
        real_pages = [p for p in pages if p]
        chunks.append({
            "content": f"[{header}]\n{body}",
            "body": body,
            "section_path": section,
            "page_start": min(real_pages) if real_pages else None,
            "page_end": max(real_pages) if real_pages else None,
            "block_type": block_type,
            "ocr": ocr,
            "file_name": title,
            "chunk_index": len(chunks),
        })

    buffer: List[str] = []
    buffer_pages: List[Optional[int]] = []
    buffer_ocr = False
    buffer_section = ""

    def _flush(carry_overlap: bool = False) -> None:
        nonlocal buffer, buffer_pages, buffer_ocr
        if not buffer:
            return
        _emit(" ".join(buffer), "text", buffer_pages, buffer_ocr, buffer_section)
        last = buffer[-1]
        if carry_overlap and len(last) <= OVERLAP_MAX_CHARS and len(buffer) > 1:
            buffer, buffer_pages = [last], buffer_pages[-1:]
        else:
            buffer, buffer_pages, buffer_ocr = [], [], False

    for block in parsed["blocks"]:
        kind = block["type"]
        if kind == "heading":
            _flush()
            level = int(block.get("level") or 1)
            while headings and headings[-1]["level"] >= level:
                headings.pop()
            headings.append({"level": level, "text": block["text"].strip()})
            continue
        section = _section_path()
        if kind == "table":
            _flush()
            for part in _split_table(block["text"], limit * 2):
                _emit(part, "table", [block.get("page")], bool(block.get("ocr")), section)
            continue
        if buffer and section != buffer_section:
            _flush()
        buffer_section = section
        header_len = len(title) + len(section) + 6
        budget = max(200, limit - header_len)
        for unit in _units(block["text"].strip(), budget):
            current_len = sum(len(u) + 1 for u in buffer)
            if buffer and current_len + len(unit) > budget:
                _flush(carry_overlap=True)
                # Overlap must not push the next chunk over budget.
                if buffer and len(buffer[0]) + len(unit) + 1 > budget:
                    buffer, buffer_pages = [], []
            buffer.append(unit)
            buffer_pages.append(block.get("page"))
            buffer_ocr = buffer_ocr or bool(block.get("ocr"))
    _flush()

    # A heading with no body under it would otherwise vanish; keep its text findable.
    if not chunks and headings:
        _emit(" / ".join(h["text"] for h in headings), "text", [None], False, "")
    return chunks


def chunk_to_vector_document(chunk: Dict[str, Any], fabric_name: str, stored_name: str = "") -> Dict[str, Any]:
    """Vector-store document for one chunk (metadata values must be scalars)."""
    metadata: Dict[str, Any] = {
        "chunk_type": "document",
        "pipeline_version": 2,
        "block_type": chunk["block_type"],
        "chunk_index": chunk["chunk_index"],
        "ocr": bool(chunk["ocr"]),
    }
    if chunk["section_path"]:
        metadata["section_path"] = chunk["section_path"][:500]
    if chunk["page_start"]:
        metadata["page_start"] = int(chunk["page_start"])
        metadata["page_end"] = int(chunk["page_end"] or chunk["page_start"])
    if stored_name:
        metadata["stored_name"] = stored_name
    doc: Dict[str, Any] = {
        "content": chunk["content"],
        "file_name": chunk["file_name"],
        "source_name": fabric_name,
        "metadata": metadata,
    }
    if chunk["page_start"]:
        doc["page_number"] = int(chunk["page_start"])
    return doc


def citation(metadata: Dict[str, Any], file_name: str = "") -> str:
    """Human-readable source reference for a retrieved chunk."""
    parts: List[str] = []
    name = file_name or metadata.get("file_name") or ""
    if name:
        parts.append(str(name))
    start, end = metadata.get("page_start"), metadata.get("page_end")
    if start:
        parts.append(f"p. {start}" if not end or end == start else f"pp. {start}-{end}")
    if metadata.get("section_path"):
        parts.append(str(metadata["section_path"]))
    if metadata.get("block_type") == "table":
        parts.append("table")
    if metadata.get("ocr"):
        parts.append("OCR")
    return ", ".join(parts)
