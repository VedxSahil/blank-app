"""Ingest tests on a PDF generated here from TEST FIXTURE text (not a real document)."""

from pathlib import Path

import pymupdf

from pereport.chunker import chunk_pages
from pereport.ingest import parse_pdf
from pereport.store import load_chunks, save_chunks


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 80), "1. FEES", fontsize=14)
    p1.insert_text((72, 110), "The management fee is 2 percent of committed capital.", fontsize=10)
    p2 = doc.new_page()
    p2.insert_text((72, 80), "2. TABLE", fontsize=14)
    # a ruled 2x3 table so find_tables can see it
    x = [72, 172, 272, 372]
    y = [120, 150, 180]
    for yy in y:
        p2.draw_line((x[0], yy), (x[-1], yy))
    for xx in x:
        p2.draw_line((xx, y[0]), (xx, y[-1]))
    cells = [["Year", "Called", "Paid"], ["2021", "100", "40"]]
    for r, row in enumerate(cells):
        for c, val in enumerate(row):
            p2.insert_text((x[c] + 4, y[r] + 20), val, fontsize=10)
    doc.new_page()  # blank page, no images -> not flagged for OCR
    doc.save(path)


def test_parse_keeps_page_numbers_and_table_rows(tmp_path: Path) -> None:
    pdf = tmp_path / "fx.pdf"
    _make_pdf(pdf)
    parsed = parse_pdf(pdf)
    assert [p.page for p in parsed.pages] == [1, 2, 3]
    assert "management fee is 2 percent" in parsed.pages[0].text
    assert "2021  100  40" in parsed.pages[1].text  # one table row per line
    assert parsed.ocr_pages == []


def test_pdf_to_chunks_roundtrip_through_store(tmp_path: Path) -> None:
    pdf = tmp_path / "fx.pdf"
    _make_pdf(pdf)
    chunks = chunk_pages(parse_pdf(pdf).pages, doc="fx", date="2024-01-01", fund="F")
    fee = next(c for c in chunks if "management fee" in c.text)
    assert fee.page == 1 and fee.section == "1. FEES"
    table = next(c for c in chunks if c.kind == "table")
    assert table.page == 2 and "2021  100  40" in table.text
    save_chunks(tmp_path / "c" / "fx.jsonl", chunks)
    assert load_chunks(tmp_path / "c" / "fx.jsonl") == chunks
