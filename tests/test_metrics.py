"""Metric tests on a six-record TEST FIXTURE with hand-counted expectations."""

import pytest

from pereport.metrics import EvalRecord, compute_metrics, is_correct, wilson_interval

D1, D2, D3, D4, D5 = (("d", p) for p in (1, 2, 3, 4, 5))


def _r(qid: str, cat: str, **kw: object) -> EvalRecord:
    base: dict[str, object] = {
        "gold_facts": [],
        "gold_pages": frozenset(),
        "answer": "",
        "cited_pages": frozenset(),
        "refused": False,
    }
    base.update(kw)
    return EvalRecord(qid, cat, **base)  # type: ignore[arg-type]


RECORDS = [
    _r("q1", "answerable", gold_facts=["2%"], gold_pages=frozenset({D1}),
       answer="Fee is 2% [d, p.1]", cited_pages=frozenset({D1})),
    _r("q2", "answerable", gold_facts=["20%"], gold_pages=frozenset({D3}),
       answer="Fee is 2%", cited_pages=frozenset({D1, D2}), verifier_passed=False),
    _r("q3", "answerable", gold_facts=["5%"], gold_pages=frozenset({D1}), refused=True),
    _r("q4", "partial", gold_facts=["31 March 2024"], gold_pages=frozenset({D4, D5}),
       answer="As of March 31, 2024 [d, p.4]", cited_pages=frozenset({D4})),
    _r("q5", "unanswerable", refused=True),
    _r("q6", "unanswerable", answer="Some invented answer", refused=False),
]  # fmt: skip


def test_hand_counted_metrics() -> None:
    m = compute_metrics(RECORDS)
    # correct: q1 yes, q2 no (20% missing), q3 no (refused), q4 yes (date forms match),
    # q5 yes (refused, unanswerable), q6 no (answered, unanswerable)
    assert m.n == 6
    assert m.answer_accuracy == pytest.approx(3 / 6)
    assert m.auto_answer_rate == pytest.approx(2 / 6)  # q1, q4 over all 6
    assert m.auto_answer_rate_answerable == pytest.approx(2 / 4)  # over q1-q4
    # answered = q1,q2,q4,q6 = 4; hallucinated = q6 only (q2 is wrong but supported) -> 1/4
    assert m.answered == 4 and m.hallucinations == 1
    assert m.hallucination_rate == pytest.approx(0.25)
    # citations over q1,q2,q4: cited 1+2+1 = 4, correct (d,1) (d,4) = 2; gold 1+1+2 = 4
    assert m.citation_precision == pytest.approx(2 / 4)
    assert m.citation_recall == pytest.approx(2 / 4)
    # refused = q3,q5; unanswerable among them = q5 -> precision 1/2.
    # unanswerable = q5,q6; refused among them = q5 -> recall 1/2.
    assert m.refusal_precision == pytest.approx(1 / 2)
    assert m.refusal_recall == pytest.approx(1 / 2)
    # verifier passed on q1,q4,q6 of the 4 answered
    assert m.faithfulness == pytest.approx(3 / 4)
    assert m.by_category == {
        "answerable": {"n": 3, "answered": 2, "refused": 1, "correct": 1},
        "partial": {"n": 1, "answered": 1, "refused": 0, "correct": 1},
        "unanswerable": {"n": 2, "answered": 1, "refused": 1, "correct": 1},
    }


def test_unsupported_facts_count_as_hallucination() -> None:
    rec = _r("q", "answerable", answer="x", refused=False, unsupported_facts=2)
    assert compute_metrics([rec]).hallucinations == 1


def test_wilson_zero_of_100_cannot_certify_two_percent() -> None:
    # k=0: upper = z^2 / (n + z^2) = 3.8416 / 103.8416 = 0.03700. A 2% claim needs n >= 188.
    lo, hi = wilson_interval(0, 100)
    assert lo == 0.0
    assert hi == pytest.approx(0.0370, abs=1e-4)
    assert wilson_interval(0, 188)[1] <= 0.02 + 1e-4
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_empty_and_degenerate_inputs() -> None:
    m = compute_metrics([])
    assert m.n == 0 and m.answer_accuracy is None and m.hallucination_rate is None
    only_refusals = compute_metrics([_r("q", "unanswerable", refused=True)])
    assert only_refusals.faithfulness is None and only_refusals.citation_precision is None
    assert only_refusals.refusal_recall == 1.0


def test_unknown_category_rejected() -> None:
    with pytest.raises(ValueError, match="unknown category"):
        compute_metrics([_r("q", "bogus")])


def test_text_gold_fact_without_digits_uses_substring() -> None:
    rec = _r("q", "answerable", gold_facts=["Alpha Fund"], answer="the alpha fund is closed-ended")
    assert is_correct(rec)
