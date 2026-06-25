# Recursive Leverage in Yield-Bearing Stablecoins

**Master's Project** · University of Zurich · 2026  
**Authors:** Igli Kristo, Dawid Rymarczyk  
**Supervisor:** Prof. Claudio J. Tessone · **Co-Supervisor:** Krzysztof M. Gogol

---

## What This Project Is About

Some large crypto wallets use a strategy called **looping**: deposit a yield-bearing token as collateral, borrow a stablecoin against it, buy more of the same token, and repeat. This amplifies returns — but also liquidation risk.

This project studies who does this, how, and whether on-chain data can predict when things get risky.

---

## Tokens Studied

- **sUSDe** (Ethena)
- **sUSDS**
- **syrupUSDC** (Maple Finance)

All USD-denominated, on Ethereum mainnet, active on **Aave v3** and **Morpho Blue**.

---

## Research Questions

1. What looping/leverage strategy patterns exist among large holders?
2. What risk characteristics (leverage depth, collateral buffers, rebalancing) separate these patterns?
3. Can on-chain data predict short-term rebalancing and stressed positions?

---

## Approach

| Stage | What |
|---|---|
| **Data collection** | GraphQL (Aave v3, Morpho Blue), Dune Analytics SQL |
| **Proof of concept** | Leverage bot script (with and without flashloans) |
| **Feature engineering** | Wallet–token–day panel: LTV, loop depth, liquidation distance, carry spread, etc. |
| **Unsupervised ML** | HDBSCAN clustering + UMAP visualisation to find strategy archetypes |
| **Supervised ML** | XGBoost classifier to predict stressed risk states, interpreted with SHAP |

---

## Repo Structure

```
├── bot/          # Proof-of-concept leverage/looping scripts
├── data/         # Data collection and pipeline scripts
├── analysis/    # Exploratory analysis
└── paper/       # LaTeX write-up (Overleaf sync)
```

