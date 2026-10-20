# Viva script (3 minutes), run on the replica sample PPM

**Document:** `data/sample/Aurelian_Peak_Fund_Sample_PPM.pdf`, a replica of a real PPM with the names changed
(see `data/sample/README.md`). It is shown with a banner in the app. This is a demonstration on a sample, not
a result on real public disclosures. Say so at the start.

## Setup
```
python scripts/build_index.py --src data/sample --out data/chunks_sample
PEREPORT_CHUNKS=data/chunks_sample PEREPORT_EVAL=eval/sample/test PEREPORT_MANIFEST=data/sample/manifest.json \
  PEREPORT_BANNER="SAMPLE DOCUMENT: replica of a real PPM with names changed." \
  uvicorn pereport.api:app_from_disk --factory --port 8000
(cd web && npm run build && npm run start -- -p 3100)   # open http://127.0.0.1:3100
```
The expected answers below are the system's actual output (captured 2026-10-20). Each was compared by the
engine author with the PDF page image. **Owner: re-check each row against the PDF before the viva.**

## Demo
| # | Type | Question (exact words) | Expected answer (system output) | Source page and chunk | Checked against the PDF |
|---|---|---|---|---|---|
| 1 | answered | What is the management fee? | "Management Fee  2% per annum of Class A Net Asset Value, calculated monthly in arrears [p.8]. Management Fee. 2% per annum of Class A Net Asset Value (before that month's fee and any accrued Performance Profit Allocation), payable monthly in arrears [p.14]." | p.8 (`p8:c12`, III. Summary of Principal Terms), p.14 (`p14:c2`, XIII. Fees and Expenses) | author: yes (2026-10-20); owner: ____ |
| 2 | answered | How long is the lock-up period? | "Lock-up  One year from issue [p.9]. Shares are redeemable at the Shareholder's option on any Dealing Day after the Lock-up Period, at the quarterly Dealing Days, on at least 45 Business Days' written notice, at the Net Asset Value on the Valuation Day [p.13]." | p.9 (`p9:c0`), p.13 (`p13:c1`, XI. Redemptions) | author: yes; owner: ____ |
| 3 | answered | What is the performance profit allocation? | "Performance Profit Allocation  20% of appreciation above the Reference Price, subject to the High Water Mark; annual [p.8]." (a second sentence on Class B Shares, p.8, is also returned) | p.8 (`p8:c5`, `p8:c13`) | author: yes; owner: ____ |
| 4 | refusal | What is the Fund's hurdle rate? | "The provided documents do not contain enough information to answer this question." (reason `low_score`, top score 0.15 against threshold 0.277) | none. The document defines a High Water Mark but never mentions a hurdle rate (searched all 20 pages: 0 occurrences). | author: yes; owner: ____ |

## What to say (finance terms for the examiner)
- **PPM:** private placement memorandum, the offering document of a fund. **NAV:** net asset value, assets less
  liabilities at a date. **Management fee:** a yearly percentage of NAV paid to the manager. **Performance
  profit allocation:** the manager's share of gains above a reference price, here with a **high water mark**
  (the manager earns it only on value above the previous peak). **Lock-up:** a period when investors cannot
  redeem. **Hurdle rate:** a minimum return that must be beaten before performance pay starts; this fund has
  none, which is why question 4 is refused.
- This sample is an open-ended fund. PE-specific LP questions (capital calls, DPI/TVPI, carry waterfall)
  are not answerable from it and are used as refusal tests.

## Results to quote (all on the sample, BM25 only; see `eval/sample/test/report.md`)
Held-out test split, 23 questions, gate calibrated on the 25-question dev split only:
| Config | Accuracy | Answered correctly (of all 23) | Hallucinations / answers given | Unanswerable refused |
|---|---|---|---|---|
| bm25, no gate, no verifier | 60.9% | 60.9% | 7/23 (30.4%) | 0 of 7 |
| bm25 + gate + verifier | 69.6% | 43.5% | 1/13 (7.7%) | 6 of 7 |

Be ready to say: the gate and verifier cut hallucinations from 30% to 8% at the cost of answering fewer
questions; the 8% still misses the 2% target and the interval is very wide at this size; the one remaining
case answered "legal advisors in Calderon" with the Veridia and Zandria rows.
