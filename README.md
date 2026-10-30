# Pre-Market Dashboard

A one-page dashboard for the Indian stock market, refreshed every weekday morning.
It needs no API key and no paid service.

It shows GIFT Nifty, Nifty 50 and Sensex previous closes, India VIX, USD/INR, Brent crude,
US markets overnight, FII and DII flows, an expected-open gap, eight headlines and a short
morning brief. Anything that cannot be fetched shows as "not found". Nothing is guessed.

For learning only. Not investment advice. Numbers can be wrong. Check them before you rely on them.

## Where the data comes from

- Yahoo Finance: Nifty 50, Sensex, India VIX, USD/INR, Brent, S&P 500, Nasdaq, Dow.
- NSE India: GIFT Nifty and FII/DII net flows.
- Top performers: NSE India's gainers list (Nifty 50 and all stocks). For the BSE Sensex card,
  BSE's own API refuses scripted requests, so prices come from Yahoo Finance's BSE (`.BO`)
  listings for a fixed list of Sensex stocks. Stocks with a missing day of history are skipped,
  and the card says how many loaded.
- Google News RSS: headlines. Tone and the "helps or hurts" line come from simple keyword
  rules, so they are rough.

## How it works

- `.github/workflows/daily-update.yml` runs at 6:30 AM IST, Monday to Friday.
- It runs `scripts/update_dashboard.py` (Python standard library only), which fetches the
  data and fills `scripts/template.html` to write `index.html`.
- A safety check runs before saving. If it fails (for example the sources are blocked), the
  old `index.html` stays and the run fails.
- If `index.html` changed, the workflow commits and pushes it. GitHub Pages serves it.

## Set up once

Turn on GitHub Pages (Settings > Pages): deploy from branch, folder `/ (root)`.
The workflow only runs on the default branch, so merge into it first.

## Run it by hand

On GitHub: Actions tab > "Daily dashboard update" > Run workflow.

On your machine:

```
python scripts/update_dashboard.py
```
