"""Chunker tests. All text below is a TEST FIXTURE written for the unit test, not fund data."""

from pereport.chunker import FRONT_MATTER, Page, chunk_pages, is_heading

FIXTURE_P1 = """\
FIXTURE FUND SUMMARY

Alpha text one. Alpha text two.

2. Fees
Beta text here."""

FIXTURE_P2 = """\
Gamma text on the next page."""


def test_headings_assigned_and_ids_deterministic() -> None:
    chunks = chunk_pages(
        [Page(1, FIXTURE_P1), Page(2, FIXTURE_P2)], doc="docX", date="2024-03-31", fund="F1"
    )
    # Hand-worked: page 1 has 2 headings, each followed by one paragraph -> 2 chunks;
    # page 2 continues section "2. Fees" -> 1 chunk. Total 3.
    assert [c.chunk_id for c in chunks] == ["docX:p1:c0", "docX:p1:c1", "docX:p2:c0"]
    assert [c.section for c in chunks] == ["FIXTURE FUND SUMMARY", "2. Fees", "2. Fees"]
    assert chunks[0].text == "Alpha text one. Alpha text two."
    assert all(c.date == "2024-03-31" and c.fund == "F1" and c.doc == "docX" for c in chunks)


def test_text_before_first_heading_is_front_matter() -> None:
    chunks = chunk_pages([Page(1, "Some intro words.\n\nITEM 1. BUSINESS\nBody.")], doc="d")
    assert chunks[0].section == FRONT_MATTER
    assert chunks[1].section == "ITEM 1. BUSINESS"


def test_sentence_packing_respects_max_words() -> None:
    # Three 3-word sentences, max_words=6: [s1 s2] (6 words) then [s3] (3 words).
    chunks = chunk_pages([Page(1, "Aa bb cc. Dd ee ff. Gg hh ii.")], doc="d", max_words=6)
    assert [c.text for c in chunks] == ["Aa bb cc. Dd ee ff.", "Gg hh ii."]


def test_oversize_sentence_is_hard_split() -> None:
    # One 10-word sentence, max_words=4 -> 4 + 4 + 2 words.
    text = "w1 w2 w3 w4 w5 w6 w7 w8 w9 w10."
    chunks = chunk_pages([Page(1, text)], doc="d", max_words=4)
    assert [len(c.text.split()) for c in chunks] == [4, 4, 2]


def test_table_block_is_kept_separate_and_split_on_rows() -> None:
    page = "Intro sentence.\n\nRow a 10 20\nRow b 30 40\nRow c 50 60"
    chunks = chunk_pages([Page(1, page)], doc="d", max_words=8)
    assert [c.kind for c in chunks] == ["text", "table", "table"]
    # Each row has 4 words; two rows = 8 <= 8 fits, third row starts a new chunk.
    assert chunks[1].text == "Row a 10 20\nRow b 30 40"
    assert chunks[2].text == "Row c 50 60"


def test_no_chunk_spans_pages() -> None:
    chunks = chunk_pages([Page(1, "End of one."), Page(2, "Start of two.")], doc="d")
    assert [(c.page, c.text) for c in chunks] == [(1, "End of one."), (2, "Start of two.")]


def test_is_heading_negatives() -> None:
    assert not is_heading("The fund returned 12% net of fees.")
    assert not is_heading("")
    assert not is_heading("2. Mr Rao resigned from the committee on 5 May.")
    assert is_heading("ITEM 7. MANAGEMENT DISCUSSION")
    assert is_heading("3.1 Capital commitments")
