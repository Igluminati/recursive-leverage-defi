# Whale Strategy Archetypes (Unsupervised)

This folder contains three Jupyter notebooks that cluster whale-day behaviour to answer **RQ1** and **RQ2**:

- **RQ1:** What recurring leverage and looping strategy archetypes exist among large YBT holders?
- **RQ2:** Which risk-management characteristics (leverage depth, collateral buffers, rebalancing behaviour) differentiate these archetypes?

---

## Notebooks

### `01_eda_panel.ipynb` — Explore & Prepare Panel
**What it does:**
- Loads `daily_features_all.csv` (712 rows, 7 whales)
- Filters to active looping days (`ltv`, `carry_spread`, `carry_spread_levered` present) → **457 rows**
- Selects 11 clustering features, median imputes, StandardScaler
- Saves cluster-ready panel

**Features used:**
- `ltv`, `loop_depth`, `distance_to_liq`
- `ltv_vol_7d`, `ltv_vol_14d`
- `rebal_freq_7d`, `rebal_freq_30d`, `days_since_rebalance`
- `ltv_lag_7`, `carry_spread`, `carry_spread_levered`

**Output:** `panel_cluster_ready.csv`

---

### `02_hdbscan_clustering.ipynb` — Baseline HDBSCAN
**What it does:**
- Runs HDBSCAN on the full 457-day panel (`min_cluster_size=15`, `min_samples=5`)
- PCA visualization of whale-days
- Explores cluster profiles and whale-specific subclusters

**Results:**
- 8 clusters + ~29% noise
- Many clusters are whale-specific (single-whale dominance)
- PC1 ≈ leverage depth; PC2 ≈ rebalancing / carry

**Key finding:** Unbalanced day counts per whale drive cluster structure. Baseline clustering reflects *who* has more days as much as *how* they behave.

**Output:** exploratory plots and cluster tables (no production labels)

---

### `03_balanced_clustering.ipynb` — Balanced HDBSCAN & Archetypes
**What it does:**
- Excludes W-7 from fit; samples **26 days × 6 whales = 156** fit rows (`random_state=42`)
- Parameter sweep: `min_cluster_size` 10/12 → 3 clusters; 15 → 2 (too coarse)
- Fits HDBSCAN with **`min_cluster_size=12`**, `min_samples=5` → 3 centroids
- Assigns all 457 days to nearest centroid; flags outliers above 95th percentile distance
- Maps cluster IDs to archetype names; PCA by archetype; whale membership %
- Saves labelled panel

**Archetypes (457 days assigned):**

| Archetype | Days | % | Mean LTV | Mean loop | Mean days since rebalance | Mean carry (levered) |
|---|---|---|---|---|---|---|
| high-LTV hold | 235 | 51% | 0.91 | 13.0 | 17 | 35.5 |
| moderate leverage | 122 | 27% | 0.62 | 4.3 | 7 | 12.4 |
| extreme leverage | 77 | 17% | 0.94 | 15.7 | 58 | 72.1 |
| idle / outlier | 23 | 5% | 0.04 | 1.1 | 1 | 7.5 |

