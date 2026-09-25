"""
Build reference_curve_v3.json: variable-bidding (plateau-then-decay) chits only.

Why v3 exists
-------------
The auction data mixes two kinds of groups:

* FIXED schedule  - bids are pre-set by the company; every auction in a month
                    has the same bid and it steps down in a straight line
                    (e.g. 35, 35, 35, 33.7, 32.4 ... 5). 21 groups, all 25-month,
                    all started 2020-2023, none after.
* VARIABLE        - members actually bid. Bids sit at the cap for months,
                    then fall to the 5% floor (plateau-then-decay).

v2 pooled both. 14 of its 29 "4|25|1L" groups were one copied fixed schedule,
so its median came out as a straight line. v3 keeps variable groups only and
only the current caps (25-month: 35%, 50-month: 40%).

A group still in its plateau counts as variable: its months at the cap are
real data, and fixed schedules leave the cap by month 4.

Run from the project root:
    python analysis/build_curve_v3.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
AUCTIONS_CSV = ROOT / "data" / "chit_auctions.csv"
CURVE_JSON = ROOT / "data" / "reference_curve_v3.json"

FC_RATE = 0.05                 # foreman commission = the 5% bid floor
CURRENT_CAP = {25: 0.35, 50: 0.40}
MIN_GROUPS_PER_MONTH = 3       # fewer than this -> month is extrapolated
MIN_GROUPS_PER_KEY = 5         # fewer than this -> only the pooled key is built


def load_auctions(path: Path = AUCTIONS_CSV) -> pd.DataFrame:
    """Real auctions only: no re-auctions, no placeholder rows."""
    a = pd.read_csv(path)
    a = a[a["reauction"].isna() & (a["is_placeholder"] == 0)].copy()
    a["start_year"] = pd.to_datetime(a["auctiondate"]).dt.year
    return a


def classify_groups(a: pd.DataFrame) -> pd.DataFrame:
    """One row per group: config, cap, and bidding type (fixed / variable)."""
    cap = a.groupby("groupid")["bid_percentage"].max()
    apm = (a.groupby(["groupid", "auctionmonth"]).size()
             .groupby("groupid").agg(lambda s: s.mode()[0]))

    # Ignore the foreman's own 5% auction in month 1 when judging the shape.
    b = a[~((a["auctionmonth"] == 1) & (a["bid_percentage"] <= FC_RATE + 1e-4))]
    m = (b.groupby(["groupid", "auctionmonth"])["bid_percentage"]
           .agg(["mean", "std", "size"]).reset_index())
    m["cap"] = m["groupid"].map(cap)
    below_cap = m[m["mean"] < m["cap"] - 0.005]

    def bid_type(gid) -> str:
        d = below_cap[below_cap["groupid"] == gid]
        if len(d) < 3:
            return "variable"                      # still on the plateau
        multi = d[d["size"] > 1]
        if len(multi) >= 3:                        # identical bids in every month?
            same = (multi["std"].fillna(0) < 1e-6).mean()
            return "fixed" if same > 0.9 else "variable"
        steps = np.diff(d["mean"].values)          # 1 auction/month: constant step?
        return "fixed" if np.std(steps) < 0.002 else "variable"

    g = a.groupby("groupid").agg(
        duration=("duration", "first"),
        chit_value=("chit_value", "first"),
        completed=("group_completed", "first"),
        start_year=("start_year", "min"),
        months_reached=("auctionmonth", "max"),
        auctions=("bid_percentage", "size"),
    )
    g["cap"] = cap
    g["apm"] = apm
    g["bid_type"] = [bid_type(gid) for gid in g.index]
    return g


def curve_groups(groups: pd.DataFrame) -> pd.DataFrame:
    """Variable-bidding groups at today's cap for their duration."""
    cur = groups["duration"].map(CURRENT_CAP)
    return groups[(groups["bid_type"] == "variable")
                  & ((groups["cap"] - cur).abs() < 1e-6)]


def monthly_bids(a: pd.DataFrame) -> pd.DataFrame:
    """Mean bid % of every auction in a month, per group.

    The foreman's 5% auction is kept on purpose: it pays no dividend, so the
    monthly mean gives the exact monthly dividend:
        dividend received in month = (mean bid % - FC) x chit value / duration
    """
    return (a.groupby(["groupid", "auctionmonth"])["bid_percentage"]
              .mean().rename("bid").reset_index())


