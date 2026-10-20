# Evaluation report (test split)

REAL DOCUMENT: official ILPA Reporting Template v2.0 (Jan 2025), a public TEMPLATE. Questions are about its definitions and structure, not any fund's data. Gate calibrated on the dev split only; test split scored once after the gold file was frozen, at commit a1284f8.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 23 | 56.5% | 52.2% | 6/22 (27.3%) | 48.2% | 100.0% | 53.8% | 87.5% | 100.0% | 14.3% |
| bm25+gate+verifier | 23 | 52.2% | 30.4% | 2/11 (18.2%) | 47.7% | 100.0% | 52.9% | 100.0% | 41.7% | 71.4% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 11 |
| partial | 1 | 1 | 0 | 1 |
| unanswerable | 7 | 6 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 9 | 6 | 7 |
| partial | 1 | 0 | 1 | 0 |
| unanswerable | 7 | 2 | 5 | 5 |
