"""FastAPI backend.

Answers only once a gate threshold calibrated on the dev split exists (eval/gate.json, written by
scripts/run_eval.py); otherwise /api/ask and /api/report return 503 instead of guessing one.
"""

import base64
import binascii
import json
import os
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pereport.chunker import Chunk, chunk_pages
from pereport.engine import Answer, Engine
from pereport.gate import Gate
from pereport.ingest import parse_pdf, parse_xlsx
from pereport.report import disclosure_rate, draft_report
from pereport.retrieval import HybridRetriever
from pereport.store import load_chunks
from pereport.verifier import VerifiedAnswer

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
UPLOAD_SUFFIXES = {".pdf", ".xlsx"}


class AskRequest(BaseModel):
    question: str
    doc: str | None = None  # search only this document; None searches all loaded documents


class UploadRequest(BaseModel):
    filename: str
    data_base64: str


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
    chunks = list(chunks)  # grows when a user uploads a document
    uploaded: set[str] = set()
    engines: dict[tuple[str | None, int], Engine] = {}
    by_id = {c.chunk_id: c for c in chunks}

    def need_engine(scope: str | None = None) -> Engine:
        if not chunks:
            raise HTTPException(
                503, "No documents loaded. Run scripts/download.py and build_index.py."
            )
        if threshold is None:
            raise HTTPException(
                503, "Gate threshold not calibrated. Run scripts/run_eval.py on dev."
            )
        key = (scope, len(chunks))
        if key not in engines:
            pool = [c for c in chunks if scope is None or c.doc == scope]
            if not pool:
                raise HTTPException(404, f"Unknown document: {scope}")
            engines[key] = Engine(HybridRetriever(pool), Gate(threshold))
        return engines[key]

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
        return _answer_json(need_engine(req.doc).ask(req.question))

    @app.post("/api/report")
    def report(doc: str | None = None) -> dict[str, Any]:
        sections = draft_report(need_engine(doc))
        got, total = disclosure_rate(sections)
        return {"disclosed": got, "total": total, "sections": [asdict(s) for s in sections]}

    @app.post("/api/upload")
    def upload(req: UploadRequest) -> dict[str, Any]:
        name = Path(req.filename).name
        suffix = Path(name).suffix.lower()
        if suffix not in UPLOAD_SUFFIXES:
            raise HTTPException(415, "Only .pdf and .xlsx files can be uploaded.")
        if len(req.data_base64) > MAX_UPLOAD_BYTES * 4 // 3 + 16:
            raise HTTPException(413, "File is larger than 25 MB.")
        try:
            raw = base64.b64decode(req.data_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(422, "The file data was not valid base64.") from e
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File is larger than 25 MB.")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"upload{suffix}"
            path.write_bytes(raw)
            try:
                parsed = parse_xlsx(path) if suffix == ".xlsx" else parse_pdf(path)
            except Exception as e:
                raise HTTPException(422, f"Could not read this file ({type(e).__name__}).") from e
        existing = {c.doc for c in chunks}
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem)[:60].strip("._") or "document"
        doc, n = stem, 2
        while doc in existing:
            doc, n = f"{stem}_{n}", n + 1
        new = chunk_pages(parsed.pages, doc)
        if not new:
            raise HTTPException(
                422,
                "No text was found in this file. Scanned documents need OCR, which is not run.",
            )
        chunks.extend(new)
        by_id.update({c.chunk_id: c for c in new})
        uploaded.add(doc)
        notes = []
        if suffix == ".xlsx":
            notes.append("Only text cells are indexed; numbers and dates in the sheets are not.")
        if parsed.ocr_pages:
            notes.append(f"Pages {parsed.ocr_pages} look scanned and were skipped (no OCR).")
        notes.append(
            "The refusal threshold was calibrated on other documents, not this one: expect some "
            "wrong refusals, and check every answer against its cited page."
        )
        return {
            "doc": doc,
            "pages": len(parsed.pages),
            "chunks": len(new),
            "kind": "sheets" if suffix == ".xlsx" else "pages",
            "notes": notes,
        }

    @app.get("/api/chunks/{chunk_id}")
    def chunk(chunk_id: str) -> dict[str, Any]:
        if chunk_id not in by_id:
            raise HTTPException(404, "Unknown chunk")
        return _chunk_json(by_id[chunk_id])

    @app.get("/api/documents")
    def documents() -> dict[str, Any]:
        docs: dict[str, dict[str, Any]] = {}
        for c in chunks:
            d = docs.setdefault(
                c.doc,
                {
                    "doc": c.doc,
                    "chunks": 0,
                    "pages": 0,
                    "date": c.date,
                    "uploaded": c.doc in uploaded,
                },
            )
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
