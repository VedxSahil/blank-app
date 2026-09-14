# Nifty Weekly Credit-Spread Strategy — Backtest & Reality Check

A Streamlit app that backtests a trend-filtered, defined-risk options-selling
strategy on the Nifty 50 index, sized to a fixed capital base and a hard
per-trade risk cap — built for a retail F&O trader working with a small,
strictly risk-limited account.

**Read this first:** a strategy that nets 5%/month (~80% annualized) *and*
wins over 80% of trades, after charges, is not a realistic, sustainable
retail target — see the in-app "Reality check" panel and the methodology
section at the bottom of the app for why. This tool computes real backtest
numbers on real (or clearly-labelled synthetic) price data; it does not
force the result to match any target.

## What it does

- Pulls daily Nifty 50 / Nifty Bank price history from Yahoo Finance
  (`engine/data.py`, via `yfinance`).
- Classifies weekly trend with EMA20/EMA50 + RSI14 + an ADX14 strength
  filter (`engine/signals.py`).
- On a qualifying trend, sells a defined-risk credit spread (bull put or
  bear call) sized so the worst-case loss never exceeds your risk cap
  (`engine/backtest.py`), pricing legs with Black-Scholes off realized
  volatility (`engine/pricing.py`) since free data has no real options
  chain.
- Applies an approximate Indian F&O charges model — brokerage, STT,
  exchange transaction charges, SEBI charges, stamp duty, GST
  (`engine/charges.py`) — so every return shown is **net of charges**.
- Shows the equity curve, trade log, win rate, and monthly return, with an
  explicit sample-size warning (a 3-month weekly backtest is only ~12-13
  opportunities — nowhere near enough to statistically confirm an 80% win
  rate).

If Yahoo Finance is unreachable (e.g. a sandboxed environment with no
outbound network access), the app falls back to clearly-labelled synthetic
demo data so you can still see how it works — those numbers are never real
market results.

## Validating the data

The app shows the last few live closes so you can spot-check them against
another source (NSE's own reports at nseindia.com, or Investing.com /
TradingView) before trusting the feed for anything beyond a backtest demo.

## Running the tests

```
$ uv run python tests/test_backtest.py
```

The tests run entirely offline against synthetic data and check the risk
controls: no trade's worst-case loss can exceed the configured cap, and
charges always reduce net P&L.

### How to run it on your own machine

Prerequisite: install `uv` if you don't already have it.

```
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Sync the dependencies

   ```
   $ uv sync
   ```

2. Run the app

   ```
   $ uv run streamlit run streamlit_app.py
   ```
