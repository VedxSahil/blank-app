# Evaluation report (dev split)

REAL DOCUMENT: official ILPA Reporting Template v2.0 (Jan 2025), a public TEMPLATE. Questions are about its definitions and structure, not about any fund's data. Dev split.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 25 | 52.0% | 48.0% | 7/24 (29.2%) | 49.2% | 66.7% | 51.7% | 71.4% | 100.0% | 12.5% |
| bm25+gate+verifier | 25 | 56.0% | 24.0% | 0/12 (0.0%) | 24.3% | 66.7% | 57.1% | 75.0% | 61.5% | 100.0% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 11 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 7 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 11 | 4 | 5 |
| partial | 2 | 1 | 1 | 1 |
| unanswerable | 8 | 0 | 8 | 8 |
