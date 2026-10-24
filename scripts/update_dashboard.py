"""Rebuild index.html from free public data. No API key needed.

Sources: Yahoo Finance chart endpoint (indices, USD/INR, Brent, US markets),
NSE India (GIFT Nifty, FII/DII flows) and Google News RSS (headlines).
Anything that cannot be fetched is shown as "not found". Nothing is guessed.
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
TEMPLATE = ROOT / "scripts" / "template.html"
IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0"
NF = "not found"
FLAT_BAND_PCT = 0.1  # within +/-0.1% of the Nifty close counts as flat

NEWS_QUERY = "Sensex Nifty stock market India when:1d"
POSITIVE = ("rally", "rallies", "surge", "surges", "gain", "gains", "jump", "jumps", "rise",
            "rises", "record high", "soar", "soars", "upbeat", "rebound", "buying", "cut rate",
            "rate cut", "beats", "strong")
NEGATIVE = ("fall", "falls", "drop", "drops", "slump", "slumps", "plunge", "plunges", "crash",
            "tumble", "tumbles", "selloff", "sell-off", "selling", "weak", "decline", "declines",
            "loss", "losses", "slide", "slides", "misses", "war", "tariff", "outflow")
# (keywords, line) - first match wins. Rough, general rules; not a view on any stock.
IMPACT_RULES = (
    (("crude", "brent", "oil"), "Oil moves matter most to importers, airlines and paint makers on one side and oil producers on the other."),
    (("rupee", "dollar", "forex", "usd/inr"), "A weaker rupee tends to help exporters and hurt importers and borrowers in dollars."),
    (("rbi", "repo", "interest rate", "rate cut", "rate hike", "inflation"), "Rate and inflation news tends to affect banks, borrowers and rate-sensitive sectors."),
    (("fii", "fpi", "foreign investor", "dii"), "Foreign and domestic fund flows tend to move the broad market."),
    (("fed", "wall street", "nasdaq", "s&p", "dow", "us market"), "US market moves tend to set the mood for Asian markets at the open."),
    (("ipo", "listing"), "IPO news matters most to the company, its bankers and people applying."),
    (("earnings", "results", "profit", "q1", "q2", "q3", "q4"), "Results mainly affect the company's own shareholders and its sector peers."),
    (("tariff", "trade", "export"), "Trade rules tend to help domestic producers and hurt exporters, or the reverse."),
)
IMPACT_DEFAULT = "The headline alone does not say who is helped or hurt."


# ---------------------------------------------------------------- fetching

def make_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", UA)]
    return opener


OPENER = make_opener()


def fetch(url, headers=None, retries=2):
    last = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(3 * attempt)  # back off after a failure (e.g. HTTP 429)
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with OPENER.open(req, timeout=20) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # network errors vary widely
            last = exc
    print(f"  fetch failed: {url} ({last})", file=sys.stderr)
    return None


def yahoo_bars(symbol):
    """Return (meta, [(date_in_exchange_tz, close), ...]) or (None, [])."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol) + "?range=1mo&interval=1d")
    time.sleep(1)  # be gentle with Yahoo
    raw = fetch(url)
    if not raw:
        return None, []
    try:
        result = json.loads(raw)["chart"]["result"][0]
        meta = result["meta"]
        tz = timezone(timedelta(seconds=meta.get("gmtoffset", 0)))
        closes = result["indicators"]["quote"][0]["close"]
        bars = [(datetime.fromtimestamp(t, tz).date(), c)
                for t, c in zip(result["timestamp"], closes) if c is not None]
        return meta, bars
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"  bad Yahoo data for {symbol}: {exc}", file=sys.stderr)
        return None, []


def prev_close(symbol, today):
    """Last completed daily close before today (IST date)."""
    meta, bars = yahoo_bars(symbol)
    bars = [b for b in bars if b[0] < today]
    if not bars:
        return None
    d, c = bars[-1]
    return {"value": c, "when": f"close of {d:%d %b %Y}", "source": "Yahoo Finance"}


def last_move(symbol, today):
    """Last close and % change vs the close before it."""
    _, bars = yahoo_bars(symbol)
    if len(bars) < 2:
        return None
    (_, prev), (d, last) = bars[-2], bars[-1]
    return {"value": last, "pct": (last - prev) / prev * 100,
            "when": f"close of {d:%d %b %Y}", "source": "Yahoo Finance"}


def latest_price(symbol):
    meta, _ = yahoo_bars(symbol)
    if not meta or meta.get("regularMarketPrice") is None:
        return None
    ts = datetime.fromtimestamp(meta["regularMarketTime"], IST)
    return {"value": meta["regularMarketPrice"], "when": f"{ts:%d %b %Y, %H:%M} IST",
            "source": "Yahoo Finance"}


