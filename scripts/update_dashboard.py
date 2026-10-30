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
from datetime import datetime, time as dtime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
TEMPLATE = ROOT / "scripts" / "template.html"
HISTORY = ROOT / "history.json"
IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0"
NF = "not found"
FLAT_BAND_PCT = 0.1  # within +/-0.1% of the Nifty close counts as flat
SPARK_DAYS = 22  # about one month of trading days
TOP_N = 8  # bars shown per top-performers chart
LINE_N = 5  # stocks drawn on the one-month line graph
LAB_MIN_BARS = 15  # a stock needs this many daily closes to be screened
LAB_SHOWN = 10  # screened stocks offered in the strategy lab
# Sensex stocks, priced from their NSE listings on Yahoo Finance (.NS). BSE's own website
# API refuses scripted requests and Yahoo's BSE (.BO) history has gaps, so NSE prices are
# used for the same companies. This fixed list may lag index changes; symbols Yahoo does
# not know are skipped and the card says how many loaded.
SENSEX_SYMBOLS = (
    "ADANIPORTS", "ASIANPAINT", "AXISBANK", "BAJAJFINSV", "BAJFINANCE", "BHARTIARTL", "ETERNAL",
    "HCLTECH", "HDFCBANK", "HINDUNILVR", "ICICIBANK", "INFY", "ITC", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "POWERGRID", "RELIANCE", "SBIN", "SUNPHARMA", "TATASTEEL",
    "TCS", "TECHM", "TITAN", "TMPV", "TRENT", "ULTRACEMCO",
)
HISTORY_KEEP = 60
HISTORY_SHOWN = 10
PRE_OPEN = dtime(9, 15)  # only runs before this time (IST) are recorded as predictions

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


_BARS_CACHE = {}


def yahoo_bars(symbol):
    """Return (meta, [(date_in_exchange_tz, close, open), ...]) or (None, [])."""
    if symbol in _BARS_CACHE:
        return _BARS_CACHE[symbol]
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(symbol) + "?range=1mo&interval=1d")
    time.sleep(1)  # be gentle with Yahoo
    raw = fetch(url)
    out = (None, [])
    if raw:
        try:
            result = json.loads(raw)["chart"]["result"][0]
            meta = result["meta"]
            tz = timezone(timedelta(seconds=meta.get("gmtoffset", 0)))
            quote = result["indicators"]["quote"][0]
            bars = [(datetime.fromtimestamp(t, tz).date(), c, o)
                    for t, c, o in zip(result["timestamp"], quote["close"], quote["open"])
                    if c is not None]
            out = (meta, bars)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            print(f"  bad Yahoo data for {symbol}: {exc}", file=sys.stderr)
    _BARS_CACHE[symbol] = out
    return out


def pct_change(last, prev):
    return (last - prev) / prev * 100 if prev else None


def prev_close(symbol, today):
    """Last completed daily close before today (IST date), with change and trend."""
    _, bars = yahoo_bars(symbol)
    bars = [b for b in bars if b[0] < today]
    if not bars:
        return None
    d, c, _ = bars[-1]
    return {"value": c, "pct": pct_change(c, bars[-2][1]) if len(bars) > 1 else None,
            "spark": [b[1] for b in bars[-SPARK_DAYS:]],
            "when": f"close of {d:%d %b %Y}", "source": "Yahoo Finance"}


def last_move(symbol, today):
    """Last close and % change vs the close before it."""
    _, bars = yahoo_bars(symbol)
    if len(bars) < 2:
        return None
    (_, prev, _), (d, last, _) = bars[-2], bars[-1]
    return {"value": last, "pct": pct_change(last, prev),
            "spark": [b[1] for b in bars[-SPARK_DAYS:]],
            "when": f"close of {d:%d %b %Y}", "source": "Yahoo Finance"}


def latest_price(symbol):
    meta, bars = yahoo_bars(symbol)
    if not meta or meta.get("regularMarketPrice") is None:
        return None
    price = meta["regularMarketPrice"]
    ts = datetime.fromtimestamp(meta["regularMarketTime"], IST)
    tz = timezone(timedelta(seconds=meta.get("gmtoffset", 0)))
    quote_day = datetime.fromtimestamp(meta["regularMarketTime"], tz).date()
    before = [b[1] for b in bars if b[0] < quote_day]
    return {"value": price, "pct": pct_change(price, before[-1]) if before else None,
            "spark": (before + [price])[-SPARK_DAYS:],
            "when": f"{ts:%d %b %Y, %H:%M} IST", "source": "Yahoo Finance"}


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


