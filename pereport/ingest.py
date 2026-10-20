"""PDF parsing with PyMuPDF: page numbers and table rows are preserved.

Table cells are written one row per line, separated by two spaces, so the chunker's table
detector (two or more numbers per line) keeps rows whole. Pages with almost no text but with
images are listed in `ocr_pages`; OCR is not run automatically (see docs/assumptions.md).
"""

from bisect import bisect_left
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


def _last_cell(cells: list[str]) -> str:
    return next((c for c in reversed(cells) if c), "")


def merge_continuations(grid: list[list[str]]) -> list[list[str]]:
    """Fold wrapped table lines back into the row they belong to.

    A line with an empty first cell always continues the row above. In sentence-style tables (most
    rows end with a full stop) a line also continues the row above when that row has not ended its
    sentence yet (repairs wrapped labels such as "Alternate / Investment Vehicles"). This is the
    fallback; `group_by_rules` is used instead when the table has ruled row separators.
    """
    filled = [r for r in grid if any(r)]
    sentence_style = bool(filled) and (
        sum(_last_cell(r).endswith((".", "!", "?")) for r in filled) * 100 >= len(filled) * 35
    )
    out: list[list[str]] = []
    for cells in grid:
        prev_open = bool(out) and not _last_cell(out[-1]).endswith((".", "!", "?"))
        header_row = len(out) == 1  # the header line ("Term  Summary") never ends in a stop
        if (
            out
            and any(cells)
            and (not cells[0] or (sentence_style and prev_open and not header_row))
        ):
            prev = out[-1]
            for i, c in enumerate(cells):
                if c:
                    prev[i] = f"{prev[i]} {c}".strip()
        else:
            out.append(list(cells))
    return out


def group_by_rules(
    grid: list[list[str]], centres: list[float], rules: list[float]
) -> list[list[str]]:
    """Merge the physical lines that sit between the same pair of horizontal rules into one row."""
    out: list[list[str]] = []
    last_bucket: int | None = None
    for cells, y in zip(grid, centres, strict=True):
        bucket = bisect_left(rules, y)
        if out and bucket == last_bucket:
            for i, c in enumerate(cells):
                if c:
                    out[-1][i] = f"{out[-1][i]} {c}".strip()
        else:
            out.append(list(cells))
        last_bucket = bucket
    return out


def _row_rules(page: pymupdf.Page, bbox: pymupdf.Rect) -> list[float]:
    """Y positions of thin horizontal rectangles (ruled row separators) inside the table's width."""
    ys = {
        round((d["rect"].y0 + d["rect"].y1) / 2, 1)
        for d in page.get_drawings()
        if d["rect"].height < 2.5
        and d["rect"].width > 20
        and bbox.x0 - 5 <= d["rect"].x0 <= bbox.x1
        and bbox.y0 <= d["rect"].y0 <= bbox.y1
    }
    return sorted(ys)


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
        grid = []
        for row in t.rows:
            # Text is read from each cell's own box: Table.extract() drops the spaces in some PDFs.
            grid.append(
                [
                    " ".join(page.get_text("text", clip=pymupdf.Rect(c)).split()) if c else ""
                    for c in row.cells
                ]
            )
        rules = _row_rules(page, r)
        if len(rules) >= 2:
            centres = [(row.bbox[1] + row.bbox[3]) / 2 for row in t.rows]
            rows_ = group_by_rules(grid, centres, rules)
        else:
            rows_ = merge_continuations(grid)
        lines = ["  ".join(c for c in cells if c) for cells in rows_ if any(cells)]
        if lines:
            items.append((r.y0, r.x0, "\n".join(lines)))
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
