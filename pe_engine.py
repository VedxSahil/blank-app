"""PEReport engine: chunking, BM25 retrieval, refusal rule, fee calculation, report drafting, validation.

Pure standard library plus pypdf (or the pdftotext utility when present). No LLM, no network, zero tokens.
"""
from __future__ import annotations
import json, math, re, shutil, subprocess, unicodedata
from collections import Counter

MISSING = "[Data Point Missing from Sources]"
ROMAN = r"(XVIII|XIX|XVII|XVI|XV|XIV|XIII|XII|XI|IX|X|VIII|VII|VI|IV|V|III|II|I)"
HEAD = re.compile(r"^\s*" + ROMAN + r"\.\s+(.+?)\s*$")
STOP = set("the a an of and or to in is are what for on with by be as at this that it from which who how".split())
GENERIC = set("what who how much many does did have has been date will shall per often long when where which whom whose give tell show list name start begin".split())


# ---------- Step 1: extraction, cleaning, chunking ----------
def clean(t: str) -> str:
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    t = re.sub(r"[^\x20-\x7E\n]", " ", t)
    return re.sub(r"[ \t]+", " ", t)


def pdf_pages(path: str) -> list[str]:
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
        pages = out.split("\f")
        return pages[:-1] if pages and not pages[-1].strip() else pages
    from pypdf import PdfReader
    return [(p.extract_text() or "") for p in PdfReader(path).pages]


def _split_long(p: str, limit: int = 900) -> list[str]:
    if len(p) <= limit:
        return [p]
    out, cur = [], ""
    for s in re.split(r"(?<=[A-Za-z0-9\)\"][.;])\s+", p):
        if cur and len(cur) + len(s) > limit:
            out.append(cur); cur = ""
        cur += (" " if cur else "") + s
    return out + ([cur] if cur else [])


def chunk_pages(pages: list[str], doc: str) -> list[dict]:
    chunks, sec = [], "Front matter"
    for i, pg in enumerate(pages):
        pg, buf = clean(pg), ""

        def flush():
            nonlocal buf
            if buf:
                chunks.append({"doc": doc, "page": i + 1, "section": sec, "text": buf}); buf = ""

        def add(text):
            nonlocal buf
            text = re.sub(r"\s*\n\s*", " ", text).strip()
            if len(text) <= 40:
                return
            for piece in _split_long(text):
                if buf and len(buf) + len(piece) > 900:
                    flush()
                buf += (" " if buf else "") + piece

        for par in re.split(r"\n\s*\n", pg):
            cur = []
            for line in par.split("\n"):
                m = HEAD.match(line) if i > 0 else None
                if m and len(m.group(2)) < 70 and not re.search(r"\s[IVX]+\.\s", m.group(2)) \
                        and re.search(r"[A-Za-z]{4}", m.group(2)) and not re.search(r"\d\s*$", m.group(2)):
                    add(" ".join(cur)); cur = []; flush()
                    sec = f"Section {m.group(1)}: {m.group(2)}"
                else:
                    cur.append(line)
            add(" ".join(cur))
        flush()
    return chunks


def load_document(path: str, name: str | None = None) -> list[dict]:
    name = name or path.split("/")[-1]
    if path.lower().endswith((".xlsx", ".xlsm")):
        return load_xlsx(path, name)
    if path.lower().endswith(".pdf"):
        pages = pdf_pages(path)
    else:
        pages = open(path, encoding="utf8", errors="ignore").read().split("\f")
    return chunk_pages(pages, name)


# ---------- Spreadsheet loader (ILPA Reporting Template and similar workbooks) ----------
SEC_ROW = re.compile(r"^([A-Z](?:\.\d+)?)\.?\s+(.{4,})$")