def nse_gainers(limit=TOP_N):
    """Top gainers from NSE: Nifty 50 and all securities, gain measured from previous close."""
    data = nse_get("/api/live-analysis-variations?index=gainers")
    if not data:
        return None
    out = {}
    for key in ("NIFTY", "allSec"):
        block = data.get(key) or {}
        rows = []
        for r in block.get("data", []):
            try:
                price, prev = float(r["ltp"]), float(r["prev_price"])
                if prev > 0:
                    rows.append({"symbol": r["symbol"], "price": price, "prev": prev,
                                 "pct": (price - prev) / prev * 100})
            except (KeyError, TypeError, ValueError):
                continue
        rows.sort(key=lambda r: r["pct"], reverse=True)
        if rows:
            out[key] = {"rows": rows[:limit], "all": rows, "source": "NSE India",
                        "when": f"NSE timestamp {block.get('timestamp', NF)}"}
    return out or None


def sensex_gainers(nse, limit=TOP_N):
    """Top Sensex movers: last close versus the close of the trading day before it.

    A Sensex stock found in NSE's own gainers list uses that row. Others come from Yahoo,
    whose histories can skip a day (which would inflate a gain), so a Yahoo row is used
    only when its previous bar is the session right before the latest one (by the Nifty
    calendar) or when it has a single bar and Yahoo gives the close before it.
    """
    nse_rows = {r["symbol"]: r for r in ((nse or {}).get("NIFTY") or {}).get("all", [])
                if r["symbol"] in SENSEX_SYMBOLS}
    _, nifty_bars = yahoo_bars("^NSEI")
    sessions = sorted({b[0] for b in nifty_bars})
    raw = {}
    for sym in SENSEX_SYMBOLS:
        meta, bars = yahoo_bars(sym + ".NS")
        if bars:
            raw[sym] = (meta, bars)
    if not raw or len(sessions) < 2:
        return None
    latest = max(bars[-1][0] for _, bars in raw.values())
    if latest not in sessions or sessions.index(latest) == 0:
        return None
    expected_prev = sessions[sessions.index(latest) - 1]
    found = []
    for sym, (meta, bars) in raw.items():
        if sym in nse_rows:
            continue
        if bars[-1][0] != latest:
            continue
        if len(bars) >= 2:
            if bars[-2][0] != expected_prev:
                continue
            prev = bars[-2][1]
        else:
            prev = (meta or {}).get("chartPreviousClose")
        if prev:
            price = bars[-1][1]
            found.append({"symbol": sym, "price": price, "prev": prev, "pct": pct_change(price, prev)})
    found += list(nse_rows.values())
    if not found:
        return None
    found.sort(key=lambda r: r["pct"], reverse=True)
    return {"rows": found[:limit], "source": "NSE India, plus Yahoo Finance for stocks not in NSE's list",
            "when": f"{latest:%d %b %Y} vs close of {expected_prev:%d %b %Y}",
            "note": f"Only {len(found)} of {len(SENSEX_SYMBOLS)} Sensex stocks had complete data, "
                    "so this list may miss some movers." if len(found) < len(SENSEX_SYMBOLS)
            else f"All {len(SENSEX_SYMBOLS)} Sensex stocks loaded."}


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


def direction(pct, mode="normal"):
    """CSS class for a move. mode: normal (up is green), invert (up is red), neutral (no judgement)."""
    if pct is None or abs(pct) < 0.005:
        return "flat"
    up = pct > 0
    if mode == "neutral":
        return "move-up" if up else "move-down"
    if mode == "invert":
        up = not up
    return "up" if up else "down"


def chg(pct, mode="normal"):
    if pct is None:
        return ""
    arrow = "▲" if pct > 0 else "▼" if pct < 0 else "■"
    return f'<span class="chg {direction(pct, mode)}">{arrow} {esc(signed(pct))}%</span>'


def spark(values, mode="normal"):
    """Inline SVG trend line for the last month."""
    if not values or len(values) < 2:
        return ""
    w, h, pad = 120, 32, 3
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = [(pad + i * (w - 2 * pad) / (len(values) - 1), h - pad - (v - lo) / span * (h - 2 * pad))
           for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad},{h - pad} {line} {w - pad},{h - pad}"
    cls = direction(pct_change(values[-1], values[0]), mode)
    ex, ey = pts[-1]
    label = f"Trend over {len(values)} trading days, from {num(values[0])} to {num(values[-1])}"
    return (f'      <svg class="spark {cls}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
            f'<polygon points="{area}" fill="currentColor" opacity="0.15"/>'
            f'<polyline points="{line}" fill="none" stroke="currentColor" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="2.4" fill="currentColor"/></svg>\n')


