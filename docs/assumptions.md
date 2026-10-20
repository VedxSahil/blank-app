# Assumptions and known limits

Each item is something the code relies on or cannot do. Nothing here is a result; no real
documents have been processed yet (see BLOCKERS.md).

## Verifier (`pereport/verifier.py`)
- A sentence is kept only if it has a citation and every number, date and capitalised entity in it
  is found in the cited chunk(s). Citation forms: `[doc, p.X]` and `[calc:name]`.
- Numbers match on value and unit, not on currency symbol. `1.2 billion` does NOT match
  `1,200 million`; such a sentence is stripped, a false rejection that is chosen over a false accept.
- A number must also sit within 5 words of at least one of the same descriptive words
  (window is 4 words on the answer side) in the evidence. This stops "management fee is 20%" being
  supported by "carry is 20%". Heavy paraphrase is therefore stripped; prompts should reuse document wording.
- Spelled-out numbers (two to ninety, hundred, thousand, half) must appear spelled out in the evidence.
  "one" is ignored (too often a pronoun).
- Dates are normalised (`31 March 2024` = `March 31, 2024` = `2024-03-31`). A year or month-year in the
  answer is supported by a fuller date in the evidence. Fiscal-year labels (`FY25`) match only `FY2025` forms.
- Entities: runs of capitalised words, split at acronyms and possessives, leading function words dropped.
  All-caps terms such as TVPI or DPI must appear in the evidence or in the computed-number label.
- **Not checked:** purely qualitative claims; negation ("fees were not charged"); that a supported number
  is the correct one for the question; arithmetic done in prose rather than via `[calc:...]`.

## Answerability gate (`pereport/gate.py`)
- Raw BM25 scores depend on query length and corpus size, so they are not comparable across queries.
  The threshold is calibrated per retriever on the dev split only. Dense and reranker scores will need
  their own calibration.
- `fp_cost` (default 3) values avoiding a wrong answer over avoiding a wrongful refusal. It is a design
  choice, not a measured quantity.

## Metrics (`pereport/metrics.py`)
- Definitions are in the module docstring. "Hallucination" means an emitted answer to an unanswerable
  question, or one containing a fact unsupported by its evidence. A supported but wrong answer is
  counted as inaccurate, not hallucinated.
- **Statistical limit:** with zero hallucinations out of 100 answers the 95% Wilson upper bound is 3.70%,
  so "hallucination rate ≤ 2%" cannot be shown with a 100-question test split. Zero errors in at least 188
  answers gives an upper bound of 2.0%. The gold set must be sized for the claim, or the claim must be
  worded as a point estimate with its interval.
- Gold facts are matched on number and date keys (case-insensitive text otherwise). Gold sets must be
  written in the same units as the source documents.

## Chunker (`pereport/chunker.py`)
- Heading detection is heuristic (numbered lines, ITEM/SECTION/PART/SCHEDULE, short ALL-CAPS lines).
  PDFs with unusual layouts will need tuning once real documents are available.
- Chunks never cross pages, so a page citation is exact, at the cost of splitting passages that
  continue onto the next page.
- Table detection looks for lines with two or more numbers; scanned or image tables need OCR first.

## Data
- No documents, models or gold questions exist in the repo. Unit tests use short invented strings that
  are labelled as fixtures and must never appear in the UI, the eval set or any report.
