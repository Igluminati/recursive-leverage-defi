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

| Archetype | Days | % | Mean LTV | Leverage | Dist. to liq. | Risk-rebal/wk | Risk-rebal/30d | Touches/wk | Carry spread levered |
|-----------|------|---|----------|----------|---------------|------------|-------------|------------|----------------------|
| stale, low leverage | 1148 | 55 | 0.54 | 4.07 | 0.36 | 0.01 | 0.65 | 0.45 | 2.70 |
| active looping | 512 | 25 | 0.78 | 8.07 | 0.14 | 1.38 | 3.17 | 2.05 | 11.37 |
| max leverage hold | 305 | 15 | 0.94 | 18.80 | 0.02 | 0.12 | 1.12 | 1.12 | 8.12 |
| outlier days | 104 | 5 | 0.23 | 1.64 | 0.70 | 1.82 | 5.31 | 2.33 | -5.69 |

**How to read the cadence columns:** *Risk-rebal/wk* and *Risk-rebal/30d* are the means of `risk_rebal_freq_7d` and `risk_rebal_freq_30d`, rolling counts of days on which the whale actually changed its leverage. *Touches/wk* is `activity_freq_7d`, the broader count of any supply/withdraw/borrow/repay day. Every archetype touches its position more often than it risk-rebalances, and the gap is what the old single flag hid: `max leverage hold` looks moderately busy at 1.1 touches per week but risk-rebalances only 0.1 times per week.

Mean `days_since_risk_rebalance` is deliberately **not** in the table. It is a poor summary of cadence: the feature is 0 on the days it counts, so it is dragged down for active groups (22% of active-looping days are zeros), and it is dragged up by rare dormant days. For outlier days the mean is 9.25 against a median of 3.0, since 19 of its 104 days exceed two weeks.

**RQ2 differentiation:** leverage level first, then risk-rebalance cadence (`risk_rebal_freq_7d`, `risk_rebal_freq_30d`).

### Pure vs mixed strategists

| Type | Count | Examples |
|------|-------|----------|
| **pure** | 12 | W-2 (90%), W-12 (100%) in max leverage hold; W-7 (88%), W-9 (91%), W-15 (100%), W-19 (100%), W-21 (100%), W-22 (100%) in active looping; W-10 (87%), W-11 (80%), W-18 (93%), W-23 (91%) in stale, low leverage |
| **mixed** | 11 | W-3 (47% stale, low leverage, spread across all four types); W-13 (spread across all four types); also W-1, W-4, W-5, W-6, W-8, W-14, W-16, W-17, W-20 |

## Key findings
1. **Four behaviour modes, not 23 whale types.** The archetypes describe how whales loop, after balancing for how many days each whale appears in the data.
2. **About half the whales are mixed strategists.** 12 of 23 are pure, meaning at least 80% of their days fall in one archetype. 11 of 23 are mixed. W-3 is a good example of a mixed whale, since it spreads across all four archetypes.
3. **The max leverage hold cluster does not split.** Every one of its 305 days sits between LTV 0.92 and 0.96, so the `moderate_sub` split at 0.75 labels all of them `moderate_core` and no day is `moderate_light`. Under continuous leverage this archetype is a tight, uniformly extreme group rather than one with a light tail.
4. **Aave whales cluster with the more aggressive Morpho whales.** W-17 through W-23 split between active looping and stale, low leverage days only.
5. **Half of what looked like rebalancing was not.** Whales touch their positions on 14.8% of whale-days but risk-rebalance on only 7.2%; the remainder is capital arriving or leaving (2.0%) and dust (5.6%). The gap is widest for the whales that looked busiest: W-3 is active on 47.5% of its days and risk-rebalances on 3.6%, and W-11 on 15.8% against 3.5%. No whale is purely a capital mover, so the strong form of that hypothesis does not hold, but the whales that manage risk (W-14, W-15, W-16 at a fifth to a half of their days) are clearly separable from those that park a position and occasionally move money. See notebook 03 for the per-whale table and the 1% / 2% / 5% threshold sensitivity.