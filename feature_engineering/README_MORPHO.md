# Morpho Whales Feature Engineering and Data Collection

A pipeline that tracks large Morpho protocol positions (whales) from raw on-chain events.

## Pipeline Steps

**1. collect_events.py**
Reads raw on-chain events from Dune CSV exports and filters them into a clean events table per whale. Outputs `panel_raw_events.csv`.

**2. build_panel.py**
Converts raw events into a daily time series. Cumulates supply/withdraw into a running collateral balance and borrow/repay into a running debt balance, one row per whale per day. Outputs `daily_panel.csv`.

**3. build_prices.py**
Fetches historical daily prices from DefiLlama for each token and joins them onto the panel. Computes USD values for collateral and borrow balances. Outputs `daily_panel_usd.csv`.

**4. build_features.py**
Computes risk metrics and behavioral features per whale per day. Outputs `daily_features.csv`.

- **LTV** `borrow_balance_usd / collateral_balance_usd`
- **Health Factor** `(collateral_balance_usd * liquidation_threshold) / borrow_balance_usd`, where liquidation threshold is hardcoded per market from Morpho's market config. A health factor below 1.0 means the position is eligible for liquidation.
- **Distance to Liquidation** `liquidation_threshold - ltv` how many percentage points of LTV buffer remain before liquidation. Positive = safe, negative = underwater.
- **Rebalancing** Binary flag (0/1) indicating whether any supply, withdraw, borrow, or repay event occurred on a given day. 
- **Loop Depth** The leverage multiple of the position, `round(1 / (1 - ltv))`, capped at the max possible for the market's liquidation threshold (`1 / (1 - liquidation_threshold)`). Recursive looping (supply, borrow, resupply) stacks leverage that converges to `1 / (1 - ltv)`, so this is roughly how many times the position is geared (90% LTV is about 10x). 0 when there is no open debt. This is derived from LTV rather than counted from raw borrow transactions: counting unique borrow tx hashes overcounts for whales that do frequent small rebalances (e.g. W-3, which executed 170 borrow events) rather than discrete recursive loops, while the LTV-derived figure reflects the position's effective leverage regardless of how it was built. Verified against W-1's event history, where the LTV-derived depth matched the actual count of supply→borrow loop transactions on its main build day.
- **LTV Volatility** Rolling 7-day and 14-day standard deviation of LTV (`ltv_vol_7d`, `ltv_vol_14d`).
- **Rebalancing Frequency** Rolling 7-day and 30-day count of rebalancing events (`rebal_freq_7d`, `rebal_freq_30d`).
- **Days Since Last Rebalance** Days since the last rebalancing event within the open position (`days_since_rebalance`).
- **Lagged LTV** LTV at t-1, t-3, t-7 days (`ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`).
- **Token Identity** One-hot encoding of collateral and borrow token (`coll_*`, `debt_*`).

**5. get_morpho_supply_rates.py**
Fetches historical daily supply APY per Morpho market from the Morpho GraphQL API (`https://api.morpho.org/graphql`), using the `marketById` query's `historicalState.supplyApy` timeseries. Queried per market id for each whale's market, with `interval: DAY` starting from a fixed historical anchor date. Results are deduplicated to one row per `(market_id, date)`, keeping the latest data point when a day has more than one (e.g. the current, unfinished day). Outputs `morpho_supply_rates.csv`.