def nse_get(path):
    fetch("https://www.nseindia.com/", retries=0)  # sets cookies NSE expects
    raw = fetch("https://www.nseindia.com" + path,
                headers={"Referer": "https://www.nseindia.com/", "Accept": "application/json"})
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def gift_nifty():
    data = nse_get("/api/marketStatus")
    try:
        g = data["giftnifty"]
        return {"value": float(g["LASTPRICE"]), "when": f"NSE timestamp {g.get('TIMESTMP', NF)}",
                "source": "NSE India"}
    except (KeyError, TypeError, ValueError):
        return None


def fii_dii():
    data = nse_get("/api/fiidiiTradeReact")
    try:
        rows = {r["category"]: r for r in data}
        fii = rows["FII/FPI"]
        dii = rows["DII"]
        return {"fii": float(fii["netValue"]), "dii": float(dii["netValue"]),
                "when": f"session of {fii['date']}", "source": "NSE India"}
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------- headlines

def tone_of(title):
    t = title.lower()
    pos = sum(w in t for w in POSITIVE)
    neg = sum(w in t for w in NEGATIVE)
    return "positive" if pos > neg else "negative" if neg > pos else "neutral"


def impact_of(title):
    t = title.lower()
    for words, line in IMPACT_RULES:
        if any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in words):
            return line
    return IMPACT_DEFAULT


def headlines(limit=8):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(NEWS_QUERY)
           + "&hl=en-IN&gl=IN&ceid=IN:en")
    raw = fetch(url)
    out, seen = [], set()
    if not raw:
        return out
    try:
        items = ET.fromstring(raw).iter("item")
        for item in items:
            title = (item.findtext("title") or "").strip()
            source = (item.findtext("source") or "").strip()
            if source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
            key = re.sub(r"\W+", "", title.lower())[:60]
            if not title or key in seen:
                continue
            seen.add(key)
            when = item.findtext("pubDate") or NF
            out.append({"title": title, "source": source or NF, "when": when,
                        "tone": tone_of(title), "impact": impact_of(title)})
            if len(out) == limit:
                break
    except ET.ParseError as exc:
        print(f"  bad RSS: {exc}", file=sys.stderr)
    return out


# ---------------------------------------------------------------- rendering

def esc(x):
    return html.escape(str(x), quote=True)


def num(x, dec=2):
    return f"{x:,.{dec}f}"


def signed(x, dec=2):
    return f"{x:+,.{dec}f}"


def meta_line(d):
    if not d:
        return f"Source: {NF} · Published: {NF}"
    return f"Source: {esc(d['source'])} · Published: {esc(d['when'])}"


def tile(label, d, text, extra=""):
    return (f'    <div class="tile">\n      <div class="label">{esc(label)}</div>\n'
            f'      <div class="value">{esc(text if d else NF)}</div>\n{extra}'
            f'      <div class="sub">{meta_line(d)}</div>\n    </div>')


def rows_tile(label, d, rows):
    body = "".join(f'      <div class="row"><span>{esc(n)}</span><span>{esc(v if d else NF)}</span></div>\n'
                   for n, v in rows)
    return (f'    <div class="tile">\n      <div class="label">{esc(label)}</div>\n{body}'
            f'      <div class="sub">{meta_line(d)}</div>\n    </div>')


