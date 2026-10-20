"""Evaluation harness: gold set, freeze lock, calibration on dev, scoring, ablations, outputs.

Gold file (JSONL), one question per line:
  {"id", "question", "category": answerable|partial|unanswerable, "split": dev|test,
   "gold_answer", "gold_facts": [str], "gold_pages": [[doc, page]], "notes"}
answerable/partial need gold_facts and gold_pages; unanswerable must have neither.

Freeze: `freeze_gold` writes <gold>.lock with the file's SHA-256. The test split can only be run
while the lock matches, and every test run is appended to <gold>.testruns.log, so tuning on the
test split leaves a visible trail.
"""

import csv
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from pereport.engine import Answer, Engine, expand_question
from pereport.fetch import sha256_file
from pereport.gate import calibrate_threshold
from pereport.metrics import CATEGORIES, EvalRecord, Metrics, compute_metrics
from pereport.retrieval import HybridRetriever


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    category: str
    split: str
    gold_answer: str
    gold_facts: list[str]
    gold_pages: list[tuple[str, int]]
    notes: str = ""


class GoldError(ValueError):
    pass


def load_gold(path: str | Path) -> list[Question]:
    qs: list[Question] = []
    seen: set[str] = set()
    with Path(path).open(encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            d = json.loads(line)
            q = Question(
                d["id"],
                d["question"],
                d["category"],
                d["split"],
                d.get("gold_answer", ""),
                list(d.get("gold_facts", [])),
                [(p[0], int(p[1])) for p in d.get("gold_pages", [])],
                d.get("notes", ""),
            )
            where = f"{path}:{n} ({q.id})"
            if q.id in seen:
                raise GoldError(f"duplicate id at {where}")
            seen.add(q.id)
            if q.category not in CATEGORIES:
                raise GoldError(f"bad category {q.category!r} at {where}")
            if q.split not in ("dev", "test"):
                raise GoldError(f"bad split {q.split!r} at {where}")
            if q.category == "unanswerable" and (q.gold_facts or q.gold_pages):
                raise GoldError(f"unanswerable question has gold facts/pages at {where}")
            if q.category != "unanswerable" and not (q.gold_facts and q.gold_pages):
                raise GoldError(f"{q.category} question needs gold_facts and gold_pages at {where}")
            qs.append(q)
    return qs


def freeze_gold(path: str | Path) -> str:
    digest = sha256_file(path)
    Path(f"{path}.lock").write_text(digest + "\n")
    return digest


def is_frozen(path: str | Path) -> bool:
    lock = Path(f"{path}.lock")
    return lock.exists() and lock.read_text().strip() == sha256_file(path)


def calibrate_gate_threshold(
    retriever: HybridRetriever, dev: list[Question], fp_cost: float = 3.0
) -> float:
    """Gate threshold from DEV questions only: top retrieval score vs answerable or not."""
    pairs = [
        (
            retriever.search(expand_question(q.question)).top_score or 0.0,
            q.category != "unanswerable",
        )
        for q in dev
    ]
    return calibrate_threshold(pairs, fp_cost=fp_cost)


def to_record(q: Question, a: Answer) -> EvalRecord:
    return EvalRecord(
        qid=q.id,
        category=q.category,
        gold_facts=q.gold_facts,
        gold_pages=frozenset(q.gold_pages),
        answer="" if a.refused else a.text,
        cited_pages=a.cited_pages,
        refused=a.refused,
        verifier_passed=a.verification.passed if a.verification else a.refused,
        unsupported_facts=a.draft_unsupported,
    )


def run_split(
    engine: Engine,
    questions: list[Question],
    split: str,
    gold_path: str | Path | None = None,
    config: str = "",
    now: datetime | None = None,
) -> list[EvalRecord]:
    """Score one split. The test split requires a matching freeze lock and is logged."""
    chosen = [q for q in questions if q.split == split]
    if split == "test":
        if gold_path is None or not is_frozen(gold_path):
            raise GoldError("test split requires a gold file whose freeze lock matches")
        stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
        with Path(f"{gold_path}.testruns.log").open("a") as log:
            log.write(f"{stamp}\t{config}\t{len(chosen)} questions\n")
    return [to_record(q, engine.ask(q.question)) for q in chosen]


CSV_FIELDS = ["config", "qid", "category", "refused", "correct_facts", "cited_pages", "answer"]


def write_results_csv(path: str | Path, rows: dict[str, list[EvalRecord]]) -> None:
    from pereport.metrics import is_correct

    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for config, records in rows.items():
            for r in records:
                pages = ";".join(f"{d}:{p}" for d, p in sorted(r.cited_pages))
                w.writerow([config, r.qid, r.category, r.refused, is_correct(r), pages, r.answer])


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def write_report(
    path: str | Path, split: str, results: dict[str, list[EvalRecord]], note: str = ""
) -> dict[str, Metrics]:
    """Write eval/report.md from computed metrics only; returns the metrics per config."""
    metrics = {c: compute_metrics(r) for c, r in results.items()}
    lines = [f"# Evaluation report ({split} split)", "", note, ""] if note else [
        f"# Evaluation report ({split} split)", ""
    ]  # fmt: skip
    lines += [
        "| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | "
        "Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c, m in metrics.items():
        hal = f"{m.hallucinations}/{m.answered} ({_pct(m.hallucination_rate)})"
        cells = [
            c, str(m.n), _pct(m.answer_accuracy), _pct(m.auto_answer_rate), hal,
            _pct(m.hallucination_upper_95), _pct(m.faithfulness), _pct(m.citation_precision),
            _pct(m.citation_recall), _pct(m.refusal_precision), _pct(m.refusal_recall),
        ]  # fmt: skip
        lines.append("| " + " | ".join(cells) + " |")
    for c, m in metrics.items():
        lines += [
            "",
            f"## Per-category: {c}",
            "",
            "| Category | N | Answered | Refused | Correct |",
            "|---|---|---|---|---|",
        ]
        for cat in CATEGORIES:
            d = m.by_category[cat]
            lines.append(
                f"| {cat} | {d['n']} | {d['answered']} | {d['refused']} | {d['correct']} |"
            )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return metrics


def write_charts(out_dir: str | Path, metrics: dict[str, Metrics]) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    configs = list(metrics)
    paths: list[Path] = []

    def bars(name: str, title: str, get: Callable[[Metrics], float | None]) -> None:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        vals = [100 * (get(m) or 0.0) for m in metrics.values()]
        ax.bar(configs, vals, color="#2a6f97")
        ax.set_ylabel("%")
        ax.set_title(title)
        ax.set_ylim(0, 100)
        for i, v in enumerate(vals):
            ax.text(i, v + 1, f"{v:.1f}", ha="center", fontsize=8)
        plt.xticks(rotation=20, ha="right", fontsize=8)
        fig.tight_layout()
        p = out / f"{name}.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(p)

    bars(
        "auto_answer_rate",
        "Questions answered automatically and correctly",
        lambda m: m.auto_answer_rate,
    )
    bars(
        "hallucination_rate",
        "Hallucination rate (of answers emitted)",
        lambda m: m.hallucination_rate,
    )
    bars(
        "refusal_recall",
        "Refusal recall (unanswerable questions refused)",
        lambda m: m.refusal_recall,
    )
    return paths


def metrics_json(metrics: dict[str, Metrics]) -> str:
    return json.dumps({c: asdict(m) for c, m in metrics.items()}, indent=2)
