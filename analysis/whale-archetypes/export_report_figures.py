"""Export LaTeX figures for the unsupervised archetype section."""
from pathlib import Path

import hdbscan
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FIG = REPO / "paper" / "overleaf_review" / "figures" / "unsupervised"
DATA = REPO / "feature_engineering" / "data" / "daily_features_all.csv"
LAB = ROOT.parent / "whale-risk-supervised" / "whale_features_labeled.csv"

FEATURES = [
    "ltv", "loop_depth", "distance_to_liq",
    "ltv_vol_7d", "ltv_vol_14d",
    "rebal_freq_7d", "rebal_freq_30d", "days_since_rebalance",
    "ltv_lag_7", "carry_spread", "carry_spread_levered",
]

sns.set_theme(style="whitegrid")
FIG.mkdir(parents=True, exist_ok=True)


def whale_sort_key(w):
    return int(w.split("-")[1])


def load_panel():
    df = pd.read_csv(DATA, parse_dates=["date"])
    panel = df.dropna(subset=["ltv", "carry_spread", "carry_spread_levered"]).copy()
    medians = panel[FEATURES].median()
    scaler = StandardScaler().fit(panel[FEATURES].fillna(medians))
    X = scaler.transform(panel[FEATURES].fillna(medians))
    return panel, medians, scaler, X


