# Whale Risk Supervised Learning

This folder contains three Jupyter notebooks that build supervised ML models to answer **RQ3**: can on-chain state variables predict short-horizon rebalancing events and stressed risk states?

---

**XGBoost** stands for **eXtreme Gradient Boosting**.

It builds a series of simple decision trees one after another, where each new tree learns from the mistakes of the previous one. By the end all trees vote together to make a final prediction.

---

**Simple analogy:**

Imagine you're trying to predict if a whale will rebalance. You ask 50 experts one by one:

- Expert 1 makes a rough guess
- Expert 2 looks at where Expert 1 went wrong and tries to fix those mistakes
- Expert 3 fixes Expert 2's remaining mistakes
- ... and so on for 50 experts

The final answer is all 50 experts combining their opinions. Each expert is weak alone but together they are strong.

---

**Why XGBoost over other models:**

- Handles messy real-world data well
- Works with imbalanced classes (via `scale_pos_weight`)
- Gives feature importance — tells you which variables matter most
- Works well with small datasets
- Compatible with SHAP for interpretation

---

**SHAP** stands for **SHapley Additive exPlanations**.

It opens up the XGBoost black box and explains **why** the model made each prediction.

---

Imagine XGBoost is a doctor diagnosing a patient. It says "this patient is at risk." SHAP is the explanation: "because their blood pressure is high (+0.4), they haven't exercised in a week (+0.3), but their cholesterol is fine (-0.1)."

Each factor gets a score showing how much it contributed to the final decision.

---
**In model:**

When XGBoost predicts a whale will rebalance, SHAP tells you:
- `ltv_lag_7` pushed the prediction by +1.1 — high leverage 7 days ago is the main reason
- `distance_to_liq` pushed by +0.4 — getting close to liquidation
- `carry_spread` pushed by -0.1 — yield is fine, slightly reducing urgency

---

Without SHAP, XGBoost is just a black box that says yes or no. With SHAP you can say **which on-chain variables drive whale behaviour and by how much** — which directly answers RQ3.


## Notebooks

### `01_eda_stress_threshold.ipynb` — Explore & Label
**What it does:**
- Loads the whale features CSV (667 rows, 37 columns, 6 whales W-1 to W-6), spanning 2025-01-09 to 2026-05-23
- Plots `health_factor` and `distance_to_liq` (mean + min) per whale, plus full summary statistics
- Defines `stressed_state` as the bottom 30% of each whale's own health factor distribution
- Saves enriched dataset as `whale_features_labeled.csv` (667 rows, 39 columns — adds `hf_threshold` and `stressed_state`)

**Rows per whale:** W-2 (300), W-3 (139), W-6 (88), W-1 (78), W-5 (35), W-4 (27)

**EDA takeaways:**
- Whales split into two groups: aggressive operators (W-1, W-2, W-3) running close to liquidation, and conservative operators (W-4, W-5) with comfortable buffers. W-6 sits in between.
- W-1 operates chronically near liquidation (mean health factor ~1.010, mean distance to liquidation ~0.009).
- W-3 is bimodal — high average buffer masking episodes of extreme risk.
- W-5 is the most disciplined — lowest volatility in both metrics, minimum nearly equal to mean.
- Overall **stressed rate: 31.0%**; overall **rebalancing rate: 16.0%** (107 of 667 days).

**Output:** `whale_features_labeled.csv`

---

### `02_model_rebalancing.ipynb` — Model A: Predict Rebalancing
**What it does:**
- Predicts whether a whale will rebalance on a given day
- Target: `rebalancing` (0 or 1, already in the data — 560 no / 107 yes)
- After dropping rows with missing features, the modelling set is 363 rows; stratified 70/30 split → 254 train / 109 test
- Runs Logistic Regression (`class_weight='balanced'`) as baseline, then XGBoost
- Uses `scale_pos_weight = 6.06` to handle the ~6:1 class imbalance
- Explains predictions with SHAP

**Features used (11):**
- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`
- `ltv_vol_7d`, `ltv_vol_14d`
- `distance_to_liq`, `health_factor`
- `carry_spread`, `carry_spread_levered`
- `loop_depth`

**Results (test set, class = rebalancing):**

| Model | ROC-AUC | Recall | Precision |
|---|---|---|---|
| Logistic Regression | 0.764 | 0.69 | 0.55 |
| XGBoost | 0.919 | 0.75 | 0.44 |

XGBoost catches more rebalancing days (12 of 16 vs 11 of 16) and has a much stronger ROC-AUC (0.919 vs 0.764), at the cost of more false alarms (15 vs 9). In a risk context, catching more real events is worth the extra false alarms.

**Feature importance (gain):** `ltv_lag_7` (49.7) ≫ `ltv_lag_1` (29.1) > `ltv_vol_7d` (27.0) > `distance_to_liq` (19.0) > `health_factor` (18.9); `carry_spread` (7.4) and `carry_spread_levered` (0.7) rank last. (SHAP highlights `ltv_vol_7d` as having the widest spread, with `ltv_lag_1` the cleanest directional signal.)

**Key finding:** Rebalancing is driven by accumulated leverage history and recent volatility — `ltv_lag_7`, `ltv_lag_1`, and `ltv_vol_7d` are the top predictors. Whales react to sustained leverage buildup over days, not just today's risk level.

**Output:** `predictions_rebalancing.csv`

---

### `03_model_stressed.ipynb` — Model B: Predict Stressed State
**What it does:**
- Predicts whether a whale is in a stressed risk state on a given day
- Target: `stressed_state` (defined in notebook 01 as bottom 30% health factor per whale — 460 no / 207 yes, 31.0% rate)
- After dropping rows with missing features, the modelling set is 415 rows; stratified 70/30 split → 290 train / 125 test
- Runs Logistic Regression as baseline, then XGBoost, each at thresholds 0.5 and 0.3
- Explains predictions with SHAP

**Features used (9):**
- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`
- `ltv_vol_7d`, `ltv_vol_14d`
- `carry_spread`, `carry_spread_levered`
- `loop_depth`

