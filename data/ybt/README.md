# YBT Data Collection - Recursive Leverage in Yield-Bearing Stablecoins

Part of the Master's Project by Igli Kristo & Dawid Rymarczyk
University of Zurich, 2026

---

## What this does

Collects metadata and historical event data for the three yield-bearing stablecoins under study:

| Token       | Protocol       | Contract Address                             |
|-------------|----------------|----------------------------------------------|
| sUSDe       | Ethena         | `0x9D39A5DE30e57443BfF2A8307A4256c8797A3497` |
| sUSDS       | Sky            | `0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD` |
| syrupUSDC   | Maple Finance  | `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` |

### Protocol coverage

| Token     | Aave v3 | Morpho Blue | SparkLend |
|-----------|---------|-------------|-----------|
| sUSDe     | Yes     | Yes         | No        |
| sUSDS     | No      | Yes         | Yes       |
| syrupUSDC | No      | Yes         | No        |

sUSDS is absent from Aave v3. Sky operates its own native lending protocol (SparkLend)
and never pursued an Aave listing. syrupUSDC is only active on Morpho Blue.

### Pipeline

1. Load token config from `ybt_metadata.json`
2. Fetch TVL and APY from DeFiLlama Yields API
3. Fetch daily prices from Dune Analytics (for depeg monitoring)
4. Fetch Aave v3 events (sUSDe only) from Dune Analytics
5. Fetch Morpho Blue events (all 3 tokens) from Dune Analytics
6. Fetch SparkLend events (sUSDS only) from Dune Analytics
7. Output metadata as JSON, prices and events as CSV

---

## Dune Queries

| Data | Dune Query |
|------|------------|
| Daily prices | https://dune.com/queries/7359293 |
| Aave v3 events (sUSDe) | https://dune.com/queries/7359302 |
| Morpho Blue events | https://dune.com/queries/7359324 |
| SparkLend events (sUSDS) | https://dune.com/queries/7368610 |

---

## Sample SQL for Aave v3 Events -> Dune

```sql
SELECT 
    'supply' AS event_type,
    evt_block_time AS block_time,
    evt_block_number AS block_number,
    evt_tx_hash AS tx_hash,
    "user",
    onBehalfOf AS on_behalf_of,
    'sUSDe' AS token,
    CAST(amount AS DOUBLE) / 1e18 AS amount
FROM aave_v3_ethereum.Pool_evt_Supply
WHERE reserve = 0x9D39A5DE30e57443BfF2A8307A4256c8797A3497

UNION ALL

SELECT 
    'withdraw' AS event_type,
    evt_block_time,
    evt_block_number,
    evt_tx_hash,
    "user",
    "to" AS on_behalf_of,
    'sUSDe',
    CAST(amount AS DOUBLE) / 1e18
FROM aave_v3_ethereum.Pool_evt_Withdraw
WHERE reserve = 0x9D39A5DE30e57443BfF2A8307A4256c8797A3497

-- ... borrow, repay, liquidation events follow same pattern

ORDER BY block_time DESC
```

---

## Sample SQL for SparkLend Events -> Dune

```sql
SELECT 
    'supply' AS event_type,
    evt_block_time AS block_time,
    evt_block_number AS block_number,
    evt_tx_hash AS tx_hash,
    "user",
    onBehalfOf AS on_behalf_of,
    'sUSDS' AS token,
    CAST(amount AS DOUBLE) / 1e18 AS amount
FROM spark_protocol_multichain.pool_evt_supply
WHERE reserve = 0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD
  AND chain = 'ethereum'

UNION ALL

SELECT 
    'withdraw' AS event_type,
    evt_block_time,
    evt_block_number,
    evt_tx_hash,
    "user",
    "to" AS on_behalf_of,
    'sUSDS',
    CAST(amount AS DOUBLE) / 1e18
FROM spark_protocol_multichain.pool_evt_withdraw
WHERE reserve = 0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD
  AND chain = 'ethereum'

-- ... borrow, repay, liquidation events follow same pattern

ORDER BY block_time DESC
```

Note: SparkLend tables use `spark_protocol_multichain` namespace with `chain = 'ethereum'` filter.

---

## Sample SQL for Morpho Blue Events -> Dune

