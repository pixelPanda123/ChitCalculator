"""
Validate curve against running (incomplete) groups.

For each incomplete group, predict bid % using the curve,
compare vs actual bids, compute error (MAE).

Runs from project root:
    python3 analysis/validate_curve_v2.py
"""

import sys
from pathlib import Path
import pandas as pd
import json

ROOT = Path(__file__).resolve().parent.parent
CSV_AUCTIONS = ROOT / "data" / "chit_auctions.csv"
CSV_GROUPS = ROOT / "group_assessment.csv"
CURVE_JSON = ROOT / "data" / "reference_curve.json"


def load_curve():
    """Load the new reference curve."""
    if not CURVE_JSON.exists():
        print(f"ERROR: {CURVE_JSON} not found")
        sys.exit(1)
    return json.loads(CURVE_JSON.read_text())


def predict_bid_pct(curve, apm, duration, chit_value, month):
    """Predict bid % using curve. Returns None if not in curve."""
    val_key = f"{int(chit_value/100000):.0f}L"
    key = f"{apm}|{duration}|{val_key}"

    if key not in curve['curve']:
        return None

    months_data = curve['curve'][key]
    if str(month) not in months_data:
        return None

    return months_data[str(month)]['p50']  # Median


def validate():
    """Main validation."""

    curve = load_curve()
    auctions = pd.read_csv(CSV_AUCTIONS)
    groups = pd.read_csv(CSV_GROUPS)

    print("\n" + "="*70)
    print("VALIDATING CURVE AGAINST RUNNING (INCOMPLETE) GROUPS")
    print("="*70 + "\n")

    # Get incomplete groups
    running = groups[groups['status'] == 'no'].copy()
    print(f"Total running groups: {len(running)}")

    # Which ones have curve data?
    running['curve_key'] = running.apply(
        lambda r: f"{int(r['apm_mode'])}|{int(r['duration'])}|{int(r['chit_value']/100000):.0f}L",
        axis=1
    )
    running['in_curve'] = running['curve_key'].isin(curve['curve'].keys())

    validatable = running[running['in_curve']].copy()
    print(f"With curve data: {len(validatable)}\n")

    if len(validatable) == 0:
        print("No validatable groups found!")
        return

    # Validate each
    results = []

    print(f"{'Group':>8} {'APM':>3} {'Max Mo':>7} {'Months':>7} {'MAE':>8}")
    print("-" * 50)

    for _, row in validatable.iterrows():
        gid = int(row['groupid'])
        apm = int(row['apm_mode'])
        dur = int(row['duration'])
        val = row['chit_value']
        max_mo = int(row['max_auction_month'])

        # Get actual bids for this group
        group_data = auctions[auctions['groupid'] == gid].copy()
        actual_monthly = group_data.groupby('auctionmonth')['bid_percentage'].mean()

        # Predict and compute errors
        errors = []
        for month in sorted(actual_monthly.index):
            if month > max_mo:
                break

            pred = predict_bid_pct(curve, apm, dur, val, month)
            if pred is None:
                continue

            actual = actual_monthly[month]
            errors.append(abs(pred - actual))

        if len(errors) == 0:
            continue

        mae = sum(errors) / len(errors)

        print(f"{gid:>8} {apm:>3} {max_mo:>7} {len(errors):>7} "
              f"{mae*100:>7.2f}%")

        results.append({
            'groupid': gid,
            'apm': apm,
            'max_month': max_mo,
            'num_months': len(errors),
            'mae': mae,
        })

    # Summary by APM
    print("\n" + "="*70)
    print("SUMMARY BY APM")
    print("="*70 + "\n")

    by_apm = {}
    for r in results:
        apm = r['apm']
        if apm not in by_apm:
            by_apm[apm] = []
        by_apm[apm].append(r['mae'])

    for apm in sorted(by_apm.keys()):
        maes = by_apm[apm]
        avg = sum(maes) / len(maes)
        print(f"  {int(apm)}-APM: {len(maes):2d} groups, "
              f"avg MAE = {avg*100:5.2f}%, "
              f"range = {min(maes)*100:5.2f}% to {max(maes)*100:5.2f}%")

    print("\n✓ Validation complete\n")


if __name__ == '__main__':
    validate()