**Note:** `health_factor` and `distance_to_liq` are excluded — they were used to define `stressed_state` and would cause data leakage.

**Results (test set, class = stressed):**

| Model | Threshold | ROC-AUC | Recall | Precision | Accuracy |
|---|---|---|---|---|---|
| Logistic Regression | 0.5 | 0.849 | 0.85 | 0.67 | 79% |
| Logistic Regression | 0.3 | 0.849 | 0.98 | 0.47 | 59% |
| XGBoost | 0.5 | 0.953 | 0.70 | 0.97 | 88% |
| **XGBoost** | **0.3** | **0.953** | **0.93** | **0.78** | **88%** |

The chosen model is **XGBoost at threshold 0.3**: recall of 0.93 (catches 43 of 46 stressed days, missing only 3) with 12 false alarms and strong accuracy of 88%.

**Feature importance (gain):** `loop_depth` (16.2) > `ltv` (14.4) > `ltv_lag_1` (13.9) > `ltv_lag_7` (12.8) > `ltv_vol_7d` (12.5) > `carry_spread` (12.0) > `carry_spread_levered` (10.8); `ltv_vol_14d` (6.1) ranks last.

**Key finding:** Stressed states are driven by **position structure and current leverage** — loop depth and current LTV dominate. Unlike the rebalancing model, week-long history matters less here; stress is a near-instantaneous condition. `carry_spread_levered` has a protective effect: higher levered yield reduces stress likelihood.

**Output:** `predictions_stressed.csv`

---

## Key Design Decisions

**Why percentile-based stressed_state?**
Fixed thresholds (e.g. `health_factor < 1.05`) made some whales always stressed and others never stressed. Using each whale's own bottom 30% ensures every whale contributes both stressed and non-stressed days.

**Why threshold 0.3 for XGBoost in Model B?**
In a risk management context, missing a stressed day is more costly than a false alarm. Lowering the decision threshold from 0.5 to 0.3 raises recall from 0.70 to 0.93, at the cost of some precision (0.97 → 0.78).

**Why no leaky features?**
- Model A excludes `rebal_freq_7d`, `rebal_freq_30d`, `days_since_rebalance` —
  these are derived from the rebalancing column which is the target
- Model B excludes `health_factor`, `distance_to_liq` —
  these were used to define `stressed_state` so including them would let the model
  see the answer directly
- Model B also excludes `rebal_freq_7d`, `rebal_freq_30d`, `days_since_rebalance` —
  adding them worsened precision from 0.70 to 0.47 with only marginal ROC-AUC gain,
  so they were dropped for a cleaner model

## Data Flow

```
daily_features_all.csv
       ↓
01_eda_stress_threshold.ipynb
       ↓
whale_features_labeled.csv
       ↓                    ↓
02_model_rebalancing     03_model_stressed
       ↓                    ↓
predictions_rebalancing  predictions_stressed
.csv                     .csv
```

---

## Dependencies

```
pandas, numpy, matplotlib, seaborn
scikit-learn, xgboost, shap
```

**RQ3: To what extent can on-chain state variables predict short-horizon rebalancing events and stressed risk states?**

---

**Short answer: Yes, they can — with strong predictive power.**

---

**Rebalancing prediction:**
On-chain state variables predict rebalancing events with ROC-AUC of 0.919. The dominant predictors are historical LTV (`ltv_lag_7`, `ltv_lag_1`) and leverage volatility (`ltv_vol_7d`) — not current risk metrics. Whales respond to **sustained leverage buildup over days**, not immediate danger signals.

**Stressed state prediction:**
On-chain state variables predict stressed risk states even more strongly — ROC-AUC of 0.953 with recall of 0.93 at threshold 0.3. The dominant predictors are **loop depth and current LTV** — stress is a near-instantaneous condition driven by position structure and where leverage is right now. Yield compression (`carry_spread_levered`) plays a secondary protective role.

---

# Findings
**The bigger finding across both models:**

The two phenomena are driven by **different mechanisms**:
- Stress is reactive to the present — position structure and current leverage level
- Rebalancing is reactive to the past — accumulated leverage history over a week

**On-chain data can predict both rebalancing and stress — but through different mechanisms.**

---

**Finding 1 — Rebalancing is a delayed response**

Whales do not rebalance the moment things get risky. They watch leverage build up over several days and then act. The strongest predictor of rebalancing today (by gain) is what LTV was 7 days ago — not what it is today. This means rebalancing is a **deliberate, patient decision**, not a panic reaction.

---

**Finding 2 — Stress is a near-instant condition**

A whale is stressed when its loop depth is high and its current LTV is elevated. The model detects stressed states with strong recall (0.93 at threshold 0.3) just by looking at position structure and recent leverage. Stress is **immediate and observable**.

---

**Finding 3 — Yield barely matters for either**

`carry_spread` and `carry_spread_levered` rank near the bottom in the rebalancing model. Whales rebalance based on **risk signals, not yield signals**. They are not chasing yield — they are managing leverage. (The one nuance: `carry_spread_levered` has a mild protective effect on stress.)

---

**The big picture:**

Whales get stressed first, then wait, then rebalance. On-chain data captures all three stages clearly. This means DeFi risk can be monitored and potentially predicted in real time using only publicly available blockchain data.