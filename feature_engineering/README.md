# Recursive Leverage Feature Engineering

## Pipeline

```
collect_events.py → build_panel.py → build_prices.py → build_features.py → build_rates.py → combine_results.py
```

Each protocol (Aave, Morpho) runs through `collect_events.py` → `build_rates.py` independently, producing its own `data/<protocol>/daily_features.csv`. `combine_results.py` merges these per-protocol outputs into a single dataset for cross-protocol analysis.

### Step 1: collect_events.py

Pulls raw on-chain events from Dune Analytics CSV exports. Events collected: supply, withdraw, borrow, repay.

Filter rule: only keep supply/withdraw of the whale's YBS collateral token, and borrow/repay of configured stablecoins. Everything else (cbBTC borrows) is dropped.

Output: `data/<protocol>/panel_raw_events.csv`

### Step 2: build_panel.py

Reconstructs daily position state from raw events using cumulative sums.

```
collateral_balance[day] = cumsum(supply - withdraw) up to that day
borrow_balance[day]     = cumsum(borrow - repay) up to that day
```

Days with no events inherit the previous day's balance. One row per `(whale_id, date, collateral_token, borrow_token)` combination.

Output: `data/<protocol>/daily_panel.csv`

### Step 3: build_prices.py

Fetches daily USD prices from DefiLlama for all tokens in the panel. Prices are forward-filled to handle gaps. Merges prices onto the panel and computes USD balances.

Output: `data/<protocol>/daily_panel_usd.csv`

### Step 4: build_features.py

Aggregates the panel to one row per `(whale_id, date)` and computes features.

Aggregation: sum `collateral_balance_usd` across all collateral tokens, sum `borrow_balance_usd` across all borrow tokens (deduplicated to avoid double-counting).

Current features:
- `collateral_balance_usd` — total USD value of collateral (from events)
- `borrow_balance_usd` — total USD value of debt (from events)
- `ltv` — loan-to-value ratio (borrow / collateral)
- `liquidation_threshold` — per-whale liquidation threshold for its market
- `health_factor` — `(collateral_usd × liquidation_threshold) / borrow_usd`; below 1.0 is liquidatable
- `distance_to_liq` — `liquidation_threshold - ltv`, headroom before liquidation
- `leverage` — continuous leverage `1 / (1 - ltv)`; 0 when there is no open debt. This is derived from LTV rather than counted from borrow transactions — tx counting overcounts for whales doing frequent small rebalances rather than discrete recursive loops, while the LTV-derived figure reflects effective leverage regardless of how the position was built.
- `ltv_vol_7d`, `ltv_vol_14d` — rolling standard deviation of LTV
- `position_activity` — 1 if any supply/withdraw/borrow/repay event occurred that day
- `ltv_cf`, `delta_leverage_rel`, `delta_equity_usd`, `delta_equity_rel` — the day's action with price movement removed (see below)
- `leverage_adjust`, `capital_flow`, `levered_scaling`, `minor_activity` — the activity class, one per active day
- `risk_rebalance` — `leverage_adjust` or `levered_scaling`
- `activity_freq_7d/30d`, `risk_rebal_freq_7d/30d`, `capital_flow_freq_7d/30d` — rolling counts
- `days_since_activity`, `days_since_risk_rebalance` — recency of each signal
- `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7` — lagged LTV for temporal context
- `coll_*`, `debt_*` — one-hot collateral and borrow token identity

Output: `data/<protocol>/daily_features.csv`

#### Classifying what a whale actually did

A day with a supply, withdraw, borrow or repay says only that the whale touched the position. Adding capital, moving capital to another protocol and managing risk all look the same at that level, so active days are classified by their effect on the position rather than by the transactions used.

A levered position is described completely by its equity `E = C - D` and its leverage `l = 1 / (1 - LTV)`, since `C = E * l` and `D = E * (l - 1)`. These are the two independent things a whale can change, so they are the axes used here. Collateral is not usable as the size axis because it moves whenever leverage moves.

Price movement is removed first. Yesterday's token balances marked at today's prices give `ltv_cf`, the position the whale would have held had they done nothing, and the action is whatever differs from it. Measured this way a day with no events moves by exactly zero.

| Class | Leverage | Capital | Reading |
|-------|---------|---------|---------|
| `leverage_adjust` | moved | flat | Risk management: risk rebalancing at constant capital |
| `capital_flow` | flat | moved | Capital arriving or leaving at constant leverage |
| `levered_scaling` | moved | moved | A loop being built or unwound |
| `minor_activity` | flat | flat | Dust |

A move counts as material at 2% relative change, with capital flows also required to clear $1,000 to exclude dust. The thresholds are relative because equity across these whales spans $5k to $12m and because one point of LTV is a 4% leverage move at LTV 0.50 but a 29% move at LTV 0.965. They mark materiality rather than a noise floor: the measured action on a quiet day is exactly zero. The first observed day of a position has no counterfactual, so it is classified from what was opened.

Use `risk_rebalance` wherever the question is risk management. `position_activity` is the broad flag and counts capital moves and dust alongside it.

### Step 5: build_rates.py

Joins daily yield, supply rate and borrow rate series onto `daily_features.csv` and computes the carry spread. YBT APY comes from DefiLlama pools; borrow rates come from Dune exports; supply rates come from Dune exports (Aave aToken rate) or the Morpho API (`historicalState.supplyApy`, queried per market ID). Updates `daily_features.csv` in place.

- `ybt_apy` — annualised yield on the collateral token
- `supply_rate` — annualised protocol supply rate on the collateral (Aave aToken rate; Morpho Blue per-market supply APY from the Morpho GraphQL API)
- `borrow_rate` — annualised borrow rate on the debt token
- `carry_spread` — `ybt_apy + supply_rate - borrow_rate`, the per-loop spread
- `carry_spread_levered` — `carry_spread * leverage`, the spread scaled by position leverage

Output: `data/<protocol>/daily_features.csv`

### Step 6: combine_results.py

Concatenates `data/aave/daily_features.csv` and `data/morpho/daily_features.csv` into a single cross-protocol dataset for analysis. Each protocol has its own set of one-hot `coll_*`/`debt_*` columns since the token universes differ (e.g. Aave's `coll_sUSDe` vs Morpho's `coll_sUSDS`); these are aligned via `pd.concat` and missing one-hot values are filled with 0.

Output: `data/daily_features_all.csv`

## Data notes
- For Aave supply rate is 0 (sUSDe)!
- No liquidations occurred for any whale in our event export.
- Balances are reconstructed from events, so they only change on event days and accrued borrow interest never appears in them. LTV drift between events is therefore price movement alone, and the slow upward creep in LTV that unpaid interest would cause is not captured.
