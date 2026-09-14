import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.backtest import BacktestConfig, run_backtest, summarize
from engine.charges import ChargeRates
from engine.data import SYMBOLS, fetch_price_history

st.set_page_config(page_title="Nifty F&O Defined-Risk Strategy", layout="wide")

st.title("Nifty Weekly Credit-Spread Strategy — Backtest & Reality Check")
st.caption(
    "Trend-filtered, defined-risk options selling on the Nifty index, sized to a fixed "
    "capital and per-trade risk cap. Built for retail F&O trading within strict risk limits."
)

with st.sidebar:
    st.header("Capital & risk")
    capital = st.number_input("Capital deployed (Rs)", min_value=10_000, max_value=10_000_000, value=100_000, step=5_000)
    max_risk_pct = st.slider("Max risk per trade (% of capital)", 1, 25, 10) / 100
    max_risk_rupees = st.number_input("Max risk per trade (Rs, hard cap)", min_value=1_000, max_value=100_000, value=10_000, step=500)

    st.header("Market & instrument")
    symbol_label = st.selectbox("Underlying", list(SYMBOLS.keys()), index=0)
    period = st.selectbox("Backtest lookback", ["3mo", "6mo", "1y"], index=0)
    lot_size = st.number_input("Lot size", min_value=1, value=65, help="NSE Nifty 50 lot size, revised Jan 2026. Check the current NSE circular before trading live.")
    spread_width = st.number_input("Spread width (points)", min_value=50, max_value=500, value=100, step=50)

    st.header("Strategy filter")
    adx_min = st.slider("Min ADX (trend strength filter)", 10, 35, 18)

    run_clicked = st.button("Run backtest", type="primary")

st.markdown("### Reality check — read this before anything else")
st.warning(
    "**A systematic strategy that nets 5%/month (≈80% annualized) AND wins over 80% of trades, "
    "after charges, does not exist as a sustainable retail strategy.** If it did, it would get "
    "arbitraged away or scaled up by funds until it stopped working. High win-rate structures "
    "(like the defined-risk credit spreads this app trades) are high win-rate *because* each win "
    "is small and occasional losses are larger — that's the trade-off, not a bug. Treat any "
    "backtest below as real math on real (or clearly-marked synthetic) price data — not a promise."
)

price_data = fetch_price_history(SYMBOLS[symbol_label], period=period)

if not price_data.is_live:
    st.error(
        f"Could not fetch live data from Yahoo Finance ({price_data.error}). "
        "Showing **synthetic demo data** so you can see how the app works — "
        "these are NOT real market numbers. Run this app on a machine/host with normal "
        "internet access (local machine, Streamlit Community Cloud, Codespaces) to backtest "
        "on real Yahoo Finance history."
    )
else:
    st.success(f"Live data loaded from {price_data.source}: {len(price_data.df)} daily bars for {symbol_label}.")
    with st.expander("Cross-check a few sample closes against another source"):
        st.write(
            "Spot-check 3-5 dates below against NSE's official close "
            "(nseindia.com/reports) or another provider (Investing.com, TradingView) "
            "before trusting this feed for real capital."
        )
        st.dataframe(price_data.df["Close"].tail(5).rename("Yahoo Finance Close"))

