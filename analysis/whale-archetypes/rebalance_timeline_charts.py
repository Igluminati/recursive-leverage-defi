"""Chronological LTV charts with risk-rebalance periods (issue #82).

The archetype-mix bars show how much of each behaviour a whale has, but not
when it happens. These charts plot the zoomed LTV trajectory (same style as
the #68 LTV history charts) and overlay the risk-rebalance days, with runs
of consecutive days shaded as one period, so multi-day campaigns such as
W-16's March 2026 wind-down are visible as blocks rather than dots.

Charts for every whale land in output/rebalance_timelines/; the
representative set for the paper is copied into output/.
"""

import shutil
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

PANEL = Path(__file__).resolve().parents[2] / "feature_engineering" / "data" / "daily_features_all.csv"
OUT_ALL = Path(__file__).resolve().parent / "output" / "rebalance_timelines"
OUT_PAPER = Path(__file__).resolve().parent / "output"

# Whales with clearly visible multi-day periods, per the 2026-08-06 call.
PAPER_WHALES = ["W-16", "W-14", "W-1", "W-11"]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.6,
    "font.size": 11,
})


def episodes(dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Runs of consecutive calendar days as (start, end) spans."""
    spans = []
    for d in dates.sort_values():
        if spans and (d - spans[-1][1]).days == 1:
            spans[-1] = (spans[-1][0], d)
        else:
            spans.append((d, d))
    return spans


def plot_whale(g: pd.DataFrame, wid: str, out_path: Path) -> bool:
    # Keep LTV == 0 rows so wind-downs to zero stay visible, but require a
    # position context (any debt over the panel).
    plot = g[g["ltv"].notna()].copy()
    if plot.empty or (g["borrow_balance_usd"].fillna(0) < 1).all():
        return False

    open_debt = plot[plot["borrow_balance_usd"].fillna(0) >= 1]
    base = open_debt if not open_debt.empty else plot
    ltv_min, ltv_max = float(base["ltv"].min()), float(base["ltv"].max())
    pad = max(0.005, (ltv_max - ltv_min) * 0.15)
    ymin, ymax = max(0.0, ltv_min - pad), min(1.0, ltv_max + pad)
    if ymax - ymin < 0.02:
        mid = (ymin + ymax) / 2
        ymin, ymax = max(0.0, mid - 0.01), min(1.0, mid + 0.01)

    lltv = None
    if plot["liquidation_threshold"].notna().any():
        lltv = float(plot["liquidation_threshold"].dropna().iloc[0])
        ymax = max(ymax, min(1.0, lltv + 0.005))

    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(plot["date"], plot["ltv"], color="#4C72B0", linewidth=1.4, zorder=2)

    rebal_days = g.loc[g["risk_rebalance"] == 1, "date"]
    for start, end in episodes(rebal_days):
        # Widen by half a day per side so single-day periods stay visible.
        ax.axvspan(
            start - pd.Timedelta(hours=12),
            end + pd.Timedelta(hours=12),
            color="#DD8452",
            alpha=0.25,
            zorder=1,
        )
    marks = plot[plot["risk_rebalance"] == 1]
    ax.scatter(
        marks["date"], marks["ltv"],
        color="#DD8452", edgecolor="#8C3B0F", s=28, zorder=3,
        label="risk-rebalance day",
    )

    if lltv is not None:
        ax.axhline(lltv, color="#C44E52", linewidth=1.2, linestyle="--", label=f"LLTV {lltv:.3f}")

    ax.set_ylim(ymin, ymax)
    ax.set_ylabel("LTV")
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.legend(loc="best", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return True


def main() -> None:
    df = pd.read_csv(PANEL, parse_dates=["date"])
    OUT_ALL.mkdir(parents=True, exist_ok=True)

    made = []
    for wid, g in df.groupby("whale_id"):
        g = g.sort_values("date")
        out = OUT_ALL / f"ltv_rebalance_timeline_{wid}.png"
        if plot_whale(g, wid, out):
            made.append(wid)

    for wid in PAPER_WHALES:
        src = OUT_ALL / f"ltv_rebalance_timeline_{wid}.png"
        if src.exists():
            shutil.copy(src, OUT_PAPER / src.name)

    print(f"Charts written for {len(made)} whales in {OUT_ALL}")
    print(f"Paper set copied to {OUT_PAPER}: {', '.join(PAPER_WHALES)}")


if __name__ == "__main__":
    main()
