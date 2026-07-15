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
├── bot/                   # Proof-of-concept leverage/looping scripts
├── data/                  # Data collection and pipeline scripts
├── feature_engineering/   # Panel / feature pipeline
├── analysis/              # Jupyter notebooks (each subfolder has its own uv env)
│   ├── whale-archetypes/
│   ├── whale-risk-supervised/
│   └── meta-archetypes/
└── paper/                 # LaTeX write-up (Overleaf sync)
```

---

## Getting Started

Each `analysis/*` folder is a self-contained [uv](https://docs.astral.sh/uv/) project
(its own `pyproject.toml` and `.venv`). Install uv once, then `cd` into the folder
that owns the notebook you want:

```bash
cd analysis/<folder>
uv sync                 # create the .venv from pyproject.toml
uv run jupyter lab      # open that folder's notebooks
```

`uv run` uses that folder's own `.venv` — no `source .venv/bin/activate` needed.

### Notebooks

| Folder | Notebooks |
|--------|-----------|
| `analysis/whale-archetypes/` | `01_eda_panel.ipynb`, `02_hdbscan_clustering.ipynb`, `03_balanced_clustering.ipynb` |
| `analysis/whale-risk-supervised/` | `01_eda_stress_threshold.ipynb`, `02_model_rebalancing.ipynb`, `03_model_stressed.ipynb` |
| `analysis/meta-archetypes/` | `meta_archetypes.ipynb` |

Examples:

```bash
cd analysis/whale-archetypes && uv sync && uv run jupyter lab
cd analysis/whale-risk-supervised && uv sync && uv run jupyter lab
cd analysis/meta-archetypes && uv sync && uv run jupyter lab
```

Headless run of one notebook (from inside its folder):

```bash
uv run jupyter nbconvert --to notebook --execute --inplace <notebook>.ipynb
```

Don't have uv? Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

