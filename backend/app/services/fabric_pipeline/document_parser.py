"""Layout-aware document parsing (Release 2.0, Phase 1).

A PDF is read page by page into ordered blocks — headings (by font size and
weight), paragraphs, and tables — each carrying its real page number. Pages
with no text layer are OCR'd; if OCR is not available the page is reported as
unreadable instead of being silently dropped. Repeated page headers/footers are
removed.

Limits (stated in the manifest when they apply): multi-column pages are read
in the order pdfplumber emits lines; figures are not interpreted.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

_BULLET_RE = re.compile(r"^\s*(?:[•●▪◦‣\-–*]|\(?\d{1,2}[.)]|\(?[a-zA-Z][.)])\s+")
_NUMBERED_HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+[A-Z]")
_PAGE_NUMBER_RE = re.compile(r"^(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?$", re.I)


class DocumentParseError(RuntimeError):
    """A document produced no usable content."""


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ocr_available() -> Tuple[bool, str]:
    """Whether OCR can run here, and why not when it cannot."""
    if not settings.PDF_OCR_ENABLED:
        return False, "OCR is turned off (PDF_OCR_ENABLED=false)"
    try:
        import pytesseract  # noqa: F401
    except Exception:
        return False, "pytesseract is not installed"
    if not shutil.which("tesseract"):
        return False, "the tesseract program is not installed"
    return True, ""


def _table_markdown(rows: List[List[Optional[str]]]) -> str:
    clean = [
        [re.sub(r"\s+", " ", (cell or "")).strip().replace("|", "\\|") for cell in row]
        for row in rows
    ]
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]
    lines = ["| " + " | ".join(clean[0]) + " |", "| " + " | ".join("---" for _ in range(width)) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in clean[1:]]
    return "\n".join(lines)


def _usable_table(rows: List[List[Optional[str]]]) -> bool:
    if not rows or len(rows) < 2:
        return False
    width = max(len(r) for r in rows)
    if width < 2:
        return False
    cells = [c for r in rows for c in r]
    filled = sum(1 for c in cells if c and str(c).strip())
    return filled >= max(4, len(cells) * 0.4)


def _line_features(line: Dict[str, Any]) -> Dict[str, Any]:
    chars = [c for c in line.get("chars") or [] if str(c.get("text", "")).strip()]
    sizes = [round(float(c.get("size") or 0), 1) for c in chars]
    size = Counter(sizes).most_common(1)[0][0] if sizes else 0.0
    bold = bool(chars) and sum(
        1 for c in chars if re.search(r"bold|black|heavy|semibold", str(c.get("fontname", "")), re.I)
    ) >= 0.8 * len(chars)
    return {
        "text": re.sub(r"\s+", " ", line.get("text") or "").strip(),
        "size": size,
        "bold": bold,
        "top": float(line.get("top") or 0),
        "bottom": float(line.get("bottom") or 0),
        "x0": float(line.get("x0") or 0),
    }


def _in_bbox(line: Dict[str, Any], bbox: Tuple[float, float, float, float]) -> bool:
    mid = (line["top"] + line["bottom"]) / 2
    return bbox[1] - 1 <= mid <= bbox[3] + 1 and line["x0"] >= bbox[0] - 2


def _is_heading(line: Dict[str, Any], body_size: float) -> bool:
    text = line["text"]
    if not text or len(text) > 140 or _BULLET_RE.match(text):
        return False
    words = text.split()
    if len(words) > 16 or not re.search(r"[A-Za-z]", text):
        return False
    bigger = body_size > 0 and line["size"] >= body_size * 1.12
    ends_like_sentence = text.endswith((".", ",", ";")) and not _NUMBERED_HEADING_RE.match(text)
    if bigger and not ends_like_sentence:
        return True
    if line["bold"] and not ends_like_sentence and len(words) <= 12:
        return True
    if _NUMBERED_HEADING_RE.match(text) and len(words) <= 10 and not ends_like_sentence and (line["bold"] or bigger):
        return True
    return False


def _paragraphs_from_lines(lines: List[Dict[str, Any]]) -> List[str]:
    """Join text lines into paragraphs using vertical gaps and bullets."""
    if not lines:
        return []
    heights = [l["bottom"] - l["top"] for l in lines if l["bottom"] > l["top"]]
    line_height = sorted(heights)[len(heights) // 2] if heights else 12.0
    paragraphs: List[str] = []
    current = ""
    prev: Optional[Dict[str, Any]] = None
    for line in lines:
        text = line["text"]
        if not text:
            continue
        new_para = prev is None
        if prev is not None:
            gap = line["top"] - prev["bottom"]
            if gap > line_height * 0.75 or _BULLET_RE.match(text):
                new_para = True
        if new_para:
            if current:
                paragraphs.append(current)
            current = text
        elif current.endswith("-") and text[:1].islower():
            current = current[:-1] + text
        else:
            current += " " + text
        prev = line
    if current:
        paragraphs.append(current)
    return paragraphs


def _ocr_page(page: Any) -> str:
    import pytesseract

    image = page.to_image(resolution=settings.PDF_OCR_RESOLUTION).original
    return pytesseract.image_to_string(image) or ""


def _repeated_margin_lines(pages_lines: List[List[Dict[str, Any]]], heights: List[float]) -> set:
    """Text that repeats in the top/bottom margin of most pages (headers, footers)."""
    if len(pages_lines) < 3:
        return set()
    counts: Counter = Counter()
    for lines, height in zip(pages_lines, heights):
        seen = set()
        for line in lines:
            if line["top"] < height * 0.08 or line["bottom"] > height * 0.92:
                key = re.sub(r"\d+", "#", line["text"]).strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    counts[key] += 1
    need = max(3, int(len(pages_lines) * 0.5))
    return {key for key, n in counts.items() if n >= need}


def parse_pdf(path: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Parse a PDF into ordered blocks with page numbers.

    Returns ``{file_name, file_type, page_count, blocks, pages, warnings, stats}``.
    Each block: ``{type: heading|paragraph|table, text, page, level?, ocr}``.
    """
    import pdfplumber

    name = display_name or os.path.basename(path)
    warnings: List[str] = []
    can_ocr, ocr_reason = ocr_available()

    raw_pages: List[Dict[str, Any]] = []
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:
        raise DocumentParseError(f"'{name}' could not be opened as a PDF: {exc}") from exc

    with pdf:
        for number, page in enumerate(pdf.pages, start=1):
            entry: Dict[str, Any] = {
                "page": number, "height": float(page.height or 0), "lines": [], "tables": [],
                "ocr": False, "ocr_text": "", "unreadable": False,
            }
            try:
                tables = []
                for table in page.find_tables():
                    rows = table.extract()
                    if _usable_table(rows):
                        tables.append({"bbox": tuple(table.bbox), "rows": rows})
                entry["tables"] = tables
                lines = [
                    _line_features(l)
                    for l in page.extract_text_lines(layout=False, strip=True, return_chars=True)
                ]
                entry["lines"] = [l for l in lines if l["text"]]
            except Exception as exc:
                warnings.append(f"Page {number}: layout extraction failed ({exc}); used plain text.")
                text = ""
                try:
                    text = page.extract_text() or ""
                except Exception:
                    pass
                entry["lines"] = [
                    {"text": t.strip(), "size": 0.0, "bold": False, "top": float(i * 14), "bottom": float(i * 14 + 12), "x0": 0.0}
                    for i, t in enumerate(text.splitlines()) if t.strip()
                ]

            text_chars = sum(len(l["text"]) for l in entry["lines"])
            if text_chars < settings.PDF_OCR_MIN_TEXT_CHARS and not entry["tables"]:
                if can_ocr:
                    try:
                        ocr_text = _ocr_page(page)
                    except Exception as exc:
                        ocr_text = ""
                        warnings.append(f"Page {number}: OCR failed ({exc}).")
                    if len(ocr_text.strip()) >= max(1, text_chars):
                        entry["ocr"] = True
                        entry["ocr_text"] = ocr_text
                        entry["lines"] = []
                if not entry["ocr"] and text_chars == 0:
                    entry["unreadable"] = True
            raw_pages.append(entry)

    page_count = len(raw_pages)
    if page_count == 0:
        raise DocumentParseError(f"'{name}' has no pages")

    size_weights: Counter = Counter()
    for entry in raw_pages:
        for line in entry["lines"]:
            if line["size"]:
                size_weights[line["size"]] += len(line["text"])
    body_size = size_weights.most_common(1)[0][0] if size_weights else 0.0
    heading_sizes = sorted(
        {l["size"] for e in raw_pages for l in e["lines"] if body_size and l["size"] >= body_size * 1.12},
        reverse=True,
    )

    def _level(line: Dict[str, Any]) -> int:
        """Bigger type is a higher level; among equal sizes "1.2" sits below "1"."""
        if line["size"] in heading_sizes:
            rank = heading_sizes.index(line["size"]) + 1
        else:
            rank = len(heading_sizes) + 1  # bold line at body size
        numbered = _NUMBERED_HEADING_RE.match(line["text"])
        depth = numbered.group(1).count(".") if numbered else 0
        return rank + depth

    repeated = _repeated_margin_lines(
        [e["lines"] for e in raw_pages], [e["height"] or 792.0 for e in raw_pages]
    )

    blocks: List[Dict[str, Any]] = []
    pages_meta: List[Dict[str, Any]] = []
    for entry in raw_pages:
        number = entry["page"]
        page_blocks: List[Tuple[float, Dict[str, Any]]] = []
        if entry["ocr"]:
            for i, para in enumerate(re.split(r"\n\s*\n", entry["ocr_text"])):
                text = re.sub(r"\s+", " ", para).strip()
                if len(text) >= 2:
                    page_blocks.append((float(i), {"type": "paragraph", "text": text, "page": number, "ocr": True}))
        else:
            height = entry["height"] or 792.0
            for table in entry["tables"]:
                page_blocks.append((
                    table["bbox"][1],
                    {"type": "table", "text": _table_markdown(table["rows"]), "page": number, "ocr": False,
                     "rows": len(table["rows"]), "columns": max(len(r) for r in table["rows"])},
                ))
            run: List[Dict[str, Any]] = []

            def _flush() -> None:
                if not run:
                    return
                top = run[0]["top"]
                for offset, para in enumerate(_paragraphs_from_lines(run)):
                    page_blocks.append((top + offset * 0.001, {"type": "paragraph", "text": para, "page": number, "ocr": False}))
                run.clear()

            for line in entry["lines"]:
                if any(_in_bbox(line, t["bbox"]) for t in entry["tables"]):
                    continue
                in_margin = line["top"] < height * 0.08 or line["bottom"] > height * 0.92
                if in_margin and (
                    re.sub(r"\d+", "#", line["text"]).strip().lower() in repeated
                    or _PAGE_NUMBER_RE.match(line["text"])
                ):
                    continue
                if _is_heading(line, body_size):
                    _flush()
                    page_blocks.append((
                        line["top"],
                        {"type": "heading", "text": line["text"], "page": number, "level": _level(line), "ocr": False},
                    ))
                else:
                    # A table found between two lines ends the paragraph run.
                    if run and any(run[-1]["bottom"] <= t["bbox"][1] <= line["top"] for t in entry["tables"]):
                        _flush()
                    run.append(line)
            _flush()
        page_blocks.sort(key=lambda item: item[0])
        blocks.extend(b for _, b in page_blocks)
        pages_meta.append({
            "page": number,
            "blocks": len(page_blocks),
            "chars": sum(len(b["text"]) for _, b in page_blocks),
            "tables": sum(1 for _, b in page_blocks if b["type"] == "table"),
            "ocr": entry["ocr"],
            "unreadable": entry["unreadable"],
        })

    unreadable = [p["page"] for p in pages_meta if p["unreadable"]]
    ocr_pages = [p["page"] for p in pages_meta if p["ocr"]]
    if unreadable:
        reason = "" if can_ocr else f" ({ocr_reason})"
        warnings.append(
            f"'{name}': {len(unreadable)} of {page_count} page(s) have no readable text{reason}: "
            f"pages {_page_list(unreadable)}."
        )
    if not any(b["text"].strip() for b in blocks):
        reason = "" if can_ocr else f" OCR was not run: {ocr_reason}."
        raise DocumentParseError(
            f"'{name}' has no extractable text on any of its {page_count} page(s).{reason}"
        )

    return {
        "file_name": name,
        "file_type": "pdf",
        "page_count": page_count,
        "blocks": blocks,
        "pages": pages_meta,
        "warnings": warnings,
        "stats": {
            "pages": page_count,
            "pages_ocr": len(ocr_pages),
            "pages_unreadable": len(unreadable),
            "headings": sum(1 for b in blocks if b["type"] == "heading"),
            "paragraphs": sum(1 for b in blocks if b["type"] == "paragraph"),
            "tables": sum(1 for b in blocks if b["type"] == "table"),
            "chars": sum(len(b["text"]) for b in blocks),
            "body_font_size": body_size,
        },
    }


