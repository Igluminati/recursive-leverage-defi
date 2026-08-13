# Whale Risk Supervised Learning

This folder contains three Jupyter notebooks that build supervised ML models to answer **RQ3**: can on-chain state variables predict short-horizon risk rebalancing and stressed risk states?

Model A predicts `risk_rebalance`, the days on which a whale actually changes its leverage. It deliberately does not predict the broader `position_activity` flag, which counts any supply, withdraw, borrow or repay and so mixes capital movements and dust in with risk management. See the feature engineering README for how the two are separated.

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

- Loads the whale features CSV: 2,506 rows, 23 whales (W-1 to W-23), spanning 2024-03-29 to 2026-06-27
- Plots `health_factor` and `distance_to_liq` (mean and min) per whale, sorted numerically (W-1 through W-23), plus full summary statistics
- Defines `stressed_state` using a fixed threshold: a whale is stressed on any day its health factor drops to 1.05 or below
- Saves the enriched dataset as `whale_features_labeled.csv`

**Rows per whale range widely**, from W-15 and W-22 with just 9 rows each up to W-11 with 622 rows. Most whales fall between 20 and 250 rows.

**Why a fixed threshold instead of a percentile?**

An earlier version of this notebook used each whale's own worst 30% of days as the stress cutoff. This turned out to be misleading, because health factor has a fixed real world meaning (1.0 means liquidation), but the percentile method compared each whale only to itself. This made a whale that lives constantly near 1.0 (like W-1) look no riskier than a whale that is always safely above 1.4 (like W-4), since both would show roughly the same 30% stressed rate.

Switching to a single fixed threshold (1.05) fixes this. Now a whale is only marked stressed when it is actually close to liquidation, which is consistent and comparable across all whales.

**EDA takeaways:**

- Whales split into three broad patterns: a small group with high average safety buffers but occasional risky dips (W-11, W-16, W-3, W-13), a group of steady conservative operators (W-4, W-5, W-8, W-23), and a couple of whales that sit close to liquidation almost constantly (W-1, W-12).
- W-1 and W-12 are stressed on more than 95% of their days under the fixed threshold.
- Several whales, including W-4, W-5, W-8, W-11, W-16, W-18, W-22, and W-23, are never stressed under this threshold.
- Overall **stressed rate: 28.9%** (725 of 2,506 days). Whales are **active on 14.8%** of days but **risk-rebalance on only 7.2%**, so roughly half of what the old broad flag counted as rebalancing was capital movement or dust.
- The ranking of "active" whales changes completely once the two are separated. W-3 is active on 47.5% of its days but risk-rebalances on 3.6%, and W-11 on 15.8% against 3.5%. The genuinely active risk managers are W-16 (44.7%), W-15 (44.4%), W-9 (29.2%) and W-14 (24.6%).

**Output:** `whale_features_labeled.csv`

---

### `02_model_risk_rebalance.ipynb`, Model A: Predict a Leverage Change

**What it does:**

- Predicts whether a whale will change its leverage on a given day
- Target: `risk_rebalance` (0 or 1, already in the data)
- After dropping rows with missing features, the modeling set is 1,475 rows. A stratified 70/30 split gives 1,032 training rows and 443 test rows.
- Runs Logistic Regression (`class_weight='balanced'`) as a baseline, then XGBoost
- Uses `scale_pos_weight = 16.49` to handle the class imbalance
- Explains predictions with feature importance and SHAP

**Features used (11):**

- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`
- `ltv_vol_7d`, `ltv_vol_14d`
- `distance_to_liq`, `health_factor`
- `carry_spread`, `carry_spread_levered`
- `leverage`

**Results (test set, class = risk rebalance, 26 of 443 days):**

| Model | ROC-AUC | Recall | Precision | Accuracy |
|---|---|---|---|---|
| Logistic Regression | 0.881 | 0.62 | 0.42 | 93% |
| XGBoost | 0.901 | 0.81 | 0.26 | 85% |

Accuracy is not informative at a 5.9% base rate, since always predicting zero would score 94%. XGBoost catches 21 of 26 risk rebalances against the baseline's 16, but raises 61 false alarms against 22. It is the better choice when missing an event is worse than raising an alert, and the baseline is better calibrated otherwise. With only 26 positive test days, the gap between the two should not be over-read.

Both models separate the classes better than the old broad-activity target did (ROC-AUC 0.820 / 0.877), even though the new target is rarer and harder. Predicting deliberate risk management is more learnable than predicting whether a whale will touch the position for any reason at all.

**Feature importance (weight):** `ltv_vol_7d` (52) dominates, followed by `carry_spread_levered` (18), `ltv_vol_14d` (17), `carry_spread` (14) and `ltv_lag_1` (13). `ltv_lag_7` (7), `ltv_lag_3` (5), `distance_to_liq` (3), `leverage` (2) and `ltv` (1) are used sparingly, and `health_factor` was not used by any tree.

**Key finding:** Risk rebalances are driven by how much the leverage ratio has moved recently, with carry economics second. The rise of the carry features under this target is the clearest evidence that the split was worth making: the old flag mixed in capital movements that carry economics do not explain.

**Output:** `predictions_risk_rebalance.csv`

---

### `03_model_stressed.ipynb`, Model B: Predict Stressed State

**What it does:**

- Predicts whether a whale is in a stressed risk state on a given day, using the fixed threshold definition from notebook 01
- Target: `stressed_state` (1,781 not stressed, 725 stressed, 28.9% stressed rate)
- After dropping rows with missing features, the modeling set is 2,091 rows. A stratified 70/30 split gives 1,463 training rows and 628 test rows.
- Runs Logistic Regression as a baseline, then XGBoost, each at thresholds 0.5 and 0.3
- Explains predictions with feature importance and SHAP

**Features used (8):**

- `ltv_vol_7d`, `ltv_vol_14d`
- `carry_spread`, `carry_spread_levered`
- `ybt_apy`, `borrow_rate`
- `collateral_price`, `borrow_price`

**Why this feature list took a few rounds to get right:**

The first attempt included `ltv`, its lagged versions, `health_factor`, `distance_to_liq`, and `leverage`, and produced a ROC-AUC of 1.000, a clear sign of data leakage. Checking the raw values confirmed it: `ltv` above about 0.87 almost perfectly separated stressed from not stressed days, and `leverage` above 8 (equivalent to LTV ≈ 0.875) did the same. Both features were removed, since `health_factor` (which defines `stressed_state`) is built directly from `ltv`, and `leverage` turned out to be tied to the same underlying formula.

After removing those, a second, smaller leak was found. `collateral_balance` and `borrow_balance` let XGBoost reach a ROC-AUC of 0.993, a much bigger jump over Logistic Regression than normal. Trees can exploit hidden cutoffs in raw numbers more easily than a straight line model can, so a leak that Logistic Regression missed still showed up in XGBoost. Removing these two balance features brought the then-current model (which still included `supply_rate`) back to a believable ROC-AUC near 0.97. `supply_rate` was later dropped as well, since Aave sUSDe earn nearly all of their yield off-protocol; the current eight-feature model sits at ROC-AUC 0.943 (XGBoost) / 0.804 (Logistic Regression).

**Features excluded and why:**

- `ltv`, `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`, `health_factor`, `distance_to_liq`, `leverage`: too closely tied to how `stressed_state` was defined
- `collateral_balance_usd`, `borrow_balance_usd`, `liquidation_threshold`: `ltv` is built directly from these
- `collateral_balance`, `borrow_balance`: raw token amounts, but still let XGBoost find a near perfect shortcut, so they were dropped even though the leak here was smaller and less obvious
- `risk_rebal_freq_7d`, `risk_rebal_freq_30d`, `days_since_risk_rebalance`, `activity_freq_*`: these belong to Model A's target, not this one, and added no real value here
- `position_activity`, `risk_rebalance`, `capital_flow`, `levered_scaling`, `minor_activity`: activity labels, not features for this model

**Results (test set, class = stressed):**

| Model | Threshold | ROC-AUC | Recall | Precision | Accuracy |
|---|---|---|---|---|---|
| Logistic Regression | 0.5 | 0.804 | 0.78 | 0.50 | 68% |
| Logistic Regression | 0.3 | 0.804 | 0.96 | 0.40 | 53% |
| XGBoost | 0.5 | 0.943 | 0.73 | 0.81 | 86% |
| **XGBoost** | **0.3** | **0.943** | **0.92** | **0.67** | **83%** |

The chosen model is **XGBoost at threshold 0.3**: it catches 184 of 199 stressed days (missing only 15), with 89 false alarms out of 429 non-stressed days. This gives the best overall balance of catching real stress events while keeping false alarms reasonably low. If keeping false alarms as low as possible matters more than catching every event, XGBoost at the default threshold of 0.5 is the more conservative choice, with only 35 false alarms but a lower recall of 73%.

**Feature importance (gain):** `ybt_apy` (80.2) is the top feature, followed by `borrow_rate` (63.1), `ltv_vol_7d` (60.3), and `collateral_price` (58.8). `ltv_vol_14d` (52.5) and `carry_spread` (43.4) sit in the middle. `carry_spread_levered` (29.6) and `borrow_price` (25.4) matter the least, though they still contribute. No single feature dominates, which is a good sign that this result is trustworthy.

**Key finding:** Stressed states are driven mainly by the yield environment (`ybt_apy`, `borrow_rate`), with leverage volatility and collateral price close behind. A whale can be in a risky position even when its leverage looks stable, if the yield it earns drops too close to its borrowing cost.

**Output:** `predictions_stressed.csv`

---

## Key Design Decisions

**Why a fixed threshold instead of a percentile for `stressed_state`?**

Health factor has a fixed, real world meaning: 1.0 means liquidation. Comparing each whale only to its own history (the percentile approach) made whales that are always near liquidation look no riskier than whales that are always safe, since both would land close to the same percentile based rate. A fixed threshold (health factor at or below 1.05) gives a result that reflects real danger and is comparable across all whales.

**Why threshold 0.3 for XGBoost in Model B?**

In a risk management context, missing a stressed day is usually more costly than a false alarm, since a missed stressed day could mean a whale gets liquidated. Lowering the decision threshold from 0.5 to 0.3 raises recall from 0.73 to 0.92, at the cost of some precision (0.81 down to 0.67).

**Why so few features in Model B compared to Model A?**

Model A predicts `risk_rebalance`, an action a whale actually takes, so features like `ltv`, `health_factor`, and `distance_to_liq` are safe to use there. Model B predicts `stressed_state`, which was built directly from `health_factor`, so any feature too closely tied to that formula would let the model see the answer instead of learning real patterns. This is why Model B's feature list looks different, even though both notebooks start from the same dataset.

**Why no leaky features overall?**

- Model A excludes `risk_rebal_freq_7d`, `risk_rebal_freq_30d`, `days_since_risk_rebalance`, `delta_leverage_rel` and `delta_equity_rel`, since these are derived from the target itself
- Model B excludes `ltv` and its lagged versions, `health_factor`, `distance_to_liq`, and `leverage`, since these were used to define `stressed_state`
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
02_model_risk_rebalance  03_model_stressed
       |                    |
predictions_leverage_    predictions_stressed
touch.csv                .csv
```

