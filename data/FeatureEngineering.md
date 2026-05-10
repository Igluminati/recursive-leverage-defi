# Feature Engineering

Part of the Master's Project by Igli Kristo & Dawid Rymarczyk
University of Zurich, 2026

---

## What this document covers

This document explains how we build the wallet-token-day panel and how we define and compute each of the eight features used in the ML pipeline. The panel is the central data structure for all three research questions.

One row in the panel equals one whale, one token, and one calendar day. The panel starts on the date of each whale's first transaction and ends on the date of its last activity, or the data collection cutoff, whichever comes first. All six whales defined in README.md are in scope.

---

## Where the data comes from

| Source | What it gives us | How to access it |
|--------|-----------------|--------------|
| The Graph, Aave v3 | Supply, borrow, repay, withdraw, and liquidation events; historical variable borrow rates per reserve | GraphQL: `https://api.thegraph.com/subgraphs/name/aave/protocol-v3` |
| The Graph, Morpho Blue | SupplyCollateral, Borrow, Repay, WithdrawCollateral, Liquidate events; borrow rate per market | GraphQL: `https://api.thegraph.com/subgraphs/name/morpho-association/morpho-blue` |
| The Graph, SparkLend | Same event structure as Aave v3, under the spark_protocol_multichain namespace | GraphQL: `https://api.thegraph.com/subgraphs/name/marsfoundation/sparklend-mainnet` |
| DeFiLlama Yields API | Daily APY per token (sUSDe, sUSDS, syrupUSDC) | REST: `https://yields.llama.fi/chart/{pool_id}`, already collected by the ybt/ scraper |
| Dune Analytics | ERC-20 transfer events for cross-checking balances | SQL queries, already used in the whale identification pipeline |
| Static / manual | Liquidation thresholds per market; automation flags per whale | Hardcoded from Etherscan analysis and protocol documentation |

Each whale pulls from a different GraphQL source depending on which protocol it uses:

| Whale | Token | Protocol | GraphQL source |
|-------|-------|----------|---------------|
| W-1 | sUSDe | Morpho Blue | The Graph, Morpho Blue |
| W-2 | sUSDe | Aave v3 | The Graph, Aave v3 |
| W-3 | sUSDS | SparkLend | The Graph, SparkLend |
| W-4 | sUSDe | Aave v3 | The Graph, Aave v3 |
| W-5 | sUSDe | Morpho Blue | The Graph, Morpho Blue |
| W-6 | syrupUSDC | Morpho Blue | The Graph, Morpho Blue |

---

## How we build the panel

### Step 1: collect raw events per whale

For each whale we query all position-relevant events from the appropriate GraphQL endpoint, filtered by wallet address and, for Morpho, by market ID.

Events we collect from Aave v3 and SparkLend:
- Supply (collateral deposited)
- Withdraw (collateral removed)
- Borrow (debt taken)
- Repay (debt repaid)
- LiquidationCall (position liquidated)

Events we collect from Morpho Blue:
- SupplyCollateral (collateral deposited)
- WithdrawCollateral (collateral removed)
- Borrow (debt taken)
- Repay (debt repaid)
- Liquidate (position liquidated)

Each event record includes block_number, block_timestamp, tx_hash, amount, and asset.

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

Days with no events inherit the previous day's balance. The panel starts on the whale's first transaction date and ends on its last active date.

### Step 3: convert balances to USD

We multiply the collateral balance by the daily YBT price from DeFiLlama to get collateral_usd. The borrow assets (USDC, USDT, USDe, USDtb, PYUSD) are all stablecoins pegged to $1, so we use the borrow balance directly as borrow_usd.

### Step 4: join all features

We join the daily position state with APY, borrow rate, and static features to produce one row per whale per day with all eight features filled in.

---

## The eight features

### F1: LTV ratio

LTV is the ratio of outstanding borrow to collateral value on a given day.

```
ltv[day] = borrow_usd[day] / collateral_usd[day]
```

Data comes from The Graph for events and DeFiLlama for the YBT price used to convert collateral to USD. LTV is 0 on days before the first borrow and set to NaN on days where collateral_usd is 0 to avoid dividing by zero. This is the most important time-series feature for both RQ2 and RQ3.

