"""
v3 vs v4, tested fairly: predict the newest cohort using ONLY older groups.

For each config, hold out every group that started in the newest year, build
v3 (pooled median) and v4 (break-month trend + decay shape) from what's left,
then score both against the held-out newest-year groups' real bids.

Run from the project root:
    python analysis/validate_curve_v4.py
Writes analysis/output/v3_vs_v4.png and prints a table.
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
from build_curve_v4 import break_months, build_series, decay_template, fit_break_trend  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "output"

CONFIGS = [(4, 25, 2026), (2, 50, 2025)]   # (apm, duration, held-out year)


def v3_curve(train: pd.DataFrame, pm: pd.DataFrame, dur: int) -> dict:
    med = pm[pm.groupid.isin(train.index)].groupby("auctionmonth")["bid"].median()
    return {m: float(med.get(m, med.iloc[-1])) for m in range(1, dur + 1)}


def main() -> None:
    a = load_auctions()
    groups = classify_groups(a)
    used = curve_groups(groups).join(break_months(a, curve_groups(groups)))

    rows, curves_for_plot = [], {}
    for apm, dur, held_out_year in CONFIGS:
        d = used[(used.apm == apm) & (used.duration == dur)]
        train, test = d[d.start_year < held_out_year], d[d.start_year == held_out_year]
        if len(test) == 0:
            continue
        pm_all = monthly_bids(a[a.groupid.isin(d.index)])

        v3 = v3_curve(train, pm_all, dur)
        pred_month, _ = fit_break_trend(train.assign(**{"break": train["break"]}), apm, dur)
        # fit_break_trend needs a fresh fit *as if* held_out_year were "now" -> reuse via monkey approach:
        # (re-derive directly here so the extrapolation target matches the held-out year)
        yearly = train.dropna(subset=["break"]).groupby("start_year")["break"].median() / dur
        if len(yearly) >= 2:
            slope, intercept = np.polyfit(yearly.index.values.astype(float), yearly.values, 1)
            pred_frac = np.clip(slope * held_out_year + intercept, 1 / dur, 0.9)
        else:
            pred_frac = yearly.mean() if len(yearly) else 0.3
        pred_month = max(2, round(pred_frac * dur))
        template = decay_template(a, train, apm, dur)
        v4 = {int(k): v["p50"] for k, v in build_series(pred_month, template, CURRENT_CAP[dur], dur).items()}

        curves_for_plot[(apm, dur)] = dict(v3=v3, v4=v4, break_month=pred_month,
                                           test=pm_all[pm_all.groupid.isin(test.index)])

        for _, r in pm_all[pm_all.groupid.isin(test.index)].iterrows():
            m = int(r.auctionmonth)
            rows.append(dict(config=f"{apm}|{dur}", month=m,
                             err_v3=abs(v3[m] - r.bid), err_v4=abs(v4[m] - r.bid)))

    e = pd.DataFrame(rows)
    e["phase"] = pd.cut(e.month, [0, 6, 16, 100], labels=["1-6", "7-16", "17+"])
    print(f"Held-out cohorts: {', '.join(f'{a}|{d} -> {y}' for a, d, y in CONFIGS)}\n")
    print((e.groupby(["config", "phase"], observed=True)[["err_v3", "err_v4"]].mean() * 100)
          .round(1).to_string())
    print("\nOverall mean |error| (bid % points):")
    print((e.groupby("config")[["err_v3", "err_v4"]].mean() * 100).round(2).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, (apm, dur) in zip(axes, curves_for_plot):
        c = curves_for_plot[(apm, dur)]
        months = list(range(1, dur + 1))
        ax.plot(months, [c["v3"][m] * 100 for m in months], "--", color="grey", label="v3 (pooled, all years)")
        ax.plot(months, [c["v4"][m] * 100 for m in months], "-", color="tab:blue", lw=2,
                label=f"v4 (trend, predicted break=month {c['break_month']})")
        for gid, g in c["test"].groupby("groupid"):
            ax.plot(g.auctionmonth, g.bid * 100, "o", color="tab:red", ms=3, alpha=0.5,
                    label="held-out newest cohort (actual)" if gid == c["test"].groupid.iloc[0] else None)
        ax.set(title=f"{apm} auctions/month, {dur} months", xlabel="month", ylabel="bid % (discount)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("v3 vs v4, predicting the newest cohort from older groups only")
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "v3_vs_v4.png", dpi=130)
    print(f"\n-> {OUT / 'v3_vs_v4.png'}")


if __name__ == "__main__":
    main()