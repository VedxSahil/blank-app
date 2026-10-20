"""Model wrappers: bge embedder, cross-encoder reranker, and an on-disk embedding cache.

sentence-transformers is imported lazily so the rest of the package works without it. If the
library or the weights cannot be loaded (for example the host is blocked), `ModelUnavailable`
is raised and callers must skip that configuration and say so; there is no fallback model.
The wrappers have not been run against real weights here (BLOCKERS.md B-N9, B-N10).
"""

import hashlib
import sqlite3
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pereport.retrieval import Embedder

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class ModelUnavailable(RuntimeError):
    pass


def _load(factory: Callable[[], Any], what: str) -> Any:
    try:
        return factory()
    except Exception as e:
        raise ModelUnavailable(f"{what} unavailable: {type(e).__name__}: {e}") from e


class SentenceTransformerEmbedder:
    def __init__(
        self, name: str = "BAAI/bge-small-en-v1.5", query_prefix: str = BGE_QUERY_PREFIX
    ) -> None:
        def make() -> Any:
            from sentence_transformers import SentenceTransformer

            return SentenceTransformer(name)

        self.name = name
        self.query_prefix = query_prefix
        self._model = _load(make, f"embedding model {name}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [[float(x) for x in v] for v in out]

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        return self.embed([self.query_prefix + t for t in texts])


class CrossEncoderReranker:
    def __init__(self, name: str = "BAAI/bge-reranker-base") -> None:
        def make() -> Any:
            from sentence_transformers import CrossEncoder

            return CrossEncoder(name)

        self.name = name
        self._model = _load(make, f"reranker {name}")

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._model.predict([(query, t) for t in texts])]


class CachedEmbedder:
    """SQLite cache keyed by sha256(model + text); the cache is part of the project's indexes."""

    def __init__(self, inner: Embedder, model_name: str, path: str | Path) -> None:
        self.inner = inner
        self.model_name = model_name
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS emb (key TEXT PRIMARY KEY, dim INT, vec BLOB)")
        self.hits = 0
        self.misses = 0

    def _key(self, text: str) -> str:
        return hashlib.sha256((self.model_name + "\x00" + text).encode()).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        keys = [self._key(t) for t in texts]
        found: dict[str, list[float]] = {}
        for k in set(keys):
            row = self.db.execute("SELECT dim, vec FROM emb WHERE key=?", (k,)).fetchone()
            if row:
                found[k] = list(struct.unpack(f"{row[0]}f", row[1]))
        todo = [(k, t) for k, t in zip(keys, texts, strict=True) if k not in found]
        uniq = list(dict(todo).items())
        if uniq:
            vecs = self.inner.embed([t for _, t in uniq])
            for (k, _), v in zip(uniq, vecs, strict=True):
                self.db.execute(
                    "INSERT OR REPLACE INTO emb VALUES (?,?,?)",
                    (k, len(v), struct.pack(f"{len(v)}f", *v)),
                )
                found[k] = [struct.unpack("f", struct.pack("f", x))[0] for x in v]
            self.db.commit()
        self.misses += len(uniq)
        self.hits += len(set(keys)) - len(uniq)
        return [found[k] for k in keys]

    def embed_query(self, texts: list[str]) -> list[list[float]]:
        fn = getattr(self.inner, "embed_query", None)
        return fn(texts) if fn else self.inner.embed(texts)
