# Whale Strategy Archetypes (Unsupervised)

HDBSCAN clustering on whale-day behaviour for **RQ1** and **RQ2**.

- **RQ1:** What recurring leverage/looping strategy archetypes exist among large YBT holders?
- **RQ2:** Which risk-management characteristics differentiate these archetypes?

**Sample:** all 24 whales (W-1–W-17 Morpho, W-18–W-24 Aave), 2,070 active looping days (from 2,507 whale-days in `daily_features_all.csv`).

---

## Notebooks (run in order)

| # | Notebook | Output |
|---|----------|--------|
| 1 | `01_eda_panel.ipynb` | `panel_cluster_ready.csv` |
| 2 | `02_hdbscan_clustering.ipynb` | baseline exploration |
| 3 | `03_balanced_clustering.ipynb` | `panel_archetypes.csv` |
| 4 | `04_stressed_by_archetype.ipynb` | `panel_archetypes_stressed.csv` |

```bash
cd analysis/whale-archetypes
uv sync
uv run jupyter lab
# or: uv run jupyter nbconvert --execute --inplace 0*.ipynb
```

---

## `01_eda_panel.ipynb`

- Loads `feature_engineering/data/daily_features_all.csv`, **all 24 whales** (Morpho + Aave)
- Keeps active looping days: non-missing `ltv`, `carry_spread`, `carry_spread_levered` → **2,070 rows**
- 11 clustering features, median impute, StandardScaler
- Saves `panel_cluster_ready.csv`

---

## `02_hdbscan_clustering.ipynb`

Baseline HDBSCAN on full panel (`min_cluster_size=15`, `min_samples=5`). Clusters are whale-dominated → motivates balanced fit in notebook 03.

---

## `03_balanced_clustering.ipynb`

- Fit pool: whales with ≥8 active days (21 of 24; excludes W-17=1, W-20=7, W-22=6 days)
- Balanced sample: **8 days × 21 whales = 168** fit rows (`random_state=42`)
- HDBSCAN: `min_cluster_size=8`, `min_samples=3` → 3 dense clusters
- All 2,070 days assigned to nearest centroid; >95th percentile distance → `idle / outlier`
- Profile-based names (not fixed cluster IDs)
- `strategist_type`: **pure** if ≥80% of days in one archetype, else **mixed**
- `moderate_sub`: splits moderate-leverage days into `moderate_light` (LTV < 0.6) vs `moderate_core` (LTV ≥ 0.6)

### Archetypes (2,070 days)

| Archetype | Days | % | Mean LTV | Loop depth | Dist. to liq. | Days since rebal. | Rebal/7d |
|-----------|------|---|----------|------------|---------------|-------------------|----------|
| moderate leverage | 868 | 42 | 0.67 | 6.3 | 0.24 | 3 | 2.0 |
| stale / light loop | 734 | 35 | 0.52 | 4.3 | 0.39 | 56 | 0.0 |
| high-LTV hold | 364 | 18 | 0.92 | 15.7 | 0.03 | 47 | 0.4 |
| idle / outlier | 104 | 5 | 0.31 | 3.3 | 0.63 | 4 | 2.5 |

**RQ2 differentiation:** leverage level and loop depth first; then rebalancing cadence (`days_since_rebalance`, `rebal_freq_7d`).

### Pure vs mixed strategists

| Type | Count | Examples |
|------|-------|----------|
| **pure** | 12 | W-2, W-12 (high-LTV hold); W-7, W-9, W-15, W-17, W-20, W-22, W-23, W-8 (moderate); W-19, W-24 (stale/light) |
| **mixed** | 12 | W-3 (71% moderate, spreads across all four); W-11 (mostly moderate/stale); W-10, W-13, W-14 |

---

## `04_stressed_by_archetype.ipynb`

Joins `stressed_state` from `../whale-risk-supervised/whale_features_labeled.csv` (HF ≤ 1.05, fixed threshold).

- All 2,070 archetype days match
- Overall stressed share on active looping days: **32.9%**
- Adds `stressed_abs` (same HF < 1.05 cut-off) for cross-archetype comparison

| Archetype | Days | Stressed % (HF ≤ 1.05) |
|-----------|------|------------------------|
| high-LTV hold | 364 | 77.7 |
| moderate leverage | 868 | 29.0 |
| stale / light loop | 734 | 17.7 |
| idle / outlier | 104 | 16.3 |

Risk grades with leverage intensity: high-LTV hold is the most stressed mode; idle / outlier and stale / light loop the least.

---

## Key findings

1. **Four behavioural modes**, not 24 whale types — archetypes describe *how* whales loop after balancing day counts.
2. **Half the whales are mixed strategists** — 12/24 are pure, 12/24 are mixed; W-3 switches between moderate, high-LTV, stale/light, and idle days.
3. **Moderate cluster splits in practice** — centroid reads “medium risk,” but day-level assignments scatter: within moderate, LTV < 0.6 days carry 0% stress vs 41% for LTV ≥ 0.6.
4. **Stress aligns with archetype severity** under a shared HF cut-off — independent check against supervised labels.
5. **Aave whales cluster with the aggressive Morpho whales** — W-18–W-24 all run high LTV (~0.79–0.89) and split mostly between moderate leverage and stale / light loop.

---

## Data flow

```
feature_engineering/data/daily_features_all.csv  (all 24 whales)
       ↓
01_eda_panel.ipynb  →  panel_cluster_ready.csv
       ↓
02_hdbscan_clustering.ipynb  (exploratory)
       ↓
03_balanced_clustering.ipynb  →  panel_archetypes.csv
       ↓
04_stressed_by_archetype.ipynb  →  panel_archetypes_stressed.csv
```

---

## Dependencies

```
pandas, numpy, matplotlib, seaborn, scikit-learn, hdbscan
```