if run_clicked or True:
    cfg = BacktestConfig(
        capital=float(capital),
        max_risk_pct=max_risk_pct,
        max_risk_rupees=float(max_risk_rupees),
        lot_size=int(lot_size),
        spread_width_points=int(spread_width),
        adx_min=float(adx_min),
        rates=ChargeRates(),
    )
    result = run_backtest(price_data.df, cfg)
    months_covered = {"3mo": 3, "6mo": 6, "1y": 12}[period]
    summary = summarize(result, months_covered=months_covered)

    st.markdown("### Backtest results" + ("" if price_data.is_live else " (synthetic demo data)"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades taken", summary["trades_taken"])
    c2.metric(
        "Win rate",
        f"{summary['win_rate_pct']:.1f}%" if summary["trades_taken"] else "n/a",
        help="Fraction of trades with positive net P&L after charges.",
    )
    c3.metric("Avg monthly return (net)", f"{summary['avg_monthly_return_pct']:.2f}%")
    c4.metric("Max drawdown", f"{summary['max_drawdown_pct']:.2f}%")

    c5, c6, c7 = st.columns(3)
    c5.metric("Ending capital", f"Rs {summary['ending_capital']:,.0f}")
    c6.metric("Total charges paid", f"Rs {summary['total_charges_paid']:,.0f}")
    c7.metric("Weeks skipped (no signal)", summary["weeks_skipped_no_signal"])

    target_met = summary["trades_taken"] > 0 and summary["avg_monthly_return_pct"] >= 5 and summary["win_rate_pct"] >= 80
    if summary["trades_taken"] == 0:
        st.info("No trades were taken in this window — the trend/ADX filter found no qualifying setup, or every candidate breached the risk cap.")
    elif target_met:
        st.warning(
            "This run shows both targets met. With only "
            f"{summary['trades_taken']} trades over {months_covered} month(s), that is very likely "
            "small-sample noise, not durable edge — do not size real capital off this alone. "
            "A CMT-level validation needs 100+ trades across multiple market regimes (trending, "
            "range-bound, high and low volatility) before you'd call this repeatable."
        )
    else:
        st.info(
            f"This run nets **{summary['avg_monthly_return_pct']:.2f}%/month** at a "
            f"**{summary['win_rate_pct']:.0f}%** win rate over {summary['trades_taken']} trades — "
            "this is the realistic range for a defined-risk, risk-capped weekly options strategy. "
            "It falls short of the 5%/month + 80% target, which is expected: see the reality check above."
        )

    st.markdown("#### Equity curve")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result.equity_curve.index, y=result.equity_curve.values, mode="lines", name="Equity"))
    fig.add_hline(y=cfg.capital, line_dash="dot", annotation_text="Starting capital")
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Capital (Rs)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Trade log")
    if result.trades:
        trade_rows = [
            {
                "Entry": t.entry_date.date(),
                "Expiry": t.expiry_date.date(),
                "Direction": t.direction,
                "Spot @ entry": round(t.spot_entry, 1),
                "Spot @ expiry": round(t.spot_expiry, 1),
                "Short strike": t.short_strike,
                "Long strike": t.long_strike,
                "Lots": t.lots,
                "Credit/unit": round(t.credit_per_unit, 2),
                "Gross P&L": round(t.gross_pnl, 0),
                "Charges": round(t.charges, 0),
                "Net P&L": round(t.net_pnl, 0),
                "Win": "Yes" if t.is_win else "No",
            }
            for t in result.trades
        ]
        st.dataframe(pd.DataFrame(trade_rows), use_container_width=True)
    else:
        st.write("No trades to show.")

st.markdown("---")
with st.expander("Strategy methodology, assumptions & limitations (read before trading real money)"):
    st.markdown(
        """
**Strategy**: Weekly, sell a defined-risk credit spread on the Nifty 50 index —
a bull put spread when EMA20 > EMA50 with RSI14 in 45-70 and ADX14 above the
threshold (confirmed uptrend), a bear call spread on the mirror-image bearish
setup, otherwise skip the week. Spread width and lot count are chosen so the
worst-case loss on any single trade never exceeds your risk cap
(`min(max_risk_pct * capital, max_risk_rupees)`).

**Why credit spreads, not just buying options**: buying options needs the
market to move enough, fast enough, to beat time decay and the bid-ask/IV
spread — that structurally caps win rate well below 50% for most systematic
entries. Selling a defined-risk spread flips that: high nominal win rate,
capped loss, but each win is only the small credit received. That's a better
structural fit for a high-win-rate target, but it caps the return per trade —
which is exactly why 80% win rate and 5%/month don't come together for free.

**Data & pricing limitations**:
- Free Yahoo Finance data has no Indian options-chain or implied-volatility
  history, so premiums here are Black-Scholes estimates off realized
  volatility (nudged up by a fixed multiplier as an IV-risk-premium proxy).
  Real quoted premiums differ, sometimes a lot, due to volatility skew around
  the strikes this strategy trades.
- "Weekly" trades are aligned to whatever trading days Yahoo returns, not the
  actual NSE weekly-expiry calendar.
- Charges (`engine/charges.py`) are ballpark discount-broker rates as of the
  2026 STT revision — confirm against your actual broker before trading.

**Sample size**: a 3-month backtest of a weekly strategy is roughly 12-13
opportunities, fewer once the trend filter skips no-signal weeks. That is far
too small to statistically confirm an 80% win rate or any specific monthly
return — treat every number on this page as illustrative, not a guarantee.

**This is not investment advice.** F&O trading carries a high risk of loss;
SEBI's own data shows most individual F&O traders lose money after costs.
Paper-trade this for at least a few months across different market
conditions before risking real capital, and never risk more than you can
afford to lose.
        """
    )
