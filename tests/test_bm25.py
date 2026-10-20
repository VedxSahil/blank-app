"""BM25 tests with hand-worked numbers. Corpus below is a TEST FIXTURE, not fund data."""

import pytest

from pereport.bm25 import BM25Index, tokenize
from pereport.chunker import Chunk


def _chunk(i: int, text: str) -> Chunk:
    return Chunk(f"t:p1:c{i}", "t", 1, "S", None, None, "text", text)


@pytest.fixture
def index() -> BM25Index:
    # d0 = "carry carry fee" (3 tokens), d1 = "fee" (1 token). N=2, avgdl=(3+1)/2=2. k1=1.5, b=0.75.
    return BM25Index([_chunk(0, "carry carry fee"), _chunk(1, "fee")])


def test_tokenize_drops_thousands_separator_and_trailing_period() -> None:
    assert tokenize("NAV of $1,250.5 million.") == ["nav", "of", "1250.5", "million"]


def test_hand_worked_term_in_one_doc(index: BM25Index) -> None:
    # "carry": n=1 -> idf = ln(1 + (2-1+0.5)/(1+0.5)) = ln 2 = 0.693147
    # d0: tf=2, norm = 1-0.75+0.75*3/2 = 1.375; tf-part = 2*2.5/(2+1.5*1.375) = 5/4.0625 = 1.230769
    #     score = 0.693147*1.230769 = 0.853104.  d1: no "carry" -> 0.
    assert index.score("carry", 0) == pytest.approx(0.853104, abs=1e-4)
    assert index.score("carry", 1) == 0.0


def test_hand_worked_length_normalisation(index: BM25Index) -> None:
    # "fee": n=2 -> idf = ln(1 + 0.5/2.5) = ln 1.2 = 0.182322
    # d0: norm 1.375 -> 1*2.5/(1+2.0625) = 0.816327 -> 0.148835
    # d1: norm = 0.25+0.75*1/2 = 0.625 -> 2.5/(1+0.9375) = 1.290323 -> 0.235255 (shorter doc wins)
    assert index.score("fee", 0) == pytest.approx(0.148835, abs=1e-4)
    assert index.score("fee", 1) == pytest.approx(0.235255, abs=1e-4)
    assert [h.chunk.chunk_id for h in index.search("fee")] == ["t:p1:c1", "t:p1:c0"]


def test_search_excludes_zero_scores_and_empty_query(index: BM25Index) -> None:
    assert index.search("waterfall") == []
    assert index.search("") == []
    assert [h.chunk.chunk_id for h in index.search("carry")] == ["t:p1:c0"]


def test_empty_corpus() -> None:
    assert BM25Index([]).search("anything") == []


def test_top_k_limits_results(index: BM25Index) -> None:
    assert len(index.search("fee", top_k=1)) == 1
