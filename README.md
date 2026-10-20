# PEReport: Fund Document Assistant (work in progress)

Retrieval with citations, an answer verifier and a refusal gate for private-equity fund documents.
Research question: how much of an LP's quarterly question set can be answered from fund documents
automatically?

**Status:** the engine, evaluation harness, API and web app are built and tested on invented fixture text.
No real documents, model weights or gold set are in the repo, so no accuracy result exists yet. See
`BLOCKERS.md`, `PROGRESS.md`, `docs/assumptions.md`, `docs/governance.md`, `docs/viva_script.md`.

```
pereport/ingest.py      PDF -> pages (PyMuPDF), page numbers and table rows preserved
pereport/chunker.py     section-aware chunks with doc, page, section, date, fund metadata
pereport/bm25.py        Okapi BM25 (plain Python)
pereport/retrieval.py   BM25 + dense (RRF) + optional reranker, models injected
pereport/models.py      bge embedder, cross-encoder, SQLite embedding cache (lazy imports)
pereport/gate.py        refuse on no evidence, low score (dev-calibrated) or unsupported facts
pereport/engine.py      retrieve -> gate -> extractive answer -> verifier, ablation switches
pereport/verifier.py    every number, date and entity must be in the cited chunk, else stripped
pereport/report.py      ILPA-style report; lines bound to chunk IDs; gaps say "Not disclosed..."
pereport/evalrun.py     gold set, freeze lock, dev-only calibration, metrics, report, charts
pereport/metrics.py     accuracy, citation P/R, refusal P/R, hallucination with Wilson bound
pereport/api.py         FastAPI (503 until the gate is calibrated)
web/                    Next.js app: Ask, Refusal, Report Builder, Evaluation, Documents
scripts/                download.py, build_index.py, run_eval.py, serve_fixture.py (tests only)
```

## Run
```
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -e '.[dev]'
make check                 # ruff, ruff format, mypy --strict, pytest
make web-check             # tsc, eslint, next build
make e2e                   # Playwright + axe on the FIXTURE corpus
# with real data (after adding URLs to data/targets.json):
python scripts/download.py && python scripts/build_index.py
python scripts/run_eval.py eval/gold.jsonl --freeze
uvicorn pereport.api:app_from_disk --factory & (cd web && npm run build && npm run start)
```
Design file (Figma): https://www.figma.com/design/aqJtZ1gjUwugO2cEWavlgM

`docker-compose.yml` exists but is untested (no Docker daemon was available).
