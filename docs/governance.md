# Project governance (PEReport)

This file governs this project. The user's earlier module A7 was skipped by instruction, so this is the
only governance text.

## Data provenance
1. Only real, public documents. No fabricated fund data, no invented documents, no placeholder numbers.
2. Every pull is logged in `sources.csv` (url, publisher, date_pulled, local_path, notes) and, once
   `data/manifest.json` exists, with its SHA-256.
3. A pull that fails is logged in BLOCKERS.md with the URL and reason, not retried silently, and
   never replaced with substitute data.
4. Files from the earlier Aurelian Peak sample (`pe_engine.py`, `eval/gold_aurelian.json`, sample PPM)
   are excluded from this project.

## Output controls
5. Every sentence shown to a user cites a source chunk (`[doc, p.X]`) or a computed number
   (`[calc:name]`), enforced by the verifier. Unverifiable sentences are removed; if none remain the
   system refuses.
6. Computed numbers come from plain-Python functions with hand-worked tests.
7. Missing report fields print "Not disclosed in provided documents".

## Evaluation integrity
8. The gold set is hand-labelled, split into dev and test, then frozen (file hash recorded). The gate
   threshold and any tuning use dev only. The test split is scored once per reported run.
9. Reported results include counts and intervals, not just percentages (see docs/assumptions.md).
10. No result is stated without the command and output that produced it.

## Change control
11. One component per commit; ruff, mypy and pytest must pass before each commit (`make check`).
12. Any change to the verifier or gate after the test split is frozen is logged in PROGRESS.md with the reason.

## Limits of use
13. Output is an assistant's reading of the supplied documents, not investment, legal or accounting advice,
    and is not a substitute for the fund's own reports.
