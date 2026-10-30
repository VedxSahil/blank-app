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
- Top performers: NSE India's gainers list (Nifty 50 and all stocks). The Sensex card uses a
  fixed list of the 30 Sensex stocks, priced from NSE India's gainers list, with Yahoo Finance's NSE listings filling in the rest, because
  BSE's own API refuses scripted requests and Yahoo's BSE history has gaps. NSE and BSE prices
  differ slightly, so gains are close but not identical to BSE's. The list is in the code and
  can lag index changes. A stock without a clean previous-day close is skipped, and the card
  says how many loaded.
- Google News RSS: headlines. Tone and the "helps or hurts" line come from simple keyword
  rules, so they are rough.

## Stock explorer

Search or filter about 120 items (roughly 100 large NSE stocks, 12 world and Indian indices,
5 rupee exchange rates and 5 commodities) and open one to see its price, 1-week to 1-year
changes, a 1M/3M/6M/1Y chart with a hover readout, the year's closing range, distance from the
50-day average, volatility, worst fall and best and worst days. A link like `#TCS` opens a
given item. Data is one year of daily closes from Yahoo Finance, embedded in the page at build
time, so it works on any static host but only covers this fixed list. P/E, market cap and other
fundamentals are not included because the free source does not provide them. The list is in
`scripts/update_dashboard.py` and symbols Yahoo does not know are skipped.

## Strategy lab

A learning calculator under the performance charts. A fixed rule screens the 30 Sensex stocks on
past prices (rose over the last month, latest price above its 10-day average, ranked by gain
divided by daily volatility). You enter an amount, a rise, a fall and costs, tick stocks, and it
shows whole-share splits, the gain and loss in rupees, and what the same amount would be worth
now if bought a month ago. It describes the past only. It is not a recommendation and does not
predict returns.

## How it works

- `.github/workflows/daily-update.yml` runs at 6:30 AM IST, Monday to Friday.
- It runs `scripts/update_dashboard.py` (Python standard library only), which fetches the
  data and fills `scripts/template.html` to write `index.html`.
- A safety check runs before saving. If it fails (for example the sources are blocked), the
  old `index.html` stays and the run fails.
- If `index.html` changed, the workflow commits and pushes it. GitHub Pages serves it.

## Host it on Vercel instead

`vercel.json` tells Vercel to deploy only `index.html` as a static page, so it does not try to
build the leftover Python files. Import the repo in Vercel with no build command and no
framework. Each time the workflow commits a new `index.html`, Vercel redeploys.

## Set up once

Turn on GitHub Pages (Settings > Pages): deploy from branch, folder `/ (root)`.
The workflow only runs on the default branch, so merge into it first.

## Run it by hand

On GitHub: Actions tab > "Daily dashboard update" > Run workflow.

On your machine:

```
python scripts/update_dashboard.py
```
