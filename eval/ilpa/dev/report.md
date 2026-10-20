# Evaluation report (dev split)

REAL DOCUMENT: official ILPA Reporting Template v2.0, a public TEMPLATE. Dev split, rerun after the section-path fix.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 25 | 56.0% | 52.0% | 7/24 (29.2%) | 49.2% | 100.0% | 57.1% | 76.2% | 100.0% | 12.5% |
| bm25+gate+verifier | 25 | 76.0% | 44.0% | 0/13 (0.0%) | 22.8% | 100.0% | 59.1% | 76.5% | 66.7% | 100.0% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 12 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 7 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 12 | 3 | 10 |
| partial | 2 | 1 | 1 | 1 |
| unanswerable | 8 | 0 | 8 | 8 |
