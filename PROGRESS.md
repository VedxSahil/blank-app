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

## Loop 2, 2026-10-20 (user: skip A1/A2/A7/A8/A9 and proceed)
Modules dropped (stubs removed). Network rechecked: still HTTP 403 for every document and model host.
Built one component per commit; `make check` (ruff, ruff format, mypy --strict, pytest) after each.

| Commit | Component | pytest after |
|---|---|---|
| stubs removed | docs updated | 44 |
| ingest | PyMuPDF pages + table rows, chunk store, SHA-256 download manifest | 49 |
| retrieval | BM25 + dense via RRF, optional reranker (fake models in tests) | 56 |
| engine | gate + extractive generator + verifier + ablation switches | 64 |
| report | ILPA-style drafter bound to chunk IDs | 71 |
| evalrun | gold validation, freeze lock, dev-only calibration, report/CSV/charts | 76 |
| models + CLIs | bge/cross-encoder wrappers, SQLite cache, build_index, run_eval | 79 |
| api | FastAPI, 503 until gate calibrated | 83 |
| web | Next.js app, Playwright e2e (11), axe light and dark, 375 px overflow check | 83 + 11 e2e |

Final gates run in this environment: `make check` exit 0 (83 passed); `tsc`, `eslint`, `next build` exit 0;
Playwright 11 passed.

Defects found by tests and fixed this loop:
- Report test: an IRR question answered with a NAV sentence (shared words "net", "fund"). Added mandatory
  acronym/number rule, glossary expansion, plural stemming.
- Table answers returned only the header row. Data rows now inherit header terms and show the header.
- Next config rewrite dropped the Tailwind loader, so the CSS bundle was 1.3 KB and the UI was unstyled while
  all behavioural tests still passed. Restored (17 KB) and checked with screenshots.
- axe: nav links in dark mode used default link blue (contrast 2:1); chip accessible name lacked its visible
  text. 375 px overflow from an absolutely positioned table caption.
- Process slips: two commits were made with a failing check because of `;` and `| tail` hiding the exit
  status. Both were fixed in the next commit; later commits gate on `make check` directly.

## Figma (2026-10-20)
Design file: https://www.figma.com/design/aqJtZ1gjUwugO2cEWavlgM ("PEReport UI screens"). Seven editable
auto-layout frames: Ask answer and refusal (light and dark), Report Builder, Evaluation, Documents. Colours are
variables in two collections (`PEReport tokens`, `PEReport tokens (dark)`; the starter plan allows one mode per
collection). Read-back audit: 0 image fills, every solid fill bound to a variable. Content is bracketed placeholders
and em dashes; no fund data. A first render showed clipped table cells (fixed 10 px height) and an overlapping
header; fixed and re-rendered. Font is Inter, the closest to the app's system font stack. The frames were built to
match the shipped web app, not the other way round, so the app remains the source of truth.

## Exit criteria status
| Criterion | Status |
|---|---|
| Zero test/lint/build errors | Met for what exists (above). Docker build not run. |
| Hallucination ≤ 2% on frozen test set | **Not measured.** No gold set. Also needs ≥188 answered questions with zero errors to bound at 2%. |
| Demo answers verified against source pages | **Not met.** No real documents. |
| Refusal works on unsupported questions | Works on fixture tests; unproven on real documents. |
| ≥300 MB of real data and indexes | **Not met.** `data/` holds only an empty `targets.json`. |
| README with setup, architecture, viva script | README and docs/viva_script.md written; the viva table is blank by design. |
| docker compose fresh-clone run | **Not met.** No Docker daemon (B-D1). |

## Blockers (open)
See BLOCKERS.md: network hosts B-N1 to B-N10 (HTTP 403), Docker B-D1, tooling B-T1 to B-T4. Modules A1/A2/A7/A8/A9
were skipped by instruction.

## Next step
Once the document and model hosts are allowed: choose real URLs in `data/targets.json`, run download and
build_index, write the gold set by hand from the real pages (≥188 test-split answerable/partial questions if the
2% claim is to be shown), freeze it, run `scripts/run_eval.py`, then fill `docs/viva_script.md`.