Difficulty: easy.

---

### F2: Loop depth

Loop depth is the number of recursive supply-borrow cycles stacked in the position. We estimate it per transaction and then take the daily maximum.

How we compute it:

1. Group all events by tx_hash.
2. Within each transaction, count the number of (SupplyCollateral, Borrow) pairs. Each pair is one loop leg.
3. loop_depth for that transaction equals the number of such pairs.
4. loop_depth for the day equals the maximum across all transactions that day. On days with no transactions we carry forward the previous day's value.

Data comes from The Graph events grouped by tx_hash. For Gnosis Safe wallets (W-2 and W-4) we also need internal transaction traces, explained below.

Protocol-specific notes:

W-5 and W-6 use purpose-built contracts where each Assemble Background call is one explicit loop leg. Loop depth is directly countable from the method name.

W-1 uses DeFi Saver where each Cast transaction executes one step. We count supply and borrow event pairs within each Cast to get the loop depth.

W-2 and W-4 use Gnosis Safe, which is the most complex case. Each Exec Transaction can bundle multiple DeFi actions into a single on-chain transaction. The Graph event tables return one aggregated result per event type per transaction and do not expose the individual sub-calls inside. To correctly count supply-borrow pairs within a single Safe execution we do the following:

Step 1: fetch internal traces using the Etherscan Trace API (trace_transaction) or the Tenderly API. This decomposes each Exec Transaction into its internal call tree and exposes each individual call to Aave's supply() and borrow() functions.

Step 2: count sequential (supply, borrow) pairs in the call tree targeting the same asset. Each pair equals one loop leg.

Step 3: take the max loop depth across all transactions on that day.

If the trace APIs are unavailable or rate-limited, we fall back to approximating loop depth from the ratio of total collateral supplied to initial capital deposited on the first day of position construction (loop_depth is roughly total_collateral divided by initial_deposit, rounded to the nearest integer). We note this approximation as a limitation in the thesis.

Difficulty: hard. This is the most complex feature to engineer.

---

### F3: Distance to liquidation

This is the gap between the liquidation threshold and the current LTV. A positive value means the position is safe. A negative value means liquidation has occurred.

```
distance_to_liq[day] = liquidation_threshold minus ltv[day]
```

Liquidation thresholds by whale:

| Whale | Protocol | Market | Liquidation threshold |
|-------|----------|--------|-----------------------|
| W-1 | Morpho Blue | sUSDe/USDtb | 86% LLTV |
| W-2 | Aave v3 | sUSDe | 72% LT |
| W-3 | SparkLend | sUSDS | 77% LT |
| W-4 | Aave v3 | sUSDe | 72% LT |
| W-5 | Morpho Blue | sUSDe/PYUSD | 86% LLTV |
| W-6 | Morpho Blue | syrupUSDC/PYUSD | 86% LLTV |

Data comes from F1 plus static hardcoded thresholds from protocol documentation.

Difficulty: easy, once LTV is computed this is just subtraction.

---

### F4: Rebalancing events

This is a binary flag showing whether any position-changing transaction happened on a given day.

```
rebalancing[day] = 1 if any Supply, Withdraw, Borrow, or Repay event occurred that day
rebalancing[day] = 0 otherwise
```

Data comes from The Graph, the same event stream as F1. This feature is also the target variable y for the RQ3 XGBoost classifier.

Difficulty: easy, trivially derived from the event stream.

---

### F5: Carry spread

Carry spread is the net daily yield from the leveraged position: what the collateral earns minus what the debt costs.

```
carry_spread[day] = ybt_apy[day] minus borrow_rate[day]
```

Both are expressed as annualised percentages.

YBT APY comes from the DeFiLlama Yields API, already collected by the ybt/ scraper.

Borrow rate comes from The Graph per protocol:
- Aave v3 and SparkLend: the variableBorrowRate field on the Reserve entity, sampled daily.
- Morpho Blue: the borrowRate field on the Market entity, sampled daily.

