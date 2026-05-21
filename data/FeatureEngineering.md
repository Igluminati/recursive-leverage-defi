# Feature Engineering

## How we build the panel

### Step 1: collect raw events per whale

For W-2 and W-3: `collect_events.py` queries The Graph endpoints directly.

For W-1, W-4, W-5: Dune SQL queries exported as CSV and merged in `collect_events.py`.

Events collected from Aave v3 and SparkLend:
- Supply (collateral deposited)
- Withdraw (collateral removed)
- Borrow (debt taken)
- Repay (debt repaid)
- LiquidationCall (position liquidated)

Events collected from Morpho Blue:
- SupplyCollateral (collateral deposited)
- WithdrawCollateral (collateral removed)
- Borrow (debt taken)
- Repay (debt repaid)
- Liquidate (position liquidated)

Each event record includes: `whale_id`, `protocol`, `event_type`, `block_number`,
`timestamp`, `tx_hash`, `asset`, `amount_raw`, `amount`, `market_id`.

### Step 2: reconstruct daily position state

From the raw events we compute a running balance for each day using forward-fill:

```
collateral_balance[day] = sum of all Supply/SupplyCollateral amounts
                          minus sum of all Withdraw/WithdrawCollateral amounts
                          up to and including that day

borrow_balance[day]     = sum of all Borrow amounts
                          minus sum of all Repay amounts
                          up to and including that day
```

Days with no events inherit the previous day's balance. The panel starts on the
whale's first transaction date and ends on its last active date.

### Step 3: convert balances to USD

We multiply the collateral balance by the daily YBT price from DeFiLlama to get
`collateral_usd`. The borrow assets (USDtb, PYUSD) are stablecoins pegged to $1,
so we use the borrow balance directly as `borrow_usd`.

### Step 4: join all features

We join the daily position state with APY, borrow rate, and static features to
produce one row per whale per day with all eight features filled in.

---

## The eight features

### F1: LTV ratio

LTV is the ratio of outstanding borrow to collateral value on a given day.

```
ltv[day] = borrow_usd[day] / collateral_usd[day]
```

LTV is 0 on days before the first borrow and set to NaN on days where
`collateral_usd` is 0 to avoid dividing by zero.

Difficulty: easy.

---

### F2: Loop depth

Loop depth is the number of recursive supply-borrow cycles stacked in the position.
We estimate it per transaction and then take the daily maximum.

How we compute it:

1. Group all events by `tx_hash`.
2. Within each transaction, count the number of (SupplyCollateral, Borrow) pairs.
3. `loop_depth` for the day equals the maximum across all transactions that day.
4. On days with no transactions we carry forward the previous day's value.

Protocol-specific notes:

**W-1 (InstaDApp DSA, Morpho Blue):** each Cast transaction executes one step.
We count supply and borrow event pairs within each Cast using the Dune decoded
event tables.

**W-2 (manual Safe, SparkLend):** each Exec Transaction submits one action at a
time, no bundling. Loop depth increments by one transaction per day as the
position is built up.

**W-3 (manual Safe, Aave v3):** most complex case. Each Exec Transaction can bundle
multiple DeFi actions into a single on-chain call. Primary approach uses Dune:

```sql
WITH supply_events AS (
    SELECT evt_tx_hash, evt_block_time, COUNT(*) AS supply_count
    FROM aave_v3_ethereum.Pool_evt_Supply
    WHERE onBehalfOf = 0xea03e659a2e59c3715c6517afe58541be162161a
    GROUP BY evt_tx_hash, evt_block_time
),
borrow_events AS (
    SELECT evt_tx_hash, COUNT(*) AS borrow_count
    FROM aave_v3_ethereum.Pool_evt_Borrow
    WHERE onBehalfOf = 0xea03e659a2e59c3715c6517afe58541be162161a
    GROUP BY evt_tx_hash
)
SELECT
    s.evt_tx_hash,
    DATE(s.evt_block_time) AS date,
    LEAST(s.supply_count, COALESCE(b.borrow_count, 0)) AS loop_depth_tx
FROM supply_events s
LEFT JOIN borrow_events b ON s.evt_tx_hash = b.evt_tx_hash
ORDER BY s.evt_block_time
```

**W-4 and W-5 (custom contracts, Morpho Blue):** each transaction is one explicit
step (Deposit, Borrow, Repay, Withdraw Supply as separate transactions). Loop depth
is directly countable from the event sequence.

Difficulty: hard.

---

### F3: Distance to liquidation

