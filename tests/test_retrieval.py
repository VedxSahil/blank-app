"""Retrieval tests with a fake embedder and reranker defined here (TEST FIXTURES, not models)."""

import math

import pytest

from pereport.chunker import Chunk
from pereport.retrieval import HybridRetriever, cosine, rrf_fuse

VOCAB = ["fee", "carry", "nav", "hurdle", "commitment"]


class BowEmbedder:
    """Bag-of-words counts over a tiny fixed vocabulary."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(t.lower().count(w)) for w in VOCAB] for t in texts]


class LenReranker:
    """Scores by negative text length so the shortest candidate wins (deterministic)."""

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [-float(len(t)) for t in texts]


def _c(i: int, text: str) -> Chunk:
    return Chunk(f"t:p{i}:c0", "t", i, "S", None, None, "text", text)


CHUNKS = [_c(1, "fee fee fee schedule"), _c(2, "carry and hurdle"), _c(3, "nav note")]


def test_cosine_hand_worked() -> None:
    # (1,1)·(1,0) = 1; |a|=sqrt2, |b|=1 -> 1/sqrt2
    assert cosine([1, 1], [1, 0]) == pytest.approx(1 / math.sqrt(2))
    assert cosine([0, 0], [1, 0]) == 0.0


def test_rrf_hand_worked() -> None:
    # k=60. Doc 7: rank1 in A (1/61) + rank2 in B (1/62) = 0.016393+0.016129 = 0.032522
    # Doc 8: rank2 in A (1/62) only = 0.016129. Doc 9: rank1 in B (1/61) = 0.016393.
    fused = rrf_fuse([[7, 8], [9, 7]])
    assert [d for d, _ in fused] == [7, 9, 8]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


def test_modes() -> None:
    assert HybridRetriever(CHUNKS).mode == "bm25"
    assert HybridRetriever(CHUNKS, BowEmbedder()).mode == "hybrid"
    assert HybridRetriever(CHUNKS, BowEmbedder(), use_bm25=False).mode == "dense"
    assert HybridRetriever(CHUNKS, BowEmbedder(), LenReranker()).mode == "hybrid+rerank"
    with pytest.raises(ValueError, match="need BM25"):
        HybridRetriever(CHUNKS, use_bm25=False)


def test_bm25_mode_returns_bm25_scores() -> None:
    r = HybridRetriever(CHUNKS).search("carry hurdle")
    assert r.mode == "bm25" and r.hits[0].chunk.page == 2 and r.top_score and r.top_score > 0


def test_dense_mode_score_is_cosine() -> None:
    r = HybridRetriever(CHUNKS, BowEmbedder(), use_bm25=False).search("nav")
    # query vector (0,0,1,0,0) vs chunk 3 vector (0,0,1,0,0) -> cosine 1
    assert r.hits[0].chunk.page == 3 and r.top_score == pytest.approx(1.0)


def test_hybrid_fuses_and_rerank_reorders() -> None:
    hybrid = HybridRetriever(CHUNKS, BowEmbedder()).search("fee nav")
    assert {h.chunk.page for h in hybrid.hits} == {1, 3}
    rr = HybridRetriever(CHUNKS, BowEmbedder(), LenReranker()).search("fee nav")
    # shortest candidate text first: "nav note" (8 chars) before "fee fee fee schedule" (20)
    assert [h.chunk.page for h in rr.hits] == [3, 1]
    assert rr.top_score == pytest.approx(-8.0)


def test_no_match_gives_no_hits() -> None:
    assert HybridRetriever(CHUNKS, BowEmbedder()).search("waterfall").top_score is None
    assert HybridRetriever([]).search("fee").hits == []
