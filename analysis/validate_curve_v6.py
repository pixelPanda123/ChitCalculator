"""
Validate v6 (v5's recent-cohort median + v4's pooled decay-shape tail-splice):

1. Fair hold-out MAE  - v3 vs v5 vs v6, predicting the newest cohort from
   older groups only (same setup as validate_curve_v5.py).
2. Cash flow          - one real subscriber's month-by-month bid %, dividend
   and prize, real vs v6-predicted (v6 curve built with that group held out),
   run through the calculator's own engine.

Run from the project root:
    python analysis/validate_curve_v6.py
Writes analysis/output/v3_v5_v6.png, analysis/output/cashflow_v6_<gid>.csv
and analysis/output/cashflow_v6.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))

from build_curve import CURRENT_CAP, FC_RATE, classify_groups, curve_groups, load_auctions, monthly_bids  # noqa: E402
from build_curve_v4 import MIN_START_YEAR, break_months, decay_template  # noqa: E402
from build_curve_v5 import recent_window  # noqa: E402
from build_curve_v6 import observed_series, recent_break_month, splice_tail  # noqa: E402
from src.auction_schedule import AuctionResult  # noqa: E402
from src.cash_flow import calculate_month_cash_flow  # noqa: E402
from src.chit_calculator import calculate_chit  # noqa: E402
from src.models import ChitInput  # noqa: E402

OUT = ROOT / "analysis" / "output"
CONFIGS = [(4, 25, 2026), (2, 50, 2025)]        # (apm, duration, held-out year)
CASHFLOW_EXAMPLES = [(3826217, 20), (3338611, 35)]   # (group, month subscriber lifts)


# --------------------------------------------------------------- 1. fair hold-out MAE
def v3_curve(train: pd.DataFrame, pm: pd.DataFrame, dur: int) -> dict:
    med = pm[pm.groupid.isin(train.index)].groupby("auctionmonth")["bid"].median()
    return {m: float(med.get(m, med.iloc[-1])) for m in range(1, dur + 1)}


def v5_curve(train: pd.DataFrame, pm: pd.DataFrame, dur: int) -> dict:
    years = sorted(train.start_year.unique(), reverse=True)
    if not years:
        return {}
    from build_curve_v5 import MIN_DEPTH_FRAC, MIN_GROUPS
    picked, cutoff = [], years[-1]
    for y in years:
        picked.append(y)
        window = train[train.start_year.isin(picked)]
        if len(window) >= MIN_GROUPS and window.months_reached.max() >= dur * MIN_DEPTH_FRAC:
            cutoff = min(picked)
            break
    return v3_curve(train[train.start_year >= cutoff], pm, dur)


def v6_curve(a_train: pd.DataFrame, train: pd.DataFrame, apm: int, dur: int, cap: float) -> dict:
    """a_train = raw auction rows for groups in `train` only (so the pooled decay
    template can't see the held-out cohort either)."""
    window, _ = recent_window(train, apm, dur)
    pm_window = monthly_bids(a_train[a_train.groupid.isin(window.index)])
    obs = observed_series(pm_window, dur)
    bm = recent_break_month(obs, cap)
    broken = train.join(break_months(a_train, train))
    template = {int(k): v for k, v in decay_template(a_train, broken, apm, dur).items()}
    spliced = splice_tail(obs, template, bm, cap, dur)
    return {int(m): v["p50"] for m, v in spliced.items()}


def holdout_mae() -> dict:
    a = load_auctions()
    groups = classify_groups(a)
    used = curve_groups(groups)
    used = used[used.start_year >= MIN_START_YEAR]

    rows, curves_for_plot = [], {}
    for apm, dur, held_out_year in CONFIGS:
        d = used[(used.apm == apm) & (used.duration == dur)]
        train, test = d[d.start_year < held_out_year], d[d.start_year == held_out_year]
        if len(test) == 0:
            continue
        pm_all = monthly_bids(a[a.groupid.isin(d.index)])
        a_train = a[a.groupid.isin(train.index)]

        v3 = v3_curve(train, pm_all, dur)
        v5 = v5_curve(train, pm_all, dur)
        v6 = v6_curve(a_train, train, apm, dur, CURRENT_CAP[dur])

        curves_for_plot[(apm, dur)] = dict(v3=v3, v5=v5, v6=v6,
                                           test=pm_all[pm_all.groupid.isin(test.index)])
        for _, r in pm_all[pm_all.groupid.isin(test.index)].iterrows():
            m = int(r.auctionmonth)
            rows.append(dict(config=f"{apm}|{dur}", month=m,
                             err_v3=abs(v3[m] - r.bid),
                             err_v5=abs(v5.get(m, v3[m]) - r.bid),
                             err_v6=abs(v6.get(m, v3[m]) - r.bid)))

    e = pd.DataFrame(rows)
    e["phase"] = pd.cut(e.month, [0, 6, 16, 100], labels=["1-6", "7-16", "17+"])
    print("1. FAIR HOLD-OUT MAE (bid % points) - predicting the newest cohort from older groups only\n"
          + "=" * 78)
    print(f"Held-out cohorts: {', '.join(f'{a}|{d} -> {y}' for a, d, y in CONFIGS)}\n")
    print((e.groupby(["config", "phase"], observed=True)[["err_v3", "err_v5", "err_v6"]].mean() * 100)
          .round(1).to_string())
    print("\nOverall mean |error| (bid % points):")
    print((e.groupby("config")[["err_v3", "err_v5", "err_v6"]].mean() * 100).round(2).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, (apm, dur) in zip(axes, curves_for_plot):
        c = curves_for_plot[(apm, dur)]
        months = list(range(1, dur + 1))
        ax.plot(months, [c["v3"][m] * 100 for m in months], "--", color="grey", label="v3 (pooled, all years)")
        v5m = [m for m in months if m in c["v5"]]
        ax.plot(v5m, [c["v5"][m] * 100 for m in v5m], "-", color="tab:orange", lw=1.8, label="v5 (recent cohort)")
        v6m = [m for m in months if m in c["v6"]]
        ax.plot(v6m, [c["v6"][m] * 100 for m in v6m], "-", color="tab:green", lw=2.2, label="v6 (recent + spliced tail)")
        for gid, g in c["test"].groupby("groupid"):
            ax.plot(g.auctionmonth, g.bid * 100, "o", color="tab:red", ms=3, alpha=0.5,
                    label="held-out newest cohort (actual)" if gid == c["test"].groupid.iloc[0] else None)
        ax.set(title=f"{apm} auctions/month, {dur} months", xlabel="month", ylabel="bid % (discount)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("v3 vs v5 vs v6, predicting the newest cohort from older groups only")
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "v3_v5_v6.png", dpi=130)
    print(f"\n-> {OUT / 'v3_v5_v6.png'}")
    return curves_for_plot


# --------------------------------------------------------------- 2. cash flow
def schedule_from_bids(bids: dict[int, float], chit: float, dur: int) -> dict:
    return {
        m: AuctionResult(month=m, bid_amount=b * chit,
                         dividend=max(0.0, (b - FC_RATE) * chit / dur),
                         prize_money=chit * (1 - b))
        for m, b in bids.items()
    }


def actual_schedule(a: pd.DataFrame, gid: int) -> dict:
    g = a[a["groupid"] == gid].sort_values(["auctionmonth", "auctionnumber"])
    sched = {}
    for m, d in g.groupby("auctionmonth"):
        won = d.iloc[0] if m > 1 else d.sort_values("bid_percentage").iloc[-1]
        sched[int(m)] = AuctionResult(month=int(m), bid_amount=float(won["bid_amount"]),
                                      dividend=float(d["dividend"].sum()),
                                      prize_money=float(won["auctionamount"]))
    return sched


def run_engine(sched: dict, chit: float, dur: int, lift: int, months: int) -> pd.DataFrame:
    inp = ChitInput(chit_value=chit, duration_months=dur, month_of_lifting=lift)
    calc = calculate_chit(inp, schedule=sched)
    rows = [calculate_month_cash_flow(m, inp, calc, sched).__dict__ for m in range(1, months + 1)]
    return pd.DataFrame(rows).set_index("month")


def cash_flow_validation() -> None:
    print("\n2. CASH FLOW - REAL vs v6-PREDICTED (group held out of its own curve)\n" + "=" * 78)
    a = load_auctions()
    groups = classify_groups(a)
    used = curve_groups(groups)

    fig = plt.figure(figsize=(14, 5 * len(CASHFLOW_EXAMPLES)), layout="constrained")
    subfigs = fig.subfigures(len(CASHFLOW_EXAMPLES), 1)
    for row, (gid, lift) in enumerate(CASHFLOW_EXAMPLES):
        gid = gid if gid in used.index else str(gid)
        g = used.loc[gid]
        chit, dur, apm = float(g.chit_value), int(g.duration), int(g.apm)
        reached = int(g.months_reached)
        months = reached - 1 if reached < dur else reached
        cap = CURRENT_CAP[dur]

        train = used.drop(index=gid)                       # held out of its own curve
        pm_train = monthly_bids(a[a.groupid.isin(train.index)])
        window, cutoff = recent_window(train, apm, dur)
        obs = observed_series(pm_train[pm_train.groupid.isin(window.index)], dur)
        bm = recent_break_month(obs, cap)
        template = {int(k): v for k, v in
                   decay_template(a, train.join(break_months(a, train)), apm, dur).items()}
        v6 = {int(m): v["p50"] for m, v in splice_tail(obs, template, bm, cap, dur).items()}

        real = run_engine(actual_schedule(a, gid), chit, dur, lift, months)
        pred = run_engine(schedule_from_bids(v6, chit, dur), chit, dur, lift, months)

        t = pd.DataFrame({"installment": real.gross_installment,
                          "dividend real": real.dividend, "dividend v6": pred.dividend,
                          "net real": real.net_cash_flow, "net v6": pred.net_cash_flow})
        t.to_csv(OUT / f"cashflow_v6_{gid}.csv")

        title = (f"Group {gid}: Rs {chit/1e5:.0f}L, {dur} months, {apm} auctions/month, "
                 f"v6 window from {cutoff}; lifts month {lift}; months 1-{months} compared")
        print("\n" + title)
        print(t.round(0).to_string())
        print(f"\n  real  dividends Rs {real.dividend.sum():>10,.0f} | prize Rs {real.prize_received.sum():>10,.0f} "
              f"| net Rs {real.net_cash_flow.sum():>10,.0f}")
        print(f"  v6    dividends Rs {pred.dividend.sum():>10,.0f} | prize Rs {pred.prize_received.sum():>10,.0f} "
              f"| net Rs {pred.net_cash_flow.sum():>10,.0f}")
        print(f"  v6 dividend error: Rs {(pred.dividend - real.dividend).abs().mean():,.0f}/month avg, "
              f"total off by Rs {pred.dividend.sum() - real.dividend.sum():+,.0f} "
              f"({(pred.dividend.sum() / real.dividend.sum() - 1) * 100:+.1f}%)")

        ax1, ax2 = subfigs[row].subplots(1, 2)
        subfigs[row].suptitle(title, fontsize=10, weight="bold")
        ax1.plot(real.index, real.dividend, "o-", color="k", ms=3, label="real")
        ax1.plot(pred.index, pred.dividend, "s--", color="tab:green", ms=3, label="v6 (held out)")
        ax2.plot(real.index, real.net_cash_flow.cumsum() / 1000, "o-", color="k", ms=3, label="real")
        ax2.plot(pred.index, pred.net_cash_flow.cumsum() / 1000, "s--", color="tab:green", ms=3, label="v6 (held out)")
        ax1.set(title="Dividend received each month (Rs)", xlabel="month")
        ax2.set(title="Cumulative net cash flow (Rs thousand)", xlabel="month")
        ax2.axvline(lift, color="green", alpha=0.4, lw=1)
        for x in (ax1, ax2):
            x.grid(alpha=0.3); x.legend(fontsize=8)
    fig.savefig(OUT / "cashflow_v6.png", dpi=130)
    print(f"\n-> {OUT / 'cashflow_v6.png'}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    holdout_mae()
    cash_flow_validation()


if __name__ == "__main__":
    main()