```
distance_to_liq[day] = liquidation_threshold minus ltv[day]
```

Liquidation thresholds by whale (verified on-chain via Dune):

| Whale | Protocol | Market | Liquidation threshold | Dune query |
|-------|----------|--------|-----------------------|------------|
| W-1 | Morpho Blue | sUSDe/USDtb | 91.5% LLTV | https://dune.com/queries/7514266 |
| W-2 | SparkLend | sUSDS | 80% LT | SparkLend Ethereum Liquidation Threshold — sUSDS |
| W-3 | Aave v3 | sUSDe | 75% LT | Aave v3 Ethereum Liquidation Threshold — sUSDe |
| W-4 | Morpho Blue | sUSDe/PYUSD | 91.5% LLTV | https://dune.com/queries/7514377 |
| W-5 | Morpho Blue | syrupUSDC/PYUSD | 91.5% LLTV | https://dune.com/queries/7514403 |

Note: the original feature engineering doc had incorrect thresholds (86% for Morpho,
77% for SparkLend, 72% for Aave). All values were verified directly from on-chain
events via Dune before hardcoding.

Difficulty: easy, once LTV is computed this is just subtraction.

---

### F4: Rebalancing events

Binary flag: did any position-changing transaction happen on a given day.

```
rebalancing[day] = 1 if any Supply, Withdraw, Borrow, or Repay event occurred that day
rebalancing[day] = 0 otherwise
```

This feature is also the target variable y for the RQ3 XGBoost classifier.

Difficulty: easy.

---

### F5: Carry spread

```
carry_spread[day] = ybt_apy[day] minus borrow_rate[day]
```

Both expressed as annualised percentages. YBT APY from DeFiLlama. Borrow rate
from The Graph per protocol (variableBorrowRate for Aave/Spark, borrowRate for
Morpho). For W-4 and W-5 (PYUSD market) we verify subgraph availability first;
fallback uses Dune AccrueInterest events if needed.

Difficulty: moderate.

---

### F6: Protocol concentration

```
protocol_concentration[day] = collateral on primary protocol / total collateral across all protocols
```

All five whales operate on a single protocol so this equals 1.0 for every
whale-day. Kept for completeness, will be dropped as zero-variance in ML.

Difficulty: easy.

---

### F7: Known automation

Removed from the panel. Originally defined as a binary flag indicating whether a
whale uses external automation infrastructure. Dropped because:

- Only W-1 would have value 1, making it perfectly collinear with `whale_id = W-1`
- The behavioral patterns captured by LTV, rebalancing frequency, and loop depth
  already implicitly encode the automation distinction
- It was manually assigned rather than derived from data, risking leakage in ML models

---

### F8: Liquidation history

Binary flag: has this whale ever been liquidated.

```
ever_liquidated = 1 if any LiquidationCall or Liquidate event exists for this address
```

All five whales confirmed unliquidated via Dune and The Graph event queries.
This feature is 0 for all whales and will be dropped as zero-variance in ML.

Difficulty: easy.

---

## Feature summary table

| Feature | Type | Source | Difficulty | RQ1 | RQ2 | RQ3 |
|---------|------|--------|------------|-----|-----|-----|
| F1: LTV ratio | time series (float) | The Graph + DeFiLlama | easy | yes | yes | yes |
| F2: Loop depth | time series (int) | The Graph + Dune | hard | yes | yes | yes |
| F3: Distance to liquidation | time series (float) | derived from F1 + static | easy | yes | yes | yes |
| F4: Rebalancing events | time series (binary) | The Graph / Dune | easy | yes | yes | yes, target |
| F5: Carry spread | time series (float) | DeFiLlama + The Graph | moderate | yes | yes | yes |
| F6: Protocol concentration | static (float) | derived from metadata | easy | yes | no | no |
| ~~F7: Known automation~~ | ~~static (binary)~~ | ~~removed~~ | — | — | — | — |
| F8: Liquidation history | static (binary) | The Graph / Dune | easy | yes | yes | no |

F6 and F8 are constant across all five whales and will be excluded from ML model
inputs. F7 (known automation) was removed entirely — see F7 section above.

---

## Panel schema

The final panel is saved as a CSV with these columns:

