"""Section-aware chunker.

Pages in, chunks out. Each chunk keeps (doc, page, section, date, fund) so every
downstream sentence can be traced to a source page and chunk ID. No chunk spans
two pages, so a page citation is always exact. A section heading carries over
onto following pages until the next heading.
"""

import re
from dataclasses import dataclass

DEFAULT_MAX_WORDS = 120
FRONT_MATTER = "Front matter"

_NUMBERED_HEADING = re.compile(r"^(?:\d+(?:\.\d+)+|\d+\.|[IVX]+\.)\s+\S")
_KEYWORD_HEADING = re.compile(
    r"^(?:item\s+\d+[a-z]?\.?|section\s+\d+|part\s+[ivx]+|schedule\s+\w+)\b", re.I
)
_NUMERIC_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
_LIST_MARKER = re.compile(r"^\d{1,2}\.\s+(?=\S)")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")


@dataclass(frozen=True)
class Page:
    """One parsed page of a source document (page numbers are 1-based, as printed by the viewer)."""

    page: int
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc: str
    page: int
    section: str
    date: str | None
    fund: str | None
    kind: str  # "text" or "table"
    text: str


def is_heading(line: str) -> bool:
    """Heuristic heading test: numbered or keyword lines, or short ALL-CAPS lines."""
    s = line.strip()
    words = s.split()
    if not s or len(words) > 12 or (s.endswith((".", ",", ";")) and not _NUMBERED_HEADING.match(s)):
        return False
    if _KEYWORD_HEADING.match(s):
        return True
    if _NUMBERED_HEADING.match(s):
        # "1. FUND SUMMARY" yes; "2. Mr Rao resigned on 5 May." no (ends with a period, long).
        return len(words) <= 8 and not s.endswith(".")
    letters = [c for c in s if c.isalpha()]
    return (
        len(letters) >= 2
        and len(words) <= 10
        and all(c.isupper() for c in letters)
        and len(letters) >= 0.6 * len(s.replace(" ", ""))
    )


def _is_table(lines: list[str]) -> bool:
    """A table: at least two lines and 80% of them have the double-space cell gaps ingest writes.

    Numbers alone do not make a table; prose lines with figures (definitions, fee clauses) must stay
    prose. Plain text that was not produced by ingest therefore needs double-space cells to be
    recognised as a table.
    """
    if len(lines) < 2:
        return False
    return sum(1 for ln in lines if "  " in ln) * 5 >= len(lines) * 4


def _split_words(text: str, max_words: int) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def _pack_sentences(text: str, max_words: int) -> list[str]:
    """Pack whole sentences up to max_words; hard-split only a sentence that alone exceeds it."""
    out: list[str] = []
    cur: list[str] = []
    cur_n = 0
    for sent in _SENTENCE_END.split(text.strip()):
        n = len(sent.split())
        if n > max_words:
            if cur:
                out.append(" ".join(cur))
                cur, cur_n = [], 0
            out.extend(_split_words(sent, max_words))
        elif cur_n + n > max_words:
            out.append(" ".join(cur))
            cur, cur_n = [sent], n
        else:
            cur.append(sent)
            cur_n += n
    if cur:
        out.append(" ".join(cur))
    return out


def _table_row_chunks(lines: list[str], max_words: int) -> list[str]:
    """One chunk per table row, each carrying the header row (a first line without digits).

    A row is the natural unit a reader asks about ("Management Fee  2% per annum..."), and one row
    scores far better in retrieval than a whole term sheet diluted into a single chunk.
    """
    header = lines[0] if len(lines) > 1 and not any(c.isdigit() for c in lines[0]) else ""
    rows = lines[1:] if header else lines
    out: list[str] = []
    for row in rows:
        pieces = [row] if len(row.split()) <= max_words else _split_words(row, max_words)
        for piece in pieces:  # an over-long row is split by words; short rows keep their cell gaps
            out.append(f"{header}\n{piece}" if header else piece)
    return out


def _page_blocks(text: str, section: str) -> tuple[list[tuple[str, str, str]], str]:
    """Split one page into (section, kind, text) blocks; return the section at page end."""
    blocks: list[tuple[str, str, str]] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            kind = "table" if _is_table(buf) else "text"
            blocks.append((section, kind, "\n".join(buf)))
            buf.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
        elif is_heading(line):
            flush()
            section = line
        else:
            # numbered-list markers ("11. Transactions...") would leak into the previous sentence
            buf.append(_LIST_MARKER.sub("", line))
    flush()
    return blocks, section


def chunk_pages(
    pages: list[Page],
    doc: str,
    date: str | None = None,
    fund: str | None = None,
    max_words: int = DEFAULT_MAX_WORDS,
) -> list[Chunk]:
    """Chunk a document. `date` and `fund` are copied onto every chunk as metadata."""
    chunks: list[Chunk] = []
    section = FRONT_MATTER
    for page in sorted(pages, key=lambda p: p.page):
        blocks, section = _page_blocks(page.text, section)

        # Merge adjacent text blocks of one section up to max_words; tables stand alone.
        merged: list[tuple[str, str, str]] = []
        for sec, kind, text in blocks:
            if (
                merged
                and kind == "text"
                and merged[-1][1] == "text"
                and merged[-1][0] == sec
                and len(merged[-1][2].split()) + len(text.split()) <= max_words
            ):
                merged[-1] = (sec, "text", merged[-1][2] + "\n" + text)
            else:
                merged.append((sec, kind, text))

        idx = 0
        for sec, kind, text in merged:
            if kind == "table":
                pieces = _table_row_chunks(text.split("\n"), max_words)
            else:
                pieces = _pack_sentences(text.replace("\n", " "), max_words)
            for piece in pieces:
                chunks.append(
                    Chunk(
                        f"{doc}:p{page.page}:c{idx}", doc, page.page, sec, date, fund, kind, piece
                    )
                )
                idx += 1
    return chunks
