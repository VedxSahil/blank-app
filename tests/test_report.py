"""Report tests. The corpus is a TEST FIXTURE (invented text)."""

from pereport.chunker import Chunk
from pereport.engine import Engine
from pereport.gate import Gate
from pereport.report import NOT_DISCLOSED, disclosure_rate, draft_report, render_markdown
from pereport.retrieval import HybridRetriever
from pereport.verifier import verify_answer

CORPUS = [
    Chunk(
        "fx:p1:c0",
        "fx",
        1,
        "FEES",
        None,
        None,
        "text",
        "The management fee is 2% of committed capital.",
    ),
    Chunk(
        "fx:p2:c0",
        "fx",
        2,
        "NAV",
        None,
        None,
        "text",
        "The net asset value of the fund was 500 million at 30 June 2023.",
    ),
]
SECTIONS = [
    ("Fees and expenses", [("Management fee", "What is the management fee?")]),
    ("Net asset value", [("NAV", "What is the net asset value of the fund and as of what date?")]),
    ("Performance", [("IRR", "What is the net IRR of the fund?")]),
]


def test_lines_are_bound_to_chunks_or_marked_not_disclosed() -> None:
    engine = Engine(HybridRetriever(CORPUS), Gate(0.5))
    report = draft_report(engine, SECTIONS)
    fee, nav, irr = (s.lines[0] for s in report)
    assert fee.disclosed and fee.chunk_ids == ["fx:p1:c0"]
    assert fee.text == "The management fee is 2% of committed capital [fx, p.1]."
    assert nav.disclosed and nav.chunk_ids == ["fx:p2:c0"]
    assert not irr.disclosed and irr.text == NOT_DISCLOSED and irr.chunk_ids == []
    assert disclosure_rate(report) == (2, 3)


def test_every_disclosed_line_passes_the_verifier() -> None:
    engine = Engine(HybridRetriever(CORPUS), Gate(0.5))
    for sec in draft_report(engine, SECTIONS):
        for ln in sec.lines:
            if ln.disclosed:
                assert verify_answer(ln.text, CORPUS).passed


def test_markdown_lists_chunk_ids_and_missing_fields() -> None:
    engine = Engine(HybridRetriever(CORPUS), Gate(0.5))
    md = render_markdown(draft_report(engine, SECTIONS))
    assert "## Fees and expenses" in md
    expected = "- **Management fee:** The management fee is 2% of committed capital [fx, p.1]."
    assert expected + " (chunks: fx:p1:c0)" in md
    assert "- **IRR:** Not disclosed in provided documents" in md
