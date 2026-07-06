"""Chunk text for LLM consumption with overlap and boundary awareness."""
import re
from typing import Any, Dict, List, Optional


class SemanticChunker:
    """Split text into semantic chunks (paragraph/sentence boundary aware)."""

    def __init__(self, max_chunk_size: int = 2000, overlap: int = 200):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Return list of {content, index, start_char, end_char}."""
        if not text or not text.strip():
            return []
        chunks: List[Dict[str, Any]] = []
        # Prefer paragraph split first
        paragraphs = re.split(r"\n\s*\n", text)
        current: List[str] = []
        current_size = 0
        start_char = 0
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            size = len(p) + 2
            if current_size + size > self.max_chunk_size and current:
                content = "\n\n".join(current)
                chunks.append({
                    "content": content,
                    "index": len(chunks),
                    "start_char": start_char,
                    "end_char": start_char + len(content),
                })
                # Overlap: keep last paragraph in next chunk
                overlap_text = current[-1] if current else ""
                start_char = start_char + len(content) - len(overlap_text)
                current = [overlap_text] if overlap_text else []
                current_size = len(overlap_text)
            current.append(p)
            current_size += size
        if current:
            content = "\n\n".join(current)
            chunks.append({
                "content": content,
                "index": len(chunks),
                "start_char": start_char,
                "end_char": start_char + len(content),
            })
        return chunks

    def chunk_sections(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunk a list of {heading, content, page_number} into LLM-sized blocks."""
        result: List[Dict[str, Any]] = []
        for sec in sections:
            content = f"{sec.get('heading', '')}\n\n{sec.get('content', '')}"
            sub_chunks = self.chunk_text(content)
            for c in sub_chunks:
                c["page_number"] = sec.get("page_number")
                c["heading"] = sec.get("heading", "")
                result.append(c)
        return result
