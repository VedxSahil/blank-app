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
    """A table: half the lines (min 2) hold two numbers, or 80% have double-space cell gaps."""
    if len(lines) < 2:
        return False
    numeric = sum(1 for ln in lines if len(_NUMERIC_TOKEN.findall(ln)) >= 2)
    columns = sum(1 for ln in lines if "  " in ln)  # ingest joins table cells with two spaces
    return numeric * 2 >= len(lines) or columns * 5 >= len(lines) * 4


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


def _pack_table_lines(lines: list[str], max_words: int) -> list[str]:
    """Split a table on row boundaries only, so a row is never cut in half."""
    out: list[str] = []
    cur: list[str] = []
    cur_n = 0
    for ln in lines:
        n = len(ln.split())
        if cur and cur_n + n > max_words:
            out.append("\n".join(cur))
            cur, cur_n = [], 0
        cur.append(ln)
        cur_n += n
    if cur:
        out.append("\n".join(cur))
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
            buf.append(line)
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
                pieces = _pack_table_lines(text.split("\n"), max_words)
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