**Whale membership (% of each whale's days):**

| Whale | extreme | high-LTV hold | idle / outlier | moderate |
|---|---|---|---|---|
| W-1 | 1.3 | 98.7 | 0.0 | 0.0 |
| W-2 | 85.2 | 6.8 | 8.0 | 0.0 |
| W-3 | 0.7 | 48.2 | 11.5 | 39.6 |
| W-4 | 0.0 | 0.0 | 0.0 | 100.0 |
| W-5 | 0.0 | 0.0 | 0.0 | 100.0 |
| W-6 | 0.0 | 92.0 | 0.0 | 8.0 |
| W-7 | 0.0 | 100.0 | 0.0 | 0.0 |

**Key finding:** Three behavioural modes separate on leverage, loop depth, rebalancing cadence, and carry — not on whale identity alone after balancing. Whales are **not** one fixed type: W-3 is mixed across archetypes; W-4/W-5 are pure moderate loopers; W-2 is mostly extreme leverage.

**Output:** `panel_archetypes.csv`

---

## Key Design Decisions

**Why cluster whale-days, not whales?**
A whale can switch modes over time. Clustering days captures recurring *behaviours*; membership % builds per-whale profiles (e.g. W-3: 40% moderate, 48% high-LTV hold).

**Why balance before HDBSCAN?**
W-2 contributes far more days than W-4/W-5. Without balancing, clusters collapse into whale-specific groups rather than shared strategy archetypes.

**Why nearest-centroid assign for all 457 days?**
HDBSCAN is fit on the balanced 156-row sample for stable centroids. All panel days are assigned by distance so W-7 and held-out whale-days still get labels.

**Why 3 archetypes + idle/outlier?**
`min_cluster_size=12` gives three dense strategy groups on the balanced fit. Distant days (low LTV, centroid outliers) are labelled idle / outlier separately.

**PCA interpretation caveat**
Archetype colours on PCA can mislead: extreme leverage sits centre-right *below* the midline (mostly W-2); the upper-right band is high-LTV hold (mostly W-3). Moderate leverage spans two patches (W-4/W-5 core vs W-3 lower-LTV days). Export PCA centroids and whale breakdowns before writing plot notes.

---

## Data Flow

```
daily_features_all.csv
       ↓
01_eda_panel.ipynb
       ↓
panel_cluster_ready.csv
       ↓
02_hdbscan_clustering.ipynb  (baseline / exploratory)
       ↓
03_balanced_clustering.ipynb
       ↓
panel_archetypes.csv
```

---

## Dependencies

```
pandas, numpy, matplotlib, seaborn
scikit-learn, hdbscan
```

---

**RQ1: What recurring leverage and looping strategy archetypes exist among large YBT holders?**

---

**Short answer: Three main looping archetypes plus idle/outlier days.**

1. **Moderate leverage** — ~60% LTV, shallow loop (~4×), more buffer (`distance_to_liq`), moderate carry
2. **High-LTV hold** — ~90% LTV, deep loop (~13×), active hold with more frequent rebalancing than extreme
3. **Extreme leverage** — ~94% LTV, deepest loop (~16×), stale rebalance (~58 days), highest levered carry
4. **Idle / outlier** — near-zero LTV or far from centroids (unwound / transitional days)

Whales reuse these modes in different proportions. No whale is locked to a single archetype except W-4, W-5 (100% moderate) and W-7 (100% high-LTV hold, 6 days only).

---

**RQ2: Which risk-management characteristics differentiate these archetypes?**

---

**Short answer: Leverage level, loop depth, rebalancing cadence, and carry — in that order.**

| Archetype | LTV | Loop depth | Rebalancing | Carry (levered) | Risk posture |
|---|---|---|---|---|---|
| moderate leverage | lower | shallow | moderate | low | conservative loop, more buffer |
| high-LTV hold | high | deep | more active | medium | aggressive but maintained |
| extreme leverage | max | deepest | stale | max | max carry, little rebalancing |
| idle / outlier | ~0 | minimal | n/a | low | not looping |

Extreme vs high-LTV hold share similar LTV and loop depth but diverge on **days since rebalance** and **carry_spread_levered** — extreme is stale, high-yield hold; high-LTV hold rebalances more often.

---

# Findings

**Finding 1 — Three recurring strategy modes, not seven whale types**

After balancing, whale-days collapse into three dense behavioural clusters. Archetypes describe *how* whales loop, not *which wallet* they are.

---

**Finding 2 — Whales are mixed strategists**

W-3 spreads across moderate, high-LTV hold, and idle. W-2 is mostly extreme. W-4/W-5 are pure moderate loopers. Strategy is **mode-switching over time**, not fixed whale taxonomy.

---

**Finding 3 — Extreme vs high-LTV hold is a rebalancing/carry split, not an LTV split**

Both sit at ~90%+ LTV and deep loops. Extreme leverage means **long time since rebalance + highest levered carry**; high-LTV hold means **shorter rebalance horizon + lower carry**. Same leverage tier, different maintenance behaviour.

---

**Finding 4 — Cluster labels need membership % to interpret**

Moderate leverage is visually split on PCA (W-4/W-5 core vs W-3 partial-unwind days). Single outlier days can sit far from their archetype centroid. Always cross-check **whale composition** and **within-cluster feature means**, not plot colour alone.

---

## Next Steps

- Join `stressed_state` from supervised pipeline (`whale_features_labeled.csv`) → stressed % by archetype and within moderate sub-groups
- Split moderate leverage post-hoc (e.g. LTV &lt; 0.6 vs ≥ 0.6) to separate W-3 light-leverage days from W-4/W-5 conservative loopers
- Optional: relabel or sub-cluster W-3 transitional days currently split across moderate, high-LTV hold, and idle
- Paper: pair RQ1/RQ2 archetype table with RQ3 supervised models (rebalancing vs stress mechanisms)
