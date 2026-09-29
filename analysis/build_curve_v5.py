"""
v5 = v3's method (plain pooled monthly median, no break/decay-template split),
but scoped to the MOST RECENT cohort of groups instead of pooling 2022-2026
together.

Why: v4's break-then-template model assumed a clean, single break month
followed by a steep fall. Real data showed that's wrong -- the population's
median bid stays near the cap for several months after the first group
"breaks" (see analysis/output/validation_report.txt and the 2025-cohort check
in chat). A plain median, computed straight from enough of the CURRENT
cohort's own months, tracks that gradual fall better than any two-piece model.

Per (apm, duration), this uses the newest start_year(s) with enough groups
(>= MIN_GROUPS), widening backward one year at a time only if the newest
year alone is too thin.

Run from the project root:
    python analysis/build_curve_v5.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_curve import (FC_RATE, MIN_GROUPS_PER_MONTH, _series, _val_key,  # noqa: E402
                            classify_groups, curve_groups, load_auctions, monthly_bids)

ROOT = Path(__file__).resolve().parent.parent
CURVE_JSON = ROOT / "data" / "reference_curve_v5.json"
MIN_GROUPS = 15   # need at least this many groups in the recent window to trust its median


MIN_DEPTH_FRAC = 0.6  # the window must include groups reaching >= 60% of the duration


def recent_window(used: pd.DataFrame, apm: int, dur: int) -> tuple[pd.DataFrame, int]:
    """
    Newest start_year(s) for this config with enough groups AND enough depth.
    Enough groups alone isn't sufficient: e.g. 62 groups from 2026 sounds like
    plenty, but they've only reached month 9 of 50 -- useless past that point.
    So this keeps widening backward until both the count and the depth clear
    their bar.
    """
    d = used[(used.apm == apm) & (used.duration == dur)]
    years = sorted(d.start_year.unique(), reverse=True)
    if not years:
        return d, None
    picked, cutoff = [], years[-1]
    for y in years:
        picked.append(y)
        window = d[d.start_year.isin(picked)]
        enough_groups = len(window) >= MIN_GROUPS
        enough_depth = window.months_reached.max() >= dur * MIN_DEPTH_FRAC
        if enough_groups and enough_depth:
            cutoff = min(picked)
            break
    return d[d.start_year >= cutoff], cutoff


def main() -> None:
    a = load_auctions()
    used = curve_groups(classify_groups(a))

    curve, meta = {}, {}
    for (apm, dur), _ in used.groupby(["apm", "duration"]):
        window, cutoff = recent_window(used, apm, dur)
        pm = monthly_bids(a[a.groupid.isin(window.index)])
        key = f"{int(apm)}|{int(dur)}|ALL"
        s = _series(pm, int(dur))
        if not s:
            continue
        curve[key] = s
        meta[key] = {"groups": int(len(window)), "start_year_cutoff": int(cutoff),
                     "note": "median computed from this start_year onward only"}
        for val, dw in window.groupby("chit_value"):
            if len(dw) >= MIN_GROUPS_PER_MONTH:
                pmv = monthly_bids(a[a.groupid.isin(dw.index)])
                sv = _series(pmv, int(dur))
                if sv:
                    curve[f"{int(apm)}|{int(dur)}|{_val_key(val)}"] = sv

    result = {"fc_rate": FC_RATE, "curve": curve, "groups_per_key": meta,
              "metadata": {"version": 5,
                          "method": "plain pooled median (v3's method), scoped to the newest "
                                    "cohort with enough groups -- no break-month model",
                          "min_groups": MIN_GROUPS}}
    CURVE_JSON.write_text(json.dumps(result, indent=1))

    print(f"{'config':10s} {'groups':>7s} {'from year':>10s}")
    for key, m in meta.items():
        print(f"{key:10s} {m['groups']:>7d} {m['start_year_cutoff']:>10d}")
    print(f"-> {CURVE_JSON}")


if __name__ == "__main__":
    main()