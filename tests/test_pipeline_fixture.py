"""Chunker -> BM25 -> gate -> verifier on a TEST FIXTURE (invented text, never shown in the app)."""

from pereport.bm25 import BM25Index
from pereport.chunker import Page, chunk_pages
from pereport.gate import Gate
from pereport.verifier import verify_answer

FIXTURE = [
    Page(1, "1. FEES\nThe management fee is 2% of committed capital.\n\n2. CARRY\nCarry is 20%."),
    Page(2, "3. NAV\nNAV was 500 million at 30 June 2023."),
]


def test_answer_cites_and_verifies_end_to_end() -> None:
    chunks = chunk_pages(FIXTURE, doc="fx")
    hits = BM25Index(chunks).search("what is the management fee", top_k=2)
    assert hits[0].chunk.page == 1 and hits[0].chunk.section == "1. FEES"
    gate = Gate(threshold=0.1)
    evidence = "\n".join(h.chunk.text for h in hits)
    draft = "The management fee is 2% of committed capital [fx, p.1]."
    assert gate.decide(hits[0].score, draft, evidence).answer
    assert verify_answer(draft, [h.chunk for h in hits]).passed


def test_unsupported_question_is_refused() -> None:
    chunks = chunk_pages(FIXTURE, doc="fx")
    hits = BM25Index(chunks).search("what is the hurdle rate waterfall", top_k=2)
    top = hits[0].score if hits else None
    assert not Gate(threshold=0.1).decide(top).answer
