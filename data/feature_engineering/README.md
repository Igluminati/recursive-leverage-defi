# Recursive Leverage Feature Engineering

## Pipeline

```
collect_events.py → build_panel.py → build_prices.py → build_features.py
                                                      ↘ aave/health_factor.py (W-3, optional)
                                                         → re-runs merge into daily_features.csv
```

### Step 1: collect_events.py

Pulls raw on-chain events from Dune Analytics CSV exports. Events collected: supply, withdraw, borrow, repay.

Filter rule: only keep supply/withdraw of the whale's YBS collateral token, and borrow/repay of configured stablecoins. Everything else (cbBTC borrows) is dropped.

Output: `data/panel_raw_events.csv`

### Step 2: build_panel.py

Reconstructs daily position state from raw events using cumulative sums.

```
collateral_balance[day] = cumsum(supply - withdraw) up to that day
borrow_balance[day]     = cumsum(borrow - repay) up to that day
```

Days with no events inherit the previous day's balance. One row per `(whale_id, date, collateral_token, borrow_token)` combination  W-3 has two collateral tokens (sUSDe and USDe) and two borrow tokens (USDC and USDe), producing 4 rows per day.

Output: `data/daily_panel.csv`

### Step 3: build_prices.py

Fetches daily USD prices from DefiLlama for all tokens in the panel. Prices are forward-filled to handle gaps. Merges prices onto the panel and computes USD balances.

Output: `data/daily_panel_usd.csv`

### Step 4: build_features.py

Aggregates the panel to one row per `(whale_id, date)` and computes features.

Aggregation: sum `collateral_balance_usd` across all collateral tokens, sum `borrow_balance_usd` across all borrow tokens (deduplicated to avoid double-counting).

Current features:
- `collateral_balance_usd` — total USD value of collateral (from events)
- `borrow_balance_usd` — total USD value of debt (from events)
- `ltv` — loan-to-value ratio (borrow / collateral), **simplified** (not Aave health factor)
- `health_factor`, `collateral_balance_usd_aave`, `borrow_balance_usd_aave` — **W-3 only**, after HF script runs

Output: `data/daily_features.csv`

### Step 4b (W-3 only): build_aave_health_factor.py

Fetches **on-chain Aave v3 health factor** per day for W-3 via `Pool.getUserAccountData` at end-of-day blocks.

```bash
uv run src/aave/health_factor.py
```

Output: `data/w3_aave_health_factor.csv` (includes `health_factor`, protocol collateral/debt USD, and panel `ltv` for comparison).

Requires an **archive** Ethereum RPC (~198 historical `eth_call`s). Block numbers are cached in `data/w3_eod_block_cache.csv`.

No liquidations occurred for any whale in our event export.

## Data notes
- W-3 supplies both sUSDe and USDe as collateral on Aave
- For liquidation analysis on W-3, use **health factor**, not panel `ltv` alone