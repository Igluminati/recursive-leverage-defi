"""Per-whale activity taxonomy with consecutive-day episodes (issue #78).

A whale executing one decision over several consecutive days (e.g. W-16's
March 2026 wind-down) is counted once per day by the daily flags. This script
adds the episode view: a run of consecutive flagged days counts as one
period, and a gap of at least one calendar day starts a new period.

Outputs the row set for the per-whale activity taxonomy table
(tab:activity-taxonomy-by-whale), both as CSV and as LaTeX-ready lines.
"""

from pathlib import Path

import pandas as pd

FEATURES_CSV = (
    Path(__file__).resolve().parents[2]
    / "feature_engineering"
    / "data"
    / "daily_features_all.csv"
)
OUTPUT_CSV = Path(__file__).resolve().parent / "output" / "activity_taxonomy_by_whale.csv"

FLAG_COLUMNS = [
    "position_activity",
    "risk_rebalance",
    "leverage_adjust",
    "capital_flow",
    "levered_scaling",
    "minor_activity",
]


def count_episodes(dates: pd.Series) -> int:
    """Number of runs of consecutive calendar days."""
    if dates.empty:
        return 0
    gaps = dates.sort_values().diff().dt.days
    return int((gaps != 1).sum())  # first row is NaN != 1, starting run one


def build_table() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_CSV, parse_dates=["date"])
    rows = []
    for whale, g in df.groupby("whale_id"):
        row = {
            "whale": whale,
            "protocol": g["protocol"].iloc[0],
            "market": f"{g['collateral_token'].iloc[0]}/{g['borrow_token'].iloc[0]}",
            "days": len(g),
        }
        for flag in FLAG_COLUMNS:
            flagged = g.loc[g[flag] == 1, "date"]
            row[f"{flag}_days"] = len(flagged)
            row[f"{flag}_episodes"] = count_episodes(flagged)
        row["risk_pct"] = 100 * row["risk_rebalance_days"] / row["days"]
        rows.append(row)
    table = pd.DataFrame(rows)
    table["order"] = table["whale"].str.extract(r"(\d+)").astype(int)
    return table.sort_values("order").drop(columns="order").reset_index(drop=True)


def to_latex_rows(table: pd.DataFrame) -> str:
    lines = []
    for _, r in table.iterrows():
        protocol = "Morpho" if r["protocol"] == "morpho" else "Aave"
        lines.append(
            f"{r['whale']} & {protocol} & {r['market']} & {r['days']} & "
            f"{r['position_activity_days']} & {r['risk_rebalance_days']} & "
            f"{r['risk_rebalance_episodes']} & {r['leverage_adjust_days']} & "
            f"{r['capital_flow_days']} & {r['levered_scaling_days']} & "
            f"{r['minor_activity_days']} & {r['risk_pct']:.1f} \\\\"
        )
    return "\n".join(lines)


def main() -> None:
    table = build_table()
    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    table.to_csv(OUTPUT_CSV, index=False)

    totals = {
        flag: (
            int(table[f"{flag}_days"].sum()),
            int(table[f"{flag}_episodes"].sum()),
        )
        for flag in FLAG_COLUMNS
    }
    print(f"Wrote {OUTPUT_CSV}")
    print("\nTotals (days -> episodes):")
    for flag, (days, episodes) in totals.items():
        print(f"  {flag}: {days} -> {episodes}")
    print("\nLaTeX rows for tab:activity-taxonomy-by-whale:\n")
    print(to_latex_rows(table))


if __name__ == "__main__":
    main()
