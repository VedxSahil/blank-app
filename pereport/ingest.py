"""PDF parsing with PyMuPDF: page numbers and table rows are preserved.

Table cells are written one row per line, separated by two spaces, which is how the chunker
recognises a table and keeps one chunk per row. Pages with almost no text but with
images are listed in `ocr_pages`; OCR is not run automatically (see docs/assumptions.md).
"""

import re
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
import pymupdf

from pereport.chunker import STRUCTURE_HEADER, Page

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


# ---------------------------------------------------------------------------------------------
# Spreadsheets (.xlsx): each sheet becomes one "page", so a citation [doc, p.4] means sheet 4.
# ---------------------------------------------------------------------------------------------

_TOP_HEADING = re.compile(r"^[A-Z]\.\d*\s+\S")
CALCULATED = "(calculated row)"


def _cell_text(v: object) -> str:
    s = " ".join(str(v).split())
    return CALCULATED if s == "(=)" else s


def _is_value(v: object) -> bool:
    return isinstance(v, int | float | datetime | date) and not isinstance(v, bool)


def _grouped_table(rows: list[list[tuple[int, object]]]) -> tuple[int, list[int]] | None:
    """Detect a header row followed by many multi-column rows whose first column is mostly blank.

    Returns (index of the header row, columns of the header) for sheets like a definitions table
    (Section | Field | Definition) where "Section" is filled only when it changes.
    """
    for i, row in enumerate(rows):
        cols = [c for c, v in row if isinstance(v, str)]
        if len(cols) < 3:
            continue
        body = [r for r in rows[i + 1 :] if any(isinstance(v, str) for _, v in r)]
        if len(body) < 10:
            return None
        has_all_but_first = sum(1 for r in body if all(c in {c for c, v in r} for c in cols[1:]))
        first_filled = sum(1 for r in body if cols[0] in {c for c, v in r})
        if has_all_but_first >= 0.9 * len(body) and first_filled <= 0.4 * len(body):
            return i, cols
        return None
    return None


def _sheet_lines(ws: Any, include_numbers: bool) -> list[str]:
    rows: list[list[tuple[int, object]]] = []
    bold: dict[int, bool] = {}
    for r in ws.iter_rows():
        cells = [(c.column, c.value) for c in r if c.value not in (None, "")]
        rows.append(cells)
        for c in r:
            if isinstance(c.value, str) and c.column <= 3:
                bold.setdefault(c.row, bool(c.font and c.font.bold))
    lines: list[str] = [f"# {ws.title}"]
    grouped = _grouped_table(rows)
    if grouped is not None:
        head_i, cols = grouped
        header = "  ".join(_cell_text(v) for c, v in rows[head_i] if c in cols[1:])
        for row in rows[head_i + 1 :]:
            by_col = {c: _cell_text(v) for c, v in row if isinstance(v, str)}
            if not by_col:
                continue
            if cols[0] in by_col:
                lines += ["", f"# {by_col[cols[0]]}", header]
            lines.append("  ".join(by_col[c] for c in cols[1:] if c in by_col))
        return lines

    top = sub = ""
    need_header = False

    def context() -> str:
        return " > ".join(x for x in (top, sub) if x) or ws.title

    for n, row in enumerate(rows, start=1):
        raw = [_cell_text(v) for _, v in row if isinstance(v, str)]
        texts = [t for t in raw if t != CALCULATED]
        calculated = len(texts) != len(raw)
        has_value = any(_is_value(v) for _, v in row)
        if not texts:
            continue  # empty row, or a bare "(=)" formula marker
        if _TOP_HEADING.match(texts[0]):
            top, sub = texts[0], ""
            lines += ["", f"# {top}"]
            need_header = len(texts) == 1  # header is written lazily, only if line items follow
            if len(texts) > 1:
                lines += [STRUCTURE_HEADER, "Column groups  " + " / ".join(texts[1:])]
            continue
        if len(texts) >= 2:
            lines.append("  ".join(texts))
            continue
        t = texts[0]
        words = len(t.split())
        if words >= 12 or t.endswith("."):
            lines += ["", t, ""]
        elif not has_value and not calculated and bold.get(n, False):
            sub, need_header = t, True
            lines += ["", f"# {context()}"]
        else:
            if need_header:
                lines.append(STRUCTURE_HEADER)
                need_header = False
            lines.append(f"{t}  {context()}" + (f" {CALCULATED}" if calculated else ""))
        if include_numbers and has_value:
            lines[-1] += "  " + " ".join(str(v) for _, v in row if _is_value(v))
    return lines


def parse_xlsx(path: str | Path, include_numbers: bool = False) -> ParsedDoc:
    """Parse a workbook into one page per sheet (page number = sheet position, from 1).

    Only text cells are indexed. Numeric and date cells are dropped unless `include_numbers`, so a
    template's example figures cannot later be quoted as if they were real fund data. Headings are
    rows with no values (or lettered like "A.1 ..."), line items become one table row each carrying
    their heading path, and a header-plus-body table with a sparse first column (a definitions
    table) gets that column forward-filled into headings.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    pages = [
        Page(i, "\n".join(_sheet_lines(ws, include_numbers)) if ws.sheet_state == "visible" else "")
        for i, ws in enumerate(wb.worksheets, start=1)
    ]
    return ParsedDoc(pages)
