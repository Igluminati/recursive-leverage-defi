# Whale Identification - Recursive Leverage in Yield-Bearing Stablecoins

Part of the Master's Project by Igli Kristo & Dawid Rymarczyk
University of Zurich, 2026

---

## What this does

Identifies the top 10 holders per protocol (Aave v3, Morpho Blue) for each of the
three yield-bearing stablecoins under study, filtered to addresses that have
actively engaged in looping or flashloan strategies:

| Token       | Protocol       | Contract Address                             |
|-------------|----------------|----------------------------------------------|
| sUSDe       | Ethena         | `0x9D39A5DE30e57443BfF2A8307A4256c8797A3497` |
| sUSDS       | Sky            | `0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD` |
| syrupUSDC   | Maple Finance  | `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` |

Pipeline:
1. Query top holders per token per protocol from Dune Analytics (ERC-20 Transfer events), filtered to addresses that have actively looped or used flashloans on Aave v3 or Morpho Blue
2. Flag each address as EOA or contract via `eth_getCode` RPC check (`== "0x"`)
3. Output final ranked whale list per token as CSV, ranked per protocol by `total_received`

### Looper definition
An address is flagged as a looper if it has:
- **Aave v3** — supplied sUSDe at least once AND borrowed any asset at least 3 times
- **Morpho Blue** — supplied any collateral at least once AND borrowed any asset at least 3 times

### Flashloaner definition
An address is flagged as a flashloaner if it has executed flashloans in at least 3 separate transactions on the respective protocol.

### Known entity exclusions
Addresses labelled in Dune's `labels.addresses` table under categories `dex`, `infrastructure`, `dao`, `institution`, or `cex users` are excluded. The `contracts` category is intentionally kept — private strategy contracts are valid research subjects.

---

## Dune Queries

Each token has two saved Dune queries — one per protocol:

| Token | Protocol | Dune Query |
|-------|----------|------------|
| sUSDe | Aave v3 | https://dune.com/queries/7349560 |
| sUSDe | Morpho Blue | https://dune.com/queries/7344848 |

---

## Sample SQL on Morpho Blue sUSDe -> Dune

```sql
-- transfers: collect all inbound (+) and outbound (-) sUSDe transfer events per address
WITH transfers AS (
    SELECT "to" AS address, value AS amount
    FROM erc20_ethereum.evt_Transfer
    WHERE contract_address = 0x9D39A5DE30e57443BfF2A8307A4256c8797A3497
    UNION ALL
    SELECT "from" AS address, -value AS amount
    FROM erc20_ethereum.evt_Transfer
    WHERE contract_address = 0x9D39A5DE30e57443BfF2A8307A4256c8797A3497
),
-- balances: reconstruct current balance and lifetime inflow per address from transfer history
balances AS (
    SELECT
        address,
        SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) / POWER(10, 18) AS total_received,
        SUM(amount) / POWER(10, 18) AS current_balance
    FROM transfers
    WHERE address != 0x0000000000000000000000000000000000000000
    GROUP BY address
    HAVING SUM(amount) > 0
),
-- supply_counts: addresses that have supplied collateral on Morpho at least once
supply_counts AS (
    SELECT caller AS address
    FROM morpho_blue_ethereum.MorphoBlue_evt_SupplyCollateral
    GROUP BY caller
    HAVING COUNT(DISTINCT evt_tx_hash) >= 1
),
-- borrow_counts: addresses that have borrowed on Morpho at least 3 separate times
borrow_counts AS (
    SELECT caller AS address
    FROM morpho_blue_ethereum.MorphoBlue_evt_Borrow
    GROUP BY caller
    HAVING COUNT(DISTINCT evt_tx_hash) >= 3
),
-- loopers: addresses that appear in both supply_counts and borrow_counts
loopers AS (
    SELECT s.address
    FROM supply_counts s
    INNER JOIN borrow_counts b ON s.address = b.address
),
-- flashloaners: addresses that have executed flashloans in at least 3 separate transactions
flashloaners AS (
    SELECT caller AS address
    FROM morpho_blue_ethereum.MorphoBlue_evt_FlashLoan
    GROUP BY caller
    HAVING COUNT(DISTINCT evt_tx_hash) >= 3
),
-- known_entities: labelled addresses to exclude (DEXes, infrastructure, DAOs, institutions, CEX users)
known_entities AS (
    SELECT DISTINCT address
    FROM labels.addresses
    WHERE blockchain = 'ethereum'
      AND category IN ('dex', 'infrastructure', 'dao', 'institution', 'cex users')
)
SELECT
    b.address,
    b.current_balance,
    b.total_received,
    ROW_NUMBER() OVER (ORDER BY b.total_received DESC) AS rank,
    CASE WHEN l.address IS NOT NULL THEN true ELSE false END AS is_looper,
    CASE WHEN f.address IS NOT NULL THEN true ELSE false END AS is_flashloaner,
    CASE
        WHEN l.address IS NOT NULL AND f.address IS NOT NULL THEN 'both'
        WHEN l.address IS NOT NULL THEN 'looper'
        WHEN f.address IS NOT NULL THEN 'flashloaner'
    END AS strategy_type
FROM balances b
LEFT JOIN loopers l ON b.address = l.address
LEFT JOIN flashloaners f ON b.address = f.address
LEFT JOIN known_entities k ON b.address = k.address
WHERE (l.address IS NOT NULL OR f.address IS NOT NULL)
  AND k.address IS NULL
ORDER BY b.total_received DESC
LIMIT 10
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
RPC_URL=https://mainnet.infura.io/v3/your_key   # or Alchemy
```

---

## Usage

Run the script:
```bash
uv run main.py
```

Output is saved to `<token_symbol>_whales.csv`

---

## Output format

Each CSV contains:

| Column            | Description                                                  |
|-------------------|--------------------------------------------------------------|
| `rank`            | Rank within protocol by `total_received` descending          |
| `address`         | Wallet address                                               |
| `current_balance` | Current token balance                                        |
| `total_received`  | Lifetime cumulative inflow of token                          |
| `is_eoa`          | True if EOA, False if smart contract                         |
| `is_looper`       | Supplied collateral + borrowed 3+ times on Aave v3 or Morpho |
| `is_flashloaner`  | Executed flashloans in 3+ separate txs on Aave v3 or Morpho  |
| `strategy_type`   | `looper`, `flashloaner`, or `both`                           |
| `protocol`        | `Aave` or `Morpho`                                           |

---

## Notes

- Balances reconstructed from ERC-20 Transfer events via Dune Analytics
- Both EOAs and smart contracts are included — `is_eoa` column distinguishes them
- In practice all identified whales are smart contracts given the scale and complexity of looping strategies
- `total_received` is used for ranking rather than `current_balance` — it captures historical activity including addresses that have fully exited positions
- `total_received` includes all inbound transfers so slightly overstates pure looping volume
- Each protocol returns its own top 10 ranked independently
- Balances may be slightly stale depending on Dune's indexing lag

---

## Project structure

```
whales/
├── .env                       # secrets - gitignored
├── .env.example               # correct look of .env
├── .python-version            # python 3.11
├── pyproject.toml             # dependencies via uv
├── uv.lock
├── main.py                    # script
├── <token_symbol>_whales.csv  # output CSVs land here
```