---

## Dependencies

```
pandas, numpy, matplotlib, seaborn
scikit-learn, xgboost, shap
```

---

## RQ3: To what extent can on-chain state variables predict short-horizon risk rebalancing and stressed risk states?

**Short answer: yes, they can, with strong predictive power.**

**Risk rebalance prediction:** On-chain state variables predict a risk rebalance with a ROC-AUC of 0.901. The dominant predictor is leverage volatility (`ltv_vol_7d`), with carry economics (`carry_spread_levered`, `carry_spread`) second. Whales appear to respond to sustained movement in leverage and to whether the position is still earning, not to immediate danger signals.

**Stressed state prediction:** On-chain state variables predict stressed risk states with a ROC-AUC of 0.943 and recall of 0.92 at threshold 0.3. The dominant predictors are yield and rate related: `ybt_apy` and `borrow_rate`, with leverage volatility close behind. Stress appears to be tied more closely to shrinking yield and rate conditions than to leverage alone.

---

## Findings

**The bigger finding across both models:**

The two phenomena are driven by different mechanisms.

- Risk rebalancing is reactive to the past: leverage volatility over 7 to 14 days, plus the carry the position is earning
- Stress is reactive to yield and rate conditions: how much a whale is earning relative to what it is paying to borrow

**Finding 1: Risk rebalancing is a delayed response**

Whales do not risk-rebalance the moment things get risky. The strongest predictor is leverage volatility over the past week, not today's leverage level. This suggests risk rebalancing is a considered decision, not a panic reaction.

**Finding 1b: Most position activity is not risk management**

Whales touch their positions on 14.8% of days but risk-rebalance on only 7.2%. Separating the two changes who counts as an active manager: W-3 is active on 47.5% of its days and risk-rebalances on 3.6%. Modelling the broad flag was therefore partly modelling capital movements and dust, and the carry features only surface as predictors once those are removed.

**Finding 2: Stress tracks yield and rate conditions closely**

A whale is more likely to be flagged as stressed when its yield (`ybt_apy`) and borrow rate move against it, more so than when its leverage alone changes. This means stress in this dataset looks less like "leverage got too high" and more like "the position stopped being worth the risk."

**Finding 3: Leverage volatility matters for both, but plays different roles**

In the risk rebalance model, `ltv_vol_7d` is the single most important feature by a wide margin. In the stressed model, it still matters but ranks behind `ybt_apy` and `borrow_rate`. This suggests volatility is more of a trigger for action (risk rebalancing) than a definition of danger (stress) in this dataset.

**The big picture:**

Whales seem to watch leverage move over time before deciding to risk-rebalance, while their stressed state on any given day is shaped more by yield and rate conditions than by leverage swings alone. On-chain data captures both of these patterns clearly, which means DeFi risk behavior can likely be monitored, and to some extent predicted, using only publicly available blockchain data.