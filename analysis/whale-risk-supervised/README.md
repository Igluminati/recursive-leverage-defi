# Whale Risk Supervised Learning

This folder contains three Jupyter notebooks that build supervised ML models to answer **RQ3**: can on-chain state variables predict short-horizon rebalancing events and stressed risk states?

---

## What is XGBoost?

**XGBoost** stands for **eXtreme Gradient Boosting**. It is a machine learning model used for making predictions from data, commonly used for things like predicting whether something will happen or not.

It builds a series of simple decision trees, one after another. Each new tree learns from the mistakes of the tree before it. At the end, all the trees vote together to make a final prediction.

**Simple analogy:**

Imagine you are trying to predict if a whale will rebalance. You ask 50 experts one by one.

- Expert 1 makes a rough guess
- Expert 2 looks at where Expert 1 went wrong and tries to fix those mistakes
- Expert 3 fixes Expert 2's remaining mistakes
- And so on, for 50 experts

The final answer is all 50 experts combining their opinions. Each expert is weak alone, but together they are strong.

**Why XGBoost over other models:**

- Handles messy real world data well
- Works with imbalanced classes, using `scale_pos_weight`
- Gives feature importance, so it tells you which variables matter most
- Works well even with a moderate amount of data
- Works well together with SHAP for interpretation

---

## What is SHAP?

**SHAP** stands for **SHapley Additive exPlanations**. It opens up the XGBoost black box and explains why the model made each prediction.

Imagine XGBoost is a doctor diagnosing a patient. It says "this patient is at risk." SHAP is the explanation: "because their blood pressure is high, they have not exercised in a week, but their cholesterol is fine." Each factor gets a score showing how much it contributed to the final decision.

In our models, when XGBoost predicts a whale will rebalance, SHAP tells us which features pushed that decision, and by how much, for example whether recent leverage swings or leverage history mattered most for that specific day.

Without SHAP, XGBoost is just a black box that says yes or no. With SHAP, we can say which on-chain variables drive whale behavior and by how much, which directly answers RQ3.

---

## Notebooks

### `01_eda_stress_threshold.ipynb`, Explore and Label

**What it does:**

- Loads the whale features CSV: 2,507 rows, 24 whales (W-1 to W-24), spanning 2024-03-29 to 2026-06-27
- Plots `health_factor` and `distance_to_liq` (mean and min) per whale, sorted numerically (W-1 through W-24), plus full summary statistics
- Defines `stressed_state` using a fixed threshold: a whale is stressed on any day its health factor drops to 1.05 or below
- Saves the enriched dataset as `whale_features_labeled.csv`

**Rows per whale range widely**, from W-17 with just 1 row up to W-11 with 622 rows. Most whales fall between 20 and 250 rows.

**Why a fixed threshold instead of a percentile?**

An earlier version of this notebook used each whale's own worst 30% of days as the stress cutoff. This turned out to be misleading, because health factor has a fixed real world meaning (1.0 means liquidation), but the percentile method compared each whale only to itself. This made a whale that lives constantly near 1.0 (like W-1) look no riskier than a whale that is always safely above 1.4 (like W-4), since both would show roughly the same 30% stressed rate.

Switching to a single fixed threshold (1.05) fixes this. Now a whale is only marked stressed when it is actually close to liquidation, which is consistent and comparable across all whales.

**EDA takeaways:**

- Whales split into three broad patterns: a small group with high average safety buffers but occasional risky dips (W-11, W-16, W-3, W-13), a group of steady conservative operators (W-4, W-5, W-8, W-24), and a couple of whales that sit close to liquidation almost constantly (W-1, W-12).
- W-1 and W-12 are stressed on more than 95% of their days under the fixed threshold.
- Several whales, including W-4, W-5, W-8, W-11, W-16, W-17, W-19, W-23, and W-24, are never stressed under this threshold.
- Overall **stressed rate: 28.9%** (725 of 2,507 days). Overall **rebalancing rate: 14.8%** (371 of 2,507 days).

**Output:** `whale_features_labeled.csv`

---

### `02_model_rebalancing.ipynb`, Model A: Predict Rebalancing

**What it does:**

- Predicts whether a whale will rebalance on a given day
- Target: `rebalancing` (0 or 1, already in the data)
- After dropping rows with missing features, the modeling set is 1,475 rows. A stratified 70/30 split gives 1,032 training rows and 443 test rows.
- Runs Logistic Regression (`class_weight='balanced'`) as a baseline, then XGBoost
- Uses `scale_pos_weight = 5.83` to handle the class imbalance
- Explains predictions with feature importance and SHAP

**Features used (11):**

- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`
- `ltv_vol_7d`, `ltv_vol_14d`
- `distance_to_liq`, `health_factor`
- `carry_spread`, `carry_spread_levered`
- `loop_depth`

**Results (test set, class = rebalancing):**

| Model | ROC-AUC | Recall | Precision | Accuracy |
|---|---|---|---|---|
| Logistic Regression | 0.828 | 0.69 | 0.36 | 78% |
| XGBoost | 0.876 | 0.71 | 0.41 | 81% |

XGBoost improves on every measure. It catches slightly more rebalancing days (46 of 65 versus 45 of 65), makes fewer false alarms (65 versus 79), and has a stronger ROC-AUC. The improvement is modest but real and consistent across the board.

**Feature importance (gain):** `ltv_vol_7d` (65.2) and `ltv_lag_7` (61.5) are the top two, followed by `ltv` (45.3), `ltv_vol_14d` (38.7), `ltv_lag_1` (34.0), and `ltv_lag_3` (33.6). `carry_spread_levered` (19.5), `carry_spread` (9.8), and `health_factor` (6.9) rank lowest. `distance_to_liq` and `loop_depth` were not used by any tree in the model.

**Key finding:** Rebalancing is driven by leverage and how it has changed over the past 7 to 14 days, not by a single snapshot value or by yield. Whales appear to react to a build up of risk over time, rather than acting on any single day's numbers.

**Output:** `predictions_rebalancing.csv`

---

### `03_model_stressed.ipynb`, Model B: Predict Stressed State

**What it does:**

- Predicts whether a whale is in a stressed risk state on a given day, using the fixed threshold definition from notebook 01
- Target: `stressed_state` (1,782 not stressed, 725 stressed, 28.9% stressed rate)
- After dropping rows with missing features, the modeling set is 2,088 rows. A stratified 70/30 split gives 1,460 training rows and 628 test rows.
- Runs Logistic Regression as a baseline, then XGBoost, each at thresholds 0.5 and 0.3
- Explains predictions with feature importance and SHAP

**Features used (9):**

- `ltv_vol_7d`, `ltv_vol_14d`
- `carry_spread`, `carry_spread_levered`
- `ybt_apy`, `borrow_rate`, `supply_rate`
- `collateral_price`, `borrow_price`

**Why this feature list took a few rounds to get right:**

The first attempt included `ltv`, its lagged versions, `health_factor`, `distance_to_liq`, and `loop_depth`, and produced a ROC-AUC of 1.000, a clear sign of data leakage. Checking the raw values confirmed it: `ltv` above about 0.87 almost perfectly separated stressed from not stressed days, and `loop_depth` above 8 did the same. Both features were removed, since `health_factor` (which defines `stressed_state`) is built directly from `ltv`, and `loop_depth` turned out to be tied to the same underlying formula.

After removing those, a second, smaller leak was found. `collateral_balance` and `borrow_balance` let XGBoost reach a ROC-AUC of 0.993, a much bigger jump over Logistic Regression than normal. Trees can exploit hidden cutoffs in raw numbers more easily than a straight line model can, so a leak that Logistic Regression missed still showed up in XGBoost. Removing these two balance features brought XGBoost back down to a believable 0.977, close to Logistic Regression's 0.971, confirming the leak was gone.

**Features excluded and why:**

- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`, `health_factor`, `distance_to_liq`, `loop_depth`: too closely tied to how `stressed_state` was defined
- `collateral_balance_usd`, `borrow_balance_usd`, `liquidation_threshold`: `ltv` is built directly from these
- `collateral_balance`, `borrow_balance`: raw token amounts, but still let XGBoost find a near perfect shortcut, so they were dropped even though the leak here was smaller and less obvious
- `rebal_freq_7d`, `rebal_freq_30d`, `days_since_rebalance`: these belong to the rebalancing target, not this one, and added no real value here
- `rebalancing`: a separate target variable, not a feature

**Results (test set, class = stressed):**

| Model | Threshold | ROC-AUC | Recall | Precision | Accuracy |
|---|---|---|---|---|---|
| Logistic Regression | 0.5 | 0.971 | 0.95 | 0.75 | 89% |
| Logistic Regression | 0.3 | 0.971 | 0.98 | 0.67 | 84% |
| XGBoost | 0.5 | 0.977 | 0.82 | 0.93 | 92% |
| **XGBoost** | **0.3** | **0.977** | **0.90** | **0.81** | **90%** |

The chosen model is **XGBoost at threshold 0.3**: it catches 180 of 199 stressed days (missing only 19), with 42 false alarms out of 429 non-stressed days. This gives the best overall balance of catching real stress events while keeping false alarms reasonably low. If keeping false alarms as low as possible matters more than catching every event, XGBoost at the default threshold of 0.5 is the more conservative choice, with only 13 false alarms but a lower recall of 82%.

**Feature importance (gain):** `ybt_apy` (89.3) is the top feature, followed closely by `carry_spread` (84.5), `supply_rate` (82.8), and `carry_spread_levered` (71.8). Leverage volatility (`ltv_vol_7d` at 69.6, `ltv_vol_14d` at 41.3) and `borrow_rate` (40.2) matter too, but less. `collateral_price` (32.6) and `borrow_price` (28.2) matter the least, though they still contribute meaningfully. No single feature dominates, which is a good sign that this result is trustworthy.

