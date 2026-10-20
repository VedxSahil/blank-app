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


def test_merge_continuations_empty_first_cell_and_sentence_style() -> None:
    from pereport.ingest import merge_continuations

    # empty first cell always continues the row above
    assert merge_continuations([["Role", "Entity"], ["Fund", "Alpha"], ["", "Beta"]]) == [
        ["Role", "Entity"],
        ["Fund", "Alpha Beta"],
    ]
    # sentence-style table: a row whose text has not reached a full stop continues on the next line
    grid = [["Term", "Summary"], ["Alternate", "May be organized in any"], ["Vehicles", "jurisdiction."],
            ["Fee", "Two percent."], ["Carry", "Twenty percent."]]  # fmt: skip
    assert merge_continuations(grid)[1:] == [
        ["Alternate Vehicles", "May be organized in any jurisdiction."],
        ["Fee", "Two percent."],
        ["Carry", "Twenty percent."],
    ]
    # address-style table (no full stops) is NOT merged by the sentence rule
    addr = [["Role", "Address"], ["Fund", "1 Quay"], ["Sponsor", "2 Tower"]]
    assert merge_continuations(addr) == addr


def test_group_by_rules_merges_lines_between_the_same_rules() -> None:
    from pereport.ingest import group_by_rules

    # Rules at y=8, 20, 40 give buckets: y<8 -> 0, 8..20 -> 1, 20..40 -> 2.
    # Header (y=5) is bucket 0; "A" (y=10) and its wrapped line (y=15) are bucket 1; "B" (y=30) is bucket 2.
    grid = [["Head", "Cell"], ["A", "one two"], ["", "three"], ["B", "four"]]
    out = group_by_rules(grid, [5.0, 10.0, 15.0, 30.0], [8.0, 20.0, 40.0])
    assert out == [["Head", "Cell"], ["A", "one two three"], ["B", "four"]]


def test_sample_ppm_tables_keep_words_and_rows() -> None:
    """Regression on the user-supplied replica PPM (skipped if the file is absent)."""
    from pathlib import Path

    import pytest

    pdf = Path("data/sample/Aurelian_Peak_Fund_Sample_PPM.pdf")
    if not pdf.exists():
        pytest.skip("sample PDF not present")
    pages = parse_pdf(pdf).pages
    assert len(pages) == 20
    summary = pages[7].text  # PDF page 8
    assert "Open-ended Zandrian public company" in summary  # words were being glued together
    assert "Management Fee  2% per annum of Class A Net Asset Value" in summary
    assert (
        "Investment Manager  Aurelian Asset Management Ltd; discretionary" in summary
    )  # wrapped label
    assert "Legal Advisors (Zandria)  Isolde Marchetti, Attorney" in pages[1].text
