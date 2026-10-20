"""Model wrapper tests with a counting fake embedder (TEST FIXTURE; no real model)."""

import importlib.util
from pathlib import Path

import pytest

from pereport.chunker import Chunk
from pereport.models import CachedEmbedder, ModelUnavailable, SentenceTransformerEmbedder
from pereport.retrieval import HybridRetriever


class Counting:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(t)), 0.5] for t in texts]


def test_cache_hits_misses_and_persistence(tmp_path: Path) -> None:
    inner = Counting()
    db = tmp_path / "e.sqlite"
    c = CachedEmbedder(inner, "m1", db)
    v1 = c.embed(["aa", "bbb", "aa"])  # "aa" duplicated -> embedded once
    assert inner.calls == [["aa", "bbb"]] and v1[0] == v1[2] == [2.0, 0.5]
    assert (c.misses, c.hits) == (2, 0)
    # a new object on the same file reuses stored vectors
    c2 = CachedEmbedder(inner, "m1", db)
    assert c2.embed(["bbb"]) == [[3.0, 0.5]] and len(inner.calls) == 1
    assert (c2.misses, c2.hits) == (0, 1)
    # a different model name must not reuse them
    c3 = CachedEmbedder(inner, "m2", db)
    c3.embed(["bbb"])
    assert len(inner.calls) == 2


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is not None, reason="library installed"
)
def test_missing_library_raises_model_unavailable() -> None:
    with pytest.raises(ModelUnavailable, match="embedding model"):
        SentenceTransformerEmbedder()


def test_retriever_uses_embed_query_when_present() -> None:
    class Asym:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        def embed_query(self, texts: list[str]) -> list[list[float]]:
            return [[0.0, 1.0] for _ in texts]

    chunks = [Chunk("d:p1:c0", "d", 1, "S", None, None, "text", "alpha")]
    # passages embed to (1,0); queries to (0,1): cosine 0 -> dense finds nothing, proving embed_query ran
    r = HybridRetriever(chunks, Asym(), use_bm25=False).search("alpha")
    assert r.hits == []