def _fmt(v):
    import datetime as dt
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v).strip()
    return f"{v:,.0f}" if float(v).is_integer() or abs(v) >= 1000 else f"{v:,.2f}"


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def load_xlsx(path: str, doc: str) -> list[dict]:
    """One chunk per data row. Numeric rows keep a `data` dict {(group, period): value} used for verified metrics."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    chunks = []
    for ws in wb.worksheets:
        sec = ws.title
        groups, periods = {}, {}
        buf, bufloc = "", None

        def flush(loc):
            nonlocal buf, bufloc
            if buf:
                chunks.append({"doc": doc, "page": bufloc[1], "loc": f"{ws.title} row {bufloc[1]}", "section": sec, "text": buf}); buf = ""

        for row in ws.iter_rows():
            r = row[0].row
            cells = {c.column_letter: c.value for c in row if c.value not in (None, "")}
            if not cells:
                continue
            if ws.title == "Definitions" and "D" in cells and "C" in cells:
                if "B" in cells: sec = f"Definitions: {str(cells['B']).strip()}"
                chunks.append({"doc": doc, "page": r, "loc": f"Definitions row {r}", "section": sec,
                               "text": f"Definition of {str(cells['C']).strip()}: {str(cells['D']).strip()}"})
                continue
            label = str(cells.get("B", "")).strip()
            nums = {k: v for k, v in cells.items() if _isnum(v) and k not in ("A", "B")}
            periods_here = {k: v for k, v in cells.items() if str(v) in ("QTD", "YTD", "ITD")}
            if periods_here:
                periods.update(periods_here)
            strs = {k: str(v).strip() for k, v in cells.items() if isinstance(v, str) and k not in ("A", "B")}
            if label and not nums and strs and not periods_here and any(k in strs for k in "EHK"):
                groups = {k: v for k, v in strs.items() if k in "EHK"}          # group header row
            if label and not nums and (m := SEC_ROW.match(label)) and (m.group(1).endswith(tuple("0123456789")) or len(m.group(1)) == 1) \
                    and (not strs or groups):
                sec = f"Section {m.group(1)}: {m.group(2)}"; continue
            if nums and label:
                data, parts = {}, []
                for col, v in nums.items():
                    gcol = "E" if col in "EFG" else "H" if col in "HIJ" else "K"
                    g = groups.get(gcol, gcol); p = periods.get(col, col)
                    data[(g, p)] = v; parts.append(f"{g} {p} {_fmt(v)}")
                chunks.append({"doc": doc, "page": r, "loc": f"{ws.title} row {r}", "section": sec,
                               "text": f"{label}: " + "; ".join(parts), "data": data, "label": label})
            else:
                line = " ".join(f"{_fmt(v)}" for k, v in cells.items())
                if not buf: bufloc = (ws.title, r)
                if len(buf) + len(line) > 900: flush(None); bufloc = (ws.title, r)
                buf += (" | " if buf else "") + line
        flush(None)
    return chunks


# ---------- Step 2: BM25 retrieval ----------
def _stem(w): return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w
def tok(s: str) -> list[str]:
    s = re.sub(r"\bnav\b", "net asset value", s.lower())
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", s) if w not in STOP]


class Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.T = [tok(c["text"] + " " + c["section"]) for c in chunks]
        self.N = max(len(chunks), 1)
        self.avg = (sum(map(len, self.T)) / self.N) or 1
        self.df = Counter(w for t in self.T for w in set(t))
        self.tf = [Counter(t) for t in self.T]
        self.prefix = {w[:5] for w in self.df}
        self.docs = sorted({c["doc"] for c in chunks})
        self.df_doc = {d: Counter(w for t, c in zip(self.T, chunks) if c["doc"] == d for w in set(t)) for d in self.docs}
        self.prefix_doc = {d: {w[:5] for w in self.df_doc[d]} for d in self.docs}

    def search(self, q: str, k: int = 5, only: str | None = None) -> list[dict]:
        qs = tok(q)
        scored = []
        for i, c in enumerate(self.chunks):
            if only and c["doc"] != only:
                continue
            s = 0.0
            for w in qs:
                f = self.tf[i].get(w)
                if not f:
                    continue
                idf = math.log(1 + (self.N - self.df[w] + .5) / (self.df[w] + .5))
                s += idf * f * 2.2 / (f + 1.2 * (.25 + .75 * len(self.T[i]) / self.avg))
            sec_words = set(re.split(r"\W+", c["section"].lower()))
            if any(len(w) > 3 and w in sec_words for w in qs):
                s *= 1.3
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        return [self.chunks[i] for _, i in scored[:k]]

    def hits_for(self, q: str, docs: list[str] | None = None) -> list[dict]:
        docs = docs or self.docs
        if len(docs) > 1:
            return [h for d in docs for h in self.search(q, 5, d)]
        return self.search(q, 5, docs[0] if len(self.docs) > 1 else None)

    # ---------- Step 4: refusal rule (applied per document) ----------
    def support(self, q: str) -> dict:
        if not self.chunks:
            return {"ok": False, "reason": "no document loaded"}
        qs = list(dict.fromkeys(w for w in tok(q) if len(w) >= 3 and w not in GENERIC))
        if not qs:
            return {"ok": False, "reason": "no searchable terms in the question"}
        best_reason, best_rank, ok_docs = "", 99, []
        for d in self.docs:
            seen = lambda w: self.df_doc[d].get(w) or (len(w) >= 5 and w[:5] in self.prefix_doc[d])
            unseen = [w for w in qs if not seen(w)]
            if unseen:
                if len(unseen) < best_rank:
                    best_rank, best_reason = len(unseen), "term(s) not found in the documents: " + ", ".join(unseen)
                continue
            hits = self.search(q, 5, d)
            u = {w for h in hits for w in tok(h["text"])}
            up = {w[:5] for w in u}
            cov = sum(1 for w in qs if w in u or (len(w) >= 5 and w[:5] in up)) / len(qs)
            if cov < 0.6:
                if best_rank > 0.5:
                    best_rank, best_reason = 0.5, f"retrieved passages cover only {round(cov*100)}% of the question terms"
                continue
            ok_docs.append(d)
        if not ok_docs:
            return {"ok": False, "reason": best_reason}
        return {"ok": True, "hits": self.hits_for(q, ok_docs), "docs": ok_docs}


def cite(c: dict) -> str:
    where = c["loc"] if c.get("loc") else f"p.{c['page']}"
    return f"[Source: {c['doc']}, {c['section']}, {where}]"


# ---------- Step 3: fee extraction and verified arithmetic ----------
def _num(x): return float(str(x).replace(",", ""))


def fee_terms(chunks: list[dict], doc: str) -> dict:
    r = {"tiers": [], "perf": None, "mgmt": None}
    tier = re.compile(r"(\d+(?:\.\d+)?)\s?%\s+(?:of the subscription amount|for amounts)\s+(up to|above|over)\s+USD\s?([\d,]+)", re.I)
    perf = re.compile(r"(\d+(?:\.\d+)?)\s?%\s+of the positive (?:difference|amount|appreciation|return|increase)", re.I)
    mg = re.compile(r"management fee[^.]{0,160}?(\d+(?:\.\d+)?)\s?(?:%|per ?cent)\s*(?:per annum|per year|p\.a\.|annually)", re.I)
    for c in (x for x in chunks if x["doc"] == doc):
        for m in tier.finditer(c["text"]):
            r["tiers"].append({"pct": float(m[1]), "up": m[2].lower().startswith("up"), "lim": _num(m[3]), "c": c})
        if not r["perf"] and (m := perf.search(c["text"])):
            r["perf"] = {"pct": float(m[1]), "c": c}
        if not r["mgmt"] and (m := mg.search(c["text"])):
            r["mgmt"] = {"pct": float(m[1]), "c": c}
    return r


def calc_fees(chunks: list[dict], doc: str, amount: float, growth: float) -> dict:
    t = fee_terms(chunks, doc)
    res = {"doc": doc, "initial": None, "performance": None, "management": None}
    if t["tiers"]:
        up = sorted((x for x in t["tiers"] if x["up"]), key=lambda x: x["lim"])
        ab = sorted((x for x in t["tiers"] if not x["up"]), key=lambda x: -x["lim"])
        hit = next((x for x in up if amount <= x["lim"]), None) or next((x for x in ab if amount >= x["lim"]), None) or (ab[0] if ab else None)
        if hit:
            res["initial"] = (round(amount * hit["pct"] / 100, 2), hit["pct"], cite(hit["c"]))
    if t["perf"]:
        res["performance"] = (round(max(amount * growth, 0) * t["perf"]["pct"] / 100, 2), t["perf"]["pct"], cite(t["perf"]["c"]))
    if t["mgmt"]:
        res["management"] = (round(amount * t["mgmt"]["pct"] / 100, 2), t["mgmt"]["pct"], cite(t["mgmt"]["c"]))
    return res


# ---------- Step 5: structured report ----------
KPI_ROWS = ["Vintage", "Commitments", "DPI", "RVPI", "TVPI", "Net IRR"]


def fund_metrics(chunks: list[dict]) -> dict:
    """Compute paid-in based multiples from capital-account rows (LP allocation, inception-to-date). Verified arithmetic."""
    def row(pattern):
        for c in chunks:
            if c.get("data") and re.search(pattern, c.get("label", ""), re.I):
                for (g, p), v in c["data"].items():
                    if "LP" in g.upper() and p == "ITD":
                        return v, c
        return None, None
    out = {}
    contrib, cc = row(r"^Contributions")
    dist, dc = row(r"^Distributions")
    nav, nc = row(r"^Ending NAV\s*.\s*Net")
    commit, kc = row(r"^Total Commitment")
    unf, uc = row(r"^Ending Unfunded")
    if contrib and dist is not None and nav is not None:
        out.update(paid_in=contrib, distributions=abs(dist), nav=nav, dpi=abs(dist) / contrib, rvpi=nav / contrib,
                   tvpi=(abs(dist) + nav) / contrib, cites=[cite(cc), cite(dc), cite(nc)])
    if commit:
        out.update(commitment=commit, commit_cite=cite(kc))
        if unf is not None: out.update(unfunded=unf)
    for c in chunks:
        if (m := re.search(r"Initial Closing:?\s*\|?\s*(\d{4})-\d\d-\d\d", c["text"])):
            out.update(vintage=m.group(1), vintage_cite=cite(c)); break
    return out


def kpi_table(chunks: list[dict]) -> list[tuple[str, str]]:
    fm = fund_metrics(chunks)
    pat = re.compile(r"minimum (?:initial )?(?:investment|subscription)[^.]{0,60}USD ?[\d,]+", re.I)
    rows = []
    for name in KPI_ROWS:
        val = MISSING
        if name == "Vintage" and "vintage" in fm:
            val = f"{fm['vintage']} (year of Initial Closing) {fm['vintage_cite']}"
        elif name == "Commitments" and "commitment" in fm:
            val = f"USD {fm['commitment']:,.0f} total commitment" + (f"; unfunded USD {fm['unfunded']:,.0f}" if "unfunded" in fm else "") + f" {fm['commit_cite']}"
        elif name in ("DPI", "RVPI", "TVPI") and name.lower() in fm:
            num = {"DPI": f"distributions {fm['distributions']:,.0f}", "RVPI": f"ending NAV {fm['nav']:,.0f}",
                   "TVPI": "DPI + RVPI"}[name]
            val = f"{fm[name.lower()]:.2f}x (computed: {num}" + (f" / paid-in {fm['paid_in']:,.0f}) " if name != "TVPI" else f"; paid-in {fm['paid_in']:,.0f}) ") + " ".join(fm["cites"])
        elif name == "Commitments":
            for c in chunks:
                if (m := pat.search(c["text"])):
                    val = f"{m.group(0)} {cite(c)}"; break
        elif name in ("Vintage", "DPI", "RVPI", "TVPI", "Net IRR"):
            key = {"Vintage": r"\bvintage\b", "DPI": r"\bDPI\b", "RVPI": r"\bRVPI\b", "TVPI": r"\bTVPI\b", "Net IRR": r"\bnet IRR\b"}[name]
            for c in chunks:  # reported only if the source states it with a number
                if (m := re.search(key + r"[^.]{0,40}?(\d[\d.,]*\s?(?:x|%)?)", c["text"], re.I)):
                    val = f"{m.group(1)} {cite(c)}"; break
        rows.append((name, val))
    return rows


def quantitative_terms(hits: list[dict], limit: int = 8) -> list[tuple[str, dict]]:
    out = []
    num = re.compile(r"\d+(\.\d+)?\s*(%|per cent|percent)|USD\s?[\d,]+|\d+\s+(days|months|years|Business Days)", re.I)
    for c in hits:
        for s in re.split(r"(?<=[A-Za-z)\"])[.;]\s+", c["text"]):
            if num.search(s):
                out.append((s.strip(), c))
    return out[:limit]


def draft_report(idx: Index, q: str) -> dict:
    sp = idx.support(q)
    if not sp["ok"]:
        return {"refused": True, "reason": sp["reason"]}
    hits = sp["hits"]
    secs = list(dict.fromkeys(h["section"] for h in hits))[:3]
    summary = (f'This report responds to the query "{q}" using {", ".join(idx.docs)}. '
               f'The most relevant disclosures appear in {"; ".join(secs)} {cite(hits[0])}. '
               "Performance metrics that are not disclosed in the sources are not estimated.")
    return {"refused": False, "summary": summary, "kpis": kpi_table(idx.chunks),
            "terms": quantitative_terms(hits), "observations": [(h["text"][:350] + "...", h) for h in hits[:4]]}


# ---------- Validation ----------
def evaluate(idx: Index, gold: list[dict]) -> dict:
    rows = []
    for g in gold:
        sp = idx.support(g["q"]); refused = not sp["ok"]
        text = " ".join(h["text"] for h in sp["hits"]) if sp["ok"] else ""
        if g["answerable"]:
            match = bool(re.search(g["expect"], text, re.I))
            ok = (not refused) and match
            typ = "false refusal" if refused else ("correct answer" if match else "wrong answer")
        else:
            ok = refused
            typ = "correct refusal" if refused else "unsupported answer given"
        rows.append({"q": g["q"], "answerable": g["answerable"], "ok": ok, "type": typ, "why": sp.get("reason", "")})
    n = len(rows); A = [r for r in rows if r["answerable"]]; U = [r for r in rows if not r["answerable"]]
    right = sum(r["ok"] for r in A); cref = sum(r["ok"] for r in U)
    fref = sum(r["type"] == "false refusal" for r in A)
    return {"rows": rows, "n": n, "accuracy": sum(r["ok"] for r in rows) / n, "coverage": right / n,
            "answerable_correct": right / len(A) if A else None, "refusals": cref + fref,
            "correct_refusals": cref, "false_refusals": fref, "wrongly_answered": len(U) - cref, "unanswerable": len(U)}


if __name__ == "__main__":  # python pe_engine.py doc.pdf gold.json
    import sys
    idx = Index(load_document(sys.argv[1]))
    print(len(idx.chunks), "chunks")
    if len(sys.argv) > 2:
        r = evaluate(idx, json.load(open(sys.argv[2])))
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "rows"})
        for x in r["rows"]:
            if not x["ok"]: print(" FAIL:", x["q"], "->", x["type"], x["why"])
