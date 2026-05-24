# Aave Whale Feature Engineering

A pipeline that tracks Aave v3 positions by replaying Dune events. Same approach as Morpho.

## Pipeline Steps

**1. collect_events.py**
Loads raw events from Dune CSV exports and normalizes them into `panel_raw_events.csv`.

**2. build_panel.py**
Replays supply/withdraw/borrow/repay events to build daily collateral and borrow balances per whale. Outputs `daily_panel.csv`.

**3. build_prices.py**
Fetches historical token prices from DeFiLlama and converts balances to USD. Outputs `daily_panel_usd.csv`.

**4. build_features.py**
Computes risk metrics and behavioral features per whale per day. Outputs `daily_features.csv`.

- **LTV** `borrow_balance_usd / collateral_balance_usd`
- **Health Factor** `(collateral_balance_usd * liquidation_threshold) / borrow_balance_usd`. Below 1.0 = liquidatable.
- **Distance to Liquidation** `liquidation_threshold - ltv`. Positive = safe, negative = underwater.
- **Rebalancing** Binary flag (0/1) indicating whether any event occurred on a given day.

## Data Flow

```
Dune CSV  →  panel_raw_events.csv  →  daily_panel.csv  →  daily_panel_usd.csv  →  daily_features.csv
```

## Dune Queries

| Whale | Query |
|-------|-------|
| W-6   | [Aave W-6 Events (sUSDe/USDT)](https://dune.com/queries/7524498) |

## Whales Tracked

| ID  | Address       | Protocol | Collateral | Borrow | Strategy |
|-----|---------------|----------|------------|--------|----------|
| W-6 | 0x029469ca... | Aave v3  | sUSDe      | USDT   | E-Mode looper |

## Liquidation Threshold

| Market                   | Threshold |
|--------------------------|-----------|
| E-Mode sUSDe Stablecoins | 0.92      |

## Features

| Feature           | Description                                                         |
|-------------------|---------------------------------------------------------------------|
| `ltv`             | Borrow balance USD / collateral balance USD                         |
| `health_factor`   | Calculated from panel data. Below 1.0 = liquidatable                |
| `distance_to_liq` | Liquidation threshold − LTV. Positive = safe, negative = underwater |
| `rebalancing`     | 1 if any supply/withdraw/borrow/repay event on that day, else 0     |
