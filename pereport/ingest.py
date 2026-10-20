"""PDF parsing with PyMuPDF: page numbers and table rows are preserved.

Table cells are written one row per line, separated by two spaces, so the chunker's table
detector (two or more numbers per line) keeps rows whole. Pages with almost no text but with
images are listed in `ocr_pages`; OCR is not run automatically (see docs/assumptions.md).
"""

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from pereport.chunker import Page

MIN_TEXT_CHARS = 20


@dataclass(frozen=True)
class ParsedDoc:
    pages: list[Page]
    ocr_pages: list[int] = field(default_factory=list)


def _inside(cx: float, cy: float, rect: pymupdf.Rect) -> bool:
    return bool(rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1)


def parse_page(page: pymupdf.Page) -> str:
    items: list[tuple[float, float, str]] = []
    tables = page.find_tables().tables
    rects = [pymupdf.Rect(t.bbox) for t in tables]
    for x0, y0, x1, y1, text, _no, kind in page.get_text("blocks"):
        if kind != 0:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(_inside(cx, cy, r) for r in rects):
            continue
        items.append((y0, x0, text.strip()))
    for t, r in zip(tables, rects, strict=True):
        rows = []
        for row in t.extract():
            cells = [" ".join((c or "").split()) for c in row]
            line = "  ".join(c for c in cells if c)
            if line:
                rows.append(line)
        if rows:
            items.append((r.y0, r.x0, "\n".join(rows)))
    items.sort(key=lambda it: (round(it[0]), it[1]))
    return "\n\n".join(text for _, _, text in items if text)


def parse_pdf(path: str | Path) -> ParsedDoc:
    pages: list[Page] = []
    ocr: list[int] = []
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf, start=1):
            text = parse_page(page)
            if len(text.strip()) < MIN_TEXT_CHARS and page.get_images():
                ocr.append(i)
            pages.append(Page(i, text))
    return ParsedDoc(pages, ocr)
