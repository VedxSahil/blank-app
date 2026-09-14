"""Black-Scholes pricing for NSE index options (European, cash-settled).

Used only as an approximation of option premiums because free Yahoo
Finance data has no Indian options-chain / implied-vol history. Real
premiums differ from this due to volatility skew, so treat backtest P&L
as directional/illustrative, not tradeable-as-is.
"""

import math

import numpy as np
from scipy.stats import norm


def _d1_d2(spot: float, strike: float, t_years: float, r: float, sigma: float):
    if t_years <= 0 or sigma <= 0:
        raise ValueError("t_years and sigma must be positive")
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return d1, d2


def bs_call(spot: float, strike: float, t_years: float, r: float, sigma: float) -> float:
    d1, d2 = _d1_d2(spot, strike, t_years, r, sigma)
    return spot * norm.cdf(d1) - strike * math.exp(-r * t_years) * norm.cdf(d2)


def bs_put(spot: float, strike: float, t_years: float, r: float, sigma: float) -> float:
    d1, d2 = _d1_d2(spot, strike, t_years, r, sigma)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def realized_vol_annualized(close: np.ndarray, window: int = 20, trading_days: int = 252) -> float:
    """Rolling annualized realized volatility from the last `window` daily
    log returns of a close-price array. Used as an implied-vol proxy;
    real index option IV typically trades above this (a volatility risk
    premium), so results are nudged up by a fixed multiplier at the call
    site rather than assumed here.
    """
    close = np.asarray(close, dtype=float)
    if len(close) < window + 1:
        raise ValueError("not enough history for the requested vol window")
    log_ret = np.diff(np.log(close[-(window + 1):]))
    return float(np.std(log_ret, ddof=1) * math.sqrt(trading_days))


def round_to_strike(price: float, interval: int = 50) -> int:
    return int(round(price / interval) * interval)
