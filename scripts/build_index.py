"""Parse every PDF and .xlsx in a folder into section-aware chunks (data/chunks/<doc>.jsonl).

Usage: python scripts/build_index.py [meta.json] [--src DIR] [--out DIR]
(defaults: --src data/raw, --out data/chunks)
meta.json (optional) maps a PDF file name to {"date": ..., "fund": ...}. Pages that look scanned
are reported; OCR is not run automatically.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pereport.chunker import chunk_pages
from pereport.ingest import parse_pdf, parse_xlsx
from pereport.store import save_chunks


def main(argv: list[str]) -> int:
    opts = {a: argv[i + 1] for i, a in enumerate(argv) if a in ("--src", "--out")}
    pos = [
        a for i, a in enumerate(argv[1:], 1) if not a.startswith("--") and argv[i - 1] not in opts
    ]
    meta = json.loads(Path(pos[0]).read_text()) if pos else {}
    src, out = Path(opts.get("--src", "data/raw")), Path(opts.get("--out", "data/chunks"))
    pdfs = sorted([*src.glob("*.pdf"), *src.glob("*.xlsx")])
    if not pdfs:
        print(f"no PDFs or workbooks in {src} (see BLOCKERS.md: nothing has been downloaded)")
        return 1
    total = 0
    for pdf in pdfs:
        parsed = parse_xlsx(pdf) if pdf.suffix == ".xlsx" else parse_pdf(pdf)
        m = meta.get(pdf.name, {})
        chunks = chunk_pages(parsed.pages, pdf.stem, m.get("date"), m.get("fund"))
        save_chunks(out / f"{pdf.stem}.jsonl", chunks)
        total += len(chunks)
        note = f", NEEDS OCR on pages {parsed.ocr_pages}" if parsed.ocr_pages else ""
        unit = "sheets" if pdf.suffix == ".xlsx" else "pages"
        print(f"{pdf.name}: {len(parsed.pages)} {unit}, {len(chunks)} chunks{note}")
    print(f"{total} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
