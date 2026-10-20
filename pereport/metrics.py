"""Evaluation metrics in plain Python.

Definitions (also in docs/assumptions.md):
- correct: answerable/partial -> not refused AND every gold fact appears in the answer;
           unanswerable -> refused.
- auto_answer_rate: correct answers to answerable/partial questions / ALL questions (headline).
  auto_answer_rate_answerable: same numerator / answerable+partial questions only.
- hallucinated: an emitted (not refused) answer that either answers an unanswerable question or
  contains a fact unsupported by its evidence. A supported-but-wrong answer is inaccurate, not
  hallucinated. hallucination_rate = hallucinated / answers emitted.
- citation precision/recall: micro-averaged over emitted answers to answerable/partial questions;
  citations are (doc, page) pairs compared with the gold source pages.
- refusal precision/recall: a refusal is "right" when the question is unanswerable.
- faithfulness: share of emitted answers on which the verifier stripped nothing.
"""

import math
from dataclasses import dataclass, field

from pereport.verifier import extract_facts

CATEGORIES = ("answerable", "partial", "unanswerable")


@dataclass(frozen=True)
class EvalRecord:
    qid: str
    category: str  # one of CATEGORIES
    gold_facts: list[str]  # facts a correct answer must contain (empty for unanswerable)
    gold_pages: frozenset[tuple[str, int]]
    answer: str
    cited_pages: frozenset[tuple[str, int]]
    refused: bool
    verifier_passed: bool = True
    unsupported_facts: int = 0  # facts unsupported by evidence, counted before verification


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _fact_keys(text: str) -> set[str]:
    """Number and date keys only; entities are matched as case-insensitive text instead."""
    return {f.key for f in extract_facts(text) if f.kind != "entity"}


def is_correct(r: EvalRecord) -> bool:
    if r.category == "unanswerable":
        return r.refused
    if r.refused:
        return False
    answer_keys = _fact_keys(r.answer)
    answer_lower = r.answer.lower()
    for gold in r.gold_facts:
        keys = _fact_keys(gold)
        if keys:
            if not keys <= answer_keys:
                return False
        elif gold.lower() not in answer_lower:
            return False
    return True


def is_hallucinated(r: EvalRecord) -> bool:
    return not r.refused and (r.category == "unanswerable" or r.unsupported_facts > 0)


@dataclass(frozen=True)
class Metrics:
    n: int
    answer_accuracy: float | None
    auto_answer_rate: float | None
    auto_answer_rate_answerable: float | None
    citation_precision: float | None
    citation_recall: float | None
    faithfulness: float | None
    refusal_precision: float | None
    refusal_recall: float | None
    answered: int
    hallucinations: int
    hallucination_rate: float | None
    hallucination_upper_95: float | None
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)


def compute_metrics(records: list[EvalRecord]) -> Metrics:
    for r in records:
        if r.category not in CATEGORIES:
            raise ValueError(f"unknown category {r.category!r} for {r.qid}")
    n = len(records)
    correct = [r for r in records if is_correct(r)]
    answerable = [r for r in records if r.category != "unanswerable"]
    auto = [r for r in answerable if is_correct(r)]
    answered = [r for r in records if not r.refused]
    halluc = [r for r in records if is_hallucinated(r)]

    cited_total = tp = gold_total = 0
    for r in answered:
        if r.category == "unanswerable":
            continue
        cited_total += len(r.cited_pages)
        tp += len(r.cited_pages & r.gold_pages)
        gold_total += len(r.gold_pages)

    refused = [r for r in records if r.refused]
    refusal_tp = sum(1 for r in refused if r.category == "unanswerable")
    unanswerable_n = sum(1 for r in records if r.category == "unanswerable")

    by_cat: dict[str, dict[str, int]] = {}
    for cat in CATEGORIES:
        rs = [r for r in records if r.category == cat]
        by_cat[cat] = {
            "n": len(rs),
            "answered": sum(1 for r in rs if not r.refused),
            "refused": sum(1 for r in rs if r.refused),
            "correct": sum(1 for r in rs if is_correct(r)),
        }

    return Metrics(
        n=n,
        answer_accuracy=_ratio(len(correct), n),
        auto_answer_rate=_ratio(len(auto), n),
        auto_answer_rate_answerable=_ratio(len(auto), len(answerable)),
        citation_precision=_ratio(tp, cited_total),
        citation_recall=_ratio(tp, gold_total),
        faithfulness=_ratio(sum(1 for r in answered if r.verifier_passed), len(answered)),
        refusal_precision=_ratio(refusal_tp, len(refused)),
        refusal_recall=_ratio(refusal_tp, unanswerable_n),
        answered=len(answered),
        hallucinations=len(halluc),
        hallucination_rate=_ratio(len(halluc), len(answered)),
        hallucination_upper_95=wilson_interval(len(halluc), len(answered))[1] if answered else None,
        by_category=by_cat,
    )
