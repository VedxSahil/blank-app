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

## Blockers (open)
1. **B1: Phase 1 is impossible.** None of the document hosts are reachable, so no real PDFs can be downloaded. Per the hard rules, no stand-in data is created.
2. **B2: No dense or rerank model weights.** bge/e5 and the cross-encoder come from huggingface.co, which is blocked. The dense, hybrid and rerank ablations cannot run until it is allowed.
3. **B3: Modules A1, A2, A7, A8, A9 not supplied.** They will be reused as given, not reinvented.
4. **B4: Existing repo is a Streamlit template.** It needs `requires-python >=3.14`, but this container has 3.13. The repo layout (`pyproject.toml`, `uv.lock`) will need adapting.

## Next step (once B1 to B3 are cleared)
Phase 1: `scripts/download.py` with a manifest (URL, date, SHA-256), then PyMuPDF parsing with page numbers preserved.

## Checklist
- [ ] Phase 1 data (≥300 MB real content)
- [ ] Phase 2 engine
- [ ] Phase 3 evaluation (gold set ≥100 questions, frozen)
- [ ] Phase 4 app
- [ ] Phase 5 quality gates
- [ ] Docs: README, viva script

## Test results
None yet. Nothing has been built or run.
