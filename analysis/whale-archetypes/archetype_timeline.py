"""Chronological archetype timeline per whale (call follow-up, 2026-08-06).

The archetype-mix bars show how much of each behaviour a whale has, but not
when. This chart shows, for every whale, which archetype each active day
belongs to over calendar time, so strategy evolution (e.g. W-11 stepping
down from looping into stale low leverage) is visible directly.
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

PANEL = Path(__file__).resolve().parent / "panel_archetypes.csv"
OUT = Path(__file__).resolve().parent / "output" / "archetype-timeline.png"

COLORS = {
    "stale, low leverage": "#4C72B0",
    "active looping": "#DD8452",
    "max leverage hold": "#C44E52",
    "outlier days": "#8172B3",
}


def spans(dates: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Runs of consecutive calendar days as (start, end)."""
    out = []
    for d in dates.sort_values():
        if out and (d - out[-1][1]).days == 1:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


def main() -> None:
    df = pd.read_csv(PANEL, parse_dates=["date"])
    whales = sorted(df["whale_id"].unique(), key=lambda w: int(w.split("-")[1]))

    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "font.size": 10,
    })
    fig, ax = plt.subplots(figsize=(11, 8))

    for i, wid in enumerate(whales):
        g = df[df["whale_id"] == wid]
        for name, color in COLORS.items():
            for start, end in spans(g.loc[g["cluster_name"] == name, "date"]):
                ax.barh(
                    y=i,
                    width=(end - start) + pd.Timedelta(days=1),
                    left=start - pd.Timedelta(hours=12),
                    height=0.72,
                    color=color,
                    linewidth=0,
                )

    ax.set_yticks(range(len(whales)))
    ax.set_yticklabels(whales)
    ax.invert_yaxis()
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.legend(
        handles=[mpatches.Patch(color=c, label=n) for n, c in COLORS.items()],
        loc="upper left",
        fontsize=9,
        framealpha=0.9,
    )
    fig.tight_layout()
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=200)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
