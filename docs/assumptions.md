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

## Engine (`pereport/engine.py`)
- The default generator is extractive: it copies whole sentences (or table rows, with their header row)
  from the top chunks and appends `[doc, p.X]`. It cannot invent a fact, but it also cannot paraphrase,
  combine two passages or do arithmetic. An LLM generator can be injected; the verifier then matters most.
- Acronyms (NAV, IRR, TVPI, DPI, RVPI, MOIC, GP, LP, AIF) and any numbers or years in the question must appear
  in the answer (an acronym may be satisfied by its spelled-out form, from `GLOSSARY`). This was added after a
  fixture test showed an IRR question answered with a NAV sentence because both contain "net" and "fund".
  Cost: a question using a synonym the documents do not use is refused.
- Plural "s" is stripped from terms (fees = fee). No other stemming.
- A table split across chunks loses its header row for the later chunks.

## Retrieval (`pereport/retrieval.py`, `pereport/models.py`)
- Dense and rerank paths are written against protocols and tested with fake embedders. They have **not**
  been run with bge or the cross-encoder (weights unreachable). Gate thresholds are per mode and must be
  calibrated on dev for each.
- bge queries use the documented instruction prefix; passages do not.

## Report drafter (`pereport/report.py`)
- Each field is one generic LP question run through the engine. No numbers are computed (no TVPI/DPI
  arithmetic yet); a multiple appears only if a document states it.

## Web app and tests
- Playwright and axe run against `scripts/serve_fixture.py`, an API over four invented sentences. They
  prove behaviour (citations, refusal, reduced motion, contrast, no horizontal scroll at 375 px), not accuracy.
- Streaming text is a client-side word-by-word reveal of the finished answer, not token streaming.

## Sample document results (`eval/sample/`)
- The document is a replica of a real PPM with the names changed, supplied by the owner. It is not an
  original public source and is a hedge-fund-style open-ended fund PPM, not a PE quarterly report.
- The 48-question gold set (`eval/sample/gold.jsonl`) was written by the engine's author from the 20 pages,
  before the engine was run on it. It is not an independent labelling. Facts and pages were audited
  mechanically against the parsed page text; four page labels were corrected after that audit.
- Dev split: 25 questions, used for calibration and for diagnosing failures (several fixes were made from
  dev failures). Test split: 23 questions, scored once after the gold file was frozen (SHA-256 in
  `eval/sample/gold.jsonl.lock`, run logged in `gold.jsonl.testruns.log`).
- With 23 test questions the intervals are wide (hallucination 1/13, 95% upper bound 33%). The ≤2% target
  cannot be assessed at this size.
- Only BM25 configurations ran. Dense, hybrid and reranker rows are skipped because the model weights are
  unreachable (BLOCKERS.md B-N9, B-N10).
- Table parsing relies on ruled row separators found in this PDF's drawing data; PDFs without them fall back
  to a punctuation heuristic and may group wrapped rows wrongly.

## ILPA Reporting Template results (`eval/ilpa/`)
- The document is the real official template, but a template: questions are about its definitions and structure
  (what a field means, what a section lists), never about a fund's performance or terms. The "LP question set"
  here is therefore not the research question's real target (fund reports and PPMs).
- Spreadsheet handling: each sheet is one page (a citation `p.N` means sheet N). Only text cells are indexed;
  numbers and dates are dropped at parse time because the Reporting Template sheet holds ILPA's illustrative
  example figures for a sample fund. Headings are inferred (lettered "A.1" rows, bold rows without values,
  bold heading rows carrying their first item); line items become one row each, with a "(template line item in
  <section path>)" note instead of a bare section name, so layout text cannot read like a field value.
- 48-question gold set written by the engine's author from the definitions text, before running the engine; facts
  and pages audited mechanically (one page list corrected). Dev 25 / test 23; frozen (SHA-256 in
  `eval/ilpa/gold.jsonl.lock`; run logged in `gold.jsonl.testruns.log`).
- The test split was scored once, at commit a1284f8. Afterwards two provenance fixes changed the chunk text
  (the "(template line item ...)" wording and the section path of reconciliation blocks). The test split was not
  re-run, so the reported test numbers describe the earlier parser; the dev split was re-run (76%, 0/13).
- Two test questions the system answered wrongly are structural near-misses, not wording problems: "general
  partner" (the template only mentions it inside a definition) and "fund size of the Parent Fund" (an empty field
  in a blank layout). A retrieval model or entailment check is needed to reject them.
- Letter-numbered lines such as "A.1 Heading" are treated as headings in PDFs too; a name like "R. K. Ashworth" on
  its own line could be mistaken for one.
