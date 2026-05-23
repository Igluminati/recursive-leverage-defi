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

## Data Flow

```
Dune CSVs  →  panel_raw_events.csv  →  daily_panel.csv  →  daily_panel_usd.csv  →  daily_features.csv
```

## Whales Tracked

| ID  | Address       | Protocol | Collateral | Borrow | Strategy                          |
|-----|---------------|----------|------------|--------|-----------------------------------|
| W-1 | 0x080ccea8... | Morpho   | sUSDe      | USDtb  | Manual, high-frequency            |
| W-2 | 0x97bb0e08... | Morpho   | sUSDS      | USDT   | Manual, long-term cycler (300 days) |
| W-3 | 0xcb1effb6... | Morpho   | sUSDS      | USDT   | Manual, daily rebalancer (170 rebalances) |
| W-4 | 0x0d4f7b20... | Morpho   | sUSDe      | PYUSD  | Manual                            |
| W-5 | 0x24385a79... | Morpho   | syrupUSDC  | PYUSD  | Manual                            |

## Liquidation Thresholds (per Morpho market config)

| Market              | Threshold |
|---------------------|-----------|
| sUSDe / USDtb       | 0.915     |
| sUSDS / USDT        | 0.965     |
| sUSDe / PYUSD       | 0.915     |
| syrupUSDC / PYUSD   | 0.915     |

## Features

| Feature               | Description                                                                 |
|-----------------------|-----------------------------------------------------------------------------|
| `ltv`                 | Borrow balance USD / collateral balance USD                                 |
| `health_factor`       | (Collateral USD × liquidation threshold) / borrow USD. Below 1.0 = liquidatable |
| `distance_to_liq`     | Liquidation threshold − LTV. Positive = safe, negative = underwater         |
| `rebalancing`         | 1 if any supply/withdraw/borrow/repay event on that day, else 0             |