```sql
SELECT 
    'supply' AS event_type,
    evt_block_time AS block_time,
    evt_block_number AS block_number,
    evt_tx_hash AS tx_hash,
    onBehalf AS on_behalf_of,
    CASE JSON_EXTRACT_SCALAR(marketParams, '$.collateralToken')
        WHEN '0x9D39A5DE30e57443BfF2A8307A4256c8797A3497' THEN 'sUSDe'
        WHEN '0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD' THEN 'sUSDS'
        WHEN '0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b' THEN 'syrupUSDC'
    END AS token,
    CAST(assets AS DOUBLE) / 1e18 AS amount
FROM morpho_blue_ethereum.MorphoBlue_evt_SupplyCollateral
WHERE JSON_EXTRACT_SCALAR(marketParams, '$.collateralToken') IN (
    '0x9D39A5DE30e57443BfF2A8307A4256c8797A3497',
    '0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD',
    '0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b'
)

UNION ALL

SELECT 
    'withdraw' AS event_type,
    evt_block_time,
    evt_block_number,
    evt_tx_hash,
    onBehalf,
    CASE JSON_EXTRACT_SCALAR(marketParams, '$.collateralToken')
        WHEN '0x9D39A5DE30e57443BfF2A8307A4256c8797A3497' THEN 'sUSDe'
        WHEN '0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD' THEN 'sUSDS'
        WHEN '0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b' THEN 'syrupUSDC'
    END,
    CAST(assets AS DOUBLE) / 1e18
FROM morpho_blue_ethereum.MorphoBlue_evt_WithdrawCollateral
WHERE JSON_EXTRACT_SCALAR(marketParams, '$.collateralToken') IN (
    '0x9D39A5DE30e57443BfF2A8307A4256c8797A3497',
    '0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD',
    '0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b'
)

-- ... borrow, repay, liquidation events follow same pattern

ORDER BY block_time DESC
```

---

## Setup

### Requirements
- Python 3.11 (see `.python-version`)
- [uv](https://github.com/astral-sh/uv) for dependency management

### Install dependencies
```bash
uv sync
```

### Environment variables
Create a `.env` file in the project root:
```
DUNE_API_KEY=your_dune_api_key
```

---

## Usage

Run the script:
```bash
uv run main.py
```

Output is saved to:
- `ybt_metadata.json`
- `ybt_prices.csv`
- `aave_events.csv` (sUSDe only)
- `morpho_events.csv` (all 3 tokens)
- `spark_events.csv` (sUSDS only)

---

## Output format

### ybt_metadata.json

| Field | Description |
|-------|-------------|
| `name` | Full token name |
| `protocol` | Issuing protocol |
| `address` | Contract address (Ethereum mainnet) |
| `decimals` | Token decimals |
| `release_date` | Token launch date |
| `tvl_usd` | Total value locked |
| `apy_percent` | Current yield |
| `scraped_at` | Scrape timestamp |

### ybt_prices.csv

| Column | Description |
|--------|-------------|
| `date` | Date (YYYY-MM-DD) |
| `token` | Token symbol |
| `price_usd` | Average daily price |
| `price_low` | Daily low |
| `price_high` | Daily high |

### aave_events.csv / morpho_events.csv / spark_events.csv

| Column | Description |
|--------|-------------|
| `event_type` | `supply`, `withdraw`, `borrow`, `repay`, or `liquidation` |
| `block_time` | Timestamp |
| `block_number` | Block number |
| `tx_hash` | Transaction hash |
| `user` | User address |
| `on_behalf_of` | Beneficiary address |
| `token` | Token symbol |
| `amount` | Amount (human-readable) |

---

## Notes

- DeFiLlama is used for TVL/APY (no API key required)
- Dune is used for prices and events (requires `DUNE_API_KEY`)
- Events data is historical; run once to collect, refresh as needed
- Data may be slightly stale depending on Dune's indexing lag
- Price data rationale: these tokens are stablecoins pegged to ~$1. Price deviations indicate potential depeg events or stress conditions, not normal market volatility. Daily prices are tracked for anomaly detection and correlation with liquidation/rebalancing activity.

---

## Project structure

```
ybt/
├── .env                  # secrets - gitignored
├── .env.example          # correct look of .env
├── .python-version       # python 3.11
├── pyproject.toml        # dependencies via uv
├── uv.lock
├── main.py               # script
├── ybt_metadata.json     # output
├── ybt_prices.csv        # output
├── aave_events.csv       # output (sUSDe)
├── morpho_events.csv     # output (all 3 tokens)
├── spark_events.csv      # output (sUSDS)
```
