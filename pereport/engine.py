"""Question answering: retrieve -> gate -> generate -> verify.

The generator is pluggable (`Generator` protocol). `ExtractiveGenerator` is the default: it returns
whole sentences copied from the top chunks with a `[doc, p.X]` citation, so it cannot invent a
fact. An LLM generator can be dropped in later; the verifier then does the real work.
Switches `use_gate` and `use_verifier` exist for the ablation study.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol

from pereport.bm25 import terms
from pereport.chunker import Chunk
from pereport.gate import Gate
from pereport.retrieval import HybridRetriever
from pereport.verifier import CITATION, VerifiedAnswer, split_sentences, verify_answer

# Finance acronyms and their spelled-out forms. Domain knowledge, not fund data.
GLOSSARY = {
    "nav": "net asset value",
    "irr": "internal rate of return",
    "tvpi": "total value to paid-in",
    "dpi": "distributions to paid-in",
    "rvpi": "residual value to paid-in",
    "moic": "multiple on invested capital",
    "gp": "general partner",
    "lp": "limited partner",
    "aif": "alternative investment fund",
}
_ACRONYM = re.compile(r"\b[A-Z]{2,}[a-z]?\b")
LABEL_BONUS = 3
_HAS_DIGIT = re.compile(r"\d")
REFUSAL_TEXT = "The provided documents do not contain enough information to answer this question."


def expand_question(question: str) -> str:
    """Append the spelled-out form of known acronyms so 'NAV' also finds 'net asset value'."""
    extra = [GLOSSARY[a.lower()] for a in _ACRONYM.findall(question) if a.lower() in GLOSSARY]
    return question + (" " + " ".join(extra) if extra else "")


def missing_mandatory_terms(question: str, answer: str) -> list[str]:
    """Acronyms and numbers asked about must appear in the answer (or their spelled-out form)."""
    have = set(terms(answer))
    asked = {a.lower() for a in _ACRONYM.findall(question)}
    asked |= {t for t in terms(question) if any(c.isdigit() for c in t)}
    missing = []
    for t in sorted(asked):
        spelled = set(terms(GLOSSARY.get(t, "")))
        if t not in have and not (spelled and spelled <= have):
            missing.append(t)
    return missing


class Generator(Protocol):
    def generate(self, question: str, chunks: list[Chunk]) -> str:
        """Draft an answer using only `chunks`, citing each sentence as [doc, p.X]."""
        ...


_LABEL_BLOCKERS = {
    "is",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "will",
    "may",
    "the",
    "a",
    "an",
}


def merge_run_in_labels(sentences: list[str]) -> list[str]:
    """Join a run-in heading ("Directors' remuneration.") with the sentence it introduces.

    A fragment counts as a label when it is at most five words, has no digit and contains no
    verb-like or article word, so it cannot stand as an answer by itself.
    """
    out: list[str] = []
    i = 0
    while i < len(sentences):
        words = sentences[i].rstrip(".:").split()
        is_label = (
            0 < len(words) <= 5
            and not any(c.isdigit() for c in sentences[i])
            and not {w.lower() for w in words} & _LABEL_BLOCKERS
            and i + 1 < len(sentences)
        )
        if is_label:
            # a colon, not a full stop: the verifier splits on full stops and would orphan the label
            out.append(f"{sentences[i].rstrip('.:')}: {sentences[i + 1]}")
            i += 2
        else:
            out.append(sentences[i])
            i += 1
    return out


class ExtractiveGenerator:
    def __init__(self, max_sentences: int = 2) -> None:
        self.max_sentences = max_sentences

    def generate(self, question: str, chunks: list[Chunk]) -> str:
        q = set(terms(question))
        if not q:
            return ""
        need = min(2, len(q))
        scored: list[tuple[int, int, int, str, Chunk]] = []
        for rank, chunk in enumerate(chunks):
            lines = (
                chunk.text.split("\n")
                if chunk.kind == "table"
                else merge_run_in_labels(split_sentences(chunk.text))
            )
            header = lines[0] if chunk.kind == "table" and not _HAS_DIGIT.search(lines[0]) else ""
            for pos, line in enumerate(lines):
                if header and pos == 0:
                    continue  # the header only accompanies its data rows
                row_terms = set(terms(line))
                if header and pos > 0:
                    row_terms |= set(terms(header))  # a data row inherits its header's words
                overlap = len(q & row_terms)
                if chunk.kind == "table":
                    label = set(terms(line.split("  ")[0]))
                    if label and label <= q:
                        overlap += LABEL_BONUS  # the row's own label is what the question names
                if overlap >= need:
                    shown = f"{header} / {line}" if header and pos > 0 else line
                    scored.append((-overlap, rank, pos, shown.strip(), chunk))
        scored.sort(key=lambda t: t[:3])
        out: list[str] = []
        seen: set[str] = set()
        for _, _, _, line, chunk in scored:
            if line in seen:
                continue
            seen.add(line)
            body = line.rstrip(".;:, ")
            out.append(f"{body} [{chunk.doc}, p.{chunk.page}].")
            if len(out) == self.max_sentences:
                break
        return " ".join(out)


@dataclass(frozen=True)
class Answer:
    question: str
    text: str
    refused: bool
    reason: str  # "answered" or the refusal reason
    mode: str  # retrieval mode
    top_score: float | None
    sources: list[Chunk] = field(default_factory=list)
    verification: VerifiedAnswer | None = None
    draft: str = ""
    draft_unsupported: int = 0  # unsupported facts in the draft, counted before stripping

    @property
    def cited_pages(self) -> frozenset[tuple[str, int]]:
        return frozenset((c.doc, c.page) for c in self.sources)


class Engine:
    def __init__(
        self,
        retriever: HybridRetriever,
        gate: Gate,
        generator: Generator | None = None,
        top_k: int = 5,
        use_gate: bool = True,
        use_verifier: bool = True,
    ) -> None:
        self.retriever = retriever
        self.gate = gate
        self.generator = generator or ExtractiveGenerator()
        self.top_k = top_k
        self.use_gate = use_gate
        self.use_verifier = use_verifier

    def _refuse(self, q: str, reason: str, mode: str, top: float | None, **kw: object) -> Answer:
        return Answer(q, REFUSAL_TEXT, True, reason, mode, top, **kw)  # type: ignore[arg-type]

    def ask(self, question: str) -> Answer:
        expanded = expand_question(question)
        retr = self.retriever.search(expanded, self.top_k)
        top, mode = retr.top_score, retr.mode
        chunks = [h.chunk for h in retr.hits]
        if top is None:
            return self._refuse(question, "no_evidence", mode, top)
        if self.use_gate:
            d = self.gate.decide(top)
            if not d.answer:
                return self._refuse(question, d.reason, mode, top)
        draft = self.generator.generate(expanded, chunks)
        if not draft.strip():
            return self._refuse(question, "no_answer_sentence", mode, top)
        if self.use_gate:
            lacking = missing_mandatory_terms(question, draft)
            if lacking:
                return self._refuse(question, "key_term_missing", mode, top, draft=draft)
        verification = verify_answer(draft, chunks)
        n_bad = verification.unsupported_fact_count
        if self.use_gate:
            d = self.gate.decide(top, draft, "\n".join(c.text for c in chunks))
            if not d.answer:
                return self._refuse(
                    question, d.reason, mode, top, draft=draft, draft_unsupported=n_bad
                )
        text = draft
        if self.use_verifier:
            if verification.refused:
                return self._refuse(
                    question,
                    "verifier_removed_all",
                    mode,
                    top,
                    verification=verification,
                    draft=draft,
                    draft_unsupported=n_bad,
                )
            text = verification.text
        cited = {(d_, int(p)) for d_, p in CITATION.findall(text)}
        sources = [c for c in chunks if (c.doc, c.page) in cited]
        return Answer(
            question, text, False, "answered", mode, top, sources, verification, draft, n_bad
        )
