# YBS Holder Panel Query — README

This Dune SQL query builds a full holder panel for a chosen yield-bearing stablecoin (YBS), showing not just wallet balances but also how much of that token each wallet has deposited into DeFi lending protocols (Morpho and, for sUSDe, Aave).


## Supported tokens

| Token | Contract address (Ethereum) | Decimals | Protocol(s) checked |
|---|---|---|---|
| syrupUSDC | `0x80ac24aa929eaf5013f6436cda2a7ba190f5cc0b` | 6 | Morpho only |
| sUSDe | `0x9d39a5de30e57443bff2a8307a4256c8797a3497` | 18 | Morpho + Aave |
| sUSDS | `0xa3931d71877c0e7a3148cb7eb4463524fec27fbd` | 18 | Morpho only |

## Csv Output columns explained

| Column | Meaning |
|---|---|
| `wallet` | The address being described |
| `YBS_wallet_balance` | How much of the token is sitting loose in the wallet itself right now |
| `YBS_in_morpho` | How much of the token this wallet currently has deposited as collateral in Morpho |
| `YBS_in_aave` | Same, but for Aave. Always 0 unless the token is sUSDe |
| `total_YBS_exposure` | The three columns above added together — the full picture of how much of the token this wallet effectively controls, wherever it's sitting |

## Aave follow-up (issue #50)

New notebook `aave_holder_analysis.ipynb` adds Aave alongside Morpho using the existing holder panel. Optional market-level SQL: `from_dune/aave_market_breakdown.sql`. Does not modify the Morpho notebook or Dune queries.
