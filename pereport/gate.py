"""Answerability gate.

Refuse when (1) there is no retrieved evidence, (2) the top evidence score is below a threshold
calibrated on the DEV split only, or (3) the drafted answer contains a number, date or entity
that the retrieved text does not contain.

Calibration picks the threshold with the lowest weighted error on dev questions, where answering
an unanswerable question (a hallucination risk) costs `fp_cost` times more than refusing an
answerable one. Ties go to the higher threshold (more refusals). Never calibrate on the test split.
"""

import itertools
import math
from dataclasses import dataclass, field

from pereport.verifier import Fact, unsupported_facts


def calibrate_threshold(
    dev: list[tuple[float, bool]], fp_cost: float = 3.0, fn_cost: float = 1.0
) -> float:
    """Threshold t such that a question is answered iff top_score >= t.

    `dev` holds (top_evidence_score, is_answerable) pairs. Raises ValueError unless both
    answerable and unanswerable questions are present (one class cannot calibrate a gate).
    """
    if not any(a for _, a in dev) or all(a for _, a in dev):
        raise ValueError("calibration needs both answerable and unanswerable dev questions")
    scores = sorted({s for s, _ in dev})
    candidates = [scores[0]]  # answer everything
    candidates += [(a + b) / 2 for a, b in itertools.pairwise(scores)]
    candidates.append(math.nextafter(scores[-1], math.inf))  # refuse everything
    best_t, best_cost = candidates[0], math.inf
    for t in candidates:
        fp = sum(1 for s, a in dev if s >= t and not a)  # answered an unanswerable question
        fn = sum(1 for s, a in dev if s < t and a)  # refused an answerable question
        cost = fp_cost * fp + fn_cost * fn
        if cost <= best_cost:  # "<=" so ties move to the higher threshold
            best_t, best_cost = t, cost
    return best_t


@dataclass(frozen=True)
class GateDecision:
    answer: bool
    reason: str  # "answer", "no_evidence", "low_score" or "unsupported_facts"
    unsupported: list[Fact] = field(default_factory=list)


@dataclass(frozen=True)
class Gate:
    threshold: float

    def decide(
        self,
        top_score: float | None,
        draft: str | None = None,
        evidence: str | None = None,
    ) -> GateDecision:
        """`top_score` is None when retrieval returned nothing. Pass `draft` and `evidence`
        (the retrieved text) to also apply the key-fact check."""
        if top_score is None:
            return GateDecision(False, "no_evidence")
        if top_score < self.threshold:
            return GateDecision(False, "low_score")
        if draft is not None:
            missing = unsupported_facts(draft, evidence or "")
            if missing:
                return GateDecision(False, "unsupported_facts", missing)
        return GateDecision(True, "answer")
