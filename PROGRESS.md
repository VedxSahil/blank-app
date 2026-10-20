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

## Loop 3, 2026-10-20 (user supplied the replica PPM and said to use it)
Context: the owner explained the file is a replica of a real document with the names changed. It states it is
fictional, so it is treated as a labelled sample (data/sample/README.md, banner in the app, separate manifest),
and results on it are not reported as real-data results.

Defects the first real PDF exposed, all fixed with tests:
- Table cells came out with spaces stripped ("Open-endedZandrianpublic..."): cells are now read from their own boxes.
- Tables arrived one visual line per row: rows regrouped by the PDF's ruled separators (heuristic fallback).
- Prose with figures was classified as a table and split into fragments; a 9-row term sheet was one diluted chunk:
  tables now need cell gaps, and each row is its own chunk.
- Verifier false positive: a number inside an entity ("Category 1 Global Business Licence") corrupted it.
- Raw BM25 scores depend on query length (refused "What is the management fee?"): gate now uses a 0..1 normalised score.
- Weak stemming (closing/close), question filler words, run-in headings ("Directors' remuneration. USD 1,500"),
  numbered-list markers leaking into sentences.

Evaluation (eval/sample/, 48 questions: 30 answerable, 3 partial, 15 unanswerable; dev 25 / test 23; gold frozen,
SHA-256 24c239ea...; labels audited mechanically, 4 page labels corrected):
| Split | Config | Accuracy | Answered correctly | Hallucinations / answers | Unanswerable refused |
|---|---|---|---|---|---|
| dev (used for tuning) | bm25 | 68.0% | 64.0% | 7/24 | 1 of 8 |
| dev (used for tuning) | bm25+gate+verifier | 84.0% | 60.0% | 2/18 | 6 of 8 |
| test (scored once, commit 1a31590) | bm25 | 60.9% | 60.9% | 7/23 | 0 of 7 |
| test (scored once, commit 1a31590) | bm25+gate+verifier | 69.6% | 43.5% | 1/13 | 6 of 7 |
Dense, hybrid and reranker rows skipped (model weights unreachable). The dev-to-test drop (84% to 70%) is what
fitting to a small dev set looks like.
Gates: `make check` 97 passed; tsc, eslint, next build clean; Playwright 12 passed (axe, banner, 375 px).

## Loop 4, 2026-10-20 (user uploaded the official ILPA Reporting Template v2.0)
First genuine public document. A template, so it tests definitions and structure, not fund answers. Registered in
`data/real/` (SHA-256 3a6582e7...), `sources.csv`, `data/real/manifest.json`.
Built: `parse_xlsx` (one page per sheet, text only, headings and line items inferred; example figures never indexed);
chunker recognises "# " and "A.1" headings. Defects found on the real file and fixed with tests:
- A definition row holds several sentences; citing the row once made the verifier strip all but the first
  (faithfulness 66.7%). Each sentence is now cited separately (faithfulness 100%).
- Layout rows tied with definition rows and won on retrieval order: layout rows now lose ties.
- A synthesised second cell (the section name) read like a field value ("Parent Fund Size: Fund of Funds-Underlying"):
  reworded to "(template line item in <path>)".
- A bold heading row carrying its first item (Reconciliation for ...) was missed, giving a wrong section path.
Evaluation (eval/ilpa/, 48 questions: 30 answerable, 3 partial, 15 unanswerable; dev 25 / test 23; gold frozen,
SHA-256 413abce3...; one page list corrected after the audit):
| Split | Config | Accuracy | Answered correctly | Hallucinations / answers | Unanswerable refused |
|---|---|---|---|---|---|
| dev (tuned on) | bm25+gate+verifier | 76.0% | 44.0% | 0/13 | 8 of 8 |
| test (scored once, commit a1284f8) | bm25 | 56.5% | 52.2% | 6/22 | 1 of 7 |
| test (scored once, commit a1284f8) | bm25+gate+verifier | 52.2% | 30.4% | 2/11 | 5 of 7 |
The parser fixes after the test run were not re-scored on test (see docs/assumptions.md). Dense, hybrid and rerank
rows still skipped. Regression: the replica PPM dev split moved from 84% to 80% with the engine changes.
Gates: `make check` 104 passed; tsc and eslint clean; Playwright 12 passed.

## Exit criteria status
| Criterion | Status |
|---|---|
| Zero test/lint/build errors | Met for what exists (above). Docker build not run. |
| Hallucination ≤ 2% on frozen test set | **Not met.** Sample test split: 1/13 answers (7.7%, 95% upper bound 33%). Needs a real corpus and ≥188 error-free answers to show 2%. |
| Demo answers verified against source pages | **Met on the ILPA template** (3 answers and 1 refusal compared with workbook cells by the author; cell references in docs/viva_script.md; owner re-check pending). Not on real fund documents. |
| Refusal works on unsupported questions | Works on the sample: 6 of 7 unanswerable test questions refused, 1 missed ("legal advisors in Calderon"). Not shown on real disclosures. |
| ≥300 MB of real data and indexes | **Not met.** One real 125 KB template (ILPA v2.0) plus the 524 KB replica PPM. |
| README with setup, architecture, viva script | README and docs/viva_script.md written; the viva table is blank by design. |
| docker compose fresh-clone run | **Not met.** No Docker daemon (B-D1). |

## Blockers (open)
See BLOCKERS.md: network hosts B-N1 to B-N10 (HTTP 403), Docker B-D1, tooling B-T1 to B-T4. Modules A1/A2/A7/A8/A9
were skipped by instruction.

## Next step
Once the document and model hosts are allowed: choose real URLs in `data/targets.json`, run download and
build_index, write the gold set by hand from the real pages (≥188 test-split answerable/partial questions if the
2% claim is to be shown), freeze it, run `scripts/run_eval.py`, then fill `docs/viva_script.md`.
