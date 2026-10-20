"""Quarterly report drafter (ILPA-style sections).

Each report line is the engine's answer to a generic field question, so it is retrieved, gated,
extracted and verified like any other answer, and is bound to the chunk IDs it came from. A field
the documents do not support prints NOT_DISCLOSED. Nothing is written from memory or from a template
of numbers; the field questions contain no fund data.
"""

from dataclasses import dataclass

from pereport.engine import Engine

NOT_DISCLOSED = "Not disclosed in provided documents"

# (section title, [(field label, question)]). Questions are generic LP questions.
SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Fund summary", [
        ("Fund name and strategy", "What is the fund's name and investment strategy?"),
        ("Fund term", "What is the term of the fund and when is the final close?"),
        ("Manager", "Who is the investment manager or general partner?"),
    ]),
    ("Commitments and contributions", [
        ("Total commitments", "What are the total capital commitments of the fund?"),
        ("Capital called", "How much capital has been called or contributed by investors?"),
        ("Unfunded commitments", "What are the unfunded commitments remaining?"),
    ]),
    ("Distributions", [
        ("Distributions paid", "How much has been distributed to investors?"),
        ("Distribution policy", "What is the distribution policy and waterfall?"),
    ]),
    ("Net asset value", [
        ("NAV", "What is the net asset value of the fund and as of what date?"),
        ("Valuation basis", "How are investments valued and by whom?"),
    ]),
    ("Performance", [
        ("IRR", "What is the net IRR of the fund?"),
        ("Multiples", "What are the TVPI, DPI and RVPI of the fund?"),
    ]),
    ("Portfolio updates", [
        ("Portfolio companies", "Which portfolio companies or investments did the fund make?"),
        ("Realisations", "What investments were realised or exited?"),
    ]),
    ("Fees and expenses", [
        ("Management fee", "What is the management fee?"),
        ("Carried interest", "What is the carried interest and hurdle rate?"),
        ("Fund expenses", "What fund expenses are charged to investors?"),
    ]),
]  # fmt: skip


@dataclass(frozen=True)
class ReportLine:
    label: str
    text: str  # answer sentence(s) with citations, or NOT_DISCLOSED
    chunk_ids: list[str]
    disclosed: bool


@dataclass(frozen=True)
class ReportSection:
    title: str
    lines: list[ReportLine]


def draft_report(
    engine: Engine, sections: list[tuple[str, list[tuple[str, str]]]] | None = None
) -> list[ReportSection]:
    out: list[ReportSection] = []
    for title, fields in sections or SECTIONS:
        lines: list[ReportLine] = []
        for label, question in fields:
            a = engine.ask(question)
            if a.refused:
                lines.append(ReportLine(label, NOT_DISCLOSED, [], False))
            else:
                lines.append(ReportLine(label, a.text, [c.chunk_id for c in a.sources], True))
        out.append(ReportSection(title, lines))
    return out


def render_markdown(report: list[ReportSection]) -> str:
    parts: list[str] = []
    for sec in report:
        parts.append(f"## {sec.title}\n")
        for ln in sec.lines:
            src = f" (chunks: {', '.join(ln.chunk_ids)})" if ln.chunk_ids else ""
            parts.append(f"- **{ln.label}:** {ln.text}{src}")
        parts.append("")
    return "\n".join(parts)


def disclosure_rate(report: list[ReportSection]) -> tuple[int, int]:
    """(fields disclosed, fields total): the share of the report the documents could support."""
    lines = [ln for s in report for ln in s.lines]
    return sum(1 for ln in lines if ln.disclosed), len(lines)
