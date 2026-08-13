"""Chronological LTV charts with risk-rebalance periods (issue #82).

The archetype-mix bars show how much of each behaviour a looper has, but not
when it happens. These charts plot the zoomed LTV trajectory (same style as
the #68 LTV history charts) and overlay the risk-rebalance days, with runs
of consecutive days shaded as one period, so multi-day campaigns such as
L-16's March 2026 wind-down are visible as blocks rather than dots.

Charts for every looper land in output/rebalance_timelines/; the
representative set for the paper is copied into output/. The panel still
carries the historical ``whale_id`` column; it is mapped to the L- ids the
paper uses at plot time.
"""

import shutil
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

PANEL = Path(__file__).resolve().parents[2] / "feature_engineering" / "data" / "daily_features_all.csv"
ARCHETYPES = Path(__file__).resolve().parent / "panel_archetypes.csv"
OUT_ALL = Path(__file__).resolve().parent / "output" / "rebalance_timelines"
OUT_PAPER = Path(__file__).resolve().parent / "output"

# Loopers with clearly visible multi-day periods, per the 2026-08-06 call.
PAPER_LOOPERS = ["L-16", "L-14", "L-1", "L-11"]

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


def mix_title(lid: str, mixes: pd.DataFrame) -> str:
    """'L-16 | active looping 45.9% ... ' with the dominant archetype in bold."""
    g = mixes[mixes["looper_id"] == lid]
    if g.empty:
        return lid
    pct = (100 * g["cluster_name"].value_counts(normalize=True)).round(1)
    parts = []
    for i, (name, p) in enumerate(pct.items()):
        label = f"{name} {p}%"
        if i == 0:  # dominant archetype
            label = r"$\bf{" + label.replace(" ", r"\ ").replace("%", r"\%").replace(",", ",\!") + "}$"
        parts.append(label)
    return f"{lid}  |  " + "  ·  ".join(parts)


def plot_looper(g: pd.DataFrame, lid: str, out_path: Path, mixes: pd.DataFrame) -> bool:
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

    # Full-unwind days: all debt repaid and collateral withdrawn, so LTV is
    # undefined and the line cannot reach the shaded period. Mark explicitly.
    closes = g[(g["risk_rebalance"] == 1) & (g["ltv"].isna())]
    if not closes.empty:
        ax.scatter(
            closes["date"], [ymin + 0.04 * (ymax - ymin)] * len(closes),
            marker="v", color="#55A868", edgecolor="#2E5C38", s=42, zorder=3,
            label="position closed (full unwind)",
        )

    if lltv is not None:
        ax.axhline(lltv, color="#C44E52", linewidth=1.2, linestyle="--", label=f"LLTV {lltv:.3f}")

    ax.set_title(mix_title(lid, mixes), loc="left", fontsize=10)
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
    df["looper_id"] = df["whale_id"].str.replace("W-", "L-", regex=False)
    mixes = pd.read_csv(ARCHETYPES, usecols=["whale_id", "cluster_name"])
    mixes["looper_id"] = mixes["whale_id"].str.replace("W-", "L-", regex=False)
    OUT_ALL.mkdir(parents=True, exist_ok=True)

    made = []
    for lid, g in df.groupby("looper_id"):
        g = g.sort_values("date")
        out = OUT_ALL / f"ltv_rebalance_timeline_{lid}.png"
        if plot_looper(g, lid, out, mixes):
            made.append(lid)

    for lid in PAPER_LOOPERS:
        src = OUT_ALL / f"ltv_rebalance_timeline_{lid}.png"
        if src.exists():
            shutil.copy(src, OUT_PAPER / src.name)

    print(f"Charts written for {len(made)} loopers in {OUT_ALL}")
    print(f"Paper set copied to {OUT_PAPER}: {', '.join(PAPER_LOOPERS)}")


if __name__ == "__main__":
    main()
