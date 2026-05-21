# Morpho Whales Feature Engineering and Data Collection

A pipeline that tracks large Morpho protocol positions (whales) from raw on-chain events to daily LTV features.

## Pipeline Steps

**1. collect_events.py**
Reads raw on-chain events from Dune CSV exports and filters them into a clean events table per whale. Outputs `panel_raw_events.csv`.

**2. build_panel.py**
Converts raw events into a daily time series. Cumulates supply/withdraw into a running collateral balance and borrow/repay into a running debt balance, one row per whale per day. Outputs `daily_panel.csv`.

**3. build_prices.py**
Fetches historical daily prices from DefiLlama for each token and joins them onto the panel. Computes USD values for collateral and borrow balances. Outputs `daily_panel_usd.csv`.

**4. build_features.py**
Computes two risk metrics per whale per day and outputs `daily_features.csv`.

- **LTV**  `borrow_balance_usd / collateral_balance_usd`
- **Health Factor** `(collateral_balance_usd * liquidation_threshold) / borrow_balance_usd`, where liquidation threshold is hardcoded per market from Morpho's market config (0.915 for all three markets). A health factor below 1.0 means the position is eligible for liquidation.

```
health_factor = (collateral_balance_usd * liquidation_threshold) / borrow_balance_usd
```

## Data Flow

```
Dune CSVs  →  panel_raw_events.csv  →  daily_panel.csv  →  daily_panel_usd.csv  →  daily_features.csv
```

## Whales Tracked

| ID  | Protocol | Collateral | Borrow |
|-----|----------|------------|--------|
| W-1 | Morpho   | sUSDe      | USDtb  |
| W-4 | Morpho   | sUSDe      | PYUSD  |
| W-5 | Morpho   | syrupUSDC  | PYUSD  |