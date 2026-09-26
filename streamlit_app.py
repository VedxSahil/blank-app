import io
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Monte Carlo VaR — NSE Portfolio", page_icon="📉", layout="wide")

COLOR_HIST = "#2a78d6"
COLOR_VAR95 = "#eda100"
COLOR_VAR99 = "#eb6834"
COLOR_CVAR95 = "#4a3aa7"
COLOR_CVAR99 = "#e34948"

DEFAULT_TICKERS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

st.title("📉 Monte Carlo VaR Engine — NSE Portfolio")
st.write(
    "Simulates one-day-ahead portfolio returns for five NSE stocks from two years "
    "of daily history, then reports 95%/99% Value-at-Risk and Conditional VaR (Expected Shortfall)."
)

# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Portfolio")
    tickers = []
    weights = []
    for i in range(5):
        c1, c2 = st.columns([2, 1])
        t = c1.text_input(f"Ticker {i + 1}", value=DEFAULT_TICKERS[i], key=f"ticker_{i}").strip().upper()
        w = c2.number_input(
            "Weight", min_value=0.0, max_value=1.0, value=0.20, step=0.05, key=f"weight_{i}"
        )
        tickers.append(t)
        weights.append(w)
    weights = np.array(weights, dtype=float)

    st.divider()
    st.header("Simulation")
    lookback_years = st.slider("Lookback (years)", 1, 5, 2)
    n_paths = st.number_input("Number of paths", min_value=1000, max_value=200_000, value=10_000, step=1000)
    dist_choice = st.selectbox("Return distribution", ["Normal (Gaussian)", "Student-t (fat tails)"])
    t_dof = 5
    if dist_choice.startswith("Student-t"):
        t_dof = st.slider("Student-t degrees of freedom", 3, 30, 5)
    notional = st.number_input(
        "Portfolio value (₹)", min_value=1_000.0, value=1_00_00_000.0, step=1_00_000.0, format="%.0f"
    )
    seed = st.number_input("Random seed", min_value=0, value=42, step=1)

    st.divider()
    uploaded = st.file_uploader(
        "Optional: upload a CSV of daily close prices instead of fetching live "
        "(columns = the 5 tickers above, first column = date)",
        type="csv",
    )

    run = st.button("Run simulation", type="primary", use_container_width=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def fetch_prices(tickers, years):
    end = date.today()
    start = end - timedelta(days=int(years * 365.25) + 10)
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame()
    prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    prices = prices[tickers] if all(t in prices.columns for t in tickers) else prices
    return prices.dropna(how="all")


def load_from_csv(file, tickers):
    df = pd.read_csv(file, index_col=0, parse_dates=True)
    missing = [t for t in tickers if t not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns for: {', '.join(missing)}")
    return df[tickers].dropna(how="all")


# ---------------------------------------------------------------------------
# Monte Carlo VaR engine
# ---------------------------------------------------------------------------
def run_monte_carlo_var(returns: pd.DataFrame, weights, n_paths, dist, dof, notional, seed):
    mu = returns.mean().values
    cov = returns.cov().values

    # jitter the diagonal if the sample covariance isn't quite PSD
    try:
        chol = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        cov = cov + np.eye(len(mu)) * 1e-10
        chol = np.linalg.cholesky(cov)

    rng = np.random.default_rng(int(seed))
    n_assets = len(mu)

    if dist.startswith("Student-t"):
        z = rng.standard_normal((n_paths, n_assets))
        chi2 = rng.chisquare(dof, size=(n_paths, 1))
        t_scale = np.sqrt(dof / chi2)
        shocks = (z @ chol.T) * t_scale
        # rescale so the shocks keep the sample covariance (t-scaling inflates variance)
        shocks *= np.sqrt((dof - 2) / dof) if dof > 2 else 1.0
    else:
        z = rng.standard_normal((n_paths, n_assets))
        shocks = z @ chol.T

    simulated_returns = mu + shocks  # (n_paths, n_assets), one-day-ahead
    portfolio_returns = simulated_returns @ weights
    pnl = portfolio_returns * notional
    return pnl, portfolio_returns


def var_cvar(pnl, confidence):
    alpha = 1 - confidence
    var_threshold = np.percentile(pnl, alpha * 100)  # a (negative) loss cutoff
    tail = pnl[pnl <= var_threshold]
    cvar = tail.mean() if len(tail) else var_threshold
    return -var_threshold, -cvar  # report as positive loss numbers


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------
if run:
    if len(set(tickers)) != 5 or any(t == "" for t in tickers):
        st.error("Please provide 5 distinct, non-empty tickers.")
        st.stop()
    if not np.isclose(weights.sum(), 1.0, atol=1e-6):
        st.error(f"Weights must sum to 1.0 (currently {weights.sum():.2f}).")
        st.stop()

    with st.spinner("Loading price history..."):
        try:
            if uploaded is not None:
                prices = load_from_csv(uploaded, tickers)
            else:
                prices = fetch_prices(tickers, lookback_years)
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            st.stop()

    if prices is None or prices.empty or prices.shape[0] < 30:
        st.error(
            "Could not fetch enough live price history for these tickers "
            "(this environment may block outbound requests to Yahoo Finance). "
            "Upload a CSV of daily close prices in the sidebar instead."
        )
        st.stop()

    prices = prices.dropna()
    log_returns = np.log(prices / prices.shift(1)).dropna()

    if log_returns.shape[0] < 30:
        st.error("Not enough overlapping daily observations across the 5 tickers.")
        st.stop()

    st.caption(
        f"Using {log_returns.shape[0]} daily observations from "
        f"{log_returns.index.min().date()} to {log_returns.index.max().date()}."
    )

    pnl, port_returns = run_monte_carlo_var(
        log_returns, weights, int(n_paths), dist_choice, t_dof, notional, seed
    )

    var95, cvar95 = var_cvar(pnl, 0.95)
    var99, cvar99 = var_cvar(pnl, 0.99)

    st.subheader("Results — 1-day horizon")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VaR 95%", f"₹{var95:,.0f}", f"{var95 / notional:.2%}")
    c2.metric("CVaR 95%", f"₹{cvar95:,.0f}", f"{cvar95 / notional:.2%}")
    c3.metric("VaR 99%", f"₹{var99:,.0f}", f"{var99 / notional:.2%}")
    c4.metric("CVaR 99%", f"₹{cvar99:,.0f}", f"{cvar99 / notional:.2%}")

    summary = pd.DataFrame(
        {
            "Confidence": ["95%", "99%"],
            "VaR (₹)": [var95, var99],
            "VaR (%)": [var95 / notional, var99 / notional],
            "CVaR (₹)": [cvar95, cvar99],
            "CVaR (%)": [cvar95 / notional, cvar99 / notional],
        }
    )
    st.dataframe(
        summary.style.format({"VaR (₹)": "{:,.0f}", "CVaR (₹)": "{:,.0f}", "VaR (%)": "{:.2%}", "CVaR (%)": "{:.2%}"}),
        hide_index=True,
        use_container_width=True,
    )

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=pnl,
            nbinsx=100,
            marker_color=COLOR_HIST,
            opacity=0.85,
            name="Simulated 1-day P&L",
        )
    )
    for val, color, label in [
        (-var95, COLOR_VAR95, "VaR 95%"),
        (-var99, COLOR_VAR99, "VaR 99%"),
        (-cvar95, COLOR_CVAR95, "CVaR 95%"),
        (-cvar99, COLOR_CVAR99, "CVaR 99%"),
    ]:
        fig.add_vline(x=val, line_width=2, line_dash="dash", line_color=color, annotation_text=label)

    fig.update_layout(
        title="Simulated one-day portfolio P&L distribution",
        xaxis_title="P&L (₹)",
        yaxis_title="Paths",
        bargap=0.02,
        showlegend=False,
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Correlation matrix of daily log returns"):
        st.dataframe(log_returns.corr().style.format("{:.2f}"), use_container_width=True)

    csv_buf = io.StringIO()
    pd.DataFrame({"simulated_pnl": pnl}).to_csv(csv_buf, index=False)
    st.download_button(
        "Download simulated P&L paths (CSV)",
        data=csv_buf.getvalue(),
        file_name="monte_carlo_pnl_paths.csv",
        mime="text/csv",
    )
else:
    st.info("Set your tickers, weights, and simulation settings in the sidebar, then click **Run simulation**.")
