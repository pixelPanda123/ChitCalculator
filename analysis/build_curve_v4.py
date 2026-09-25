"""
v4 = v3's plateau-then-decay shape, but the plateau LENGTH tracks the trend
over start_year instead of being pooled across all years.

Why: newer batches leave the cap earlier (see analysis/output/validation_report.txt,
section on months 7-16). v3 pools 2022-2026 groups into one curve, so its plateau
is set mostly by the older, slower-breaking groups and runs too long for a group
starting today.

v4 does two things separately:
  1. BREAK MONTH: for each (apm, duration), fit break_month/duration vs start_year
     (linear, least squares on yearly medians) and extrapolate to the current year.
  2. DECAY SHAPE: pool every broken group's bids by k = month_since_break (this
     shape was similar across years - see validation), take the median, and hang
     it off the predicted break month.

Run from the project root:
    python analysis/build_curve_v4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_curve import (FC_RATE, CURRENT_CAP, classify_groups, curve_groups,  # noqa: E402
                            load_auctions, monthly_bids, _val_key)

ROOT = Path(__file__).resolve().parent.parent
CURVE_JSON = ROOT / "data" / "reference_curve_v4.json"
THIS_YEAR = 2026  # "now", for extrapolating the break-month trend
MIN_START_YEAR = 2023  # drop 2018-2022: too few groups, and pre-dates the current caps' rollout

# "groups that plateau first": both the break-month trend and the decay shape are
# fit only from groups that have ALREADY left the plateau (an observed break month).
# A group still sitting at the cap tells us nothing about when or how fast it falls,
# so it would only add noise here - it still anchors the curve's flat part via cap.


def break_months(a: pd.DataFrame, groups: pd.DataFrame) -> pd.Series:
    """First month (>=2) each group's mean bid fell below its cap. NaN = still on it."""
    pm = monthly_bids(a[a.groupid.isin(groups.index)]).join(groups[["cap"]], on="groupid")
    out = {}
    for gid, d in pm[pm.auctionmonth >= 2].groupby("groupid"):
        below = d[d.bid < d.cap - 0.005].sort_values("auctionmonth")
        out[gid] = int(below.auctionmonth.iloc[0]) if len(below) else np.nan
    return pd.Series(out, name="break")


def fit_break_trend(groups: pd.DataFrame, apm: int, dur: int) -> tuple[float, dict]:
    """Least-squares fit of break/duration on start_year -> predicted break month for THIS_YEAR."""
    d = groups[(groups.apm == apm) & (groups.duration == dur)].dropna(subset=["break"])
    yearly = d.groupby("start_year")["break"].median() / dur
    if len(yearly) < 2:
        pred_frac = yearly.mean() if len(yearly) else 0.3
    else:
        x, y = yearly.index.values.astype(float), yearly.values
        slope, intercept = np.polyfit(x, y, 1)
        pred_frac = slope * THIS_YEAR + intercept
    pred_frac = float(np.clip(pred_frac, 1.0 / dur, 0.9))
    pred_month = max(2, round(pred_frac * dur))
    return pred_month, {str(int(k)): round(float(v), 3) for k, v in yearly.items()}


def decay_template(a: pd.DataFrame, groups: pd.DataFrame, apm: int, dur: int) -> dict[int, float]:
    """Median bid at k months after the break, pooled over every broken group in this config."""
    d = groups[(groups.apm == apm) & (groups.duration == dur)].dropna(subset=["break"])
    pm = monthly_bids(a[a.groupid.isin(d.index)]).merge(
        d[["break"]], left_on="groupid", right_index=True)
    pm["k"] = pm.auctionmonth - pm["break"]
    return pm[pm.k >= 0].groupby("k")["bid"].median().to_dict()


def build_series(break_month: int, template: dict[int, float], cap: float, dur: int) -> dict:
    if not template:                                        # no group has broken yet in this config
        template = {0: cap}
    out = {}
    for m in range(1, dur + 1):
        if m < break_month:
            bid, src = cap, "plateau"
        else:
            k = m - break_month
            if k in template:
                bid, src = template[k], "decay-observed"
            else:                                          # past the observed decay: ramp to floor
                last_k = max(template)
                bid = template[last_k] + (FC_RATE - template[last_k]) * min(1.0, (k - last_k) / max(1, dur - break_month - last_k))
                src = "decay-extrapolated"
        out[str(m)] = {"p50": round(float(bid), 4), "source": src}
    return out


def main() -> None:
    a = load_auctions()
    groups = classify_groups(a)
    used = curve_groups(groups)
    used = used[used.start_year >= MIN_START_YEAR]
    used = used.join(break_months(a, used))

    curve, meta = {}, {}
    for (apm, dur), _ in used.groupby(["apm", "duration"]):
        cap = CURRENT_CAP[int(dur)]
        pred_month, yearly = fit_break_trend(used, apm, dur)
        template = decay_template(a, used, apm, dur)
        key = f"{int(apm)}|{int(dur)}|ALL"
        curve[key] = build_series(pred_month, template, cap, int(dur))
        meta[key] = {"predicted_break_month": pred_month, "break_month_by_start_year": yearly,
                     "groups": int(len(used[(used.apm == apm) & (used.duration == dur)]))}
        # chit-value-specific curves reuse the same pooled break/decay (too little data to split further)
        for val, dv in used[(used.apm == apm) & (used.duration == dur)].groupby("chit_value"):
            if len(dv) >= 5:
                curve[f"{int(apm)}|{int(dur)}|{_val_key(val)}"] = curve[key]

    result = {
        "fc_rate": FC_RATE,
        "curve": curve,
        "meta": meta,
        "metadata": {
            "version": 4,
            "change_from_v3": "plateau length is fit per start_year and extrapolated to "
                              f"{THIS_YEAR}, instead of pooling all cohort years into one median",
            "predict_year": THIS_YEAR,
        },
    }
    CURVE_JSON.write_text(json.dumps(result, indent=1))

    print(f"{'config':10s} {'pred. break month':>18s}   break month by start_year")
    for key, m in meta.items():
        print(f"{key:10s} {m['predicted_break_month']:>18d}   {m['break_month_by_start_year']}")
    print(f"-> {CURVE_JSON}")


if __name__ == "__main__":
    main()