| Column | Type | Description |
|--------|------|-------------|
| `whale_id` | string | W-1 through W-5 |
| `address` | string | Wallet address |
| `token` | string | sUSDe, sUSDS, or syrupUSDC |
| `protocol` | string | Aave, Morpho, or Spark |
| `date` | date | Calendar day (YYYY-MM-DD) |
| `collateral_balance` | float | Raw token units |
| `collateral_usd` | float | USD value |
| `borrow_balance` | float | Raw token units (stablecoin) |
| `borrow_usd` | float | USD value |
| `ltv` | float | F1, LTV ratio |
| `loop_depth` | int | F2, loop depth (forward-filled) |
| `distance_to_liq` | float | F3, distance to liquidation threshold |
| `rebalancing` | int | F4, rebalancing event flag (0 or 1) |
| `carry_spread` | float | F5, annualised carry spread in percent |
| `protocol_concentration` | float | F6, always 1.0 in current sample |
| `ever_liquidated` | int | F8, liquidation history flag (0 or 1) |
| `ybt_apy` | float | Raw YBT APY from DeFiLlama in percent |
| `borrow_rate` | float | Raw borrow rate from protocol in percent |
| `liq_threshold` | float | Verified on-chain liquidation threshold (0.915 / 0.80 / 0.75) |
| `price_usd` | float | Daily YBT price used for collateral USD conversion |

---

## Engineering notes

### Loop depth edge cases

W-4 and W-5 build positions step by step across multiple transactions — loop depth
increments by one each time a Deposit+Borrow pair is added. W-1 also operates
step by step but each Cast transaction is one action (supply OR borrow), so pairs
must be inferred from adjacent events.

We forward-fill loop depth only while `collateral_balance > 0`. After the position
is fully closed we reset loop depth to 0.

### PYUSD borrow rate fallback for W-4 and W-5

If the Morpho Blue subgraph does not expose historical `borrowRate` for the PYUSD
markets, we reconstruct it from Dune using AccrueInterest events:

```sql
SELECT
    DATE(evt_block_time) AS date,
    AVG(CAST(newBorrowRate AS DOUBLE)) / 1e18 * 365 AS borrow_rate_annualised
FROM morpho_blue_ethereum.MorphoBlue_evt_AccrueInterest
WHERE id = 0x<pyusd_market_id>
GROUP BY DATE(evt_block_time)
ORDER BY date
```

### Class imbalance for RQ3

| Whale | Total days | Rebalancing days | Positive rate |
|-------|------------|------------------|---------------|
| W-1 | 97 | 53 | 55% |
| W-2 | 548 | 58 | 11% |
| W-3 | 268 | 257 | 96% |
| W-4 | 60 | 24 | 40% |
| W-5 | 65 | 46 | 71% |

W-3 at 96% positive rate is the main imbalance problem. Mitigations:
1. Downsample W-3 to ~55% positive rate before pooling with W-1
2. Apply per-sample weights (1 / positive rate) so W-3 days do not overpower W-1
3. Evaluate on F1-score not accuracy

---

## Output files

| File | Description |
|------|-------------|
| `data/panel_raw_events.csv` | All raw events per whale before aggregation (merged from Graph + Dune) |
| `data/morpho_w1_events.csv` | Dune export for W-1 |
| `data/morpho_w4_events.csv` | Dune export for W-4 |
| `data/morpho_w5_events.csv` | Dune export for W-5 |
| `data/panel_daily.csv` | Final wallet-token-day panel with all 8 features |
| `data/panel_train.csv` | W-1 + W-3 rows for RQ3 training |
| `data/panel_validation.csv` | W-2 + W-4 + W-5 rows for RQ3 out-of-sample validation |

---

## Project structure

```
feature_engineering/
├── src/
│   ├── collect_events.py       # The Graph queries for W-2 and W-3; merges Dune CSVs for W-1/W-4/W-5
│   ├── build_panel.py          # Reconstruct daily balances, join features
│   ├── compute_loop_depth.py   # Transaction-level loop counting (F2)
│   ├── fetch_apy.py            # DeFiLlama APY fetch
│   └── fetch_borrow_rates.py   # The Graph borrow rate queries per protocol
├── data/
│   ├── morpho_w1_events.csv    # Dune export, W-1
│   ├── morpho_w4_events.csv    # Dune export, W-4
│   ├── morpho_w5_events.csv    # Dune export, W-5
│   ├── panel_raw_events.csv    # merged output
│   ├── panel_daily.csv         # main panel output
│   ├── panel_train.csv         # RQ3 training set
│   └── panel_validation.csv    # RQ3 validation set
├── .env                        # GRAPH_API_KEY, DUNE_API_KEY
├── .env.example
├── pyproject.toml
└── README.md
```