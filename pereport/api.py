"""FastAPI backend.

Answers only once a gate threshold calibrated on the dev split exists (eval/gate.json, written by
scripts/run_eval.py); otherwise /api/ask and /api/report return 503 instead of guessing one.
"""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pereport.chunker import Chunk
from pereport.engine import Answer, Engine
from pereport.gate import Gate
from pereport.report import disclosure_rate, draft_report
from pereport.retrieval import HybridRetriever
from pereport.store import load_chunks
from pereport.verifier import VerifiedAnswer


class AskRequest(BaseModel):
    question: str


def _chunk_json(c: Chunk) -> dict[str, Any]:
    return asdict(c)


def _answer_json(a: Answer) -> dict[str, Any]:
    v = a.verification
    return {
        "question": a.question,
        "text": a.text,
        "refused": a.refused,
        "reason": a.reason,
        "mode": a.mode,
        "top_score": a.top_score,
        "sources": [_chunk_json(c) for c in a.sources],
        "stripped": [{"sentence": s.sentence, "reasons": s.reasons} for s in v.stripped]
        if v
        else [],
        "verified": bool(v and v.passed),
    }


def _stripped_json(v: VerifiedAnswer | None) -> list[dict[str, Any]]:
    return [{"sentence": s.sentence, "reasons": s.reasons} for s in v.stripped] if v else []


def load_threshold(path: Path) -> float | None:
    if not path.exists():
        return None
    return float(json.loads(path.read_text())["bm25"])


def create_app(
    chunks: list[Chunk],
    threshold: float | None,
    manifest: list[dict[str, Any]] | None = None,
    eval_metrics: dict[str, Any] | None = None,
    banner: str | None = None,
) -> FastAPI:
    app = FastAPI(title="PEReport", version="0.1.0")
    engine = (
        Engine(HybridRetriever(chunks), Gate(threshold))
        if chunks and threshold is not None
        else None
    )
    by_id = {c.chunk_id: c for c in chunks}

    def need_engine() -> Engine:
        if not chunks:
            raise HTTPException(
                503, "No documents loaded. Run scripts/download.py and build_index.py."
            )
        if engine is None:
            raise HTTPException(
                503, "Gate threshold not calibrated. Run scripts/run_eval.py on dev."
            )
        return engine

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "chunks": len(chunks),
            "calibrated": threshold is not None,
            "banner": banner,
        }

    @app.post("/api/ask")
    def ask(req: AskRequest) -> dict[str, Any]:
        if not req.question.strip():
            raise HTTPException(422, "Empty question")
        return _answer_json(need_engine().ask(req.question))

    @app.post("/api/report")
    def report() -> dict[str, Any]:
        sections = draft_report(need_engine())
        got, total = disclosure_rate(sections)
        return {"disclosed": got, "total": total, "sections": [asdict(s) for s in sections]}

    @app.get("/api/chunks/{chunk_id}")
    def chunk(chunk_id: str) -> dict[str, Any]:
        if chunk_id not in by_id:
            raise HTTPException(404, "Unknown chunk")
        return _chunk_json(by_id[chunk_id])

    @app.get("/api/documents")
    def documents() -> dict[str, Any]:
        docs: dict[str, dict[str, Any]] = {}
        for c in chunks:
            d = docs.setdefault(c.doc, {"doc": c.doc, "chunks": 0, "pages": 0, "date": c.date})
            d["chunks"] += 1
            d["pages"] = max(d["pages"], c.page)
        meta = {Path(m["local_path"]).stem: m for m in manifest or []}
        for name, d in docs.items():
            m = meta.get(name)
            d.update({k: m[k] for k in ("url", "publisher", "date_pulled", "sha256")} if m else {})
        return {"documents": list(docs.values())}

    @app.get("/api/eval")
    def evaluation() -> dict[str, Any]:
        if eval_metrics is None:
            return {"available": False}
        return {"available": True, "metrics": eval_metrics}

    return app


def app_from_disk() -> FastAPI:
    """Serve chunks and eval output from disk.

    PEREPORT_CHUNKS, PEREPORT_EVAL and PEREPORT_MANIFEST choose other locations (for example the
    replica sample PPM); PEREPORT_BANNER shows a notice strip on every screen of the web app.
    """
    chunks_dir = Path(os.environ.get("PEREPORT_CHUNKS", "data/chunks"))
    eval_dir = Path(os.environ.get("PEREPORT_EVAL", "eval"))
    mpath = Path(os.environ.get("PEREPORT_MANIFEST", "data/manifest.json"))
    chunks = [c for f in sorted(chunks_dir.glob("*.jsonl")) for c in load_chunks(f)]
    epath = eval_dir / "metrics.json"
    return create_app(
        chunks,
        load_threshold(eval_dir / "gate.json"),
        json.loads(mpath.read_text()) if mpath.exists() else None,
        json.loads(epath.read_text()) if epath.exists() else None,
        os.environ.get("PEREPORT_BANNER"),
    )
