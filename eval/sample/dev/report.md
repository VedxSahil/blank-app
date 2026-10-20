# Evaluation report (dev split)

SAMPLE DOCUMENT (replica PPM with names changed). Pipeline test, not a real-data result.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 25 | 60.0% | 56.0% | 7/24 (29.2%) | 49.2% | 95.8% | 74.1% | 55.6% | 100.0% | 12.5% |
| bm25+gate+verifier | 25 | 60.0% | 28.0% | 0/10 (0.0%) | 27.8% | 90.0% | 71.4% | 43.5% | 53.3% | 100.0% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 13 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 7 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 9 | 6 | 7 |
| partial | 2 | 1 | 1 | 0 |
| unanswerable | 8 | 0 | 8 | 8 |
