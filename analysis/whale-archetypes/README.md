# Whale Strategy Archetypes (Unsupervised)

HDBSCAN clustering on whale-day behaviour for **RQ1** and **RQ2**.

- **RQ1:** What recurring leverage/looping strategy archetypes exist among large YBT holders?
- **RQ2:** Which risk-management characteristics differentiate these archetypes?


---

## Notebooks (run in order)

| # | Notebook | Output |
|---|----------|--------|
| 1 | `01_eda_panel.ipynb` | `panel_cluster_ready.csv` |
| 2 | `02_hdbscan_clustering.ipynb` | baseline exploration |
| 3 | `03_balanced_clustering.ipynb` | `panel_archetypes.csv` |

```bash
cd analysis/whale-archetypes
uv sync
uv run jupyter lab
```

---

## `01_eda_panel.ipynb`

- Loads `feature_engineering/data/daily_features_all.csv`, **all 24 whales** (Morpho + Aave)
- Keeps active looping days: non-missing `ltv`, `carry_spread`, `carry_spread_levered`, giving **2,070 rows**
- 11 clustering features, median impute, StandardScaler
- Saves `panel_cluster_ready.csv`

---

## `02_hdbscan_clustering.ipynb`

Baseline HDBSCAN on full panel (`min_cluster_size=15`, `min_samples=5`). Clusters are whale-dominated, which motivates the balanced fit in notebook 03.

---

## `03_balanced_clustering.ipynb`

- Fit pool: whales with at least 6 active days 
- All 2,070 days assigned to nearest centroid; anything past the 95th percentile distance becomes `idle, outlier days`
- Archetypes are named based on their profile
- `strategist_type`: **pure** if at least 80% of days fall in one archetype, otherwise **mixed**
- `moderate_sub`: splits the max leverage hold days into `moderate_light`(LTV under 0.6) and `moderate_core` (LTV at or above 0.6)

### Archetypes (2,070 days)

| Archetype | Days | % | Mean LTV | Loop depth | Dist. to liq. | Days since rebal. | LTV lag 7 | Carry spread | Carry spread levered |
|-----------|------|---|----------|------------|---------------|-------------------|-----------|--------------|-----------------------|
| max leverage hold | 364 | 18 | 0.92 | 14.95 | 0.04 | 42.87 | 0.91 | 7.80 | 80.73 |
| active looping | 868 | 42 | 0.75 | 7.88 | 0.16 | 2.84 | 0.73 | 7.30 | 40.61 |
| stale, low leverage | 734 | 35 | 0.48 | 3.64 | 0.42 | 49.23 | 0.47 | 3.94 | 8.65 |

**RQ2 differentiation:** leverage level and loop depth first, then rebalancing cadence (`days_since_rebalance`, `rebal_freq_7d`).

### Pure vs mixed strategists

| Type | Count | Examples |
|------|-------|----------|
| **pure** | 11 | W-2 (90%), W-12 (100%) in max leverage hold; W-7 (97%), W-9 (83%), W-15 (100%), W-20 (100%), W-22 (100%), W-23 (100%) in active looping; W-17 (100%), W-19 (95%), W-24 (92%) in stale, low leverage |
| **mixed** | 13 | W-3 (64% active looping, spread across all four types); W-13 (spread across three types); also W-1, W-4, W-5, W-6, W-8, W-10, W-11, W-14, W-16, W-18, W-21 |

## Key findings
1. **Four behaviour modes, not 24 whale types.** The archetypes describe how whales loop, after balancing for how many days each whale appears in the data.
2. **About half the whales are mixed strategists.** 11 of 24 are pure, meaning at least 80% of their days fall in one archetype. 13 of 24 are mixed. W-3 is a good example of a mixed whale, since it spreads across active looping, max leverage hold, and stale, low leverage days.
3. **The max leverage hold cluster splits in practice.** Within this cluster, low LTV days (under 0.6) show different stress levels than high LTV days (0.6 or above). This is the split that the moderate_sub column captures.
5. **Aave whales cluster with the more aggressive Morpho whales.** W-18 through W-24 mostly split between active looping and stale, low leverage days.