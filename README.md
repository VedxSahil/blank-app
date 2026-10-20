# PEReport: Fund Document Assistant (work in progress)

Retrieval with citations, an answer verifier and a refusal gate for private-equity fund documents.
Research question: how much of an LP's quarterly question set can be answered from fund documents
automatically?

**Status:** the core engine pieces exist and are unit-tested on invented fixture text. No real documents,
models or gold set are in the repo yet. See `BLOCKERS.md`, `PROGRESS.md`, `docs/assumptions.md`,
`docs/governance.md`.

```
pereport/chunker.py    section-aware chunks with doc, page, section, date, fund metadata
pereport/bm25.py       Okapi BM25 (plain Python)
pereport/verifier.py   every number, date and entity in a sentence must be in the cited chunk
pereport/gate.py       refuse on missing evidence, low score (dev-calibrated) or unsupported facts
pereport/metrics.py    accuracy, citation P/R, refusal P/R, hallucination rate with Wilson bound
```

## Run the checks
```
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python pytest ruff mypy
make check      # ruff, ruff format, mypy --strict, pytest
```
