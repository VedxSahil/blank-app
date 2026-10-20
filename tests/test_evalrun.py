"""Eval harness tests. Gold questions and corpus are TEST FIXTURES (invented)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pereport.chunker import Chunk
from pereport.engine import Engine
from pereport.evalrun import (
    GoldError,
    calibrate_gate_threshold,
    freeze_gold,
    is_frozen,
    load_gold,
    run_split,
    write_charts,
    write_report,
    write_results_csv,
)
from pereport.gate import Gate
from pereport.metrics import EvalRecord
from pereport.retrieval import HybridRetriever

CORPUS = [
    Chunk(
        "fx:p1:c0",
        "fx",
        1,
        "S",
        None,
        None,
        "text",
        "The management fee is 2% of committed capital.",
    ),
    Chunk("fx:p2:c0", "fx", 2, "S", None, None, "text", "Carry is 20% over an 8% hurdle."),
]
GOLD: list[dict[str, object]] = [
    {"id": "d1", "question": "What is the management fee?", "category": "answerable", "split": "dev",
     "gold_facts": ["2%"], "gold_pages": [["fx", 1]]},
    {"id": "d2", "question": "What is the carry?", "category": "answerable", "split": "dev",
     "gold_facts": ["20%"], "gold_pages": [["fx", 2]]},
    {"id": "d3", "question": "What is the catch-up waterfall?", "category": "unanswerable", "split": "dev"},
    {"id": "t1", "question": "What is the management fee?", "category": "answerable", "split": "test",
     "gold_facts": ["2%"], "gold_pages": [["fx", 1]]},
    {"id": "t2", "question": "What is the clawback?", "category": "unanswerable", "split": "test"},
]  # fmt: skip


def _write(tmp: Path, rows: list[dict[str, object]]) -> Path:
    p = tmp / "gold.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_load_and_validate(tmp_path: Path) -> None:
    qs = load_gold(_write(tmp_path, GOLD))
    assert [q.id for q in qs] == ["d1", "d2", "d3", "t1", "t2"]
    assert qs[0].gold_pages == [("fx", 1)]
    bad_cases = [
        ({**GOLD[0], "category": "maybe"}, "bad category"),
        ({**GOLD[0], "split": "val"}, "bad split"),
        ({**GOLD[2], "gold_facts": ["x"]}, "unanswerable question has gold"),
        ({**GOLD[0], "gold_pages": []}, "needs gold_facts and gold_pages"),
        (GOLD[0], "duplicate id"),
    ]
    for row, msg in bad_cases:
        rows = [GOLD[0], row] if msg == "duplicate id" else [row]
        with pytest.raises(GoldError, match=msg):
            load_gold(_write(tmp_path, rows))


def test_freeze_lock_detects_edits(tmp_path: Path) -> None:
    p = _write(tmp_path, GOLD)
    assert not is_frozen(p)
    freeze_gold(p)
    assert is_frozen(p)
    p.write_text(p.read_text() + "\n")
    assert not is_frozen(p)


def test_test_split_needs_lock_and_is_logged(tmp_path: Path) -> None:
    p = _write(tmp_path, GOLD)
    qs = load_gold(p)
    engine = Engine(HybridRetriever(CORPUS), Gate(0.1))
    with pytest.raises(GoldError, match="freeze lock"):
        run_split(engine, qs, "test", p)
    freeze_gold(p)
    when = datetime(2026, 5, 6, 7, 8, 9, tzinfo=UTC)
    recs = run_split(engine, qs, "test", p, config="bm25+gate", now=when)
    # t1 answered correctly with the fee sentence on page 1; t2 refused (no evidence)
    by = {r.qid: r for r in recs}
    assert not by["t1"].refused and by["t1"].cited_pages == {("fx", 1)}
    assert by["t2"].refused
    assert (
        Path(f"{p}.testruns.log").read_text()
        == "2026-05-06T07:08:09+00:00\tbm25+gate\t2 questions\n"
    )
    assert len(run_split(engine, qs, "dev")) == 3  # dev needs no lock and writes no log


def test_calibration_uses_dev_only(tmp_path: Path) -> None:
    qs = load_gold(_write(tmp_path, GOLD))
    retriever = HybridRetriever(CORPUS)
    t = calibrate_gate_threshold(retriever, [q for q in qs if q.split == "dev"])
    answerable_scores = [retriever.search(q.question).top_score for q in qs if q.id in ("d1", "d2")]
    lo = min(s for s in answerable_scores if s is not None)
    # d3 scores 0.0 (no evidence); hand-worked: best cut is the midpoint (0 + lo) / 2
    assert t == pytest.approx(lo / 2)


def test_report_csv_charts_from_hand_records(tmp_path: Path) -> None:
    good = EvalRecord("a", "answerable", ["2%"], frozenset({("d", 1)}), "Fee 2% [d, p.1]",
                      frozenset({("d", 1)}), False)  # fmt: skip
    refused = EvalRecord("u", "unanswerable", [], frozenset(), "", frozenset(), True)
    results = {"fixture-config": [good, refused]}
    metrics = write_report(tmp_path / "report.md", "dev", results, note="Fixture run.")
    text = (tmp_path / "report.md").read_text()
    m = metrics["fixture-config"]
    assert m.auto_answer_rate == 0.5 and m.hallucinations == 0 and m.answered == 1
    # Wilson upper for 0/1: z^2/(n+z^2) = 3.8416/4.8416 = 79.3%
    assert (
        "| fixture-config | 2 | 100.0% | 50.0% | 0/1 (0.0%) | 79.3% | 100.0% | 100.0% | 100.0% |"
        in text
    )
    assert "Fixture run." in text and "| unanswerable | 1 | 0 | 1 | 1 |" in text
    write_results_csv(tmp_path / "results.csv", results)
    rows = (tmp_path / "results.csv").read_text().splitlines()
    assert rows[0].startswith("config,qid,category,refused") and len(rows) == 3
    assert "fixture-config,a,answerable,False,True,d:1" in rows[1]
    charts = write_charts(tmp_path / "charts", metrics)
    assert [c.name for c in charts] == [
        "auto_answer_rate.png",
        "hallucination_rate.png",
        "refusal_recall.png",
    ]
    assert all(c.stat().st_size > 1000 for c in charts)
