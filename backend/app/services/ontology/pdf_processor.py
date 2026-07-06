"""PDF text extraction with section/heading/table candidate detection."""
import re
from typing import Any, Dict, List, Optional, Tuple

import PyPDF2

from app.models.ontology import OntologyEvidence, SourceArtifact


class PDFProcessor:
    """Extract text and structure from PDFs for ontology extraction."""

    # Common section header patterns (domain-agnostic)
    SECTION_PATTERNS = [
        re.compile(r"^\d+\.\s+.+$"),  # 1. Section
        re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*$"),  # Title Case line
        re.compile(r"^[A-Z][^.]{2,60}$"),  # All caps or title, no period
        re.compile(r"^(?:Chapter|Section|Part|Appendix)\s+.+", re.I),
        re.compile(r"^#{1,3}\s+.+$"),  # Markdown-style
    ]

    def process(self, artifact: SourceArtifact) -> Tuple[str, List[Dict[str, Any]], List[OntologyEvidence]]:
        """
        Process a PDF artifact. Returns:
        - full_text
        - sections: list of {heading, content, page_number}
        - evidence_list for traceability
        """
        full_text_parts: List[str] = []
        sections: List[Dict[str, Any]] = []
        evidence_list: List[OntologyEvidence] = []

        try:
            with open(artifact.file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text() or ""
                    if not text.strip():
                        continue
                    full_text_parts.append(text)
                    # Section detection: split by likely headers
                    page_sections = self._detect_sections(text, page_num)
                    for sec in page_sections:
                        sections.append(sec)
                        evidence_list.append(
                            OntologyEvidence(
                                id=f"evt_{artifact.id}_{page_num}_{len(evidence_list)}",
                                artifact_id=artifact.id,
                                artifact_type="pdf",
                                page_number=page_num,
                                text_snippet=sec.get("content", "")[:500],
                                extraction_stage="pdf_processor",
                            )
                        )
        except Exception as e:
            full_text_parts.append(f"[PDF read error: {e}]")

        full_text = "\n\n".join(full_text_parts)
        return full_text, sections, evidence_list

    def _detect_sections(self, page_text: str, page_number: int) -> List[Dict[str, Any]]:
        """Split page text into heading + content blocks."""
        lines = page_text.split("\n")
        sections: List[Dict[str, Any]] = []
        current_heading: Optional[str] = None
        current_content: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_content:
                    sections.append({
                        "heading": current_heading or "Body",
                        "content": "\n".join(current_content),
                        "page_number": page_number,
                    })
                    current_content = []
                continue
            if self._looks_like_heading(stripped) and len(stripped) < 120:
                if current_content or current_heading:
                    sections.append({
                        "heading": current_heading or "Body",
                        "content": "\n".join(current_content),
                        "page_number": page_number,
                    })
                current_heading = stripped
                current_content = []
            else:
                current_content.append(stripped)

        if current_content or current_heading:
            sections.append({
                "heading": current_heading or "Body",
                "content": "\n".join(current_content),
                "page_number": page_number,
            })
        return sections

    def _looks_like_heading(self, line: str) -> bool:
        for pat in self.SECTION_PATTERNS:
            if pat.match(line):
                return True
        return False

    def extract_table_candidates(self, text: str) -> List[Dict[str, Any]]:
        """Heuristic: lines that look like table headers (short, pipe/space aligned)."""
        candidates: List[Dict[str, Any]] = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            # Header-like: multiple short tokens, possibly separated
            tokens = [t.strip() for t in re.split(r"\s{2,}|\t|\|", line) if t.strip()]
            if 2 <= len(tokens) <= 15 and all(len(t) < 40 for t in tokens):
                candidates.append({
                    "row_index": i,
                    "tokens": tokens,
                    "raw": line[:200],
                })
        return candidates
