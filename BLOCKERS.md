# BLOCKERS

Last audited: 2026-10-20. Each network host was tried once and returned HTTP 403 from the egress proxy
(`CONNECT` refused: environment network policy). Not retried, per instruction.

## User modules A1, A2, A7, A8, A9
**Skipped by the user's instruction (2026-10-20).** They were never found (searched all branches, the filesystem
and /mnt). Their stubs were removed. Nothing in this project depends on them:
- computed numbers use `pereport` code with hand-worked tests, not A8;
- retrieval is `pereport.bm25` plus hybrid fusion, not A2;
- `docs/governance.md` stands alone, with no A7 to reconcile against.

## Blocked network sources (HTTP 403, policy denial)
| ID | URL tried | Needed for |
|---|---|---|
| B-N1 | https://www.sebi.gov.in/ (AIF disclosures) | SEBI AIF documents |
| B-N2 | https://ilpa.org/reporting-template/ | ILPA Reporting Template, Capital Call and Distribution Notice, DDQ |
| B-N3 | https://www.sec.gov/ | KKR, Blackstone, Apollo, Carlyle 10-Ks |
| B-N4 | https://ir.kkr.com/, https://www.kkr.com/ | KKR reports |
| B-N5 | https://ir.blackstone.com/ | Blackstone reports |
| B-N6 | https://ir.carlyle.com/ | Carlyle reports |
| B-N7 | https://ir.apollo.com/ | Apollo reports |
| B-N8 | https://www.bseindia.com/, https://www.nseindia.com/ | Indian listed PE/AIF-linked entities |
| B-N9 | https://huggingface.co/BAAI/bge-small-en-v1.5/... | dense embedding model weights |
| B-N10 | https://huggingface.co/BAAI/bge-reranker-base/... | cross-encoder reranker weights |

Reachable: pypi.org, registry.npmjs.org (code dependencies only).

## Tooling blockers
| ID | Item | Status |
|---|---|---|
| B-D1 | Docker daemon | Not running in this container, so `docker compose up` was never run. Dockerfiles and compose file are written but **untested**; the "fresh-clone run via docker compose" gate is unmet. |
| B-T1 | shadcn/ui CLI | `ui.shadcn.com` blocked (request cancelled). Components were hand-written in the shadcn pattern (`web/components/ui`). |
| B-T2 | 21st.dev Magic MCP | Not available in this session. Components built by hand. |
| B-T3 | UI/UX Pro Max skill | Not available in this session. Design decisions made directly and checked with axe and screenshots. |
| B-T4 | Google Fonts | Blocked; system font stack used instead of `next/font/google`. |

## Consequences (network)
- `data/` and `models/` do not exist; `sources.csv` has no rows (no real pull has succeeded).
- Gold set (≥100 hand-labelled questions with source pages) cannot be written without real documents. Gold files must be written by a person reading the real pages; nothing here generates them.
- Dense, hybrid and reranker ablations cannot run; only BM25 exists.
- Exit criteria on corpus size (≥300 MB), hallucination rate on a frozen test set and demo page citations are **unmet**.
- Aurelian Peak files, `pe_engine.py` and `eval/gold_aurelian.json` (branch `claude/stoic-edison-nxyb7y`) are deliberately unused.