def export_mean_ltv(panel):
    order = sorted(panel["whale_id"].unique(), key=whale_sort_key)
    means = panel.groupby("whale_id")["ltv"].mean().reindex(order)
    fig, ax = plt.subplots(figsize=(10, 4))
    means.plot(kind="bar", ax=ax, color="#4a7ebB")
    ax.set_xlabel("Whale")
    ax.set_ylabel("Mean LTV")
    ax.set_title("Mean LTV per whale (active looping days)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(FIG / "mean-ltv-per-whale.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def export_baseline_pca(panel, X_scaled):
    labels = hdbscan.HDBSCAN(min_cluster_size=15, min_samples=5).fit_predict(X_scaled)
    panel = panel.copy()
    panel["cluster"] = labels
    pca = PCA(n_components=2, random_state=42).fit_transform(X_scaled)
    panel["x"], panel["y"] = pca[:, 0], pca[:, 1]
    fig, ax = plt.subplots(figsize=(9, 5))
    for c in sorted(panel["cluster"].unique()):
        s = panel[panel["cluster"] == c]
        ax.scatter(s["x"], s["y"], label=c, alpha=0.7, s=20)
    ax.legend(title="cluster", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xlabel("PCA-1")
    ax.set_ylabel("PCA-2")
    fig.subplots_adjust(right=0.82)
    fig.savefig(FIG / "pca-by-baseline-cluster.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for w in sorted(panel["whale_id"].unique(), key=whale_sort_key):
        s = panel[panel["whale_id"] == w]
        ax.scatter(s["x"], s["y"], label=w, alpha=0.7, s=20)
    ax.legend(title="whale_id", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7)
    ax.set_xlabel("PCA-1")
    ax.set_ylabel("PCA-2")
    fig.subplots_adjust(right=0.82)
    fig.savefig(FIG / "pca-by-whale.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def assign_archetypes(panel, medians, scaler):
    fit_pool = panel[panel.groupby("whale_id")["whale_id"].transform("count") >= 8]
    rng = np.random.default_rng(42)
    n_per = fit_pool.groupby("whale_id").size().min()
    idx = [i for _, g in fit_pool.groupby("whale_id") for i in rng.choice(g.index, n_per, replace=False)]
    X_bal = scaler.transform(panel.loc[idx, FEATURES].fillna(medians))
    labels_bal = hdbscan.HDBSCAN(min_cluster_size=8, min_samples=3).fit_predict(X_bal)

    centroids = {}
    for cid in sorted(set(labels_bal) - {-1}):
        centroids[cid] = X_bal[labels_bal == cid].mean(axis=0)
    X_all = scaler.transform(panel[FEATURES].fillna(medians))
    dists = np.column_stack([cdist(X_all, c.reshape(1, -1)).ravel() for c in centroids.values()])
    nearest = np.array(list(centroids.keys()))[dists.argmin(axis=1)]
    panel = panel.copy()
    panel["cluster_id"] = nearest
    panel["dist_to_centroid"] = dists.min(axis=1)
    thresh = np.percentile(panel["dist_to_centroid"], 95)
    panel.loc[panel["dist_to_centroid"] > thresh, "cluster_id"] = -1

    prof = panel[panel["cluster_id"] >= 0].groupby("cluster_id")[["ltv", "loop_depth", "days_since_rebalance"]].mean()
    remaining = list(prof.index)
    name_map = {}
    hi = prof["ltv"].idxmax()
    name_map[hi] = "high-LTV hold"
    remaining.remove(hi)
    mod = prof.loc[remaining, "days_since_rebalance"].idxmin()
    name_map[mod] = "moderate leverage"
    remaining.remove(mod)
    name_map[remaining[0]] = "stale / light loop"
    panel["cluster_name"] = panel["cluster_id"].map({**name_map, -1: "idle / outlier"})
    return panel, scaler.transform(panel[FEATURES].fillna(medians))


def export_archetype_pca(panel, X):
    pca = PCA(n_components=2, random_state=42).fit_transform(X)
    panel = panel.copy()
    panel["x"], panel["y"] = pca[:, 0], pca[:, 1]
    order = ["moderate leverage", "high-LTV hold", "stale / light loop", "idle / outlier"]
    colors = {
        "moderate leverage": "#4c9f70",
        "high-LTV hold": "#e1a948",
        "stale / light loop": "#c0392b",
        "idle / outlier": "#95a5a6",
    }
    fig, ax = plt.subplots(figsize=(7, 5))
    for name in order:
        s = panel[panel["cluster_name"] == name]
        if len(s):
            ax.scatter(s["x"], s["y"], label=name, alpha=0.7, s=20, c=colors.get(name, "#888"))
    ax.legend(title="archetype")
    ax.set_xlabel("PCA-1")
    ax.set_ylabel("PCA-2")
    plt.tight_layout()
    fig.savefig(FIG / "pca-by-archetype.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return panel


def export_stress(panel):
    lab = pd.read_csv(LAB, parse_dates=["date"])
    merged = panel.merge(lab[["whale_id", "date", "stressed_state", "health_factor"]], on=["whale_id", "date"], how="left")
    by_arch = (
        merged.groupby("cluster_name")["stressed_state"]
        .agg(days="size", stressed_pct="mean")
        .sort_values("stressed_pct", ascending=False)
    )
    colors = {
        "moderate leverage": "#4c9f70",
        "high-LTV hold": "#e1a948",
        "stale / light loop": "#c0392b",
        "idle / outlier": "#95a5a6",
    }
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(by_arch.index, by_arch["stressed_pct"] * 100,
                  color=[colors.get(a, "#888") for a in by_arch.index])
    overall = merged["stressed_state"].mean() * 100
    ax.axhline(overall, ls="--", c="k", lw=1, label=f"overall {overall:.1f}%")
    for b, pct, n in zip(bars, by_arch["stressed_pct"] * 100, by_arch["days"]):
        ax.text(b.get_x() + b.get_width() / 2, pct + 0.6, f"{pct:.1f}%\n(n={int(n)})",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("stressed days (%)")
    ax.set_title("Stressed share by archetype (per-whale label)")
    ax.set_ylim(0, max(by_arch["stressed_pct"] * 100) * 1.25)
    ax.legend()
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    fig.savefig(FIG / "stress-by-archetype.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    panel, medians, scaler, X = load_panel()
    X_scaled = X
    export_mean_ltv(panel)
    export_baseline_pca(panel, X_scaled)
    panel, X = assign_archetypes(panel, medians, scaler)
    export_archetype_pca(panel, X)
    export_stress(panel)
    print("Saved figures to", FIG)
    for name in [
        "mean-ltv-per-whale.png",
        "pca-by-baseline-cluster.png",
        "pca-by-whale.png",
        "pca-by-archetype.png",
        "stress-by-archetype.png",
    ]:
        print(" ", name, (FIG / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
