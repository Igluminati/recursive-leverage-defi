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
| 4 | `04_ltv_history_krzys.ipynb` | `output/whale_markets_ltv_summary.csv`, `output/ltv_history_W-*.png` |

```bash
cd analysis/whale-archetypes
uv sync
uv run jupyter lab
```

---

## Outputs (`output/`)

Committed figures and tables for review / paper reuse:

- `whale_markets_ltv_summary.csv` — per-whale protocol, market (`collateral / borrow`), and open-debt LTV distribution (min, quartiles, median, max, mean)
- `ltv_history_W-*.png` — zoomed historical LTV charts for a representative whale set (W-12, W-1, W-3, W-11, W-17, W-5), with LLTV reference line
- Unsupervised paper PNGs: `archetype-mix-by-whale.png`, `ltv-over-time.png`, `mean-ltv-per-whale.png`, `pca-baseline-pair.png`, `pca-by-archetype.png`, `pca-by-baseline-cluster.png`, `pca-by-whale.png`, `stale-vs-stress.png`, `stress-by-archetype.png`

---

## `01_eda_panel.ipynb`

- Loads `feature_engineering/data/daily_features_all.csv`, **all 23 whales** (Morpho + Aave)
- Keeps active looping days: non-missing `ltv`, `carry_spread`, `carry_spread_levered`, giving **2,069 rows**
- 11 clustering features, median impute, StandardScaler
- Saves `panel_cluster_ready.csv`

---

## `02_hdbscan_clustering.ipynb`

Baseline HDBSCAN on full panel (`min_cluster_size=15`, `min_samples=5`). Clusters are whale-dominated, which motivates the balanced fit in notebook 03.

---

## `03_balanced_clustering.ipynb`

- Fit pool: whales with at least 6 active days 
- All 2,069 days assigned to nearest centroid; anything past the 95th percentile distance becomes `outlier days`
- Archetypes are named based on their profile
- `strategist_type`: **pure** if at least 80% of days fall in one archetype, otherwise **mixed**
- `moderate_sub`: splits the max leverage hold days into `moderate_light` (LTV under 0.75) and `moderate_core` (LTV at or above 0.75)

### Archetypes (2,069 days)

| Archetype | Days | % | Mean LTV | Leverage | Dist. to liq. | Events/wk | Events/30d | Carry spread levered |
|-----------|------|---|----------|----------|---------------|-----------|------------|----------------------|
| stale, low leverage | 1032 | 50 | 0.52 | 3.97 | 0.37 | 0.19 | 1.97 | 5.25 |
| active looping | 688 | 33 | 0.76 | 8.54 | 0.15 | 2.39 | 7.10 | 6.36 |
| max leverage hold | 245 | 12 | 0.94 | 18.13 | 0.02 | 0.22 | 1.81 | 5.68 |
| outlier days | 104 | 5 | 0.29 | 2.90 | 0.65 | 2.49 | 7.48 | -3.58 |

**How to read the cadence columns:** *Events/wk* and *Events/30d* are the means of `rebal_freq_7d` and `rebal_freq_30d`, rolling counts of supply/withdraw/borrow/repay events in the prior 7 and 30 days. Active looping rebalances far more than the two stale modes (2.4 vs ~0.2 per week), and the outlier group is about as active (2.5).

Mean `days_since_rebalance` is deliberately **not** in the table. It is a poor summary of cadence: the feature is 0 on rebalance days, so it is dragged down for active groups (36% of active-looping days are zeros), and it is dragged up by rare dormant days. For outlier days the mean is 6.80 but the median is 1.0, since 6 of its 104 days exceed two weeks and two exceed 150 days.

**RQ2 differentiation:** leverage level first, then rebalancing cadence (`rebal_freq_7d`, `rebal_freq_30d`).

### Pure vs mixed strategists

| Type | Count | Examples |
|------|-------|----------|
| **pure** | 11 | W-2 (91%), W-12 (99%) in max leverage hold; W-7 (100%), W-9 (91%), W-15 (100%), W-19 (100%), W-21 (100%), W-22 (100%) in active looping; W-10 (94%), W-18 (86%), W-23 (90%) in stale, low leverage |
| **mixed** | 12 | W-3 (66% active looping, spread across all four types); W-13 (spread across all four types); also W-1, W-4, W-5, W-6, W-8, W-11, W-14, W-16, W-17, W-20 |

## Key findings
1. **Four behaviour modes, not 23 whale types.** The archetypes describe how whales loop, after balancing for how many days each whale appears in the data.
2. **About half the whales are mixed strategists.** 11 of 23 are pure, meaning at least 80% of their days fall in one archetype. 12 of 23 are mixed. W-3 is a good example of a mixed whale, since it spreads across all four archetypes.
3. **The max leverage hold cluster does not split.** Every one of its 245 days sits between LTV 0.93 and 0.96, so the `moderate_sub` split at 0.75 labels all of them `moderate_core` and no day is `moderate_light`. Under continuous leverage this archetype is a tight, uniformly extreme group rather than one with a light tail.
4. **Aave whales cluster with the more aggressive Morpho whales.** W-17 through W-23 split between active looping and stale, low leverage days only.