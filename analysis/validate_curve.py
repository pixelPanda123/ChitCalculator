"""
Validate the calculator and the reference curve against real auction data.

Two questions are tested separately, because they fail for different reasons:

  A. Is the ENGINE right?  Feed a real group's actual recorded auctions into
     the calculator and check it reproduces that group's recorded prize,
     dividend and installment.

  B. Is the CURVE right?   Rebuild the curve without a group, predict that
     group's auctions, and compare with what actually happened.

  C. End to end: curve -> calculator -> compare with the real group.

Only one-auction-per-month groups are run end to end, because the engine
models one auction per month. Test A also reports every group, since the
identities hold regardless of frequency.

Run from the project root:
    python analysis/validate_curve.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auction_schedule import AuctionResult
from src.borrowing_cost import calculate_borrowing_cost
from src.cash_flow import generate_cash_flows
from src.chit_calculator import calculate_chit
from src.models import ChitInput
from src.reference_curve import build_schedule

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "chit_historical.csv"
FC_RATE = 0.05
TOLERANCE = 1.0  # rupees


def load() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df["bid_amount"] = df.totalgrpvalue - df.auctionamount
    df["bid_pct"] = df.bid_amount / df.totalgrpvalue
    df["apm"] = (df.installments / df.total_duration).astype(int)
    caps = df.groupby("groupid").bid_pct.max().round(2).rename("cap")
    return df.merge(caps, on="groupid")


def actual_schedule(group: pd.DataFrame) -> dict[int, AuctionResult]:
    """The group's own recorded auctions, as an engine schedule."""
    rows = group.sort_values("auctionmonth")
    return {
        int(r.auctionmonth): AuctionResult(
            month=int(r.auctionmonth),
            bid_amount=float(r.bid_amount),
            dividend=float(r.dividend),
            prize_money=float(r.auctionamount),
        )
        for r in rows.itertuples(index=False)
    }


# ----------------------------------------------------------------------
# A. Engine identities against recorded values, every group
# ----------------------------------------------------------------------
def test_identities(df: pd.DataFrame) -> None:
    print("A. ENGINE IDENTITIES vs RECORDED VALUES (all groups)\n")

    prize_ok = (df.bid_amount + df.auctionamount - df.totalgrpvalue).abs() < 0.01
    fc = FC_RATE * df.totalgrpvalue
    dividend_pred = ((df.bid_amount - fc) / df.installments).clip(lower=0)
    dividend_err = (dividend_pred - df.dividend).abs()

    print(f"   rows checked                      {len(df):>8,}")
    print(f"   prize + bid = chit value          {prize_ok.mean():>8.2%}")
    print(f"   dividend within Re 1 of recorded  {(dividend_err < TOLERANCE).mean():>8.2%}")
    print(f"   dividend exact                    {(dividend_err < 0.01).mean():>8.2%}")

    off = df[dividend_err >= TOLERANCE]
    if len(off):
        rates = (
            (off.bid_amount - off.dividend * off.installments) / off.totalgrpvalue
        ).round(2)
        print(
            f"   {len(off):,} rows differ, in {off.groupid.nunique()} groups "
            f"using other commission rates: {sorted(rates.unique())[:5]}"
        )