One thing to check before starting: W-5 and W-6 borrow PYUSD on Morpho Blue. We need to verify that the Morpho Blue subgraph exposes historical borrowRate for the PYUSD market. If it does not, we reconstruct it from interest accrual events on Dune as a fallback (see the engineering notes section below).

Difficulty: moderate. Requires joining DeFiLlama and The Graph data on date, plus the PYUSD availability check.

---

### F6: Protocol concentration

This is the fraction of the whale's total collateral held on a single protocol versus spread across multiple protocols.

```
protocol_concentration[day] = collateral on primary protocol / total collateral across all protocols
```

In our current sample all six whales operate on a single protocol, so this feature equals 1.0 for every whale-day in the panel. It will not help differentiate archetypes in this sample. We keep it for completeness and in case the sample is expanded later. In the ML pipeline it will be dropped or flagged as a zero-variance feature.

Data source: static, derived from whale metadata, no event query needed.

Difficulty: easy.

---

### F7: Known automation

This is a binary flag showing whether the whale uses external automation infrastructure (DeFi Saver, Gelato, Relend, or similar) for position management.

```
known_automation = 1 if automation infrastructure was detected via Etherscan analysis
known_automation = 0 otherwise
```

Values by whale (constant across all days, set once at panel construction):

| Whale | Value | Evidence |
|-------|-------|----------|
| W-1 | 1 | DeFi Saver Cast method; DeFi Saver Fee Receiver appears in transfers |
| W-2 | 1 | Gelato: Executor and Relend Network: Deployer are callers |
| W-3 | 0 | Sole caller is the deployer only, no automation contracts detected |
| W-4 | 0 | Sole caller is the deployer only, no automation contracts detected |
| W-5 | 0 | Sole caller is the deployer only, no automation contracts detected |
| W-6 | 0 | Sole caller is the deployer only, no automation contracts detected |

Data source: static, hardcoded from Etherscan analysis. No pipeline needed.

Difficulty: easy.

---

### F8: Liquidation history

This is a binary flag (with an optional cumulative count) showing whether the whale has ever been liquidated on the protocol under study.

```
ever_liquidated   = 1 if any LiquidationCall or Liquidate event exists for this address
liquidation_count = total number of liquidation events to date
```

Data comes from The Graph, the same event stream as F1. We query LiquidationCall on Aave v3 and SparkLend, and Liquidate on Morpho Blue, filtered to the six whale addresses.

Based on the Etherscan review none of the six whales appear to have been liquidated. We confirm this programmatically. If confirmed, ever_liquidated equals 0 for all whales and this feature becomes a zero-variance constant like F6. We keep it in the panel for completeness.

Difficulty: easy, same query as F1 but filtering on a different event type.

---

## Feature summary table

| Feature | Type | Source | Difficulty | RQ1 | RQ2 | RQ3 |
|---------|------|--------|------------|-----|-----|-----|
| F1: LTV ratio | time series (float) | The Graph + DeFiLlama | easy | yes | yes | yes |
| F2: Loop depth | time series (int) | The Graph | hard | yes | yes | yes |
| F3: Distance to liquidation | time series (float) | derived from F1 + static | easy | yes | yes | yes |
| F4: Rebalancing events | time series (binary) | The Graph | easy | yes | yes | yes, target |
| F5: Carry spread | time series (float) | DeFiLlama + The Graph | moderate | yes | yes | yes |
| F6: Protocol concentration | static (float) | derived from metadata | easy | yes | no | no |
| F7: Known automation | static (binary) | Etherscan / manual | easy | yes | yes | yes |
| F8: Liquidation history | static (binary) | The Graph | easy | yes | yes | no |

F4 (rebalancing events) is both a feature (using lagged values as inputs) and the prediction target for the RQ3 XGBoost classifier.

F6 and F8 are likely to be constant across all six whales in the current sample and will be excluded from ML model inputs. They stay in the panel for documentation purposes.

---

## Panel schema

The final panel is saved as a CSV with these columns:

