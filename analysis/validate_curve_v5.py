"""
v3 vs v4 vs v5, tested fairly: predict the newest cohort using ONLY older
groups (same held-out setup as validate_curve_v4.py), now with v5 added.

Run from the project root:
    python analysis/validate_curve_v5.py
Writes analysis/output/v3_v4_v5.png and prints a table.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_curve import CURRENT_CAP, classify_groups, curve_groups, load_auctions, monthly_bids  # noqa: E402
from build_curve_v4 import MIN_START_YEAR, break_months, build_series, decay_template  # noqa: E402
from build_curve_v5 import MIN_DEPTH_FRAC, MIN_GROUPS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "output"

CONFIGS = [(4, 25, 2026), (2, 50, 2025)]   # (apm, duration, held-out year)


def v3_curve(train: pd.DataFrame, pm: pd.DataFrame, dur: int) -> dict:
    med = pm[pm.groupid.isin(train.index)].groupby("auctionmonth")["bid"].median()
    return {m: float(med.get(m, med.iloc[-1])) for m in range(1, dur + 1)}


def v5_curve(train: pd.DataFrame, pm: pd.DataFrame, dur: int) -> tuple[dict, int]:
    """Same widen-backward logic as build_curve_v5.recent_window, but scoped to train only."""
    years = sorted(train.start_year.unique(), reverse=True)
    if not years:
        return {}, None
    picked, cutoff = [], years[-1]
    for y in years:
        picked.append(y)
        window = train[train.start_year.isin(picked)]
        if len(window) >= MIN_GROUPS and window.months_reached.max() >= dur * MIN_DEPTH_FRAC:
            cutoff = min(picked)
            break
    window = train[train.start_year >= cutoff]
    return v3_curve(window, pm, dur), int(cutoff), int(len(window))


def main() -> None:
    a = load_auctions()
    groups = classify_groups(a)
    used = curve_groups(groups)
    used = used[used.start_year >= MIN_START_YEAR]
    used = used.join(break_months(a, used))

    rows, curves_for_plot = [], {}
    for apm, dur, held_out_year in CONFIGS:
        d = used[(used.apm == apm) & (used.duration == dur)]
        train, test = d[d.start_year < held_out_year], d[d.start_year == held_out_year]
        if len(test) == 0:
            continue
        pm_all = monthly_bids(a[a.groupid.isin(d.index)])

        v3 = v3_curve(train, pm_all, dur)

        yearly = train.dropna(subset=["break"]).groupby("start_year")["break"].median() / dur
        if len(yearly) >= 2:
            slope, intercept = np.polyfit(yearly.index.values.astype(float), yearly.values, 1)
            pred_frac = np.clip(slope * held_out_year + intercept, 1 / dur, 0.9)
        else:
            pred_frac = yearly.mean() if len(yearly) else 0.3
        pred_month = max(2, round(pred_frac * dur))
        template = decay_template(a, train, apm, dur)
        v4 = {int(k): v["p50"] for k, v in build_series(pred_month, template, CURRENT_CAP[dur], dur).items()}

        v5, v5_cutoff, v5_n = v5_curve(train, pm_all, dur)

        curves_for_plot[(apm, dur)] = dict(v3=v3, v4=v4, v5=v5, break_month=pred_month,
                                           v5_cutoff=v5_cutoff, v5_n=v5_n,
                                           test=pm_all[pm_all.groupid.isin(test.index)])

        for _, r in pm_all[pm_all.groupid.isin(test.index)].iterrows():
            m = int(r.auctionmonth)
            rows.append(dict(config=f"{apm}|{dur}", month=m,
                             err_v3=abs(v3[m] - r.bid), err_v4=abs(v4[m] - r.bid),
                             err_v5=abs(v5.get(m, v3[m]) - r.bid)))

    e = pd.DataFrame(rows)
    e["phase"] = pd.cut(e.month, [0, 6, 16, 100], labels=["1-6", "7-16", "17+"])
    print(f"Held-out cohorts: {', '.join(f'{a}|{d} -> {y}' for a, d, y in CONFIGS)}\n")
    print((e.groupby(["config", "phase"], observed=True)[["err_v3", "err_v4", "err_v5"]].mean() * 100)
          .round(1).to_string())
    print("\nOverall mean |error| (bid % points):")
    print((e.groupby("config")[["err_v3", "err_v4", "err_v5"]].mean() * 100).round(2).to_string())
    for key, c in curves_for_plot.items():
        print(f"v5 for {key}: trained on start_year >= {c['v5_cutoff']} ({c['v5_n']} groups)")

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, (apm, dur) in zip(axes, curves_for_plot):
        c = curves_for_plot[(apm, dur)]
        months = list(range(1, dur + 1))
        ax.plot(months, [c["v3"][m] * 100 for m in months], "--", color="grey", label="v3 (pooled, all years)")
        ax.plot(months, [c["v4"][m] * 100 for m in months], "-", color="tab:blue", lw=2,
                label=f"v4 (trend, predicted break=month {c['break_month']})")
        v5_months = [m for m in months if m in c["v5"]]
        if v5_months:
            ax.plot(v5_months, [c["v5"][m] * 100 for m in v5_months], "-", color="tab:green", lw=2,
                    label=f"v5 (recent cohort median, >= {c['v5_cutoff']})")
        for gid, g in c["test"].groupby("groupid"):
            ax.plot(g.auctionmonth, g.bid * 100, "o", color="tab:red", ms=3, alpha=0.5,
                    label="held-out newest cohort (actual)" if gid == c["test"].groupid.iloc[0] else None)
        ax.set(title=f"{apm} auctions/month, {dur} months", xlabel="month", ylabel="bid % (discount)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("v3 vs v4 vs v5, predicting the newest cohort from older groups only")
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "v3_v4_v5.png", dpi=130)
    print(f"\n-> {OUT / 'v3_v4_v5.png'}")


if __name__ == "__main__":
    main()