# BLOCKERS

Last audited: 2026-10-20. Each network host was tried once and returned HTTP 403 from the egress proxy
(`CONNECT` refused: environment network policy). Not retried, per instruction.

## Missing user modules
Searched: current branch, all local and remote branches (content and filenames), whole filesystem,
`/mnt/user-data`, `/mnt/attach`, `/mnt/skills`. Patterns: structured extraction, retrieval pipeline,
governance note, fund administration, dashboard and commentary, A1/A2/A7/A8/A9. **No matches.**

| ID | Module | Status | Stub |
|---|---|---|---|
| B-A1 | A1 structured extraction | not found | `pereport/a1_extraction.py` raises NotImplementedError |
| B-A2 | A2 retrieval pipeline | not found | `pereport/a2_retrieval.py` raises NotImplementedError (BM25 baseline in `pereport/bm25.py` is new code, not A2) |
| B-A7 | A7 governance note | not found | `pereport/a7_governance.py` raises NotImplementedError (`docs/governance.md` is project text, not A7) |
| B-A8 | A8 fund administration engine | not found | `pereport/a8_fund_admin.py` raises NotImplementedError |
| B-A9 | A9 dashboard and commentary | not found | `pereport/a9_dashboard.py` raises NotImplementedError |

Needed from the user: the files or pasted text of each module. The legend of artifact codes alone is not content.

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

## Consequences
- `data/` and `models/` do not exist; `sources.csv` has no rows (no real pull has succeeded).
- Gold set (≥100 hand-labelled questions with source pages) cannot be written without real documents.
- Dense, hybrid and reranker ablations cannot run; only BM25 exists.
- Exit criteria on corpus size (≥300 MB), hallucination rate on a frozen test set and demo page citations are **unmet**.
- Aurelian Peak files, `pe_engine.py` and `eval/gold_aurelian.json` (branch `claude/stoic-edison-nxyb7y`) are deliberately unused.
