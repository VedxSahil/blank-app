# Evaluation report (test split)

SAMPLE DOCUMENT (replica PPM with names changed). Pipeline test, not a real-data result. Gate calibrated on the dev split only; test split scored once after the gold file was frozen.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 23 | 60.9% | 60.9% | 7/23 (30.4%) | 50.9% | 95.7% | 74.1% | 64.5% | n/a | 0.0% |
| bm25+gate+verifier | 23 | 69.6% | 43.5% | 1/13 (7.7%) | 33.3% | 92.3% | 76.2% | 61.5% | 60.0% | 85.7% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 13 |
| partial | 1 | 1 | 0 | 1 |
| unanswerable | 7 | 7 | 0 | 0 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 12 | 3 | 10 |
| partial | 1 | 0 | 1 | 0 |
| unanswerable | 7 | 1 | 6 | 6 |