def _val_key(v: float) -> str:
    return f"{int(round(v / 100000))}L"


def _series(per_month: pd.DataFrame, duration: int) -> dict:
    """p10/p50/p90 for every month; thin or missing months are extrapolated."""
    out, last_good = {}, None
    for month in range(1, duration + 1):
        vals = per_month.loc[per_month["auctionmonth"] == month, "bid"]
        if len(vals) >= MIN_GROUPS_PER_MONTH:
            out[month] = {
                "p10": round(float(vals.quantile(0.10)), 4),
                "p50": round(float(vals.median()), 4),
                "p90": round(float(vals.quantile(0.90)), 4),
                "n": int(len(vals)),
                "source": "observed",
            }
            last_good = month
    # Straight line from the last observed month down to the 5% floor at the end.
    if last_good is None:
        return {}
    start = out[last_good]["p50"]
    span = duration - last_good
    for month in range(last_good + 1, duration + 1):
        p = start + (FC_RATE - start) * (month - last_good) / span
        out[month] = {"p10": round(p, 4), "p50": round(p, 4), "p90": round(p, 4),
                      "n": 0, "source": "extrapolated"}
    return {str(k): out[k] for k in sorted(out)}


def build_curve(a: pd.DataFrame, groups: pd.DataFrame,
                exclude: set | None = None) -> dict:
    """Build the curve dict. ``exclude`` drops groups (used for hold-out tests)."""
    use = curve_groups(groups)
    if exclude:
        use = use[~use.index.isin(exclude)]
    pm = monthly_bids(a[a["groupid"].isin(use.index)]).join(use, on="groupid")

    curve, meta = {}, {}
    for (apm, dur), d in pm.groupby(["apm", "duration"]):
        keys = {f"{apm}|{dur}|ALL": d}                       # pooled over chit value
        for val, dv in d.groupby("chit_value"):
            if dv["groupid"].nunique() >= MIN_GROUPS_PER_KEY:
                keys[f"{apm}|{dur}|{_val_key(val)}"] = dv
        pooled = None
        for key, dk in keys.items():              # ALL is built first
            s = _series(dk, int(dur))
            if not s:
                continue
            if pooled is None:
                pooled = s
            else:                                  # value key: borrow pooled months
                for month, point in s.items():     # it has too little data for
                    if point["source"] != "observed":
                        src = "pooled" if pooled[month]["source"] == "observed" else "extrapolated"
                        s[month] = {**pooled[month], "source": src}
            curve[key] = s
            meta[key] = {"groups": int(dk["groupid"].nunique())}
    return {"fc_rate": FC_RATE, "curve": curve, "groups_per_key": meta}


def main() -> None:
    a = load_auctions()
    groups = classify_groups(a)
    use = curve_groups(groups)

    result = build_curve(a, groups)
    result["metadata"] = {
        "version": 3,
        "bidding": "variable only (plateau-then-decay); fixed schedules excluded",
        "caps": {str(k): v for k, v in CURRENT_CAP.items()},
        "bid_pct": "mean of all auctions in the month (incl. foreman's 5% auction in month 1)",
        "monthly_dividend": "(p50 - fc_rate) * chit_value / duration",
        "key": "APM|duration|chit value (or ALL = pooled over chit values)",
        "min_groups_per_month": MIN_GROUPS_PER_MONTH,
        "groups_used": int(len(use)),
        "groups_excluded": {
            "fixed_schedule": int((groups["bid_type"] == "fixed").sum()),
            "variable_old_cap": int(((groups["bid_type"] == "variable")
                                     & ~groups.index.isin(use.index)).sum()),
        },
    }
    CURVE_JSON.write_text(json.dumps(result, indent=1))

    print(f"Groups: {len(groups)} total | fixed {(groups.bid_type=='fixed').sum()}"
          f" | variable {(groups.bid_type=='variable').sum()} | used {len(use)}")
    for key, m in result["groups_per_key"].items():
        s = result["curve"][key]
        obs = sum(v["source"] == "observed" for v in s.values())
        plateau = sum(1 for k in range(2, len(s) + 1)
                      if s[str(k)]["p50"] >= CURRENT_CAP[int(key.split("|")[1])] - 0.005)
        print(f"  {key:10s} {m['groups']:3d} groups, {obs}/{len(s)} months observed,"
              f" median at cap for months 2-{plateau + 1}")
    print(f"-> {CURVE_JSON}")


if __name__ == "__main__":
    main()