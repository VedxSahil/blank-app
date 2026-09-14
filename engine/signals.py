"""Technical trend/momentum signal used to pick which side of the market
(bull put spread vs bear call spread) to sell premium on each week.

Plain-pandas implementations (no ta-lib dependency) of EMA, RSI and ADX.
"""

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """df must have columns Open, High, Low, Close. Returns df with added
    indicator columns."""
    out = df.copy()
    out["ema_fast"] = ema(out["Close"], 20)
    out["ema_slow"] = ema(out["Close"], 50)
    out["rsi14"] = rsi(out["Close"], 14)
    out["adx14"] = adx(out["High"], out["Low"], out["Close"], 14)
    return out


def classify_trend(row, adx_min: float = 18.0) -> str:
    """Returns 'bullish', 'bearish' or 'neutral' for one indicator row."""
    if pd.isna(row["ema_fast"]) or pd.isna(row["ema_slow"]) or pd.isna(row["adx14"]):
        return "neutral"
    if row["adx14"] < adx_min:
        return "neutral"
    if row["ema_fast"] > row["ema_slow"] and 45 <= row["rsi14"] <= 70:
        return "bullish"
    if row["ema_fast"] < row["ema_slow"] and 30 <= row["rsi14"] <= 55:
        return "bearish"
    return "neutral"
