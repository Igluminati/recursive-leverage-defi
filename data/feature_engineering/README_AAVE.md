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
- **Loop Depth** The leverage multiple of the position, `round(1 / (1 - ltv))`. Recursive looping (supply, borrow, resupply) stacks leverage that converges to `1 / (1 - ltv)`, so this is roughly how many times the position is geared (90% LTV is about 10x). 0 when there is no open debt.
- **LTV Volatility** Rolling 7-day and 14-day standard deviation of LTV (`ltv_vol_7d`, `ltv_vol_14d`).
- **Rebalancing Frequency** Rolling 7-day and 30-day count of rebalancing events (`rebal_freq_7d`, `rebal_freq_30d`).
- **Days Since Last Rebalance** Days since the last rebalancing event within the open position (`days_since_rebalance`).
- **Lagged LTV** LTV at t-1, t-3, t-7 days (`ltv_lag_1`, `ltv_lag_3`, `ltv_lag_7`).
- **Token Identity** One-hot encoding of collateral and borrow token (`coll_*`, `debt_*`).

**5. build_rates.py**
Joins daily yield, supply rate and borrow rate series onto the features table and computes the carry spread. YBT APY comes from DeFiLlama (sUSDe pool); the sUSDe supply rate and the per-token variable borrow rates (USDT for W-6, USDe for W-7) come from Dune exports in `from_dune/`, matched by collateral and borrow token. Updates `daily_features.csv` in place.

- **YBT APY** Annualised yield on the collateral token (`ybt_apy`).
- **Supply Rate** Annualised Aave supply rate earned on the collateral aToken (`supply_rate`).
- **Borrow Rate** Annualised variable borrow rate paid on the debt token (`borrow_rate`).
- **Carry Spread** `ybt_apy + supply_rate - borrow_rate`, the per-loop spread (`carry_spread`).
- **Levered Carry Spread** `carry_spread * loop_depth`, the spread scaled by recursion (`carry_spread_levered`).

## Data Flow

```
Dune CSV  →  panel_raw_events.csv  →  daily_panel.csv  →  daily_panel_usd.csv  →  daily_features.csv  →  + rates (build_rates.py)
```

## Dune Queries

## Whales Tracked

| ID   | Address       | Protocol | Collateral | Borrow | Strategy |
|------|---------------|----------|------------|--------|----------|
| W-18 | 0x029469ca80e6c94436af010a369f54935a711080 | Aave v3  | sUSDe      | USDT   | E-Mode looper |
| W-19 | 0x5D876B100Dd38D0701725035B97632553eaa1836 | Aave v3  | sUSDe      | USDC   | E-Mode looper |
| W-20 | 0x5D876B100Dd38D0701725035B97632553eaa1836 | Aave v3  | sUSDe      | USDe   | E-Mode looper |
| W-21 | 0x852689F44a4CA94a0E424EAd14A1Bb63719314db | Aave v3  | sUSDe      | USDe   | E-Mode looper |
| W-22 | 0x24201ECD8b3f062215640B8c0740C4e892c091E3 | Aave v3  | sUSDe      | USDe   | E-Mode looper |
| W-23 | 0x23270C161c42fFd0636fe786Cc7c518A0181234F | Aave v3  | sUSDe      | USDC   | E-Mode looper |
| W-24 | 0xF3AdD38c51924221Dcf30767f69c6E57D77D9566 | Aave v3  | sUSDe      | USDC   | E-Mode looper |## Whales Tracked



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
| `loop_depth`      | Leverage multiple `round(1 / (1 - ltv))`; 0 when there is no open debt           |
| `ltv_vol_7d`      | Rolling 7-day standard deviation of LTV                             |
| `ltv_vol_14d`     | Rolling 14-day standard deviation of LTV                            |
| `rebal_freq_7d`   | Rolling 7-day count of rebalancing events                           |
| `rebal_freq_30d`  | Rolling 30-day count of rebalancing events                          |
| `days_since_rebalance` | Days since the last rebalancing event within the open position |
| `ltv_lag_1` / `ltv_lag_3` / `ltv_lag_7` | LTV lagged by 1, 3, and 7 days             |
| `coll_*` / `debt_*` | One-hot identity of collateral and borrow token (market)          |
| `ybt_apy`         | Annualised yield on the collateral token (DeFiLlama)                |
| `supply_rate`     | Annualised Aave supply rate earned on the collateral aToken         |
| `borrow_rate`     | Annualised variable borrow rate on the debt token (USDT or USDe)    |
| `carry_spread`    | `ybt_apy + supply_rate − borrow_rate`, the per-loop carry spread    |
| `carry_spread_levered` | `carry_spread × loop_depth`, the spread scaled by recursion    |
