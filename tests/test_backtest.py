"""Runs entirely offline against synthetic price data (no Yahoo Finance
needed) to check the backtest engine's math and risk controls: max loss
per trade must never exceed the configured risk cap, charges must be
subtracted, and summary stats must be internally consistent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.backtest import BacktestConfig, run_backtest, summarize
from engine.data import _synthetic_series


def test_risk_cap_never_breached():
    cfg = BacktestConfig(capital=100_000, max_risk_pct=0.10, max_risk_rupees=10_000)
    df = _synthetic_series(period="3mo", seed=42)
    result = run_backtest(df, cfg)
    risk_cap = min(cfg.max_risk_pct * cfg.capital, cfg.max_risk_rupees)
    for t in result.trades:
        worst_case_loss = cfg.spread_width_points * cfg.lot_size * t.lots - t.credit_per_unit * cfg.lot_size * t.lots
        assert worst_case_loss <= risk_cap + 1e-6, (
            f"trade on {t.entry_date} had worst-case loss {worst_case_loss} "
            f"exceeding risk cap {risk_cap}"
        )


def test_charges_reduce_pnl():
    cfg = BacktestConfig()
    df = _synthetic_series(period="3mo", seed=7)
    result = run_backtest(df, cfg)
    assert len(result.trades) > 0, "expected at least one trade over 3 months of synthetic data"
    for t in result.trades:
        assert t.charges > 0
        assert t.net_pnl == t.gross_pnl - t.charges


def test_summary_consistency():
    cfg = BacktestConfig()
    df = _synthetic_series(period="3mo", seed=123)
    result = run_backtest(df, cfg)
    summary = summarize(result, months_covered=3)
    assert summary["trades_taken"] == summary["wins"] + summary["losses"]
    if summary["trades_taken"] > 0:
        assert 0 <= summary["win_rate_pct"] <= 100
    assert summary["ending_capital"] == result.ending_capital


def test_capital_never_exceeds_available_margin():
    cfg = BacktestConfig(capital=100_000)
    df = _synthetic_series(period="6mo", seed=99)
    result = run_backtest(df, cfg)
    for t in result.trades:
        margin = cfg.spread_width_points * cfg.lot_size * t.lots - t.credit_per_unit * cfg.lot_size * t.lots
        assert margin <= cfg.capital


if __name__ == "__main__":
    test_risk_cap_never_breached()
    test_charges_reduce_pnl()
    test_summary_consistency()
    test_capital_never_exceeds_available_margin()
    print("All tests passed.")
