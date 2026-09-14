"""Price data loading: live Yahoo Finance via yfinance, with a clearly
labelled synthetic fallback so the app stays usable when Yahoo Finance is
unreachable (e.g. blocked outbound network in a sandboxed environment).
Never treat the fallback as a real backtest result.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "NIFTY BANK": "^NSEBANK",
}


@dataclass
class PriceData:
    df: pd.DataFrame
    is_live: bool
    source: str
    error: str | None = None


def fetch_price_history(symbol: str, period: str = "3mo", interval: str = "1d") -> PriceData:
    try:
        import yfinance as yf

        raw = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False)
        if raw is None or raw.empty:
            raise RuntimeError("empty response from Yahoo Finance")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = raw[["Open", "High", "Low", "Close"]].dropna().copy()
        if len(df) < 30:
            raise RuntimeError(f"only {len(df)} rows returned, too little history")
        return PriceData(df=df, is_live=True, source="Yahoo Finance (yfinance)")
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not swallowed
        synthetic = _synthetic_series(period=period, seed=abs(hash(symbol)) % (2**32))
        return PriceData(
            df=synthetic,
            is_live=False,
            source="SYNTHETIC DEMO DATA (Yahoo Finance unreachable)",
            error=str(exc),
        )


def _synthetic_series(period: str, seed: int, start_level: float = 25000.0) -> pd.DataFrame:
    """Geometric Brownian motion placeholder series, for UI/demo purposes
    only when live data cannot be fetched. NOT a real market backtest."""
    days = {"1mo": 22, "3mo": 63, "6mo": 126, "1y": 252}.get(period, 63)
    rng = np.random.default_rng(seed)
    mu, sigma_daily = 0.0002, 0.009
    rets = rng.normal(mu, sigma_daily, days)
    close = start_level * np.exp(np.cumsum(rets))
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    high = close * (1 + rng.uniform(0.001, 0.006, days))
    low = close * (1 - rng.uniform(0.001, 0.006, days))
    open_ = close * (1 + rng.normal(0, 0.002, days))
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close}, index=dates)
