# PEReport — PROGRESS

## Goal
RAG over real, public PE fund documents with citations, refusals and a verifier, plus a report drafter. Scored on a frozen gold set of at least 100 LP questions. See the task brief for exit criteria.

## Loop 0 (environment audit), 2026-10-20
| Check | Result |
|---|---|
| Python 3.13, Node 22, Docker 29, 4 CPU, 15 GB RAM, no GPU, ~30 GB free disk | OK. Embedding and rerank models must run on CPU. |
| `pdfplumber` and `numpy` installed. PyMuPDF, sentence-transformers, rank-bm25, faiss, fastapi, pytest, ruff and mypy not installed | Installable from PyPI. |
| pypi.org, registry.npmjs.org | Reachable (HTTP 200). |
| sec.gov, data.sec.gov, sebi.gov.in, ilpa.org, kkr.com, ir.kkr.com, blackstone.com, carlyle.com, apollo.com, bseindia.com, nseindia.com, s2.q4cdn.com | **Blocked.** Proxy CONNECT returns 403 (network policy). |
| huggingface.co, cdn.jsdelivr.net, arxiv.org | **Blocked.** Same 403. |

## Loop 1, 2026-10-20
Searched for modules A1, A2, A7, A8, A9: all branches (content and filenames), filesystem, /mnt/*. None found.
Retried each data host once: all HTTP 403. Details and IDs in BLOCKERS.md. `sources.csv` has no rows.

Built and committed one component at a time; `make check` (ruff, ruff format, mypy --strict, pytest) after each:

| Commit | Component | Tests after commit |
|---|---|---|
| skeleton | pyproject (py3.13), stubs for A1/A2/A7/A8/A9, BLOCKERS.md, sources.csv | 5 passed |
| chunker | section-aware, page-exact chunk IDs, table rows kept whole | 12 passed |
| bm25 | plain-Python Okapi BM25, hand-worked scores | 18 passed |
| verifier | per-sentence citation, number, date, entity checks; `[calc:]` support | 33 passed |
| gate | dev-calibrated threshold, key-fact check | 40 passed |
| metrics | accuracy, citation P/R, refusal P/R, hallucination, Wilson bound | 46 passed |

BM25 stopword filtering added after the integration test showed "what is the" matching unrelated text. Final: 49 passed.

Defects found by probing and fixed: entity runs fused across possessives; citation after the full stop
attached to the wrong sentence; a number supported by another number's context ("fee is 20%" vs "carry is 20%");
spelled-out numbers unchecked; entity-only gold facts compared case-sensitively.

## Blockers (open)
Modules A1/A2/A7/A8/A9 skipped by user instruction (stubs removed). Network hosts B-N1 to B-N10 still HTTP 403 (rechecked in Loop 2).

## Not done (depends on blockers)
Phase 1 data and manifest, dense and reranker retrieval, real chunking tests on PDFs, gold set, ablations,
report drafter (needs real documents), FastAPI and Next.js app, Playwright demo, docker compose,
viva script, ≥300 MB corpus. The hallucination exit criterion is unmet and, with 100 questions, cannot be shown
at 2% (docs/assumptions.md).

## Next step
When network access and modules arrive: `scripts/download.py` with SHA-256 manifest, PyMuPDF parsing, then gold set.
