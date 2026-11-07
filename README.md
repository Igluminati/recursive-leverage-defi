# Recursive Leverage in Yield-Bearing Stablecoins

**Master's Project** · University of Zurich · 2026  
**Authors:** Igli Kristo, Dawid Rymarczyk  
**Supervisor:** Prof. Claudio J. Tessone · **Co-Supervisor:** Krzysztof M. Gogol

**Final report (PDF):** [Recursive Leverage in Yield-Bearing Stablecoins: Proof of Concept and Empirical Analysis](paper/Recursive_Leverage_in_Yield_Bearing_Stablecoins__Proof_of_Concept_and_Empirical_Analysis.pdf)

**Grade:** 5.50 / 6. The findings were published as *How Whales Loop Yield-Bearing Stablecoins, Step by Step* (K. Gogol, D. Rymarczyk, I. Kristo), Stablewatch industry research report, October 2026.

Public repository for the MSc project code, analysis notebooks, and the submitted write-up.

---

## What This Project Is About

Some large crypto wallets use a strategy called **looping**: deposit a yield-bearing token as collateral, borrow a stablecoin against it, buy more of the same token, and repeat. That amplifies yield but also liquidation risk.

We study who does this on Ethereum, whether a small set of shared strategy patterns shows up in on-chain data, how those patterns differ in risk management, and whether position state can flag stressful days before they happen.

---

## Key Findings

- **Data:** a daily panel of the 23 largest leveraged holders (2,506 holder-days), built from on-chain events, prices, borrow rates and health factors.
- **Risk is concentrated:** in the high-risk bands, 13% of Aave positions hold 97% of the value.
- **Small moves, large exposure:** no liquidations happened in the sample, but a 3 to 5% price fall would raise liquidatable Aave collateral from about $40M to over $510M.
- **Three behaviours:** HDBSCAN on 12 standardised features finds low-leverage holding, active looping, and holding at max leverage near liquidation. The first clustering mostly grouped days from the same wallet, which was corrected before treating clusters as strategies.
- **Prediction:** XGBoost flags stressed days (ROC-AUC 0.977) and risk rebalancing (0.901). SHAP shows stress is driven by yield and borrow rates, not by leverage itself.
- **Leakage check:** the first stressed-day model scored a perfect 1.000 because of target leakage. Removing the leaking features gave the 0.977 above.

---

## Tokens Studied

- **sUSDe** (Ethena)
- **sUSDS**
- **syrupUSDC** (Maple Finance)

All USD-denominated, on Ethereum mainnet, active on **Aave v3** and **Morpho Blue**.

---

## Research Questions

1. What looping/leverage strategy patterns exist among large holders?
2. What risk characteristics (leverage depth, collateral buffers, risk rebalancing) separate these patterns?
3. Can on-chain data predict short-term risk rebalancing and stressed positions?

---

## Approach

| Stage | What |
|---|---|
| **Data collection** | GraphQL (Aave v3, Morpho Blue), Dune Analytics SQL |
| **Proof of concept** | Leverage bot script (with and without flashloans) |
| **Feature engineering** | Wallet-token-day panel: LTV, leverage, liquidation distance, carry spread, etc. |
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
└── paper/                 # Final report PDF (LaTeX source lives on Overleaf)
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

`uv run` uses that folder's own `.venv`; you do not need `source .venv/bin/activate`.

### Notebooks

| Folder | Notebooks |
|--------|-----------|
| `analysis/whale-archetypes/` | `01_eda_panel.ipynb`, `02_hdbscan_clustering.ipynb`, `03_balanced_clustering.ipynb` |
| `analysis/whale-risk-supervised/` | `01_eda_stress_threshold.ipynb`, `02_model_risk_rebalance.ipynb`, `03_model_stressed.ipynb` |
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
