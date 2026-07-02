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
- `loop_depth` — leverage multiple `round(1 / (1 - ltv))`, capped at the max possible for the market's liquidation threshold; 0 when there is no open debt. This is derived from LTV rather than counted from borrow transactions — tx counting overcounts for whales doing frequent small rebalances rather than discrete recursive loops, while the LTV-derived figure reflects effective leverage regardless of how the position was built.
- `ltv_vol_7d`, `ltv_vol_14d` — rolling standard deviation of LTV
- `rebal_freq_7d`, `rebal_freq_30d` — rolling count of rebalancing events
- `days_since_rebalance` — days since the last rebalancing event
- `ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7` — lagged LTV for temporal context
- `coll_*`, `debt_*` — one-hot collateral and borrow token identity

Output: `data/<protocol>/daily_features.csv`

### Step 5: build_rates.py

Joins daily yield, supply rate and borrow rate series onto `daily_features.csv` and computes the carry spread. YBT APY comes from DefiLlama pools; borrow rates come from Dune exports; supply rates come from Dune exports (Aave aToken rate) or the Morpho API (`historicalState.supplyApy`, queried per market ID). Updates `daily_features.csv` in place.

- `ybt_apy` — annualised yield on the collateral token
- `supply_rate` — annualised protocol supply rate on the collateral (Aave aToken rate; Morpho Blue per-market supply APY from the Morpho GraphQL API)
- `borrow_rate` — annualised borrow rate on the debt token
- `carry_spread` — `ybt_apy + supply_rate - borrow_rate`, the per-loop spread
- `carry_spread_levered` — `carry_spread * loop_depth`, the spread scaled by recursion

Output: `data/<protocol>/daily_features.csv`

### Step 6: combine_results.py

Concatenates `data/aave/daily_features.csv` and `data/morpho/daily_features.csv` into a single cross-protocol dataset for analysis. Each protocol has its own set of one-hot `coll_*`/`debt_*` columns since the token universes differ (e.g. Aave's `coll_sUSDe` vs Morpho's `coll_sUSDS`); these are aligned via `pd.concat` and missing one-hot values are filled with 0.

Output: `data/daily_features_all.csv`

## Data notes
- For Aave supply rate is 0 (sUSDe)!
- No liquidations occurred for any whale in our event export.
