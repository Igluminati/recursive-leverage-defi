"""Regenerate every paper figure that carries a per-wallet label.

The detailed-analysis sample is named after its behaviour (loopers, L-1 to
L-23) rather than after balance (whales), so every figure printing a wallet id
or the word "whale" has to be redrawn. Figures come from notebooks that are
slow to re-run, so the plotting code for the paper-facing set is collected
here. The panels still use the historical ``whale_id`` column; it is mapped to
the L- ids at plot time.

Run with the whale-archetypes environment, which has hdbscan:

    analysis/whale-archetypes/.venv/bin/python analysis/regenerate_looper_figures.py
"""

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import hdbscan
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "paper" / "overleaf_live" / "figures"
UNSUPERVISED = FIG / "unsupervised"
SUPERVISED = FIG / "supervised"

DAILY = ROOT / "feature_engineering" / "data" / "daily_features_all.csv"
ARCHETYPES = ROOT / "analysis" / "whale-archetypes" / "panel_archetypes.csv"
CLUSTER_READY = ROOT / "analysis" / "whale-archetypes" / "panel_cluster_ready.csv"
LABELLED = ROOT / "analysis" / "whale-risk-supervised" / "whale_features_labeled.csv"

CLUSTER_FEATURES = [
    "ltv", "leverage", "distance_to_liq",
    "ltv_vol_7d", "ltv_vol_14d",
    "risk_rebal_freq_7d", "risk_rebal_freq_30d", "days_since_risk_rebalance",
    "capital_flow_freq_30d",
    "ltv_lag_7", "carry_spread", "carry_spread_levered",
]

ARCHETYPE_COLORS = {
    "stale, low leverage": "#4C72B0",
    "active looping": "#DD8452",
    "max leverage hold": "#C44E52",
    "outlier days": "#8172B3",
}

sns.set_theme(style="whitegrid")


def to_looper(wallet_id: str) -> str:
    return wallet_id.replace("W-", "L-")


def looper_order(values) -> list:
    return sorted(set(values), key=lambda v: int(v.split("-")[1]))


def load(path: Path, **kwargs) -> pd.DataFrame:
    df = pd.read_csv(path, **kwargs)
    df["looper_id"] = df["whale_id"].map(to_looper)
    return df


def save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path.name)


def health_factor_per_looper(daily: pd.DataFrame) -> None:
    summary = daily.groupby("looper_id")["health_factor"].agg(["mean", "min"])
    summary = summary.reindex(looper_order(summary.index))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(summary.index, summary["min"], color="red", zorder=5, label="Min", s=100)
    ax.bar(summary.index, summary["mean"], color="steelblue", label="Mean")
    ax.set_title("Health Factor per Looper (mean + min)", fontsize=14)
    ax.set_xlabel("Looper")
    ax.set_ylabel("Health Factor")
    ax.tick_params(axis="x", labelrotation=45)
    ax.legend()
    fig.tight_layout()
    save(fig, UNSUPERVISED / "health_factor_per_looper.png")


def health_factor_violin(daily: pd.DataFrame) -> None:
    selected = ["L-1", "L-3", "L-14", "L-18", "L-10", "L-11"]
    palette = ["#66c2a5", "#e6c34f", "#e78ac3", "#d9d9d9", "#fc8d62", "#8da0cb"]
    y_top = 1.30

    active = daily[daily["borrow_balance_usd"].fillna(0) >= 1].dropna(subset=["health_factor"])

    labels, series = [], []
    for looper in selected:
        rows = active[active["looper_id"] == looper]
        market = f"{rows['collateral_token'].iloc[0]}-{rows['borrow_token'].iloc[0]}"
        labels.append(f"{looper}\n{rows['protocol'].iloc[0]}\n{market}")
        series.append(rows["health_factor"].to_numpy())

    fig, ax = plt.subplots(figsize=(10, 5))
    parts = ax.violinplot(series, showextrema=False, widths=0.8)
    for body, colour in zip(parts["bodies"], palette):
        body.set_facecolor(colour)
        body.set_edgecolor("#555555")
        body.set_alpha(0.9)

    for i, values in enumerate(series, start=1):
        q1, med, q3 = np.percentile(values, [25, 50, 75])
        ax.vlines(i, values.min(), min(values.max(), y_top), color="#3a3a3a", lw=1.2)
        ax.vlines(i, q1, q3, color="#3a3a3a", lw=7)
        ax.plot(i, med, marker="o", ms=4, color="white", zorder=6)
        if values.max() > y_top:
            ax.text(i, y_top - 0.008, f"max {values.max():.2f}", ha="center", va="top",
                    fontsize=8, style="italic", color="#444444")

    ax.axhline(1.00, color="black", lw=1.4, label="Liquidation (1.00)")
    ax.axhline(1.05, color="red", ls="--", lw=1.2, label="Stress threshold (1.05)")
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0.99, y_top)
    ax.set_xlabel("Looper (Protocol / Collateral-Borrow)")
    ax.set_ylabel("Health Factor")
    ax.set_title("Distribution of Health Factor on Active-Borrowing Days")
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    save(fig, UNSUPERVISED / "health_factor_violin_plot.png")


