"""Run the ablation study on the dev split (and, with --test, the frozen test split).

Usage: python scripts/run_eval.py eval/gold.jsonl [--test] [--freeze]
Needs data/chunks/*.jsonl (scripts/build_index.py). Configurations whose models cannot be loaded
are skipped and listed in the report; nothing is substituted.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pereport.engine import Engine
from pereport.evalrun import (
    calibrate_gate_threshold,
    freeze_gold,
    load_gold,
    metrics_json,
    run_split,
    write_charts,
    write_report,
    write_results_csv,
)
from pereport.gate import Gate
from pereport.models import (
    CachedEmbedder,
    CrossEncoderReranker,
    ModelUnavailable,
    SentenceTransformerEmbedder,
)
from pereport.retrieval import HybridRetriever
from pereport.store import load_chunks

# name: (use_bm25, dense, rerank, gate, verifier)
CONFIGS = {
    "bm25": (True, False, False, False, False),
    "dense": (False, True, False, False, False),
    "hybrid": (True, True, False, False, False),
    "bm25+gate+verifier": (True, False, False, True, True),
    "hybrid+rerank+gate+verifier": (True, True, True, True, True),
}


def main(argv: list[str]) -> int:
    gold_path = Path(argv[1])
    questions = load_gold(gold_path)
    if "--freeze" in argv:
        print("frozen, sha256", freeze_gold(gold_path))
    chunk_files = sorted(Path("data/chunks").glob("*.jsonl"))
    if not chunk_files:
        print("no chunks in data/chunks (run scripts/build_index.py on real PDFs first)")
        return 1
    chunks = [c for f in chunk_files for c in load_chunks(f)]
    dev = [q for q in questions if q.split == "dev"]
    split = "test" if "--test" in argv else "dev"
    skipped: list[str] = []
    results = {}
    embedder = reranker = None
    try:
        embedder = CachedEmbedder(
            SentenceTransformerEmbedder(), "bge-small-en-v1.5", "data/index/embeddings.sqlite"
        )
        reranker = CrossEncoderReranker()
    except ModelUnavailable as e:
        skipped.append(str(e))
    for name, (bm25, dense, rerank, gate_on, ver_on) in CONFIGS.items():
        if (dense or rerank) and (embedder is None or (rerank and reranker is None)):
            skipped.append(f"{name}: skipped, model unavailable")
            continue
        retriever = HybridRetriever(
            chunks, embedder if dense else None, reranker if rerank else None, use_bm25=bm25
        )
        threshold = calibrate_gate_threshold(retriever, dev) if gate_on else float("-inf")
        if name == "bm25+gate+verifier":  # the configuration the API serves
            Path("eval").mkdir(exist_ok=True)
            Path("eval/gate.json").write_text(json.dumps({"bm25": threshold}) + "\n")
        engine = Engine(retriever, Gate(threshold), use_gate=gate_on, use_verifier=ver_on)
        results[name] = run_split(engine, questions, split, gold_path, name)
    note = "Skipped configurations: " + "; ".join(skipped) if skipped else ""
    Path("eval").mkdir(exist_ok=True)
    metrics = write_report("eval/report.md", split, results, note)
    Path("eval/metrics.json").write_text(metrics_json(metrics))
    write_results_csv("eval/results.csv", results)
    write_charts("eval/charts", metrics)
    print(Path("eval/report.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
