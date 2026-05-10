# Whale Identification - Recursive Leverage in Yield-Bearing Stablecoins

Part of the Master's Project by Igli Kristo & Dawid Rymarczyk
University of Zurich, 2026

---

## What this does

Identifies the top addresses per token per protocol that have actively engaged
in looping or flashloan strategies, ranked by lifetime token volume (`total_received`).

| Token     | Issuer        | Address                                      | Decimals |
|-----------|---------------|----------------------------------------------|----------|
| sUSDe     | Ethena        | `0x9D39A5DE30e57443BfF2A8307A4256c8797A3497` | 18       |
| sUSDS     | Sky           | `0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD` | 18       |
| syrupUSDC | Maple Finance | `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` | 6        |

### Protocol coverage

| Token     | Aave v3 | Morpho Blue | SparkLend |
|-----------|---------|-------------|-----------|
| sUSDe     | ✅       | ✅           | ❌         |
| sUSDS     | ❌       | ✅           | ✅         |
| syrupUSDC | ❌       | ✅           | ❌         |

sUSDS is absent from Aave v3 — Sky operates its own native lending protocol (SparkLend)
and never pursued an Aave listing.

### Pipeline

1. Run Dune SQL queries per token per protocol (ERC-20 Transfer events + protocol events)
2. Flag each address as EOA or contract via `eth_getCode` RPC check (`== "0x"`)
3. Output ranked whale list per token per protocol as CSV

---

## Strategy definitions

**Looper** — supplied the token as collateral at least once AND borrowed any asset
at least 3 times on the same protocol.

**Flashloaner** — executed flashloans in at least 3 separate transactions on the
respective protocol.

---

## Dune Queries

| Token     | Protocol    | Dune Query                       |
|-----------|-------------|----------------------------------|
| sUSDe     | Aave v3     | https://dune.com/queries/7349560 |
| sUSDe     | Morpho Blue | https://dune.com/queries/7344848 |
| sUSDS     | Morpho Blue | https://dune.com/queries/7367663 |
| sUSDS     | SparkLend   | https://dune.com/queries/7368059 |
| syrupUSDC | Morpho Blue | https://dune.com/queries/7367806 |

---

## Implementation notes

### Morpho Blue — market-scoped filtering

sUSDS and syrupUSDC looping is concentrated in specific markets. Unlike sUSDe which
dominates Morpho activity protocol-wide, these tokens require filtering
`SupplyCollateral` and `Borrow` events to their specific market IDs:

**sUSDS markets:**

| Market       | Market ID                                                            |
|--------------|----------------------------------------------------------------------|
| sUSDS / USDT | `0x3274643db77a064abd3bc851de77556a4ad2e2f502f4f0c80845fa8f909ecf0b` |
| sUSDS / AUSD | `0x09cf702bb8b6fe8c6effb6021744e365f598b89bc28f3ea7cd6c55115af825df` |

**syrupUSDC markets:**

| Market            | Market ID                                                            |
|-------------------|----------------------------------------------------------------------|
| syrupUSDC / USDC  | `0x729badf297ee9f2f6b3f717b96fd355fc6ec00422284ce1968e76647b258cf44` |
| syrupUSDC / AUSD  | `0xab3196447663a41382ba4b4d55eab3fa702ee2cf071db224fd72492953040056` |
| syrupUSDC / PYUSD | `0xc9629945524f3fde56c7e8854a6c3d48e76b9d97236abbe73c750fcc7aeb8501` |
| syrupUSDC / RLUSD | `0xc0ae375fd761ff19b3f04de5534c0f1ec110f80e1c2ede27c42c1c43c3040394` |

Flashloan detection remains protocol-wide in all cases.

### Exclusions

Addresses in Dune's `labels.addresses` under `dex`, `infrastructure`, `dao`,
`institution`, or `cex users` are excluded. The `contracts` category is kept, because
private strategy contracts are valid research subjects.

The following Morpho infrastructure contract is excluded manually as it aggregates
transactions from many end users rather than representing an independent strategy actor:

| Contract              | Address                                      |
|-----------------------|----------------------------------------------|
| Morpho ETH Bundler V2 | `0x4095f064b8d3c3548a3bebfd0bbfd04750e30077` |

### SparkLend

SparkLend tables are under the `spark_protocol_multichain` namespace in Dune,
filtered with `chain = 'ethereum'`. In practice only loopers are identified for
sUSDS on SparkLend, no flashloaners were found.


## Setup

### Requirements

- Python 3.11 (see `.python-version`)
- [uv](https://github.com/astral-sh/uv) for dependency management

```bash
uv sync
```

### Environment variables

```
DUNE_API_KEY=your_dune_api_key
RPC_URL=https://mainnet.infura.io/v3/your_key   # or Alchemy
```

---

## Usage

```bash
uv run main.py
```

Output is saved to `<token_symbol>_<protocol>_whales.csv`

---

## Output format

| Column              | Description                                                                 |
|---------------------|-----------------------------------------------------------------------------|
| `rank`              | Rank within protocol by `total_received` descending                         |
| `address`           | Wallet address                                                               |
| `current_balance`   | Current token balance                                                        |
| `total_received`    | Lifetime cumulative inflow of token                                          |
| `distinct_funders`  | Number of distinct addresses that sent the token to this address (excl. mints); 0 means self-minted only |
| `is_eoa`            | True if EOA, False if smart contract                                         |
| `is_looper`         | Supplied collateral + borrowed 3+ times                                      |
| `is_flashloaner`    | Executed flashloans in 3+ separate transactions                              |
| `strategy_type`     | `looper`, `flashloaner`, or `both`                                           |
| `protocol`          | `Aave`, `Morpho`, or `Spark`                                                 |

---

## Notes

- Balances reconstructed from ERC-20 Transfer events via Dune Analytics
- `total_received` is used for ranking — it captures historical activity including
  addresses that have fully exited positions and slightly overstates pure looping volume
- In practice all identified whales are smart contracts given the scale and complexity
  of looping strategies — `is_eoa` column distinguishes them
- Balances may be slightly stale depending on Dune's indexing lag
- `distinct_funders = 0` indicates all inflows arrived via minting (from the zero address),
  which is excluded from the count by design; such addresses are self-funded single operators

---

## Project structure

```
whales/
├── .env                          # secrets - gitignored
├── .env.example
├── .python-version               # python 3.11
├── pyproject.toml
├── uv.lock
├── main.py
├── <token>_<protocol>_whales.csv # output CSVs land here
```