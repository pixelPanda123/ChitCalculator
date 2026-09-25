"""
Validate reference_curve_v3.json (variable bidding) against real groups.

1. Data inventory   - how much data sits behind each bidding type.
2. Discrepancy      - fixed-schedule "smooth decay" vs variable "plateau-then-decay",
                      and what the old v2 curve predicted.
3. Hold-out error   - every group is predicted from a curve built WITHOUT it
                      (leave-one-group-out), so no group grades itself.
4. Cash flow        - one subscriber's month-by-month cash flow, real vs predicted,
                      both run through the calculator's own engine.

Run from the project root:
    python analysis/validate_curve_v3.py
Outputs go to analysis/output/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))

from build_curve import (FC_RATE, build_curve, classify_groups,   # noqa: E402
                            curve_groups, load_auctions, monthly_bids, _val_key)
from src.auction_schedule import AuctionResult                        # noqa: E402
from src.cash_flow import calculate_month_cash_flow                   # noqa: E402
from src.chit_calculator import calculate_chit                        # noqa: E402
from src.models import ChitInput                                      # noqa: E402

OUT = ROOT / "analysis" / "output"
V2_JSON = ROOT / "data" / "reference_curve_v2.json"

# (group, month the subscriber lifts the chit)
EXAMPLES = [(6929397, 12), (3338588, 20)]


# ---------------------------------------------------------------- helpers
def lookup(curve: dict, apm, dur, val) -> dict | None:
    """Exact chit-value key if present, else the pooled key."""
    for key in (f"{apm}|{dur}|{_val_key(val)}", f"{apm}|{dur}|ALL"):
        if key in curve["curve"]:
            return curve["curve"][key]
    return None


def schedule_from_bids(bids: dict[int, float], chit: float, dur: int) -> dict:
    """Monthly bid % -> engine schedule. Dividend = what one member receives."""
    return {
        m: AuctionResult(
            month=m,
            bid_amount=b * chit,
            dividend=max(0.0, (b - FC_RATE) * chit / dur),
            prize_money=chit * (1 - b),
        )
        for m, b in bids.items()
    }


def actual_schedule(a: pd.DataFrame, gid: int) -> dict:
    """Real auctions -> engine schedule (sum of the month's real dividends)."""
    g = a[a["groupid"] == gid].sort_values(["auctionmonth", "auctionnumber"])
    sched = {}
    for m, d in g.groupby("auctionmonth"):
        won = d.iloc[0] if m > 1 else d.sort_values("bid_percentage").iloc[-1]
        sched[int(m)] = AuctionResult(
            month=int(m),
            bid_amount=float(won["bid_amount"]),
            dividend=float(d["dividend"].sum()),
            prize_money=float(won["auctionamount"]),
        )
    return sched


def run_engine(sched: dict, chit: float, dur: int, lift: int, months: int) -> pd.DataFrame:
    inp = ChitInput(chit_value=chit, duration_months=dur, month_of_lifting=lift)
    calc = calculate_chit(inp, schedule=sched)
    rows = [calculate_month_cash_flow(m, inp, calc, sched).__dict__
            for m in range(1, months + 1)]
    return pd.DataFrame(rows).set_index("month")


# ---------------------------------------------------------------- 1. inventory
def inventory(groups: pd.DataFrame) -> None:
    print("\n1. DATA INVENTORY\n" + "=" * 70)
    used = curve_groups(groups)
    groups = groups.assign(
        bucket=groups["bid_type"].where(
            ~((groups["bid_type"] == "variable") & ~groups.index.isin(used.index)),
            "variable (old 30% cap)"))
    t = groups.groupby("bucket").agg(
        groups=("duration", "size"),
        completed=("completed", lambda s: (s == "yes").sum()),
        auctions=("auctions", "sum"),
        started=("start_year", lambda s: f"{s.min()}-{s.max()}"),
        durations=("duration", lambda s: ",".join(map(str, sorted(s.unique())))))
    print(t.to_string())
    print("\nVariable groups used in v3, by how far they have got:")
    bins = pd.cut(used["months_reached"], [0, 6, 12, 24, 36, 50],
                  labels=["1-6", "7-12", "13-24", "25-36", "37-50"])
    print(used.groupby(["duration", bins], observed=True).size()
              .unstack(fill_value=0).to_string())


# ---------------------------------------------------------------- 2. discrepancy
def discrepancy(a, groups, v3, v2) -> None:
    print("\n2. FIXED vs VARIABLE (4 auctions/month, 25 months, Rs 1L)\n" + "=" * 70)
    pm = monthly_bids(a).join(groups, on="groupid")
    sel = pm[(pm.apm == 4) & (pm.duration == 25) & (pm.chit_value == 100000)]
    fixed = sel[(sel.bid_type == "fixed") & (sel.cap == 0.35)].groupby("auctionmonth")["bid"].median()
    var = pd.Series({int(k): v["p50"] for k, v in v3["curve"]["4|25|1L"].items()})
    old = pd.Series({int(k): v["p50"] for k, v in v2["curve"]["4|25|1L"].items()})
    t = pd.DataFrame({"fixed schedule": fixed, "variable (v3)": var, "v2 curve": old}) * 100
    t["v3 - fixed"] = t["variable (v3)"] - t["fixed schedule"]
    print(t.round(1).to_string())
    print(f"\nmean |gap| fixed vs variable: {t['v3 - fixed'].abs().mean():.1f} pts")

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for gid, d in sel[sel.index.isin(sel.index) & (sel.bid_type == "variable") & (sel.cap == 0.35)].groupby("groupid"):
        ax[0].plot(d.auctionmonth, d.bid * 100, color="tab:blue", alpha=0.12, lw=1)
    ax[0].plot(fixed.index, fixed * 100, "o-", color="tab:red", label="fixed schedule (18 groups, 1 copied schedule)")
    ax[0].plot(var.index, var * 100, "s-", color="tab:blue", lw=2.5, label="variable - v3 median (39 groups)")
    ax[0].plot(old.index, old * 100, "--", color="grey", label="v2 curve (mixed both)")
    ax[0].set(title="25 months, 4 auctions/month, Rs 1L", xlabel="month", ylabel="bid % (discount)")
    ax[0].legend(fontsize=8)

    pm50 = pm[(pm.duration == 50) & (pm.bid_type == "variable")]
    for gid, d in pm50.groupby("groupid"):
        ax[1].plot(d.auctionmonth, d.bid * 100, color="tab:blue", alpha=0.08, lw=1)
    c = v3["curve"]["2|50|ALL"]
    xs = [int(k) for k in c]; ys = [c[k]["p50"] * 100 for k in c]
    obs = [c[k]["source"] == "observed" for k in c]
    ax[1].plot([x for x, o in zip(xs, obs) if o], [y for y, o in zip(ys, obs) if o],
               "s-", color="tab:blue", lw=2.5, label="variable - v3 median (103 groups)")
    ax[1].plot([x for x, o in zip(xs, obs) if not o], [y for y, o in zip(ys, obs) if not o],
               ":", color="tab:blue", lw=2.5, label="extrapolated (no data yet)")
    ax[1].set(title="50 months, 2 auctions/month (no fixed groups exist)", xlabel="month")
    ax[1].legend(fontsize=8)
    for x in ax:
        x.grid(alpha=0.3)
    fig.suptitle("Faint lines = individual real groups")
    fig.tight_layout()
    fig.savefig(OUT / "fixed_vs_variable.png", dpi=130)


# ---------------------------------------------------------------- 3. hold-out
def holdout(a, groups, v2) -> None:
    print("\n3. LEAVE-ONE-GROUP-OUT ERROR (bid % points, observed months only)\n" + "=" * 70)
    used = curve_groups(groups)
    pm = monthly_bids(a[a.groupid.isin(used.index)])
    rows = []
    for gid, g in used.iterrows():
        cv = lookup(build_curve(a, groups, exclude={gid}), g.apm, g.duration, g.chit_value)
        c2 = lookup(v2, g.apm, g.duration, g.chit_value) if g.duration == 25 else None
        for _, r in pm[pm.groupid == gid].iterrows():
            m = str(int(r.auctionmonth))
            if cv is None or m not in cv:
                continue
            rows.append({"groupid": gid, "key": f"{g.apm}|{g.duration}", "month": int(m),
                         "err_v3": abs(cv[m]["p50"] - r.bid),
                         "in_band": cv[m]["p10"] - 1e-9 <= r.bid <= cv[m]["p90"] + 1e-9,
                         "err_v2": abs(c2[m]["p50"] - r.bid) if c2 and m in c2 else None})
    e = pd.DataFrame(rows)
    e.to_csv(OUT / "holdout_errors.csv", index=False)
    s = e.groupby("key").agg(groups=("groupid", "nunique"), months=("month", "size"),
                             mae_v3=("err_v3", "mean"), in_p10_p90=("in_band", "mean"),
                             mae_v2=("err_v2", "mean"))
    s[["mae_v3", "mae_v2"]] *= 100
    print(s.round(3).to_string())
    e["phase"] = pd.cut(e.month, [0, 1, 6, 12, 24, 50], labels=["1", "2-6", "7-12", "13-24", "25+"])
    print("\nv3 error by month:\n" + (e.groupby(["key", "phase"], observed=True).err_v3.mean() * 100)
          .round(1).unstack().to_string())


# ---------------------------------------------------------------- 4. cash flow
def cash_flows(a, groups, v2) -> None:
    print("\n4. CASH FLOW - REAL vs PREDICTED (one subscriber, one ticket)\n" + "=" * 70)
    fig = plt.figure(figsize=(14, 5 * len(EXAMPLES)), layout="constrained")
    subfigs = fig.subfigures(len(EXAMPLES), 1)
    for row, (gid, lift) in enumerate(EXAMPLES):
        g = groups.loc[gid]
        chit, dur, reached = float(g.chit_value), int(g.duration), int(g.months_reached)
        months = reached - 1 if reached < dur else reached   # last month may be partial
        cv = lookup(build_curve(a, groups, exclude={gid}), g.apm, dur, chit)  # held out

        flows = {"real": run_engine(actual_schedule(a, gid), chit, dur, lift, months),
                 "v3 (held out)": run_engine(
                     schedule_from_bids({int(k): v["p50"] for k, v in cv.items()}, chit, dur),
                     chit, dur, lift, months)}
        c2 = lookup(v2, g.apm, dur, chit) if dur == 25 else None
        if c2:
            flows["v2"] = run_engine(schedule_from_bids({int(k): v["p50"] for k, v in c2.items()},
                                                        chit, dur), chit, dur, lift, months)

        t = pd.DataFrame({"installment": flows["real"].gross_installment})
        for name, f in flows.items():
            t[f"dividend {name}"] = f.dividend
            t[f"net {name}"] = f.net_cash_flow
        t.to_csv(OUT / f"cashflow_{gid}.csv")

        title = (f"Group {gid}: Rs {chit/1e5:.0f}L, {dur} months, {g.apm} auctions/month, "
                 f"started {g.start_year}; lifts in month {lift}; months 1-{months} compared")
        print("\n" + title)
        print(t.round(0).to_string())
        print("\nTotals over compared months:")
        for name, f in flows.items():
            print(f"  {name:14s} dividends Rs {f.dividend.sum():>10,.0f} | prize Rs "
                  f"{f.prize_received.sum():>10,.0f} | net Rs {f.net_cash_flow.sum():>10,.0f}")
        real, pred = flows["real"], flows["v3 (held out)"]
        print(f"  v3 dividend error: Rs {(pred.dividend - real.dividend).abs().mean():,.0f}/month avg, "
              f"total off by Rs {pred.dividend.sum() - real.dividend.sum():+,.0f} "
              f"({(pred.dividend.sum() / real.dividend.sum() - 1) * 100:+.1f}%)")
        if "v2" in flows:
            print(f"  v2 dividend error: Rs {(flows['v2'].dividend - real.dividend).abs().mean():,.0f}/month avg, "
                  f"total off by Rs {flows['v2'].dividend.sum() - real.dividend.sum():+,.0f}")

        ax1, ax2 = subfigs[row].subplots(1, 2)
        subfigs[row].suptitle(title, fontsize=10.5, weight="bold")
        styles = {"real": ("k", "o-"), "v3 (held out)": ("tab:blue", "s--"), "v2": ("grey", ":")}
        for name, f in flows.items():
            col, st = styles[name]
            ax1.plot(f.index, f.dividend, st, color=col, ms=3, label=name)
            ax2.plot(f.index, f.net_cash_flow.cumsum() / 1000, st, color=col, ms=3, label=name)
        ax1.set(title="Dividend received each month (Rs)", xlabel="month")
        ax2.set(title="Cumulative net cash flow (Rs thousand)", xlabel="month")
        ax2.axvline(lift, color="green", alpha=0.4, lw=1)
        for x in (ax1, ax2):
            x.grid(alpha=0.3); x.legend(fontsize=8)
    fig.savefig(OUT / "cashflow_real_vs_predicted.png", dpi=130)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    a = load_auctions()
    groups = classify_groups(a)
    v3 = json.loads((ROOT / "data" / "reference_curve_v3.json").read_text())
    v2 = json.loads(V2_JSON.read_text())
    inventory(groups)
    discrepancy(a, groups, v3, v2)
    holdout(a, groups, v2)
    cash_flows(a, groups, v2)
    print(f"\nCharts and CSVs -> {OUT}")


if __name__ == "__main__":
    main()