"""Okapi BM25 in plain Python (Lucene-style non-negative IDF).

score(q, d) = sum over query terms t of
    idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avgdl))
    idf(t)  = ln(1 + (N - n_t + 0.5) / (n_t + 0.5))
where N = number of chunks, n_t = chunks containing t, tf = count of t in d.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

from pereport.chunker import Chunk

_TOKEN = re.compile(r"[a-z0-9]+(?:[.,][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens. Thousands separators are dropped so '1,250.5' matches '1250.5'."""
    out: list[str] = []
    for tok in _TOKEN.findall(text.lower()):
        out.append(tok.replace(",", "") if any(c.isdigit() for c in tok) else tok)
    return out


STOPWORDS = frozenset({
    "a", "an", "the", "of", "and", "or", "to", "in", "on", "at", "by", "for", "with", "from",
    "as", "is", "are", "was", "were", "be", "been", "it", "its", "this", "that", "these", "those",
    "what", "which", "who", "whom", "how", "when", "where", "why", "do", "does", "did", "has",
    "have", "had", "not", "no", "many", "much", "often", "take", "define", "defined", "definition",
    "mean", "means", "meaning", "explain",
})  # fmt: skip


def stem(token: str) -> str:
    """Light suffix stripping so fees/fee, closing/close and meeting/meet match.

    Only alphabetic tokens longer than three letters are touched: ies -> y, then ing, ed or a
    plural s (not ss), then a final silent e. Numbers and words ending in 'ss' are left alone.
    """
    if len(token) <= 3 or not token.isalpha():
        return token
    t = token
    if t.endswith("ies") and len(t) > 4:
        t = t[:-3] + "y"
    elif t.endswith("ing") and len(t) > 5:
        t = t[:-3]
    elif t.endswith("ed") and len(t) > 4:
        t = t[:-2]
    elif t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    if t.endswith("e") and len(t) > 3:
        t = t[:-1]
    return t


def terms(text: str) -> list[str]:
    """Index/query terms: stemmed tokens without stopwords (numbers are never stopwords)."""
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self._tf = [Counter(terms(c.text)) for c in chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avgdl = sum(self._len) / len(chunks) if chunks else 0.0
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query: str, i: int) -> float:
        total = 0.0
        tf_i = self._tf[i]
        norm = 1 - self.b + self.b * self._len[i] / self._avgdl if self._avgdl else 1.0
        for term in set(terms(query)):
            tf = tf_i.get(term, 0)
            if tf:
                total += self._idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return total

    def max_score(self, query: str) -> float:
        """Best score a chunk could reach on this query: every term present with saturated tf.

        A query term that is absent from the corpus counts with the largest possible IDF, so a
        question using words the documents never use scores low instead of being ignored.
        """
        n = len(self.chunks)
        absent_idf = math.log(1 + (n + 0.5) / 0.5)
        return sum(self._idf.get(t, absent_idf) * (self.k1 + 1) for t in set(terms(query)))

    def search(self, query: str, top_k: int = 5, normalize: bool = False) -> list[Hit]:
        """Top-k chunks with a positive score, best first (ties keep corpus order).

        With `normalize`, scores are divided by `max_score(query)`: a 0..1 fraction of a perfect
        match, comparable across short and long queries (raw BM25 is not).
        """
        scored = [(self.score(query, i), i) for i in range(len(self.chunks))]
        scored = [(s, i) for s, i in scored if s > 0]
        scored.sort(key=lambda si: (-si[0], si[1]))
        denom = self.max_score(query) if normalize else 0.0
        return [Hit(self.chunks[i], s / denom if denom else s) for s, i in scored[:top_k]]
