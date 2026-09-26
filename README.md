# 📉 Monte Carlo VaR Engine — NSE Portfolio

A Streamlit app that runs a Monte Carlo simulation for a 5-stock NSE portfolio
and reports 1-day 95%/99% Value-at-Risk and Conditional VaR (Expected Shortfall).

- Pulls two years of daily prices for 5 user-chosen NSE tickers via `yfinance`
  (or accepts an uploaded CSV of daily close prices as a fallback).
- Builds the sample mean/covariance of daily log returns and simulates 10,000
  (configurable) correlated one-day-ahead return paths via Cholesky decomposition,
  with a choice of Normal or fat-tailed Student-t shocks.
- Reports VaR and CVaR at 95% and 99% confidence, a P&L distribution chart,
  and the return correlation matrix.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://blank-app-template.streamlit.app/)

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
