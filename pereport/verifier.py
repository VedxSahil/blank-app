"""Answer verifier.

Rule: every sentence of an answer must carry a citation, either ``[doc, p.X]`` (a retrieved
chunk) or ``[calc:name]`` (a computed number), and every number, date and entity in it must be
found in the cited chunk text (or, for numbers, in the cited computed value). A sentence that
fails is stripped; if nothing survives the answer is a refusal.

What it does NOT check (see docs/assumptions.md): qualitative claims with no number, date or
capitalised entity; whether a supported number is attached to the right noun; unit conversions
(1.2 billion is not matched to 1,200 million; the sentence is stripped instead).
"""

import re
from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from pereport.chunker import Chunk

CITATION = re.compile(r"\[([^\[\]]+?),\s*p\.?\s*(\d+)\]")
CALC = re.compile(r"\[calc:\s*([\w.\-]+)\]")

_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_MONTH_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MONTH}\b\.?,?\s+(\d{{4}})\b", re.I)
_MDY = re.compile(rf"\b{_MONTH}\b\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I)
_MY = re.compile(rf"\b{_MONTH}\b\.?,?\s+(\d{{4}})\b", re.I)
_QTR = re.compile(r"\bQ([1-4])\s*(?:FY)?\s*'?(\d{4}|\d{2})\b", re.I)
_FY = re.compile(r"\bFY\s*'?(\d{4}|\d{2})\b", re.I)
_UNIT_AFTER = r"(?!\s?(?:%|x\b|bn\b|billion\b|mn\b|million\b|crore\b|cr\b|lakh\b))"
_YEAR = re.compile(rf"(?<![\w.,$₹€£-])((?:19|20)\d{{2}})\b(?![.,]\d){_UNIT_AFTER}")
_NUMBER = re.compile(
    r"(?<![\w.])(-|\u2212)?(?:[$₹€£]|rs\.?\s?|usd\s?|inr\s?)?"
    r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:\s?(%|(?:x|bn|billion|mn|million|crore|cr|lakh|k)\b))?(?!st\b|nd\b|rd\b|th\b)",
    re.I,
)
# Dates and numbers are blanked with this non-space character, so an entity run cannot silently
# close over them ("Category 1 Global Business Licence" must not become "Category Global ...").
_MASK = "\u00a7"
_UNIT_CANON = {
    "%": "pct", "x": "x", "bn": "bn", "billion": "bn", "mn": "mn", "million": "mn",
    "crore": "cr", "cr": "cr", "lakh": "lakh", "k": "k",
}  # fmt: skip
_WORD = re.compile(r"[A-Za-z][A-Za-z&'\u2019\-]*")
_CONNECTORS = {"of", "and", "&", "the", "for"}
_STOP = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "in", "on", "at", "as",
    "for", "of", "by", "with", "from", "to", "and", "but", "or", "per", "is", "was", "were",
    "are", "has", "have", "had", "there", "based", "according", "during", "after", "before",
    "no", "not", "all", "each", "both", "see", "note",
}  # fmt: skip
_NUMBER_WORDS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
    "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "half", "double", "triple",
}  # fmt: skip
_CTX_SKIP = _STOP | {"million", "billion", "crore", "lakh", "percent", "usd", "inr", "rs"}
_LOWER_WORD = re.compile(r"[a-z]+")
_ABBREV = {"mr", "mrs", "ms", "dr", "inc", "ltd", "co", "corp", "no", "vs", "st", "approx", "fig"}


@dataclass(frozen=True)
class Fact:
    kind: str  # "number", "date" or "entity"
    key: str  # canonical form used for matching
    raw: str  # as written
    # Numbers only: descriptive words found near the number. The evidence must show the same
    # number near at least one of them, so "fee is 20%" is not supported by "carry is 20%".
    ctx: frozenset[str] = field(default=frozenset(), compare=False)


@dataclass(frozen=True)
class Computed:
    """A number produced by code (not read from a document), cited as ``[calc:name]``."""

    value: float
    label: str  # plain-language description; entity words in it count as supported


@dataclass(frozen=True)
class Stripped:
    sentence: str
    reasons: list[str]


@dataclass(frozen=True)
class VerifiedAnswer:
    text: str
    kept: list[str]
    stripped: list[Stripped]
    unsupported_fact_count: int = 0
    unsupported_facts: list[Fact] = field(default_factory=list)

    @property
    def refused(self) -> bool:
        """Nothing survived verification."""
        return not self.kept

    @property
    def passed(self) -> bool:
        """Something was answered and nothing had to be stripped."""
        return bool(self.kept) and not self.stripped


def strip_markers(text: str) -> str:
    return CALC.sub(" ", CITATION.sub(" ", text))


