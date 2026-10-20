# Evaluation report (dev split)

SAMPLE DOCUMENT (replica PPM with names changed). Pipeline test, not a real-data result.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 25 | 64.0% | 60.0% | 7/24 (29.2%) | 49.2% | 100.0% | 75.9% | 61.1% | 100.0% | 12.5% |
| bm25+gate+verifier | 25 | 72.0% | 44.0% | 1/14 (7.1%) | 31.5% | 100.0% | 72.7% | 57.1% | 63.6% | 87.5% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 14 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 7 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 12 | 3 | 11 |
| partial | 2 | 1 | 1 | 0 |
| unanswerable | 8 | 1 | 7 | 7 |