def tile(label, d, text, mode="normal", with_chg=True):
    change = chg(d.get("pct"), mode) if d and with_chg else ""
    return (f'    <div class="tile">\n      <div class="label">{esc(label)}</div>\n'
            f'      <div class="value">{esc(text if d else NF)} {change}</div>\n'
            f'{spark(d["spark"], mode) if d and d.get("spark") else ""}'
            f'      <div class="sub">{meta_line(d)}</div>\n    </div>')


def rows_tile(label, d, rows):
    """rows are (name, already-escaped html)."""
    body = "".join(f'      <div class="row"><span>{esc(n)}</span><span>{v if d else NF}</span></div>\n'
                   for n, v in rows)
    return (f'    <div class="tile">\n      <div class="label">{esc(label)}</div>\n{body}'
            f'      <div class="sub">{meta_line(d)}</div>\n    </div>')


# ---------------------------------------------------------------- top performers

def bar_chart(title, d):
    head = f'    <div class="card perf">\n      <h3>{esc(title)}</h3>\n'
    if not d or not d["rows"]:
        return head + f'      <div class="value">{NF}</div>\n      <div class="sub">Source: {NF}</div>\n    </div>'
    top = max(abs(r["pct"]) for r in d["rows"]) or 1
    rows = []
    for r in d["rows"]:
        cls = direction(r["pct"])
        rows.append(
            '      <div class="bar-row">\n'
            f'        <div class="bar-head"><span class="bar-sym">{esc(r["symbol"])}</span>'
            f'<span class="chg {cls}">{esc(signed(r["pct"]))}%</span></div>\n'
            f'        <div class="bar-track" role="img" aria-label="{esc(r["symbol"])} {esc(signed(r["pct"]))} percent">'
            f'<div class="bar-fill {cls}" style="width:{max(abs(r["pct"]) / top * 100, 2):.1f}%"></div></div>\n'
            f'        <div class="sub">₹{esc(num(r["price"]))} now · ₹{esc(num(r["prev"]))} previous close · '
            f'{"+" if r["price"] >= r["prev"] else "-"}₹{esc(num(abs(r["price"] - r["prev"])))}</div>\n'
            '      </div>')
    note = f' {esc(d["note"])}' if d.get("note") else ""
    return (head + "\n".join(rows) +
            f'\n      <div class="sub">Source: {esc(d["source"])} · {esc(d["when"])}.{note}</div>\n    </div>')


def month_lines(nse):
    """One-month % change since the start of the window for the top Nifty 50 gainers."""
    rows = ((nse or {}).get("NIFTY") or {}).get("rows", [])[:LINE_N]
    _, nifty_bars = yahoo_bars("^NSEI")
    sessions = sorted({b[0] for b in nifty_bars})[-SPARK_DAYS:]
    if not rows or len(sessions) < 2:
        return None
    series = []
    for r in rows:
        _, bars = yahoo_bars(r["symbol"] + ".NS")
        pts = [(d, c) for d, c, _ in bars if d >= sessions[0] and c]
        if len(pts) >= 2:
            base = pts[0][1]
            series.append({"symbol": r["symbol"], "pts": [(d, (c / base - 1) * 100) for d, c in pts]})
    return {"sessions": sessions, "series": series} if series else None


SERIES_COLOURS = ("var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)")


