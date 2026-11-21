"""Tiny PDF writer for tests: real text (standard fonts), ruled tables, pages.

Produces PDFs with a genuine text layer and vector ruling lines, so layout
parsing is exercised the same way as with a PDF exported from a word processor.
"""
from __future__ import annotations

from typing import List, Sequence

PAGE_W, PAGE_H = 612, 792
MARGIN = 72


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class PdfBuilder:
    def __init__(self) -> None:
        self._pages: List[List[str]] = [[]]
        self._y = PAGE_H - MARGIN

    @property
    def _ops(self) -> List[str]:
        return self._pages[-1]

    def new_page(self) -> "PdfBuilder":
        self._pages.append([])
        self._y = PAGE_H - MARGIN
        return self

    def _text(self, x: float, y: float, text: str, size: float, bold: bool) -> None:
        font = "F2" if bold else "F1"
        self._ops.append(f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({_esc(text)}) Tj ET")

    def _need(self, height: float) -> None:
        if self._y - height < MARGIN:
            self.new_page()

    def heading(self, text: str, size: float = 18, bold: bool = True) -> "PdfBuilder":
        self._need(size * 2.2)
        self._y -= size * 1.6
        self._text(MARGIN, self._y, text, size, bold)
        self._y -= size * 0.6
        return self

    def paragraph(self, text: str, size: float = 11, width_chars: int = 88) -> "PdfBuilder":
        words, lines, current = text.split(), [], ""
        for word in words:
            if current and len(current) + 1 + len(word) > width_chars:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
        leading = size * 1.25
        self._y -= size * 0.9  # paragraph gap
        for line in lines:
            self._need(leading)
            self._y -= leading
            self._text(MARGIN, self._y, line, size, False)
        return self

    def table(self, rows: Sequence[Sequence[str]], col_width: float = 110, row_height: float = 20, size: float = 10) -> "PdfBuilder":
        height = row_height * len(rows)
        self._need(height + 20)
        self._y -= 14
        top = self._y
        cols = max(len(r) for r in rows)
        left = MARGIN
        right = left + col_width * cols
        self._ops.append("0.7 w")
        for r in range(len(rows) + 1):
            y = top - r * row_height
            self._ops.append(f"{left:.1f} {y:.1f} m {right:.1f} {y:.1f} l S")
        for c in range(cols + 1):
            x = left + c * col_width
            self._ops.append(f"{x:.1f} {top:.1f} m {x:.1f} {top - height:.1f} l S")
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                self._text(left + c * col_width + 4, top - (r + 1) * row_height + 6, str(cell), size, r == 0)
        self._y = top - height - 6
        return self

    def footer_all(self, text: str) -> "PdfBuilder":
        """Same footer line (plus page number) on every page."""
        for index, ops in enumerate(self._pages, start=1):
            ops.append(f"BT /F1 8 Tf {MARGIN} 30 Td ({_esc(text)} - Page {index}) Tj ET")
        return self

    def build(self) -> bytes:
        objects: List[bytes] = []

        def add(body: str) -> int:
            objects.append(body.encode("latin-1"))
            return len(objects)

        add("<< /Type /Catalog /Pages 2 0 R >>")
        add("")  # pages placeholder (object 2)
        add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        kids: List[int] = []
        for ops in self._pages:
            stream = "\n".join(ops)
            content = add(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
            page = add(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content} 0 R >>"
            )
            kids.append(page)
        objects[1] = (
            f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
        ).encode("latin-1")

        out = bytearray(b"%PDF-1.4\n")
        offsets: List[int] = []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for offset in offsets:
            out += f"{offset:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)


def scanned_pdf(path: str, lines: Sequence[str]) -> bool:
    """Write an image-only PDF (no text layer). Returns False if Pillow cannot render sized text."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=44)
    except TypeError:
        return False
    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)
    y = 160
    for line in lines:
        draw.text((140, y), line, fill="black", font=font)
        y += 90
    image.save(path, "PDF", resolution=200.0)
    return True
