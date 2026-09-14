"""Approximate Indian F&O (index options) transaction cost model.

Rates are ballpark discount-broker figures (Zerodha-style) as of the 2026
STT revision and are meant for backtest realism, not for tax/compliance
use. Override the defaults via ChargeRates if your broker differs.
"""

from dataclasses import dataclass


@dataclass
class ChargeRates:
    brokerage_per_order: float = 20.0       # flat, per executed leg
    stt_sell_pct: float = 0.15 / 100         # on sell-side premium turnover
    stt_exercise_pct: float = 0.125 / 100    # on ITM intrinsic value at expiry
    exchange_txn_pct: float = 0.03503 / 100  # NSE, on premium turnover (both sides)
    sebi_pct: float = 0.0001 / 100           # ~Rs 10 per crore
    stamp_duty_buy_pct: float = 0.003 / 100  # on buy-side premium turnover
    gst_pct: float = 18.0 / 100              # on (brokerage + exchange + sebi)


def leg_open_close_charges(
    premium: float,
    quantity: int,
    side: str,
    rates: ChargeRates,
) -> float:
    """Charges for opening or closing one option leg (one executed order).

    side: "buy" or "sell". premium is per-unit option price, quantity is
    lots * lot_size.
    """
    turnover = premium * quantity
    brokerage = rates.brokerage_per_order
    exchange_txn = turnover * rates.exchange_txn_pct
    sebi = turnover * rates.sebi_pct
    stt = turnover * rates.stt_sell_pct if side == "sell" else 0.0
    stamp = turnover * rates.stamp_duty_buy_pct if side == "buy" else 0.0
    gst = (brokerage + exchange_txn + sebi) * rates.gst_pct
    return brokerage + exchange_txn + sebi + stt + stamp + gst


def expiry_settlement_charges(
    intrinsic_value: float,
    quantity: int,
    rates: ChargeRates,
) -> float:
    """Charges for a leg that settles in-the-money at expiry (auto exercise,
    no brokerage order placed, but STT applies on intrinsic value)."""
    if intrinsic_value <= 0:
        return 0.0
    turnover = intrinsic_value * quantity
    stt = turnover * rates.stt_exercise_pct
    gst = 0.0  # STT itself does not carry GST
    return stt + gst
