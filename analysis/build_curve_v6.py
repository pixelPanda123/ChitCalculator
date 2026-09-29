"""
v6 = v5 (recent-cohort median) for the part of the curve with real recent
data, PLUS v4's pooled decay-shape template to finish the tail once the
recent cohort runs out of depth.

Why: v5 alone just extrapolates the tail in a straight line to the 5% floor
once a config's recent cohort thins out (e.g. past month ~16 of 25, or
month ~30 of 50) -- not wrong, just not using anything. The user's point:
the SHAPE of decay after a group leaves the plateau looks the same
regardless of *when* it breaks (only the break month itself moved earlier
over the years, not the shape following it) -- see build_curve_v4.py's
decay_template(), which already pools this shape across all years.

So v6:
  1. Takes v5's recent-cohort window + observed monthly medians (real data
     only, MIN_GROUPS_PER_MONTH-filtered).
  2. Finds the recent cohort's OWN break month (first observed month its
     median drops below cap).
  3. Pools the decay shape (median bid at k = months-since-break) across
     EVERY broken group at the current cap, any year -- more data than any
     single cohort has alone.
  4. Past the recent cohort's last reliable observed month, continues using
     that pooled shape (indexed by k = month - recent break month), shifted
     by a constant so it connects continuously with the last real point
     (no jump), then clipped to [floor, cap] and forced non-increasing.

Run from the project root:
    python analysis/build_curve_v6.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_curve import (FC_RATE, CURRENT_CAP, MIN_GROUPS_PER_MONTH, _val_key,  # noqa: E402
                            classify_groups, curve_groups, load_auctions, monthly_bids)
from build_curve_v4 import break_months, decay_template  # noqa: E402
from build_curve_v5 import MIN_GROUPS, recent_window  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CURVE_JSON = ROOT / "data" / "reference_curve_v6.json"


def observed_series(pm: pd.DataFrame, dur: int) -> dict[int, float]:
    """Real per-month medians only (no extrapolation) -- month: p50, for months with enough groups."""
    out = {}
    for month in range(1, dur + 1):
        vals = pm.loc[pm.auctionmonth == month, "bid"]
        if len(vals) >= MIN_GROUPS_PER_MONTH:
            out[month] = float(vals.median())
    return out


def recent_break_month(obs: dict[int, float], cap: float) -> int | None:
    """First observed month (>=2) where the recent cohort's own median already left the cap."""
    for m in sorted(obs):
        if m >= 2 and obs[m] < cap - 0.005:
            return m
    return None


def splice_tail(obs: dict[int, float], template: dict[int, float], break_month: int | None,
                 cap: float, dur: int) -> dict[str, dict]:
    last_good = max(obs) if obs else None
    out = {}
    if last_good is None:
        return {str(m): {"p50": round(cap, 4), "source": "no-data"} for m in range(1, dur + 1)}

    for m in range(1, last_good + 1):
        out[m] = {"p50": round(obs[m], 4), "source": "observed"}

    if last_good >= dur:
        return {str(k): v for k, v in out.items()}

    if not template or break_month is None:
        # nothing to splice with -- fall back to a straight line to the floor
        span = dur - last_good
        for m in range(last_good + 1, dur + 1):
            p = obs[last_good] + (FC_RATE - obs[last_good]) * (m - last_good) / span
            out[m] = {"p50": round(p, 4), "source": "extrapolated-linear"}
        return {str(k): v for k, v in out.items()}

    k_last_good = last_good - break_month
    template_at_last_good = template.get(k_last_good, template.get(max(k for k in template if k <= k_last_good), cap))
    offset = obs[last_good] - template_at_last_good     # so the spliced tail starts exactly where real data ends

    prev = obs[last_good]
    for m in range(last_good + 1, dur + 1):
        k = m - break_month
        if k in template:
            p = template[k] + offset
        else:                                            # past the pooled template too -> ramp to floor
            last_k = max(template)
            base = template[last_k] + offset
            p = base + (FC_RATE - base) * min(1.0, (k - last_k) / max(1, dur - break_month - last_k))
        p = min(prev, max(FC_RATE, p))                    # clip to floor and force non-increasing
        out[m] = {"p50": round(p, 4), "source": "decay-template-spliced"}
        prev = p
    return {str(k): v for k, v in out.items()}


def main() -> None:
    a = load_auctions()
    used = curve_groups(classify_groups(a))

    # Pooled decay shape from EVERY broken group at the current cap, any year --
    # this is what "the shape stays the same no matter when it breaks" draws on.
    broken = used.join(break_months(a, used))

    curve, meta = {}, {}
    for (apm, dur), _ in used.groupby(["apm", "duration"]):
        cap = CURRENT_CAP[int(dur)]
        window, cutoff = recent_window(used, apm, dur)
        pm_window = monthly_bids(a[a.groupid.isin(window.index)])
        obs = observed_series(pm_window, int(dur))
        bm = recent_break_month(obs, cap)

        template = {int(k): v for k, v in decay_template(a, broken, apm, dur).items()}
        key = f"{int(apm)}|{int(dur)}|ALL"
        curve[key] = splice_tail(obs, template, bm, cap, int(dur))
        meta[key] = {"groups": int(len(window)), "start_year_cutoff": int(cutoff) if cutoff else None,
                     "recent_cohort_break_month": bm,
                     "last_observed_month": max(obs) if obs else None,
                     "template_groups": int(broken[(broken.apm == apm) & (broken.duration == dur)]
                                            .dropna(subset=["break"]).shape[0])}

        for val, dw in window.groupby("chit_value"):
            if len(dw) >= MIN_GROUPS:
                pmv = monthly_bids(a[a.groupid.isin(dw.index)])
                obsv = observed_series(pmv, int(dur))
                bmv = recent_break_month(obsv, cap)
                curve[f"{int(apm)}|{int(dur)}|{_val_key(val)}"] = splice_tail(obsv, template, bmv, cap, int(dur))

    result = {"fc_rate": FC_RATE, "curve": curve, "groups_per_key": meta,
              "metadata": {"version": 6,
                          "method": "v5 (recent-cohort median) for observed months, then the pooled "
                                    "all-years decay-shape template (by months-since-break) splices in "
                                    "the tail, shifted to connect with the last real point",
                          "min_groups": MIN_GROUPS}}
    CURVE_JSON.write_text(json.dumps(result, indent=1))

    print(f"{'config':10s} {'groups':>7s} {'from year':>10s} {'break':>7s} {'last obs':>9s} {'tmpl n':>7s}")
    for key, m in meta.items():
        print(f"{key:10s} {m['groups']:>7d} {str(m['start_year_cutoff']):>10s} "
              f"{str(m['recent_cohort_break_month']):>7s} {str(m['last_observed_month']):>9s} "
              f"{m['template_groups']:>7d}")
    print(f"-> {CURVE_JSON}")


if __name__ == "__main__":
    main()