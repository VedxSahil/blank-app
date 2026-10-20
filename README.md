# PEReport: Fund Document Assistant (work in progress)

Retrieval with citations, an answer verifier and a refusal gate for private-equity fund documents.
Research question: how much of an LP's quarterly question set can be answered from fund documents
automatically?

**Latest:** the official ILPA Reporting Template v2.0 (real, public, a template) is now indexed and evaluated
(`eval/ilpa/`): held-out test 52.2% accuracy, 2 hallucinations in 11 answers, 5 of 7 unanswerable questions refused.
See `docs/viva_script.md`. Numbers below for the replica PPM are older and separate.

**Status:** the engine, evaluation harness, API and web app are built and tested. They have run end to end on one
document: `data/sample/Aurelian_Peak_Fund_Sample_PPM.pdf`, a replica of a real PPM with the names changed, supplied
by the owner. Results on it (BM25 only, 23 held-out questions: 69.6% accuracy, 1 hallucination in 13 answers, 6 of 7
unanswerable questions refused) are pipeline tests, **not** results on real public disclosures. No SEBI, 10-K or
ILPA documents or model weights could be downloaded (BLOCKERS.md), so the research question is still unanswered. See
`BLOCKERS.md`, `PROGRESS.md`, `docs/assumptions.md`, `docs/governance.md`, `docs/viva_script.md`.

```
pereport/ingest.py      PDF -> pages (PyMuPDF); .xlsx -> one page per sheet, text only
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
# on the replica sample PPM (what the viva script uses):
python scripts/build_index.py --src data/sample --out data/chunks_sample
python scripts/run_eval.py eval/sample/gold.jsonl --chunks data/chunks_sample --out eval/sample/dev
# with real data (after adding URLs to data/targets.json):
python scripts/download.py && python scripts/build_index.py
python scripts/run_eval.py eval/gold.jsonl --freeze
uvicorn pereport.api:app_from_disk --factory & (cd web && npm run build && npm run start)
```
Design file (Figma): https://www.figma.com/design/aqJtZ1gjUwugO2cEWavlgM

`docker-compose.yml` exists but is untested (no Docker daemon was available).
