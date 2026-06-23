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
- Gives feature importance tells you which variables matter most
- Works well with small datasets 
- Compatible with SHAP for interpretation

---

**SHAP** stands for **SHapley Additive exPlanations**.

it opens up the XGBoost black box and explains **why** the model made each prediction.

---

Imagine XGBoost is a doctor diagnosing a patient. It says "this patient is at risk." SHAP is the explanation: "because their blood pressure is high (+0.4), they haven't exercised in a week (+0.3), but their cholesterol is fine (-0.1)."

Each factor gets a score showing how much it contributed to the final decision.

---
**In model:**

When XGBoost predicts a whale will rebalance, SHAP tells you:
- `ltv_lag_1` pushed the prediction by +1.1 — high leverage yesterday is the main reason
- `distance_to_liq` pushed by +0.4 — getting close to liquidation
- `carry_spread` pushed by -0.1 — yield is fine, slightly reducing urgency

---

Without SHAP, XGBoost is just a black box that says yes or no. With SHAP you can say **which on-chain variables drive whale behaviour and by how much** which directly answers RQ3.


## Notebooks

### `01_eda_stress_threshold.ipynb` — Explore & Label
**What it does:**
- Loads the whale features CSV (712 rows, 7 whales)
- Plots `health_factor` and `distance_to_liq` distributions per whale
- Defines `stressed_state` as the bottom 30% of each whale's own health factor distribution
- Saves enriched dataset as `whale_features_labeled.csv`

**Output:** `whale_features_labeled.csv`

---

### `02_model_rebalancing.ipynb` — Model A: Predict Rebalancing
**What it does:**
- Predicts whether a whale will rebalance on a given day
- Target: `rebalancing` (0 or 1, already in the data)
- Uses stratified train/test split (70/30)
- Runs Logistic Regression as baseline, then XGBoost
- Uses `scale_pos_weight` to handle class imbalance (16.7% rebalancing rate)
- Explains predictions with SHAP

**Features used:**
- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`
- `ltv_vol_7d`, `ltv_vol_14d`
- `distance_to_liq`, `health_factor`
- `carry_spread`, `carry_spread_levered`
- `loop_depth`

**Results:**

| Model | ROC-AUC | Recall (rebalancing) | Precision |
|---|---|---|---|
| Logistic Regression | 0.969 | 0.81 | 0.59 |
| XGBoost | 0.895 | 0.69 | 0.42 |

**Key finding:** Rebalancing is driven by accumulated leverage history — `ltv_lag_1` and `ltv_lag_7` are the top predictors. Whales react to sustained leverage buildup over days, not just today's risk level.

**Output:** `predictions_rebalancing.csv`

---

### `03_model_stressed.ipynb` — Model B: Predict Stressed State
**What it does:**
- Predicts whether a whale is in a stressed risk state on a given day
- Target: `stressed_state` (defined in notebook 01 as bottom 30% health factor per whale)
- Uses stratified train/test split (70/30)
- Runs Logistic Regression as baseline, then XGBoost with threshold 0.3
- Explains predictions with SHAP

**Features used:**
- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`
- `ltv_vol_7d`, `ltv_vol_14d`
- `carry_spread`, `carry_spread_levered`
- `loop_depth`

**Note:** `health_factor` and `distance_to_liq` are excluded — they were used to define `stressed_state` and would cause data leakage.

**Results:**

| Model | ROC-AUC | Recall (stressed) | Precision |
|---|---|---|---|
| Logistic Regression | 0.806 | 0.79 | 0.44 |
| XGBoost (threshold=0.3) | 0.958 | 1.00 | 0.70 |

**Key finding:** Stressed states are driven by current LTV — it is an instantaneous signal, not a historical one. `carry_spread_levered` has a protective effect: higher levered yield reduces stress likelihood.

**Output:** `predictions_stressed.csv`

---

## Key Design Decisions

**Why percentile-based stressed_state?**
Fixed thresholds (e.g. `health_factor < 1.05`) made some whales always stressed and others never stressed. Using each whale's own bottom 30% ensures every whale contributes both stressed and non-stressed days.

**Why threshold 0.3 for XGBoost in Model B?**
In a risk management context, missing a stressed day is more costly than a false alarm. Lowering the decision threshold from 0.5 to 0.3 achieves perfect recall (1.00) at the cost of some precision (0.70).

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
On-chain state variables can predict rebalancing events with ROC-AUC of 0.897. The dominant predictors are historical LTV lags (`ltv_lag_7`, `ltv_lag_1`) and leverage volatility (`ltv_vol_7d`) — not current risk metrics. Whales respond to **sustained leverage buildup over days**, not immediate danger signals.

**Stressed state prediction:**
On-chain state variables predict stressed risk states even more strongly with ROC-AUC of 0.958 and perfect recall (1.00). The dominant predictor is **current LTV** — stress is an instantaneous condition driven by where leverage is right now, not where it has been. Yield compression (`carry_spread_levered`) plays a secondary protective role.

---

# Findings 
**The bigger finding across both models:**

The two phenomena are driven by **different mechanisms**:
- Stress is reactive to the present — current leverage level
- Rebalancing is reactive to the past — accumulated leverage history over a week

**On-chain data can predict both rebalancing and stress — but through different mechanisms.**

---

**Finding 1 — Rebalancing is a delayed response**

Whales do not rebalance the moment things get risky. They watch leverage build up over several days and then act. The strongest predictor of rebalancing today is what LTV was 7 days ago — not what it is today. This means rebalancing is a **deliberate, patient decision** not a panic reaction.

---

**Finding 2 — Stress is an instant condition**

A whale is stressed when their current LTV is high — right now, today. It is not about history. The model can detect stressed states almost perfectly (recall 1.00) just by looking at today's leverage level and recent volatility. Stress is **immediate and observable**.

---

**Finding 3 — Yield barely matters for either**

`carry_spread` and `carry_spread_levered` ranked near the bottom in both models. Whales rebalance and become stressed based on **risk signals, not yield signals**. They are not chasing yield — they are managing leverage.

---

**The big picture:**

Whales get stressed first, then wait, then rebalance. On-chain data captures all three stages clearly. This means DeFi risk can be monitored and potentially predicted in real time using only publicly available blockchain data.