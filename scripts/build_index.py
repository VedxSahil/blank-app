"""Parse every PDF in data/raw into section-aware chunks (data/chunks/<doc>.jsonl).

Usage: python scripts/build_index.py [meta.json]
meta.json (optional) maps a PDF file name to {"date": ..., "fund": ...}. Pages that look scanned
are reported; OCR is not run automatically.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pereport.chunker import chunk_pages
from pereport.ingest import parse_pdf
from pereport.store import save_chunks


def main(argv: list[str]) -> int:
    meta = json.loads(Path(argv[1]).read_text()) if len(argv) > 1 else {}
    pdfs = sorted(Path("data/raw").glob("*.pdf"))
    if not pdfs:
        print("no PDFs in data/raw (see BLOCKERS.md: nothing has been downloaded)")
        return 1
    total = 0
    for pdf in pdfs:
        parsed = parse_pdf(pdf)
        m = meta.get(pdf.name, {})
        chunks = chunk_pages(parsed.pages, pdf.stem, m.get("date"), m.get("fund"))
        save_chunks(Path("data/chunks") / f"{pdf.stem}.jsonl", chunks)
        total += len(chunks)
        note = f", NEEDS OCR on pages {parsed.ocr_pages}" if parsed.ocr_pages else ""
        print(f"{pdf.name}: {len(parsed.pages)} pages, {len(chunks)} chunks{note}")
    print(f"{total} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