def ltv_histories(daily: pd.DataFrame) -> None:
    for looper in ["L-3", "L-11", "L-12"]:
        rows = daily[daily["looper_id"] == looper].sort_values("date")
        plot = rows[rows["ltv"].notna() & (rows["borrow_balance_usd"].fillna(0) >= 1)]

        low, high = float(plot["ltv"].min()), float(plot["ltv"].max())
        pad = max(0.005, (high - low) * 0.15)
        ymin, ymax = max(0.0, low - pad), min(1.0, high + pad)
        if ymax - ymin < 0.02:
            mid = (ymin + ymax) / 2
            ymin, ymax = max(0.0, mid - 0.01), min(1.0, mid + 0.01)

        lltv = None
        if plot["liquidation_threshold"].notna().any():
            lltv = float(plot["liquidation_threshold"].dropna().iloc[0])
            ymax = max(ymax, min(1.0, lltv + 0.005))

        fig, ax = plt.subplots(figsize=(9, 3.8))
        ax.plot(plot["date"], plot["ltv"], color="#4C72B0", linewidth=1.4)
        if lltv is not None:
            ax.axhline(lltv, color="#C44E52", linestyle="--", linewidth=1.0,
                       label=f"LLTV {lltv:.3f}")
            ax.legend(frameon=False, loc="best")
        ax.set_ylim(ymin, ymax)
        ax.set_ylabel("LTV")
        ax.set_xlabel("Date")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate(rotation=0, ha="center")

        market = f"{plot['collateral_token'].iloc[0]} / {plot['borrow_token'].iloc[0]}"
        caption = f"{looper} · {plot['protocol'].iloc[0]} · {market} (open-debt days)"
        fig.text(0.01, 0.02, caption, fontsize=9, color="#555555", transform=fig.transFigure)
        fig.tight_layout(rect=[0, 0.06, 1, 1])
        save(fig, UNSUPERVISED / f"ltv_history_{looper}.png")


def pca_baseline_pair() -> None:
    panel = load(CLUSTER_READY, parse_dates=["date"])
    features = panel[CLUSTER_FEATURES].fillna(panel[CLUSTER_FEATURES].median())
    scaled = StandardScaler().fit_transform(features)

    panel["cluster"] = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5).fit_predict(scaled)
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(scaled)
    panel["x"], panel["y"] = coords[:, 0], coords[:, 1]
    var = pca.explained_variance_ratio_ * 100

    clusters = sorted(c for c in panel["cluster"].unique() if c >= 0)
    cluster_colours = plt.get_cmap("tab20")(np.linspace(0, 1, 20))
    loopers = looper_order(panel["looper_id"])
    looper_colours = plt.get_cmap("tab20")(np.linspace(0, 1, 20))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharex=True, sharey=True)

    noise = panel[panel["cluster"] == -1]
    axes[0].scatter(noise["x"], noise["y"], color="#cfcfcf", s=12, alpha=0.8)
    for i, cluster in enumerate(clusters):
        rows = panel[panel["cluster"] == cluster]
        axes[0].scatter(rows["x"], rows["y"], color=cluster_colours[i % 20], s=12, alpha=0.9)
    axes[0].set_title("(a) by HDBSCAN cluster (grey = noise)", fontsize=10, loc="left")
    print(f"    baseline fit: {len(clusters)} clusters, "
          f"{(panel['cluster'] == -1).mean():.1%} noise")

    for i, looper in enumerate(loopers):
        rows = panel[panel["looper_id"] == looper]
        axes[1].scatter(rows["x"], rows["y"], color=looper_colours[i % 20], s=12,
                        alpha=0.9, label=looper)
    axes[1].set_title("(b) by looper", fontsize=10, loc="left")

    for ax in axes:
        ax.set_xlabel(f"PC1 ({var[0]:.1f}% variance)")
    axes[0].set_ylabel(f"PC2 ({var[1]:.1f}% variance)")

    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, title="Looper", loc="lower center", ncol=12,
               fontsize=8, title_fontsize=9, frameon=True, bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    save(fig, UNSUPERVISED / "pca-baseline-pair.png")


