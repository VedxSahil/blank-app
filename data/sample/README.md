# Sample document (replica, names changed)

`Aurelian_Peak_Fund_Sample_PPM.pdf` (20 pages) was supplied by the project owner. Per the owner it is based
on a real document and is a replica with the names changed. The document labels itself "SAMPLE / ILLUSTRATIVE
DOCUMENT" and states that every entity, person, regulator, law, licence and figure in it is fictional.

How it is used in this repo
- As a working test document for the pipeline (parsing, chunking, retrieval, gate, verifier, report, UI).
- Results on it are labelled "sample document" everywhere. They are **not** results on real public disclosures
  (SEBI, 10-K, ILPA) and must not be quoted as the answer to the research question.
- It is not an original public source, so it is not listed in `data/manifest.json` or `sources.csv`; its
  provenance is in `data/sample/manifest.json` (SHA-256, kind, origin).
- It is an open-ended hedge-fund-style PPM (Class A shares, monthly dealing, Performance Profit Allocation), not
  a PE fund quarterly report. PE-specific LP questions (capital calls, DPI/TVPI, carry waterfall) are
  unanswerable from it by design and appear as refusal tests.
- If the underlying real document is public, add its URL to `data/targets.json` so the real original enters the
  corpus.
