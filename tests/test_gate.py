"""Gate tests. Scores and text below are TEST FIXTURES with hand-worked costs."""

import math

import pytest

from pereport.gate import Gate, calibrate_threshold

DEV = [(0.1, False), (0.3, False), (0.5, True), (0.6, False), (0.8, True), (0.9, True)]


def test_calibration_hand_worked() -> None:
    # Cost = 3*FP + 1*FN, answer iff score >= t.
    #  t=0.1  (answer all):           FP=3 (0.1,0.3,0.6)               cost 9
    #  t=0.2:                         FP=2 (0.3,0.6)                   cost 6
    #  t=0.4:                         FP=1 (0.6)                       cost 3
    #  t=0.55:                        FP=1 (0.6), FN=1 (0.5)           cost 4
    #  t=0.7:                         FP=0, FN=1 (0.5)                 cost 1  <- minimum
    #  t=0.85:                        FN=2 (0.5,0.8)                   cost 2
    #  t>0.9  (refuse all):           FN=3                             cost 3
    assert calibrate_threshold(DEV) == pytest.approx(0.7)


def test_cost_weighting_changes_the_answer() -> None:
    # With fp_cost=0.5 answering wrongly is cheap: t=0.4 costs 0.5*1=0.5, t=0.7 costs 1.
    assert calibrate_threshold(DEV, fp_cost=0.5) == pytest.approx(0.4)


def test_tie_goes_to_higher_threshold() -> None:
    # dev [(0.4 answerable), (0.5 unanswerable)], fp_cost=fn_cost=1:
    # answer both: FP=1 -> 1; t=0.45: FP=1,FN=1 -> 2; refuse both: FN=1 -> 1. Tie -> refuse both.
    t = calibrate_threshold([(0.4, True), (0.5, False)], fp_cost=1.0)
    assert t == math.nextafter(0.5, math.inf)


def test_calibration_needs_both_classes() -> None:
    with pytest.raises(ValueError, match="both answerable and unanswerable"):
        calibrate_threshold([(0.5, True), (0.6, True)])
    with pytest.raises(ValueError, match="both answerable and unanswerable"):
        calibrate_threshold([])


def test_gate_reasons_and_boundary() -> None:
    gate = Gate(0.7)
    assert gate.decide(None).reason == "no_evidence"
    assert gate.decide(0.69).reason == "low_score"
    assert gate.decide(0.7).answer  # boundary: score == threshold is answered
    assert gate.decide(0.7).reason == "answer"


def test_gate_refuses_when_key_facts_missing_from_evidence() -> None:
    gate = Gate(0.5)
    evidence = "TVPI was 1.8x and the management fee is 2%."
    ok = gate.decide(0.9, draft="TVPI was 1.8x.", evidence=evidence)
    bad = gate.decide(0.9, draft="TVPI was 1.9x.", evidence=evidence)
    assert ok.answer
    assert not bad.answer and bad.reason == "unsupported_facts"
    assert [f.raw for f in bad.unsupported] == ["1.9x"]


def test_low_score_wins_over_fact_check() -> None:
    assert Gate(0.5).decide(0.1, draft="TVPI was 1.8x.", evidence="").reason == "low_score"
