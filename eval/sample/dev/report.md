# Evaluation report (dev split)

SAMPLE DOCUMENT (replica PPM with names changed). Pipeline test, not a real-data result.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 25 | 68.0% | 64.0% | 7/24 (29.2%) | 49.2% | 79.2% | 75.9% | 61.1% | 100.0% | 12.5% |
| bm25+gate+verifier | 25 | 84.0% | 60.0% | 2/18 (11.1%) | 32.8% | 83.3% | 77.8% | 63.6% | 85.7% | 75.0% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 15 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 7 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 15 |
| partial | 2 | 1 | 1 | 0 |
| unanswerable | 8 | 2 | 6 | 6 |