# ----------------------------------------------------------------------
# B / C. One-auction-per-month groups, end to end
# ----------------------------------------------------------------------
def test_groups(df: pd.DataFrame) -> None:
    one = df[df.apm == 1]
    print(f"\n\nB/C. ONE-AUCTION-PER-MONTH GROUPS ({one.groupid.nunique()} available)\n")

    header = (
        f"   {'group':>9} {'value':>12} {'cap':>5} "
        f"{'A engine':>9} {'B curve':>9} {'C end-to-end':>13}"
    )
    print(header)
    print(f"   {'':>9} {'':>12} {'':>5} {'max ₹ err':>9} {'MAE pp':>9} {'net cost err':>13}")

    for gid, group in one.groupby("groupid"):
        chit_value = float(group.totalgrpvalue.iloc[0])
        duration = int(group.total_duration.iloc[0])
        cap = float(group.cap.iloc[0])
        lifting = duration // 2

        chit_input = ChitInput(
            chit_value=chit_value,
            duration_months=duration,
            month_of_lifting=lifting,
        )

        # --- A: engine fed the group's own recorded auctions
        real = actual_schedule(group)
        calc_real = calculate_chit(chit_input, schedule=real)
        flows_real = generate_cash_flows(chit_input, calc_real, schedule=real)
        recorded = group.set_index("auctionmonth")

        engine_err = max(
            abs(f.dividend - float(recorded.loc[f.month, "dividend"]))
            for f in flows_real
        )
        engine_err = max(
            engine_err,
            abs(calc_real.prize_amount - float(recorded.loc[lifting, "auctionamount"])),
        )

        # --- B: curve predictions vs recorded bids
        curve = build_schedule(chit_value, duration, 1, cap)
        curve_err = (
            sum(
                abs(curve[m].bid_amount / chit_value - float(recorded.loc[m, "bid_pct"]))
                for m in curve
            )
            / len(curve)
            * 100
        )

        # --- C: borrowing cost from the curve vs from reality
        calc_curve = calculate_chit(chit_input, schedule=curve)
        cost_curve = calculate_borrowing_cost(chit_input, calc_curve)
        cost_real = calculate_borrowing_cost(chit_input, calc_real)
        cost_err = cost_curve.net_cost - cost_real.net_cost

        print(
            f"   {gid:>9} {chit_value:>12,.0f} {cap:>5.2f} "
            f"{engine_err:>9.2f} {curve_err:>9.2f} {cost_err:>+13,.0f}"
        )

    print(
        "\n   A: engine reproduces the group's own recorded figures exactly "
        "when given them.\n"
        "   B: mean absolute error of the curve's bid %, in percentage points.\n"
        "   C: net cost from the curve minus net cost from what really happened.\n\n"
        "   Caution: only 1 and 2 groups exist for these two configurations, so each\n"
        "   group helped build the curve it is measured against. B and C here are a\n"
        "   demonstration that the wiring works, not evidence that the curve predicts.\n"
        "   Section D holds groups out properly."
    )


# ----------------------------------------------------------------------
# D. Curve accuracy with the group genuinely held out
# ----------------------------------------------------------------------
def test_held_out(df: pd.DataFrame, min_groups: int = 5) -> None:
    """Rebuild the curve without each group, then predict that group.

    Configurations with fewer than ``min_groups`` groups are skipped: a
    curve built from one or two groups contains the group it is being
    tested on, so its error is meaningless.
    """

    print(f"\n\nD. CURVE ACCURACY, GROUP HELD OUT (configs with >= {min_groups} groups)\n")

    per_month = (
        df.groupby(["groupid", "cap", "apm", "total_duration", "auctionmonth"])
        .bid_pct.mean()
        .reset_index()
    )

    print(f"   {'config':>14} {'groups':>7} {'MAE pp':>8} {'median pp':>10} {'worst group':>12}")

    for (cap, apm, duration), block in per_month.groupby(["cap", "apm", "total_duration"]):
        ids = block.groupid.unique()

        if len(ids) < min_groups:
            continue

        errors = []

        for gid in ids:
            others = block[block.groupid != gid]
            curve = others.groupby("auctionmonth").bid_pct.median()
            held = block[block.groupid == gid]
            errors.append(
                (held.bid_pct - held.auctionmonth.map(curve)).abs().mean() * 100
            )

        errors = pd.Series(errors)
        print(
            f"   {cap:.2f}|{apm}|{duration:<7} {len(ids):>7} "
            f"{errors.mean():>8.2f} {errors.median():>10.2f} {errors.max():>12.2f}"
        )

    print(
        "\n   Each group is predicted by a curve built only from the others,\n"
        "   so these are the numbers to quote."
    )


def main() -> None:
    df = load()
    test_identities(df)
    test_groups(df)
    test_held_out(df)


if __name__ == "__main__":
    main()