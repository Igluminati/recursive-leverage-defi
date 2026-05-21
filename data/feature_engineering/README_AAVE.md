# Aave Whale Feature Engineering and Data Collection

A pipeline that tracks the W-3 Aave v3 position from on-chain health factor queries.

## Pipeline Steps

**1. health_factor.py**
Fetches on-chain Aave v3 health factor for W-3 via `Pool.getUserAccountData` at end-of-day blocks. Requires an archive Ethereum RPC endpoint (set `RPC_URL` in `.env`). Outputs `w3_aave_health_factor.csv` with:

- **health_factor** — on-chain HF from Aave's `getUserAccountData`
- **total_collateral_usd** — protocol-reported collateral value
- **total_debt_usd** — protocol-reported debt value

```
health_factor = (collateral_value * liquidation_threshold) / debt_value
```

Note: Unlike Morpho, we fetch HF directly from Aave rather than calculating from panel data. This is more accurate as it uses Aave's oracle prices and accounts for aToken interest accrual.

## Data Flow

```
Archive RPC  →  w3_aave_health_factor.csv
```

## Whales Tracked

| ID  | Protocol | Collateral     | Borrow       |
|-----|----------|----------------|--------------|
| W-3 | Aave v3  | sUSDe + USDe   | USDC + USDe  |
