"""Hybrid retrieval: BM25 + dense embeddings fused by reciprocal rank, optional reranker.

The dense embedder (bge/e5) and cross-encoder reranker are injected through the `Embedder` and
`Reranker` protocols, so this module has no model dependency. With neither supplied the retriever
is BM25 only. Scores used by the gate:
  reranker given -> the reranker's score for the top hit;
  else dense given -> cosine similarity of the top hit;
  else           -> BM25 score.
Each mode needs its own calibrated gate threshold.
"""

import math
from dataclasses import dataclass
from typing import Protocol

from pereport.bm25 import BM25Index, Hit
from pereport.chunker import Chunk

RRF_K = 60


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


def cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal rank fusion: score(d) = sum over rankings of 1 / (k + rank), rank from 1."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit]  # best first; Hit.score is the score named by `mode`
    mode: str  # "bm25", "dense", "hybrid", "hybrid+rerank"

    @property
    def top_score(self) -> float | None:
        return self.hits[0].score if self.hits else None


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        use_bm25: bool = True,
        candidates: int = 20,
    ) -> None:
        if not use_bm25 and embedder is None:
            raise ValueError("need BM25 or an embedder")
        self.chunks = chunks
        self.embedder = embedder
        self.reranker = reranker
        self.use_bm25 = use_bm25
        self.candidates = candidates
        self._bm25 = BM25Index(chunks)
        self._vecs = embedder.embed([c.text for c in chunks]) if embedder and chunks else []

    @property
    def mode(self) -> str:
        if self.reranker is not None:
            return "hybrid+rerank" if self.use_bm25 and self.embedder else "rerank"
        if self.embedder is not None and self.use_bm25:
            return "hybrid"
        return "dense" if self.embedder is not None else "bm25"

    def search(self, query: str, top_k: int = 5) -> Retrieval:
        if not self.chunks:
            return Retrieval([], self.mode)
        rankings: list[list[int]] = []
        dense_scores: dict[int, float] = {}
        if self.use_bm25:
            order = {c.chunk_id: i for i, c in enumerate(self.chunks)}
            rankings.append(
                [order[h.chunk.chunk_id] for h in self._bm25.search(query, self.candidates)]
            )
        if self.embedder is not None:
            embed_q = getattr(self.embedder, "embed_query", self.embedder.embed)
            q = embed_q([query])[0]
            sims = sorted(
                ((cosine(q, v), i) for i, v in enumerate(self._vecs)), key=lambda t: (-t[0], t[1])
            )
            top = [(s, i) for s, i in sims[: self.candidates] if s > 0]
            dense_scores = {i: s for s, i in top}
            rankings.append([i for _, i in top])
        fused = rrf_fuse(rankings)[: self.candidates]
        if not fused:
            return Retrieval([], self.mode)

        if self.reranker is not None:
            ids = [i for i, _ in fused]
            scores = self.reranker.score(query, [self.chunks[i].text for i in ids])
            ranked = sorted(zip(ids, scores, strict=True), key=lambda t: (-t[1], t[0]))
            hits = [Hit(self.chunks[i], s) for i, s in ranked[:top_k]]
        elif self.embedder is not None and not self.use_bm25:
            hits = [Hit(self.chunks[i], dense_scores[i]) for i, _ in fused[:top_k]]
        elif self.embedder is not None:
            # hybrid without reranker: order by fusion, gate on the top hit's dense cosine
            hits = [Hit(self.chunks[i], dense_scores.get(i, 0.0)) for i, _ in fused[:top_k]]
        else:
            by_id = {h.chunk.chunk_id: h.score for h in self._bm25.search(query, top_k)}
            hits = [Hit(self.chunks[i], by_id[self.chunks[i].chunk_id]) for i, _ in fused[:top_k]]
        return Retrieval(hits, self.mode)