def archetype_mix(arch: pd.DataFrame) -> None:
    order = ["max leverage hold", "active looping", "stale, low leverage", "outlier days"]
    colours = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]

    share = (
        pd.crosstab(arch["looper_id"], arch["cluster_name"], normalize="index") * 100
    ).reindex(columns=order, fill_value=0.0)
    share = share.reindex(looper_order(share.index))

    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = np.zeros(len(share))
    for name, colour in zip(order, colours):
        ax.bar(share.index, share[name], bottom=bottom, label=name, color=colour)
        bottom += share[name].to_numpy()
    ax.set_xlabel("Looper")
    ax.set_ylabel("Percent of activity")
    ax.set_title("Archetype mix by looper", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 100)
    ax.legend(title="Archetype", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    save(fig, UNSUPERVISED / "archetype-mix-by-looper.png")


def stress_share(labelled: pd.DataFrame) -> None:
    share = labelled.groupby("looper_id")["stressed_state"].mean() * 100
    share = share.reindex(looper_order(share.index))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(share.index, share.to_numpy(), color="#C44E52")
    ax.set_xlabel("Looper")
    ax.set_ylabel("Stressed days (%)")
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    save(fig, SUPERVISED / "stress-share-by-looper.png")


def spans(dates: pd.Series) -> list:
    """Runs of consecutive calendar days as (start, end)."""
    out = []
    for d in dates.sort_values():
        if out and (d - out[-1][1]).days == 1:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


def archetype_timeline(arch: pd.DataFrame) -> None:
    loopers = looper_order(arch["looper_id"])

    with plt.rc_context({"figure.facecolor": "white", "axes.facecolor": "white",
                         "font.size": 10, "axes.grid": False}):
        fig, ax = plt.subplots(figsize=(11, 8))
        for i, lid in enumerate(loopers):
            g = arch[arch["looper_id"] == lid]
            for name, color in ARCHETYPE_COLORS.items():
                for start, end in spans(g.loc[g["cluster_name"] == name, "date"]):
                    ax.barh(y=i, width=(end - start) + pd.Timedelta(days=1),
                            left=start - pd.Timedelta(hours=12), height=0.72,
                            color=color, linewidth=0)

        ax.set_yticks(range(len(loopers)))
        ax.set_yticklabels(loopers)
        ax.invert_yaxis()
        ax.grid(axis="x", color="#dddddd", linewidth=0.6)
        ax.set_axisbelow(True)
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.legend(handles=[mpatches.Patch(color=c, label=n)
                           for n, c in ARCHETYPE_COLORS.items()],
                  loc="upper left", fontsize=9, framealpha=0.9)
        fig.tight_layout()
        save(fig, UNSUPERVISED / "archetype-timeline.png")


def mix_title(lid: str, mixes: pd.DataFrame) -> str:
    g = mixes[mixes["looper_id"] == lid]
    if g.empty:
        return lid
    pct = (100 * g["cluster_name"].value_counts(normalize=True)).round(1)
    parts = []
    for i, (name, p) in enumerate(pct.items()):
        label = f"{name} {p}%"
        if i == 0:
            label = r"$\bf{" + label.replace(" ", r"\ ").replace("%", r"\%").replace(",", ",\\!") + "}$"
        parts.append(label)
    return f"{lid}  |  " + "  ·  ".join(parts)


def rebalance_timeline(g: pd.DataFrame, lid: str, out_path: Path, mixes: pd.DataFrame) -> bool:
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

    with plt.rc_context({"figure.facecolor": "white", "axes.facecolor": "white",
                         "axes.edgecolor": "#333333", "axes.grid": True,
                         "grid.color": "#dddddd", "grid.linewidth": 0.6, "font.size": 11}):
        fig, ax = plt.subplots(figsize=(9, 3.8))
        ax.plot(plot["date"], plot["ltv"], color="#4C72B0", linewidth=1.4, zorder=2)

        for start, end in spans(g.loc[g["risk_rebalance"] == 1, "date"]):
            ax.axvspan(start - pd.Timedelta(hours=12), end + pd.Timedelta(hours=12),
                       color="#DD8452", alpha=0.25, zorder=1)

        marks = plot[plot["risk_rebalance"] == 1]
        ax.scatter(marks["date"], marks["ltv"], color="#DD8452", edgecolor="#8C3B0F",
                   s=28, zorder=3, label="risk-rebalance day")

        closes = g[(g["risk_rebalance"] == 1) & (g["ltv"].isna())]
        if not closes.empty:
            ax.scatter(closes["date"], [ymin + 0.04 * (ymax - ymin)] * len(closes),
                       marker="v", color="#55A868", edgecolor="#2E5C38", s=42, zorder=3,
                       label="position closed (full unwind)")

        if lltv is not None:
            ax.axhline(lltv, color="#C44E52", linewidth=1.2, linestyle="--",
                       label=f"LLTV {lltv:.3f}")

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
    print("wrote", out_path.name)
    return True


def main() -> None:
    daily = load(DAILY, parse_dates=["date"])
    labelled = load(LABELLED, parse_dates=["date"])
    arch = load(ARCHETYPES, parse_dates=["date"])

    health_factor_per_looper(daily)
    health_factor_violin(daily)
    ltv_histories(daily)
    pca_baseline_pair()
    archetype_mix(arch)
    stress_share(labelled)
    archetype_timeline(arch)

    for lid in ["L-16", "L-14", "L-1", "L-11"]:
        g = daily[daily["looper_id"] == lid].sort_values("date")
        rebalance_timeline(g, lid, UNSUPERVISED / f"ltv_rebalance_timeline_{lid}.png", arch)


if __name__ == "__main__":
    main()