def build(today):
    print("Fetching data...")
    gift = gift_nifty()
    nifty = prev_close("^NSEI", today)
    sensex = prev_close("^BSESN", today)
    vix = prev_close("^INDIAVIX", today)
    usdinr = latest_price("INR=X")
    brent = latest_price("BZ=F")
    us = {n: last_move(s, today) for n, s in (("S&P 500", "^GSPC"), ("Nasdaq", "^IXIC"), ("Dow", "^DJI"))}
    flows = fii_dii()
    news = headlines()

    # Expected open: GIFT Nifty minus Nifty previous close.
    if gift and nifty:
        gap = gift["value"] - nifty["value"]
        pct = gap / nifty["value"] * 100
        label = "flat" if abs(pct) <= FLAT_BAND_PCT else "gap-up" if gap > 0 else "gap-down"
        tone = {"gap-up": "positive", "gap-down": "negative", "flat": "neutral"}[label]
        exp_html = (
            '    <div class="tile expected">\n      <div class="label">Expected open</div>\n'
            f'      <div class="value">{esc(signed(gap))} pts</div>\n'
            f'      <div class="sub"><span class="tone {tone}">{label}</span> '
            f'GIFT Nifty {esc(num(gift["value"]))} minus Nifty previous close {esc(num(nifty["value"]))} '
            f'({esc(signed(pct))}%). Flat means within ±{FLAT_BAND_PCT}%.</div>\n    </div>')
    else:
        gap = label = None
        exp_html = (
            '    <div class="tile expected">\n      <div class="label">Expected open</div>\n'
            f'      <div class="value">{NF}</div>\n'
            '      <div class="sub">Needs both GIFT Nifty and the Nifty previous close.</div>\n    </div>')

    us_found = any(us.values())
    us_rows = [(n, f"{num(d['value'])} ({signed(d['pct'])}%)" if d else NF) for n, d in us.items()]
    us_meta = next((d for d in us.values() if d), None)
    flow_rows = [("FII net (₹ crore)", signed(flows["fii"]) if flows else NF),
                 ("DII net (₹ crore)", signed(flows["dii"]) if flows else NF)]

    tiles = "\n".join([
        tile("GIFT Nifty", gift, num(gift["value"]) if gift else ""),
        tile("Nifty 50 previous close", nifty, num(nifty["value"]) if nifty else ""),
        tile("Sensex previous close", sensex, num(sensex["value"]) if sensex else ""),
        tile("India VIX", vix, num(vix["value"]) if vix else ""),
        tile("USD/INR", usdinr, num(usdinr["value"], 4) if usdinr else ""),
        tile("Brent crude (USD)", brent, num(brent["value"]) if brent else ""),
        rows_tile("US markets overnight", us_meta if us_found else None, us_rows),
        rows_tile("FII and DII net flows (previous session)", flows, flow_rows),
        exp_html,
    ])

    if news:
        items = []
        for h in news:
            items.append(
                '    <li class="card">\n'
                f'      <div class="headline-title">{esc(h["title"])}</div>\n'
                f'      <div class="meta"><span>Source: {esc(h["source"])}</span>'
                f'<span>{esc(h["when"])}</span><span class="tone {h["tone"]}">{h["tone"]}</span></div>\n'
                f'      <div class="impact">Who it helps or hurts: {esc(h["impact"])}</div>\n    </li>')
        headlines_html = "\n".join(items)
    else:
        headlines_html = f'    <li class="card"><div class="headline-title">Headlines {NF}</div></li>'

    # Five plain sentences, built only from numbers shown above.
    s1 = (f"GIFT Nifty is at {num(gift['value'])} against a Nifty 50 previous close of {num(nifty['value'])}, "
          f"an expected open of {signed(gap)} points ({label})."
          if gap is not None else
          "The expected open could not be worked out because GIFT Nifty or the Nifty 50 previous close was not found.")
    s2 = (f"Sensex closed at {num(sensex['value'])}." if sensex else "The Sensex previous close was not found.") + \
         (f" India VIX closed at {num(vix['value'])}." if vix else " India VIX was not found.")
    s3 = ("Overnight in the US, " + ", ".join(
        f"the {n} moved {signed(d['pct'])}%" for n, d in us.items() if d) + "."
          if us_found else "US overnight moves were not found.")
    s4 = (f"USD/INR is at {num(usdinr['value'], 4)}" if usdinr else "USD/INR was not found") + \
         (f" and Brent crude is at {num(brent['value'])} dollars." if brent else " and Brent crude was not found.")
    s5 = (f"In the previous session FIIs were net {'buyers' if flows['fii'] >= 0 else 'sellers'} "
          f"({signed(flows['fii'])} crore rupees) and DIIs were net "
          f"{'buyers' if flows['dii'] >= 0 else 'sellers'} ({signed(flows['dii'])} crore rupees)."
          if flows else "FII and DII flows for the previous session were not found.")
    brief = "\n".join(f"    <p>{esc(s)}</p>" for s in (s1, s2, s3, s4, s5))

    found = sum(x is not None for x in (gift, nifty, sensex, vix, usdinr, brent, flows)) + int(us_found)
    updated = datetime.now(IST).strftime("%d %b %Y, %H:%M") + " IST"
    page = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        updated=esc(updated), tiles=tiles, headlines=headlines_html, brief=brief)
    return page, found


def check(page, found):
    problems = []
    if not page.lower().startswith("<!doctype html>"):
        problems.append("does not start with <!doctype html>")
    if not page.rstrip().lower().endswith("</html>"):
        problems.append("does not end with </html>")
    for words in ("Expected open", "Not investment advice"):
        if words not in page:
            problems.append(f'missing the words "{words}"')
    if len(page) < 3000:
        problems.append(f"too short ({len(page)} characters)")
    if found < 3:
        problems.append(f"only {found} of 8 data groups found; sources look blocked or down")
    return problems


def main():
    page, found = build(datetime.now(IST).date())
    problems = check(page, found)
    if problems:
        print("Safety check failed. Keeping the old index.html.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    INDEX.write_text(page, encoding="utf-8")
    print(f"index.html updated ({found} of 8 data groups found).")


if __name__ == "__main__":
    main()