def _year(s: str) -> str:
    return s if len(s) == 4 else "20" + s


def _month(name: str) -> int:
    return _MONTH_NUM[name.lower()[:3]]


def _norm_decimal(whole: str, frac: str | None) -> Decimal | None:
    try:
        return Decimal(whole.replace(",", "") + (frac or ""))
    except InvalidOperation:  # pragma: no cover - regex guarantees digits
        return None


def _fmt(d: Decimal) -> str:
    return format(d.normalize(), "f")


def _extract_dates(text: str) -> tuple[list[Fact], str]:
    """Return date facts and the text with date spans blanked out."""
    facts: list[Fact] = []

    def sub(pattern: re.Pattern[str], make: Callable[[re.Match[str]], str], s: str) -> str:
        def repl(m: re.Match[str]) -> str:
            facts.append(Fact("date", make(m), m.group(0)))
            return _MASK * len(m.group(0))

        return pattern.sub(repl, s)

    s = text
    s = sub(_ISO, lambda m: f"{m[1]}-{m[2]}-{m[3]}", s)
    s = sub(_DMY, lambda m: f"{m[3]}-{_month(m[2]):02d}-{int(m[1]):02d}", s)
    s = sub(_MDY, lambda m: f"{m[3]}-{_month(m[1]):02d}-{int(m[2]):02d}", s)
    s = sub(_MY, lambda m: f"{m[2]}-{_month(m[1]):02d}", s)
    s = sub(_QTR, lambda m: f"Q{m[1]}-{_year(m[2])}", s)
    s = sub(_FY, lambda m: f"FY{_year(m[1])}", s)
    s = sub(_YEAR, lambda m: m[1], s)
    return facts, s


def _ctx_word(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _extract_numbers(text: str, window: int) -> tuple[list[Fact], str]:
    """Numbers (digits and spelled-out) with the descriptive words within `window` words."""
    words = [(m.start(), m.group(0)) for m in _LOWER_WORD.finditer(text.lower())]
    starts = [w[0] for w in words]
    facts: list[Fact] = []

    def near(pos: int) -> frozenset[str]:
        idx = bisect_left(starts, pos)
        around = words[max(0, idx - window) : idx + window]
        return frozenset(_ctx_word(w) for _, w in around if len(w) >= 3 and w not in _CTX_SKIP)

    def repl(m: re.Match[str]) -> str:
        d = _norm_decimal(m[2], m[3])
        if d is not None:
            sign = "-" if m[1] else ""
            unit = _UNIT_CANON.get((m[4] or "").lower(), "")
            facts.append(
                Fact("number", f"{sign}{_fmt(d)}{unit}", m.group(0).strip(), near(m.start()))
            )
        return _MASK * len(m.group(0))

    rest = _NUMBER.sub(repl, text)
    for pos, w in words:
        if w in _NUMBER_WORDS:
            facts.append(Fact("number", f"w:{w}", w, near(pos) - {w}))
    return facts, rest


def _extract_entities(text: str) -> list[Fact]:
    toks = [(m.start(), m.end(), m.group(0)) for m in _WORD.finditer(text)]

    def cap(i: int) -> bool:
        return toks[i][2][0].isupper()

    def acronym(i: int) -> bool:
        return len(toks[i][2]) >= 2 and toks[i][2].isupper()

    def adjacent(i: int, j: int) -> bool:
        return text[toks[i][1] : toks[j][0]].strip() == ""

    def can_extend(i: int, j: int) -> bool:
        """Run may continue from token i to token j: no acronyms, no run past a possessive."""
        return not (acronym(i) or acronym(j) or re.search(r"['\u2019]s$", toks[i][2]))

    facts: list[Fact] = []
    i = 0
    while i < len(toks):
        if not cap(i):
            i += 1
            continue
        j = i
        while True:
            if j + 1 < len(toks) and cap(j + 1) and adjacent(j, j + 1) and can_extend(j, j + 1):
                j += 1
            elif (
                j + 2 < len(toks)
                and toks[j + 1][2].lower() in _CONNECTORS
                and cap(j + 2)
                and adjacent(j, j + 1)
                and adjacent(j + 1, j + 2)
                and can_extend(j, j + 2)
            ):
                j += 2
            else:
                break
        words = [re.sub(r"['\u2019]s$", "", t[2]) for t in toks[i : j + 1]]
        while words and words[0].lower() in _STOP:
            words.pop(0)
        if words:
            phrase = " ".join(words)
            facts.append(Fact("entity", phrase.lower(), phrase))
        i = j + 1
    return facts


def extract_facts(text: str, window: int = 4) -> list[Fact]:
    """Numbers, dates and entities in `text` (citation markers are ignored)."""
    clean = strip_markers(text)
    dates, rest = _extract_dates(clean)
    numbers, rest = _extract_numbers(rest, window)
    return dates + numbers + _extract_entities(rest)


def _expand_dates(keys: set[str]) -> set[str]:
    out = set(keys)
    for k in keys:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k):
            out.update((k[:7], k[:4]))
        elif re.fullmatch(r"\d{4}-\d{2}", k):
            out.add(k[:4])
        elif k.startswith("Q"):
            out.add(k[3:])
        elif k.startswith("FY"):
            out.add(k[2:])
    return out


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def unsupported_facts(text: str, evidence: str, extra_labels: str = "") -> list[Fact]:
    """Facts in `text` that do not appear in `evidence` (plus `extra_labels` for entities)."""
    ev = extract_facts(evidence, window=5)
    ev_numbers = {f.key for f in ev if f.kind == "number"}
    ev_ctx: dict[str, set[str]] = {}
    for f in ev:
        if f.kind == "number":
            ev_ctx.setdefault(f.key, set()).update(f.ctx)
    ev_dates = _expand_dates({f.key for f in ev if f.kind == "date"})
    ev_text = _squash(evidence + " " + extra_labels)
    missing: list[Fact] = []
    for f in extract_facts(text):
        if f.kind == "number":
            ok = f.key in ev_numbers and (not f.ctx or bool(f.ctx & ev_ctx.get(f.key, set())))
        elif f.kind == "date":
            ok = f.key in ev_dates
        else:
            ok = re.search(rf"(?<![a-z0-9]){re.escape(f.key)}(?![a-z0-9])", ev_text) is not None
        if not ok:
            missing.append(f)
    return missing


