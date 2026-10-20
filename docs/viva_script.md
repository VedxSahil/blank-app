# Viva script (3 minutes), run on the official ILPA Reporting Template v2.0

**Document:** `data/real/ILPA_Reporting_Template_v2.0.xlsx`, the official ILPA Reporting Template (version 2.0,
last updated January 22, 2025), published by the Institutional Limited Partners Association. It is a real, public
document, but it is a **template**: it defines the fields an LP report should contain. It holds no fund's data, so
the system answers what the template *says*, not what any fund *reported*. Say this at the start.

**Citations:** a spreadsheet has no pages, so `p.N` means **sheet N**: 1 Suggested Guidance, 2 Reporting Template,
3 Fund of Funds-Underlying, 4 Definitions, 5 Summary of Revisions. The source panel also shows the section.
ILPA's illustrative example figures (for a sample fund) are deliberately not indexed.

## Setup
```
python scripts/build_index.py data/real/meta.json --src data/real --out data/chunks
PEREPORT_CHUNKS=data/chunks PEREPORT_EVAL=eval/ilpa/test PEREPORT_MANIFEST=data/real/manifest.json \
  PEREPORT_BANNER="REAL DOCUMENT: official ILPA Reporting Template v2.0 (public template)." \
  uvicorn pereport.api:app_from_disk --factory --port 8000
(cd web && npm run build && npm run start -- -p 3100)   # open http://127.0.0.1:3100
```
Expected answers are the system's actual output (captured 2026-10-20, gate threshold 0.361 calibrated on the dev split).
Each was compared with the workbook cell named in the last column. **Owner: open the workbook and re-check each row.**

## Demo
| # | Type | Question (exact words) | Expected answer (first sentence, system output) | Source | Checked against the workbook |
|---|---|---|---|---|---|
| 1 | answered | What is a Returned Clawback? | "Returned Clawback  Excess carried interest paid to the investment adviser or any of its related persons, including amounts held in escrow, which has been returned to the private fund [p.4]." A second sentence cites the line item in sheet 2 (section "Reconciliation for Accrued/Earned/Paid Carried Interest"). | sheet 4 Definitions, cell C83/D83 (`p4:c81`) | author: yes (2026-10-20); owner: ____ |
| 2 | answered | What are Origination Fees? | "Origination Fees  Fees/expenses that are allocated or paid to the investment adviser or any of its related persons (include any fees not subject to offset) relating to the sourcing of investment opportunities [p.4]." | sheet 4, C95/D95; line item in sheet 2, B126 | author: yes; owner: ____ |
| 3 | answered | What are Monitoring Fees? | "Monitoring Fees  Fees/expenses, including accelerated monitoring fees, that are allocated or paid to the investment adviser or any of its related persons (include any fees not subject to offset) as part of an agreement between the portfolio investment and the investment adviser or any of its related persons over a finite or indefinite period [p.4]." | sheet 4, C92/D92; line item in sheet 2, B123 | author: yes; owner: ____ |
| 4 | refusal | What is the fund's hurdle rate? | "The provided documents do not contain enough information to answer this question." (reason `low_score`, top score 0.10 against threshold 0.361) | none. The template never mentions a hurdle rate (0 occurrences). A follow-up refusal: "What was the fund's net IRR for the period?" The template contains no returns; ILPA's separate Performance Templates (named in sheet 1) cover performance. | author: yes; owner: ____ |

## What to say (finance terms for the examiner)
- **ILPA:** Institutional Limited Partners Association, the LP industry body. Its Reporting Template standardises how
  a GP reports fees, expenses and carried interest to LPs each quarter.
- **Clawback:** carried interest a GP paid itself that must be returned if later results do not justify it.
  **Carried interest:** the GP's share of profits. **Management fee offsets:** fees the GP's affiliates earn from
  portfolio companies are credited against the management fee. **Monitoring / origination fees:** fees a GP's affiliate
  charges a portfolio company for oversight / for sourcing the deal.
- **Why refuse:** a template has no fund performance. An answer such as an IRR here could only be invented.

## Results to quote (all BM25 only, `eval/ilpa/test/report.md`)
Held-out test split, 23 questions, gate calibrated on the 25-question dev split only, scored once at commit a1284f8:
| Config | Accuracy | Answered correctly (of all 23) | Hallucinations / answers given | Unanswerable refused |
|---|---|---|---|---|
| bm25, no gate, no verifier | 56.5% | 52.2% | 6/22 (27.3%) | 1 of 7 |
| bm25 + gate + verifier | 52.2% | 30.4% | 2/11 (18.2%; 95% upper bound 47.7%) | 5 of 7 |

Be ready to say: faithfulness (verifier pass rate) was 100%, so every sentence shown is supported by the cited
cell; the 18% is questions that look answerable but are not (a "general partner" question returned the GP's
Allocation definition; "fund size of the Parent Fund" matched an empty template field). On the same split, 6 of 15
answerable questions were refused by the gate. Dev accuracy was 76% to 80%, so the dev-to-test gap again shows
over-fitting to a small dev set. The 2% hallucination target is not met and cannot be tested at this sample size.

## Second document: the replica sample PPM
`data/sample/Aurelian_Peak_Fund_Sample_PPM.pdf` (a renamed replica of a real PPM, see `data/sample/README.md`) is
kept as a PDF test document: 3 answered and 1 refused question on it are in `eval/sample/` (test split: 69.6%
accuracy, 1 hallucination in 13 answers). It is not an original public source.
