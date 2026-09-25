"""
Estimate an auction from the historical reference curve.

The curve is built by analysis/build_curve.py. This module only looks values
up and applies the existing chit identities to them:

    bid amount = bid % x chit value
    prize      = chit value - bid amount
    dividend   = max(0, (bid amount - FC) / installments)

Estimates are historical medians, not predictions of a specific auction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.auction_schedule import AuctionResult

CURVE_PATH = Path(__file__).resolve().parent.parent / "data" / "reference_curve.json"


@dataclass
class AuctionEstimate:
    """A month's estimated auction, with a low-high range around it."""

    month: int
    bid_pct: float
    bid_amount: float
    prize_amount: float
    dividend: float
    bid_pct_low: float
    bid_pct_high: float
    sample_groups: int


@lru_cache(maxsize=1)
def _load() -> dict:
    if not CURVE_PATH.exists():
        raise FileNotFoundError(
            f"{CURVE_PATH} not found. Run: python analysis/build_curve.py"
        )
    return json.loads(CURVE_PATH.read_text())


def available_configurations() -> list[str]:
    """Keys of the form 'cap|auctions_per_month|duration'."""
    return sorted(_load()["curve"])


def _lookup(cap: float, apm: int, duration: int, month: int) -> dict:
    curve = _load()["curve"]
    key = f"{cap:.2f}|{apm}|{duration}"

    if key not in curve:
        raise KeyError(
            f"No historical data for {key}. Available: {', '.join(curve)}"
        )

    months = curve[key]

    if str(month) not in months:
        raise KeyError(f"No data for month {month} in {key}.")

    return months[str(month)]


def estimate_auction(
    chit_value: float,
    duration_months: int,
    auctions_per_month: int,
    month: int,
    cap: float = 0.35,
    fc_rate: float | None = None,
) -> AuctionEstimate:
    """Estimate one month's auction from the reference curve."""

    point = _lookup(cap, auctions_per_month, duration_months, month)
    installments = duration_months * auctions_per_month
    fc = (fc_rate if fc_rate is not None else _load()["fc_rate"]) * chit_value

    bid_pct = point["p50"]
    bid_amount = bid_pct * chit_value

    return AuctionEstimate(
        month=month,
        bid_pct=bid_pct,
        bid_amount=bid_amount,
        prize_amount=chit_value - bid_amount,
        dividend=max(0.0, (bid_amount - fc) / installments),
        bid_pct_low=point["p10"],
        bid_pct_high=point["p90"],
        sample_groups=point["n"],
    )


def estimate_schedule(
    chit_value: float,
    duration_months: int,
    auctions_per_month: int,
    cap: float = 0.35,
    fc_rate: float | None = None,
) -> list[AuctionEstimate]:
    """Estimate every month, giving a full schedule like auction_schedule.py."""

    return [
        estimate_auction(
            chit_value, duration_months, auctions_per_month, month, cap, fc_rate
        )
        for month in range(1, duration_months + 1)
    ]


def build_schedule(
    chit_value: float,
    duration_months: int,
    auctions_per_month: int = 1,
    cap: float = 0.35,
    fc_rate: float | None = None,
) -> dict[int, AuctionResult]:
    """
    Build a schedule the calculation engine can use directly.

    Pass the result as the ``schedule`` argument of calculate_chit() and
    generate_cash_flows() to run the calculator on historical medians
    instead of the built-in demo schedule.

    Note: the engine treats one auction per month. For groups with more
    than one auction a month a subscriber collects every auction's
    dividend, which the engine does not yet model.
    """

    schedule = {}

    for estimate in estimate_schedule(
        chit_value, duration_months, auctions_per_month, cap, fc_rate
    ):
        schedule[estimate.month] = AuctionResult(
            month=estimate.month,
            bid_amount=estimate.bid_amount,
            dividend=estimate.dividend,
            prize_money=estimate.prize_amount,
        )

    return schedule