def _page_list(pages: List[int], limit: int = 12) -> str:
    shown = ", ".join(str(p) for p in pages[:limit])
    return shown + (f" and {len(pages) - limit} more" if len(pages) > limit else "")


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_text_file(path: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Parse a plain-text / Markdown file into headings and paragraphs (no pages)."""
    name = display_name or os.path.basename(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    warnings: List[str] = []
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        warnings.append(f"'{name}' is not UTF-8; read as Latin-1.")
    blocks: List[Dict[str, Any]] = []
    for para in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [l.rstrip() for l in para.split("\n") if l.strip()]
        if not lines:
            continue
        buffer: List[str] = []

        def _flush() -> None:
            if buffer:
                blocks.append({"type": "paragraph", "text": " ".join(s.strip() for s in buffer), "page": None, "ocr": False})
                buffer.clear()

        for index, line in enumerate(lines):
            md = _MD_HEADING_RE.match(line)
            stripped = line.strip()
            short_caps = (
                len(lines) == 1 and len(stripped) <= 80 and stripped.upper() == stripped
                and re.search(r"[A-Z]{3,}", stripped) and not stripped.endswith(".")
            )
            underline = index + 1 < len(lines) and re.fullmatch(r"\s*(={3,}|-{3,})\s*", lines[index + 1])
            if re.fullmatch(r"\s*(={3,}|-{3,})\s*", line):
                continue
            if md:
                _flush()
                blocks.append({"type": "heading", "text": md.group(2), "page": None, "level": len(md.group(1)), "ocr": False})
            elif short_caps or underline:
                _flush()
                blocks.append({"type": "heading", "text": stripped, "page": None, "level": 1 if underline and "=" in lines[index + 1] else 2, "ocr": False})
            else:
                buffer.append(line)
        _flush()
    if not any(b["text"].strip() for b in blocks):
        raise DocumentParseError(f"'{name}' is empty")
    return {
        "file_name": name,
        "file_type": "txt",
        "page_count": 0,
        "blocks": blocks,
        "pages": [],
        "warnings": warnings,
        "stats": {
            "pages": 0, "pages_ocr": 0, "pages_unreadable": 0,
            "headings": sum(1 for b in blocks if b["type"] == "heading"),
            "paragraphs": sum(1 for b in blocks if b["type"] == "paragraph"),
            "tables": 0,
            "chars": sum(len(b["text"]) for b in blocks),
        },
    }


def parse_document(path: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    ext = os.path.splitext(display_name or path)[1].lower() or os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(path, display_name)
    if ext in (".txt", ".md", ".markdown"):
        return parse_text_file(path, display_name)
    raise DocumentParseError(f"'{display_name or os.path.basename(path)}': unsupported file type '{ext}'")
