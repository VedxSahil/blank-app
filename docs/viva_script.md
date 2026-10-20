# Viva script (3 minutes): TO BE COMPLETED ON REAL DOCUMENTS

**Status: not complete.** No real documents are in the repo (BLOCKERS.md B-N1 to B-N10), so there are no
real answers or page numbers to quote. Expected answers below are left blank on purpose; filling them with
invented figures would break the project's no-fabrication rule.

## Procedure
1. `python scripts/download.py` then `python scripts/build_index.py` (real public documents only).
2. Write and freeze the gold set (`eval/gold.jsonl`), then `python scripts/run_eval.py eval/gold.jsonl --freeze`.
3. Start the API and web app (`uvicorn pereport.api:app_from_disk --factory`, `npm run start` in `web/`).
4. Pick three answerable questions and one unsupported question **from the gold set's dev split**.
5. For each answer: open the cited page in the source PDF yourself and confirm the sentence. Record the
   result in the table. A row is not demo-ready until its last column says "checked by <name> on <date>".

## Demo (3 minutes)
| # | Type | Question (exact words) | Expected answer (copy from source) | Source file, page, chunk ID | Verified |
|---|---|---|---|---|---|
| 1 | answered | | | | |
| 2 | answered | | | | |
| 3 | answered | | | | |
| 4 | refusal | | "The provided documents do not contain enough information to answer this question." | none (explain which fact is absent from the documents) | |

## What to say (finance terms for the examiner)
- **Capital call:** the GP asks LPs to pay in part of their commitment. **NAV:** net asset value, the fund's
  assets less liabilities at a date. **DPI / RVPI / TVPI:** distributions, residual value, and total value, each
  divided by paid-in capital. **Carry:** the GP's share of profit above the hurdle rate. **Waterfall:** the order
  in which distributions are split between LPs and the GP.
- Why refuse: an LP report that states a number the documents do not contain is worse than one that says
  "not disclosed". Refusals are counted and scored (refusal precision and recall).
- How it is checked: every number, date and name in an answer must appear in the page it cites, or the sentence
  is removed. Say plainly what that does not cover (docs/assumptions.md).
