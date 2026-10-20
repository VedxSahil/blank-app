# Evaluation report (dev split)

SAMPLE DOCUMENT (replica PPM with names changed). Pipeline test, not a real-data result.

Skipped configurations: embedding model BAAI/bge-small-en-v1.5 unavailable: ModuleNotFoundError: No module named 'sentence_transformers'; dense: skipped, model unavailable; hybrid: skipped, model unavailable; hybrid+rerank+gate+verifier: skipped, model unavailable

| Config | N | Accuracy | Auto-answered (headline) | Hallucination | 95% upper | Faithfulness | Cit. P | Cit. R | Refusal P | Refusal R |
|---|---|---|---|---|---|---|---|---|---|---|
| bm25 | 25 | 56.0% | 52.0% | 8/24 (33.3%) | 53.3% | 87.5% | 63.0% | 47.2% | 100.0% | 12.5% |
| bm25+gate+verifier | 25 | 52.0% | 28.0% | 2/13 (15.4%) | 42.2% | 92.3% | 52.6% | 50.0% | 50.0% | 75.0% |

## Per-category: bm25

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 15 | 0 | 12 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 7 | 1 | 1 |

## Per-category: bm25+gate+verifier

| Category | N | Answered | Refused | Correct |
|---|---|---|---|---|
| answerable | 15 | 9 | 6 | 6 |
| partial | 2 | 2 | 0 | 1 |
| unanswerable | 8 | 2 | 6 | 6 |