This step exists because Morpho Blue markets do pass through a real supply APY (native rate plus the collateral token's own yield contribution) — confirmed against the Morpho app's Rates panel — so supply rate cannot be hardcoded to 0 the way it was originally assumed.

**6. build_rates.py**
Joins daily yield, supply rate, and borrow rate series onto the features table and computes the carry spread. YBT APY comes from DefiLlama pools (sUSDe, sUSDS, syrupUSDC); borrow rate comes from the Dune export `from_dune/morpho_borrow_rates.csv`; supply rate comes from `morpho_supply_rates.csv` (Step 5). All three are matched per whale by Morpho market id and forward-filled within each whale/market group. Updates `daily_features.csv` in place.

- **YBT APY** Annualised yield on the collateral token (`ybt_apy`).
- **Supply Rate** Annualised protocol supply rate earned on the collateral, per Morpho market, sourced from the Morpho API (`supply_rate`).
- **Borrow Rate** Annualised borrow rate paid on the debt token, per Morpho market (`borrow_rate`).
- **Carry Spread** `ybt_apy + supply_rate - borrow_rate`, the per-loop spread (`carry_spread`).
- **Levered Carry Spread** `carry_spread * loop_depth`, the spread scaled by recursion (`carry_spread_levered`).

## Data Flow

```
Dune CSVs  →  panel_raw_events.csv  →  daily_panel.csv  →  daily_panel_usd.csv  →  daily_features.csv  →  + rates (build_rates.py, using get_morpho_supply_rates.py output)
```

## Whales Tracked

| ID  | Address       | Protocol | Collateral | Borrow | Strategy                          |
|-----|---------------|----------|------------|--------|-----------------------------------|
| W-1 | 0x080ccea8... | Morpho   | sUSDe      | USDtb  | Manual, high-frequency            |
| W-2 | 0x97bb0e08... | Morpho   | sUSDS      | USDT   | Manual, long-term cycler (300 days) |
| W-3 | 0xcb1effb6... | Morpho   | sUSDS      | USDT   | Manual, daily rebalancer (170 rebalances) |
| W-4 | 0x0d4f7b20... | Morpho   | sUSDe      | PYUSD  | Manual                            |
| W-5 | 0x24385a79... | Morpho   | syrupUSDC  | PYUSD  | Manual                            |
| W-6 | 0xfafc2c5f... | Morpho   | sUSDS      | USDT   | Manual                            |
| W-7 | 0x32f07401... | Morpho   | sUSDe      | PYUSD  | Manual, active rebalancer (>1k txs) |
| W-8 | 0x218b5b98... | Morpho   | sUSDe      | DAI    | Manual, short-lived (2024)        |
| W-9 | 0x309e161a... | Morpho   | sUSDe      | DAI    | Manual, short-lived (2024)        |
| W-10| 0x3363aca0... | Morpho   | sUSDe      | DAI    | Manual, long-term cycler (2024)   |
| W-11| 0xb48ac9c5... | Morpho   | sUSDe      | DAI    | Manual, low-leverage cycler (2024-25) |
| W-12| 0x9bcb2ee2... | Morpho   | sUSDS      | USDT   | Manual, deep looper (2026)        |
| W-13| 0x206777f4... | Morpho   | sUSDS      | USDT   | Manual, deep looper (2026)        |
| W-14| 0xc05855cb... | Morpho   | sUSDS      | USDT   | Manual, active cycler (2026)      |
| W-15| 0x59b6c75e... | Morpho   | syrupUSDC  | USDC   | Manual, short-lived (2026)        |
| W-16| 0xf28dc8b6... | Morpho   | syrupUSDC  | USDC   | Manual, active cycler (2026)      |
| W-17| 0xc5d6a3e7... | Morpho   | syrupUSDC  | PYUSD  | Manual, single-day open (2026)    |

## Liquidation Thresholds (per Morpho market config)

| Market              | Threshold |
|---------------------|-----------|
| sUSDe / USDtb       | 0.915     |
| sUSDS / USDT        | 0.965     |
| sUSDe / PYUSD       | 0.915     |
| syrupUSDC / PYUSD   | 0.915     |
| sUSDe / DAI         | 0.915     |
| sUSDe / DAI (legacy market) | 0.86 |
| syrupUSDC / USDC    | 0.915     |

## Features

| Feature               | Description                                                                 |
|-----------------------|-----------------------------------------------------------------------------|
| `ltv`                 | Borrow balance USD / collateral balance USD                                 |
| `health_factor`       | (Collateral USD × liquidation threshold) / borrow USD. Below 1.0 = liquidatable |
| `distance_to_liq`     | Liquidation threshold − LTV. Positive = safe, negative = underwater         |
| `rebalancing`         | 1 if any supply/withdraw/borrow/repay event on that day, else 0             |
| `loop_depth`          | Leverage multiple `round(1 / (1 - ltv))`, capped at `1 / (1 - liquidation_threshold)`; 0 when there is no open debt |
| `ltv_vol_7d`          | Rolling 7-day standard deviation of LTV                                     |
| `ltv_vol_14d`         | Rolling 14-day standard deviation of LTV                                    |
| `rebal_freq_7d`       | Rolling 7-day count of rebalancing events                                   |
| `rebal_freq_30d`      | Rolling 30-day count of rebalancing events                                  |
| `days_since_rebalance`| Days since the last rebalancing event within the open position              |
| `ltv_lag_1` / `ltv_lag_3` / `ltv_lag_7` | LTV lagged by 1, 3, and 7 days (temporal context for RQ3) |
| `coll_*` / `debt_*`   | One-hot identity of collateral and borrow token (market)                    |
| `ybt_apy`             | Annualised yield on the collateral token (DefiLlama pool)                   |
| `supply_rate`         | Annualised protocol supply rate on the collateral, per Morpho market (Morpho GraphQL API) |
| `borrow_rate`         | Annualised borrow rate on the debt token, per Morpho market                 |
| `carry_spread`        | `ybt_apy + supply_rate − borrow_rate`, the per-loop carry spread            |
| `carry_spread_levered`| `carry_spread × loop_depth`, the spread scaled by recursion                 |