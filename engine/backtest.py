"""Weekly defined-risk credit-spread backtest.

Strategy: each week, classify trend on the underlying index (EMA20/EMA50 +
RSI14 + ADX14 filter). If bullish, sell a bull put spread; if bearish,
sell a bear call spread; if neutral, skip. Spread width and position size
are chosen so the worst-case loss on a trade never exceeds the user's risk
cap. Premiums are Black-Scholes estimates off realized volatility (see
engine/pricing.py) since free data has no real options chain.

This models a real, sensible retail structure (defined risk, high nominal
win-rate). It is NOT guaranteed to hit any particular return or win-rate
target - those numbers come out of the backtest, not into it.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .charges import ChargeRates, expiry_settlement_charges, leg_open_close_charges
from .pricing import bs_call, bs_put, realized_vol_annualized, round_to_strike
from .signals import build_indicators, classify_trend


@dataclass
class BacktestConfig:
    capital: float = 100_000.0
    max_risk_pct: float = 0.10
    max_risk_rupees: float = 10_000.0
    lot_size: int = 65             # NSE Nifty 50 lot size, revised Jan 2026
    spread_width_points: int = 100
    strike_interval: int = 50
    risk_free_rate: float = 0.07
    iv_risk_premium_mult: float = 1.15  # implied vol typically > realized vol
    vol_window_days: int = 20
    adx_min: float = 18.0
    days_to_expiry: int = 7
    rates: ChargeRates = field(default_factory=ChargeRates)


@dataclass
class Trade:
    entry_date: pd.Timestamp
    expiry_date: pd.Timestamp
    direction: str          # "bull_put" or "bear_call"
    spot_entry: float
    spot_expiry: float
    short_strike: int
    long_strike: int
    lots: int
    credit_per_unit: float
    gross_pnl: float
    charges: float
    net_pnl: float

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0


@dataclass
class BacktestResult:
    trades: list[Trade]
    skipped_weeks: int
    equity_curve: pd.Series
    starting_capital: float
    ending_capital: float


def _max_drawdown_pct(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    return float(drawdown.min() * 100)


def run_backtest(price_df: pd.DataFrame, cfg: BacktestConfig) -> BacktestResult:
    ind = build_indicators(price_df)
    weekly_close_idx = ind.resample("W-FRI").last().dropna(subset=["Close"]).index
    # Map each weekly Friday marker to the nearest actual trading day <= it.
    available_days = ind.index
    week_end_days = []
    for wk in weekly_close_idx:
        candidates = available_days[available_days <= wk]
        if len(candidates):
            week_end_days.append(candidates[-1])
    week_end_days = sorted(set(week_end_days))

    capital = cfg.capital
    equity_points = [(price_df.index[0], capital)]
    trades: list[Trade] = []
    skipped = 0

    for i in range(len(week_end_days) - 1):
        entry_date = week_end_days[i]
        expiry_date = week_end_days[i + 1]
        row = ind.loc[entry_date]
        trend = classify_trend(row, adx_min=cfg.adx_min)

        if trend == "neutral":
            skipped += 1
            equity_points.append((expiry_date, capital))
            continue

        hist_close = ind.loc[:entry_date, "Close"].to_numpy()
        try:
            sigma = realized_vol_annualized(hist_close, window=cfg.vol_window_days) * cfg.iv_risk_premium_mult
        except ValueError:
            skipped += 1
            equity_points.append((expiry_date, capital))
            continue

        spot = float(row["Close"])
        t_years = cfg.days_to_expiry / 365.0
        one_sd_move = spot * sigma * math.sqrt(t_years)

        if trend == "bullish":
            short_strike = round_to_strike(spot - 0.8 * one_sd_move, cfg.strike_interval)
            long_strike = short_strike - cfg.spread_width_points
            short_prem = bs_put(spot, short_strike, t_years, cfg.risk_free_rate, sigma)
            long_prem = bs_put(spot, long_strike, t_years, cfg.risk_free_rate, sigma)
        else:  # bearish
            short_strike = round_to_strike(spot + 0.8 * one_sd_move, cfg.strike_interval)
            long_strike = short_strike + cfg.spread_width_points
            short_prem = bs_call(spot, short_strike, t_years, cfg.risk_free_rate, sigma)
            long_prem = bs_call(spot, long_strike, t_years, cfg.risk_free_rate, sigma)

        credit = short_prem - long_prem
        if credit <= 0:
            skipped += 1
            equity_points.append((expiry_date, capital))
            continue

        max_loss_per_lot = (cfg.spread_width_points - credit) * cfg.lot_size
        risk_cap = min(cfg.max_risk_pct * cfg.capital, cfg.max_risk_rupees)
        lots = int(risk_cap // max_loss_per_lot) if max_loss_per_lot > 0 else 0
        margin_needed = max_loss_per_lot * max(lots, 1)
        if lots < 1 or margin_needed > capital:
            skipped += 1
            equity_points.append((expiry_date, capital))
            continue

        quantity = lots * cfg.lot_size
        spot_expiry = float(ind.loc[expiry_date, "Close"])

        if trend == "bullish":
            short_intrinsic = max(0.0, short_strike - spot_expiry)
            long_intrinsic = max(0.0, long_strike - spot_expiry)
        else:
            short_intrinsic = max(0.0, spot_expiry - short_strike)
            long_intrinsic = max(0.0, spot_expiry - long_strike)

        loss_per_unit = min(short_intrinsic - long_intrinsic, cfg.spread_width_points)
        gross_pnl = (credit - loss_per_unit) * quantity

        open_charges = leg_open_close_charges(
            short_prem, quantity, "sell", cfg.rates
        ) + leg_open_close_charges(long_prem, quantity, "buy", cfg.rates)
        settle_charges = expiry_settlement_charges(
            short_intrinsic, quantity, cfg.rates
        ) + expiry_settlement_charges(long_intrinsic, quantity, cfg.rates)
        total_charges = open_charges + settle_charges

        net_pnl = gross_pnl - total_charges
        capital += net_pnl

        trades.append(
            Trade(
                entry_date=entry_date,
                expiry_date=expiry_date,
                direction="bull_put" if trend == "bullish" else "bear_call",
                spot_entry=spot,
                spot_expiry=spot_expiry,
                short_strike=short_strike,
                long_strike=long_strike,
                lots=lots,
                credit_per_unit=credit,
                gross_pnl=gross_pnl,
                charges=total_charges,
                net_pnl=net_pnl,
            )
        )
        equity_points.append((expiry_date, capital))

    equity_curve = pd.Series(
        [v for _, v in equity_points], index=[d for d, _ in equity_points]
    )
    return BacktestResult(
        trades=trades,
        skipped_weeks=skipped,
        equity_curve=equity_curve,
        starting_capital=cfg.capital,
        ending_capital=capital,
    )


def summarize(result: BacktestResult, months_covered: float) -> dict:
    n = len(result.trades)
    wins = sum(t.is_win for t in result.trades)
    total_charges = sum(t.charges for t in result.trades)
    total_net_pnl = result.ending_capital - result.starting_capital
    total_return_pct = total_net_pnl / result.starting_capital * 100
    months_covered = max(months_covered, 1e-9)
    avg_monthly_return_pct = total_return_pct / months_covered
    win_rate_pct = (wins / n * 100) if n else float("nan")
    return {
        "trades_taken": n,
        "weeks_skipped_no_signal": result.skipped_weeks,
        "wins": wins,
        "losses": n - wins,
        "win_rate_pct": win_rate_pct,
        "total_return_pct": total_return_pct,
        "avg_monthly_return_pct": avg_monthly_return_pct,
        "total_charges_paid": total_charges,
        "max_drawdown_pct": _max_drawdown_pct(result.equity_curve),
        "ending_capital": result.ending_capital,
    }