def _number_from_computed(fact: Fact, computed: list[Computed]) -> bool:
    m = re.fullmatch(r"(-?)(\d+(?:\.\d+)?)([a-z]*)", fact.key)
    if not m:
        return False
    written = Decimal(m[1] + m[2])
    places = len(m[2].split(".")[1]) if "." in m[2] else 0
    return any(Decimal(str(round(c.value, places))) == written for c in computed)


_LEADING_MARKERS = re.compile(r"(?:\s*(?:\[[^\[\]]+?,\s*p\.?\s*\d+\]|\[calc:\s*[\w.\-]+\]))+")


def split_sentences(text: str) -> list[str]:
    """Split on sentence ends; keep abbreviations (Mr. Inc.) together.

    A citation that follows the full stop ("... 2%. [D, p.2] Next") belongs to the sentence
    before it, since a sentence never starts with a citation.
    """
    out: list[str] = []
    start = 0
    for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z\[\"'(])", text):
        if m.start() < start:
            continue  # boundary already consumed as part of a trailing citation
        prev_word = re.search(r"([A-Za-z]+)[.!?]$", text[start : m.start()])
        if prev_word and prev_word[1].lower() in _ABBREV and text[m.start() - 1] == ".":
            continue
        end = m.start()
        lead = _LEADING_MARKERS.match(text, m.end())
        if lead:
            end = lead.end()
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        start = max(m.end(), end)
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def verify_answer(
    answer: str,
    retrieved: list[Chunk],
    computed: dict[str, Computed] | None = None,
) -> VerifiedAnswer:
    """Keep only sentences whose citations resolve and whose facts are all supported."""
    computed = computed or {}
    kept: list[str] = []
    stripped: list[Stripped] = []
    all_missing: list[Fact] = []
    for sent in split_sentences(answer):
        cites = [(d.strip(), int(p)) for d, p in CITATION.findall(sent)]
        calcs = CALC.findall(sent)
        reasons: list[str] = []
        if not cites and not calcs:
            reasons.append("no_citation")
        evidence_parts: list[str] = []
        for doc, page in cites:
            found = [c.text for c in retrieved if c.doc == doc and c.page == page]
            if found:
                evidence_parts.extend(found)
            else:
                reasons.append(f"citation_not_retrieved: [{doc}, p.{page}]")
        used = [computed[n] for n in calcs if n in computed]
        reasons.extend(f"unknown_calc: {n}" for n in calcs if n not in computed)
        if not reasons:
            missing = unsupported_facts(
                sent, "\n".join(evidence_parts), " ".join(c.label for c in used)
            )
            missing = [
                f for f in missing if not (f.kind == "number" and _number_from_computed(f, used))
            ]
            reasons.extend(f"unsupported_{f.kind}: {f.raw}" for f in missing)
            all_missing.extend(missing)
        if reasons:
            stripped.append(Stripped(sent, reasons))
        else:
            kept.append(sent)
    return VerifiedAnswer(" ".join(kept), kept, stripped, len(all_missing), all_missing)