**Key finding:** Stressed states are driven mainly by yield and interest rate changes, more than by leverage swings alone. A whale can be in a risky position even when its leverage looks stable, if the yield it earns drops too close to its borrowing cost. Leverage volatility still adds some signal, but it plays a smaller role than the yield and rate features here.

**Output:** `predictions_stressed.csv`

---

## Key Design Decisions

**Why a fixed threshold instead of a percentile for `stressed_state`?**

Health factor has a fixed, real world meaning: 1.0 means liquidation. Comparing each whale only to its own history (the percentile approach) made whales that are always near liquidation look no riskier than whales that are always safe, since both would land close to the same percentile based rate. A fixed threshold (health factor at or below 1.05) gives a result that reflects real danger and is comparable across all whales.

**Why threshold 0.3 for XGBoost in Model B?**

In a risk management context, missing a stressed day is usually more costly than a false alarm, since a missed stressed day could mean a whale gets liquidated. Lowering the decision threshold from 0.5 to 0.3 raises recall from 0.82 to 0.90, at the cost of some precision (0.93 down to 0.81).

**Why so few features in Model B compared to Model A?**

Model A predicts `rebalancing`, an action a whale actually takes, so features like `ltv`, `health_factor`, and `distance_to_liq` are safe to use there. Model B predicts `stressed_state`, which was built directly from `health_factor`, so any feature too closely tied to that formula would let the model see the answer instead of learning real patterns. This is why Model B's feature list looks different, even though both notebooks start from the same dataset.

**Why no leaky features overall?**

- Model A excludes `rebal_freq_7d`, `rebal_freq_30d`, `days_since_rebalance`, since these are derived from the rebalancing column itself, which is the target
- Model B excludes `ltv` and its lagged versions, `health_factor`, `distance_to_liq`, and `loop_depth`, since these were used to define `stressed_state`
- Model B also excludes `collateral_balance` and `borrow_balance`, since these let XGBoost find a near perfect shortcut even though the leak was less obvious than with `ltv`

---

## Data Flow

```
daily_features_all.csv
       |
01_eda_stress_threshold.ipynb
       |
whale_features_labeled.csv
       |                    |
02_model_rebalancing     03_model_stressed
       |                    |
predictions_rebalancing  predictions_stressed
.csv                     .csv
```

---

## Dependencies

```
pandas, numpy, matplotlib, seaborn
scikit-learn, xgboost, shap
```

---

## RQ3: To what extent can on-chain state variables predict short-horizon rebalancing events and stressed risk states?

**Short answer: yes, they can, with strong predictive power.**

**Rebalancing prediction:** On-chain state variables predict rebalancing events with a ROC-AUC of 0.876. The dominant predictors are leverage volatility (`ltv_vol_7d`) and leverage history (`ltv_lag_7`), not current risk metrics. Whales appear to respond to sustained leverage buildup over days, not to immediate danger signals.

**Stressed state prediction:** On-chain state variables predict stressed risk states with a ROC-AUC of 0.977 and recall of 0.90 at threshold 0.3. The dominant predictors are yield and rate related: `ybt_apy`, `carry_spread`, and `supply_rate`. Stress appears to be tied more closely to shrinking yield and rate conditions than to leverage alone.

---

## Findings

**The bigger finding across both models:**

The two phenomena are driven by different mechanisms.

- Rebalancing is reactive to the past: accumulated leverage history and volatility over 7 to 14 days
- Stress is reactive to yield and rate conditions: how much a whale is earning relative to what it is paying to borrow

**Finding 1: Rebalancing is a delayed response**

Whales do not rebalance the moment things get risky. The strongest predictors of rebalancing are leverage volatility over the past week and leverage from a week ago, not today's leverage level alone. This suggests rebalancing is a considered decision, not a panic reaction.

**Finding 2: Stress tracks yield and rate conditions closely**

A whale is more likely to be flagged as stressed when its yield (`ybt_apy`), carry spread, and supply rate move against it, more so than when its leverage alone changes. This means stress in this dataset looks less like "leverage got too high" and more like "the position stopped being worth the risk."

**Finding 3: Leverage volatility matters for both, but plays different roles**

In the rebalancing model, `ltv_vol_7d` is the single most important feature. In the stressed model, it still matters but ranks behind the yield and rate features. This suggests volatility is more of a trigger for action (rebalancing) than a definition of danger (stress) in this dataset.

**The big picture:**

Whales seem to watch leverage build up over time before deciding to rebalance, while their stressed state on any given day is shaped more by yield and rate conditions than by leverage swings alone. On-chain data captures both of these patterns clearly, which means DeFi risk behavior can likely be monitored, and to some extent predicted, using only publicly available blockchain data.