| Column | Type | Description |
|--------|------|-------------|
| `whale_id` | string | W-1 through W-6 |
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
| `known_automation` | int | F7, automation flag (0 or 1) |
| `ever_liquidated` | int | F8, liquidation history flag (0 or 1) |
| `ybt_apy` | float | Raw YBT APY from DeFiLlama in percent |
| `borrow_rate` | float | Raw borrow rate from protocol in percent |
| `liq_threshold` | float | Hardcoded liquidation threshold for this whale |

---

## Engineering notes

### Loop depth edge cases

If a whale builds a position atomically in a single transaction with multiple legs, loop depth on day 1 will spike to its maximum and stay stable from there. This is expected for W-5 and W-6.

If a whale builds a position iteratively over multiple days (W-2, W-3, W-4), loop depth increments by one per day until the target depth is reached.

We forward-fill loop depth only while collateral_balance is greater than 0. After the position is fully closed we reset loop depth to 0.

### PYUSD borrow rate fallback for W-5 and W-6

If the Morpho Blue subgraph does not expose historical borrowRate for the PYUSD market, we reconstruct it from Dune using AccrueInterest events:

```sql
SELECT
    DATE(evt_block_time) AS date,
    AVG(CAST(newBorrowRate AS DOUBLE)) / 1e18 * 365 AS borrow_rate_annualised
FROM morpho_blue_ethereum.MorphoBlue_evt_AccrueInterest
WHERE id = 0x<pyusd_market_id>
GROUP BY DATE(evt_block_time)
ORDER BY date
```

### How to interpret carry spread

A positive carry spread means the position earns more in YBT yield than it pays in borrow interest. The loop is profitable.

A negative carry spread means the borrow rate exceeds the YBT yield. The operator is losing money on the leverage and has an incentive to unwind or reduce loop depth.

A drop from positive to negative carry spread is a strong candidate predictor for RQ3 rebalancing events and is worth examining closely during SHAP analysis.

### Class imbalance for RQ3

Rebalancing days (F4 = 1) are common for some whales and rare for others. The expected distribution based on transaction counts:

| Whale | Total days | Rebalancing days | Approximate positive rate |
|-------|------------|------------------|--------------------------|
| W-1 | 95 | 53 | 56% |
| W-2 | 269 | 141 | 52% |
| W-3 | 548 | 58 | 11% |
| W-4 | 266 | 257 | 97% |
| W-5 | 58 | 24 | 41% |
| W-6 | 63 | 46 | 73% |

W-4 at 97% is the main problem. If we pool it with W-1 and W-2 as-is, the model will be skewed toward predicting rebalancing on every day. We handle this with three mitigations applied together:

1. Downsample W-4 by randomly sampling its days to reach a roughly 55% positive rate before pooling with W-1 and W-2.
2. Apply per-sample weights using sample_weight = 1 divided by the whale's positive rate, so W-4 days are further down-weighted even after downsampling.
3. Evaluate on F1-score rather than accuracy so the model is not rewarded for always predicting the majority class.

W-3 has been inactive for over a year and its activity happened during a different market regime (2024 versus the 2025 to 2026 period of the training wallets). Lower model performance on W-3 during out-of-sample validation may reflect structural market changes rather than archetype-specific behavior. We acknowledge this as a limitation in the thesis.

---

## Output files

| File | Description |
|------|-------------|
| `panel_raw_events.csv` | All raw events per whale before aggregation |
| `panel_daily.csv` | Final wallet-token-day panel with all 8 features |
| `panel_train.csv` | W-1 plus W-2 plus W-4 rows for RQ3 training |
| `panel_validation.csv` | W-3 plus W-5 plus W-6 rows for RQ3 out-of-sample validation |

---

## Project structure

```
feature_engineering/
├── collect_events.py       # GraphQL queries per whale per protocol
├── build_panel.py          # Reconstruct daily balances, join features
├── compute_loop_depth.py   # Transaction-level loop counting (F2)
├── fetch_apy.py            # DeFiLlama APY fetch (already in ybt/)
├── fetch_borrow_rates.py   # The Graph borrow rate queries per protocol
├── panel_raw_events.csv    # output
├── panel_daily.csv         # output, main panel
├── panel_train.csv         # output, RQ3 training set
└── panel_validation.csv    # output, RQ3 validation set
```