def line_graph(d):
    head = ('    <div class="card perf wide">\n'
            '      <h3>Last month: today\'s top 5 Nifty 50 gainers</h3>\n')
    if not d:
        return head + f'      <div class="value">{NF}</div>\n    </div>'
    sessions, series = d["sessions"], d["series"]
    w, h, left, right, top, bottom = 640, 280, 44, 12, 12, 26
    ys = [v for sr in series for _, v in sr["pts"]] + [0]
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    step = next(x for x in (1, 2, 5, 10, 20, 50) if (hi - lo) / x <= 6)
    xpos = {day: left + i * (w - left - right) / (len(sessions) - 1) for i, day in enumerate(sessions)}

    def y(v):
        return top + (hi - v) / (hi - lo) * (h - top - bottom)

    parts = [f'<svg class="linegraph" viewBox="0 0 {w} {h}" role="img" '
             f'aria-label="Line graph of the last month\'s percentage change for {esc(", ".join(sr["symbol"] for sr in series))}">']
    tick = (int(lo // step) + 1) * step
    while tick < hi:
        yy = y(tick)
        parts.append(f'<line x1="{left}" x2="{w - right}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid-line{" zero" if tick == 0 else ""}"/>'
                     f'<text x="{left - 6}" y="{yy + 3.5:.1f}" text-anchor="end" class="axis">{"0" if tick == 0 else f"{tick:+d}"}%</text>')
        tick += step
    if lo < 0 < hi and 0 % step:
        yy = y(0)
        parts.append(f'<line x1="{left}" x2="{w - right}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid-line zero"/>'
                     f'<text x="{left - 6}" y="{yy + 3.5:.1f}" text-anchor="end" class="axis">0%</text>')
    for i, day in ((0, sessions[0]), (len(sessions) // 2, sessions[len(sessions) // 2]), (len(sessions) - 1, sessions[-1])):
        anchor = "start" if i == 0 else "end" if i == len(sessions) - 1 else "middle"
        parts.append(f'<text x="{xpos[day]:.1f}" y="{h - 8}" text-anchor="{anchor}" class="axis">{day:%d %b}</text>')
    for sr, colour in zip(series, SERIES_COLOURS):
        pts = [(xpos[day], y(v)) for day, v in sr["pts"] if day in xpos]
        if len(pts) < 2:
            continue
        parts.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" '
                     f'stroke="{colour}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
                     f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3.2" fill="{colour}"/>')
    parts.append('</svg>')
    legend = "".join(
        f'<span class="legend-item"><i style="background:{c}"></i>{esc(sr["symbol"])} '
        f'<b class="{direction(sr["pts"][-1][1])}">{esc(signed(sr["pts"][-1][1]))}%</b></span>'
        for sr, c in zip(series, SERIES_COLOURS))
    return (head + "      " + "".join(parts) + f'\n      <div class="legend">{legend}</div>\n'
            f'      <div class="sub">Each line starts at 0% on {sessions[0]:%d %b %Y} and shows the change in closing '
            'price since then; the last point is the latest price. Source: Yahoo Finance (NSE listings).</div>\n    </div>')


def strategy_lab():
    """Rule-based screen of Sensex stocks on past prices, for the strategy lab.

    Rules: rose over the window, latest close above its 10-day average, and ranked by
    window return divided by daily volatility. This describes the past only.
    """
    stocks = []
    for sym in SENSEX_SYMBOLS:
        _, bars = yahoo_bars(sym + ".NS")
        closes = [c for _, c, _ in bars]
        if len(closes) < LAB_MIN_BARS:
            continue
        rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        mean = sum(rets) / len(rets)
        vol = (sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) ** 0.5 * 100
        stocks.append({"symbol": sym, "price": round(closes[-1], 2),
                       "ret": round((closes[-1] / closes[0] - 1) * 100, 2), "vol": round(vol, 2),
                       "above": closes[-1] > sum(closes[-10:]) / 10, "since": bars[0][0].isoformat()})
    passing = [x for x in stocks if x["ret"] > 0 and x["above"] and x["vol"] > 0]
    for x in passing:
        x["score"] = round(x["ret"] / x["vol"], 2)
    passing.sort(key=lambda x: x["score"], reverse=True)
    for x in passing:
        del x["above"]
    return {"stocks": passing[:LAB_SHOWN], "checked": len(stocks), "universe": len(SENSEX_SYMBOLS)}


def lab_html(lab):
    blob = json.dumps(lab).replace("<", "\\u003c")
    return blob, (f"{len(lab['stocks'])} of {lab['checked']} screened Sensex stocks passed the rules"
                  if lab["checked"] else "Price history was not found")


def performers_html(nse, bse):
    nse = nse or {}
    return "\n".join([
        bar_chart("NSE · Nifty 50 top gainers", nse.get("NIFTY")),
        bar_chart("Sensex 30 · top gainers (NSE prices)", bse),
        bar_chart("NSE · all stocks top gainers", nse.get("allSec")),
        line_graph(month_lines(nse)),
    ])


# ---------------------------------------------------------------- history

def load_history():
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_history(history, now, today, gift, nifty):
    """Fill in actual opens for past days, then record today's prediction (pre-open runs only)."""
    _, bars = yahoo_bars("^NSEI")
    opens = {b[0].isoformat(): b[2] for b in bars if b[2] is not None}
    for day, entry in history.items():
        if day < today.isoformat() and "actual_open" not in entry and day in opens:
            entry["actual_open"] = opens[day]
            entry["actual_gap"] = opens[day] - entry["nifty_prev"]
    if today.weekday() < 5 and now.time() < PRE_OPEN and gift and nifty:
        gap = gift["value"] - nifty["value"]
        history[today.isoformat()] = {
            "gift": gift["value"], "nifty_prev": nifty["value"], "pred_gap": gap,
            "label": "flat" if abs(gap / nifty["value"] * 100) <= FLAT_BAND_PCT
            else "gap-up" if gap > 0 else "gap-down"}
    for day in sorted(history)[:-HISTORY_KEEP]:
        del history[day]
    return history


def history_html(history):
    days = sorted(history, reverse=True)[:HISTORY_SHOWN]
    if not days:
        return ('    <p class="sub">No days recorded yet. A day is recorded when the page is built '
                'on a weekday before 9:15 AM IST, and its actual open is filled in the next run.</p>')
    rows, done, hits = [], 0, 0
    for day in days:
        e = history[day]
        if "actual_gap" in e:
            match = (e["pred_gap"] > 0) == (e["actual_gap"] > 0)
            done += 1
            hits += match
            actual = esc(signed(e["actual_gap"]))
            verdict = '<span class="chg up">same direction</span>' if match else '<span class="chg down">opposite</span>'
        else:
            actual, verdict = "pending", ""
        rows.append(f'      <tr><td>{esc(datetime.fromisoformat(day).strftime('%d %b %Y'))}</td>'
                    f'<td>{esc(signed(e["pred_gap"]))} <span class="sub">{esc(e["label"])}</span></td>'
                    f'<td>{actual}</td><td>{verdict}</td></tr>')
    summary = (f"Predicted direction matched the actual open on {hits} of {done} completed days shown."
               if done else "No completed days yet.")
    return (f'    <p class="sub">{summary} Points versus the Nifty previous close. '
            'Actual open comes from the Yahoo daily bar.</p>\n'
            '    <div class="table-wrap"><table>\n'
            '      <thead><tr><th>Date</th><th>GIFT-implied gap</th><th>Actual gap</th><th>Result</th></tr></thead>\n'
            '      <tbody>\n' + "\n".join(rows) + '\n      </tbody>\n    </table></div>')


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
    nse_top = nse_gainers()
    bse_top = sensex_gainers(nse_top)

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
    us_rows = [(n, f"{esc(num(d['value']))} {chg(d['pct'])}" if d else NF) for n, d in us.items()]
    us_meta = next((d for d in us.values() if d), None)
    def flow(v):
        return f'<span class="chg {direction(v)}">{esc(signed(v))}</span>'

    flow_rows = [("FII net (₹ crore)", flow(flows["fii"]) if flows else NF),
                 ("DII net (₹ crore)", flow(flows["dii"]) if flows else NF)]

    tiles = "\n".join([
        tile("GIFT Nifty", gift, num(gift["value"]) if gift else ""),
        tile("Nifty 50 previous close", nifty, num(nifty["value"]) if nifty else ""),
        tile("Sensex previous close", sensex, num(sensex["value"]) if sensex else ""),
        tile("India VIX", vix, num(vix["value"]) if vix else "", mode="invert"),
        tile("USD/INR", usdinr, num(usdinr["value"], 4) if usdinr else "", mode="neutral"),
        tile("Brent crude (USD)", brent, num(brent["value"]) if brent else "", mode="neutral"),
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

    lab_json, lab_summary = lab_html(strategy_lab())

    now = datetime.now(IST)
    history = update_history(load_history(), now, today, gift, nifty)

    found = sum(x is not None for x in (gift, nifty, sensex, vix, usdinr, brent, flows)) + int(us_found)
    updated = now.strftime("%d %b %Y, %H:%M") + " IST"
    page = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        updated=esc(updated), tiles=tiles, headlines=headlines_html, brief=brief,
        history=history_html(history), performers=performers_html(nse_top, bse_top),
        lab_json=lab_json, lab_summary=esc(lab_summary))
    return page, found, history


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
    page, found, history = build(datetime.now(IST).date())
    problems = check(page, found)
    if problems:
        print("Safety check failed. Keeping the old index.html.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    INDEX.write_text(page, encoding="utf-8")
    HISTORY.write_text(json.dumps(history, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"index.html updated ({found} of 8 data groups found).")


if __name__ == "__main__":
    main()
