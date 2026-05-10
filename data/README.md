# Data Scrapers

This folder contains the data collection and whale identification pipeline for the master's project on recursive leverage in yield-bearing stablecoins.

## What is in here

| Folder | Description |
|--------|-------------|
| `ybt/` | Collects metadata, daily prices, and protocol events for the three tokens under study |
| `whales/` | Identifies and ranks the top strategy operators per token per protocol |

---

## The six whales we selected

After running the identification queries and manually reviewing each candidate on Etherscan, we settled on six addresses for the core analysis. The selection process was more work than expected. We rejected a lot of candidates along the way for reasons like being Pendle PT loopers (a different strategy), multi-user protocol vaults where you cannot isolate a single operator's decisions, or simply having too few transactions to build a meaningful panel.

The six below survived all of those filters. They were chosen to cover all three tokens (sUSDe, sUSDS, syrupUSDC), all three protocols (Aave v3, Morpho Blue, SparkLend), and a range of operator sophistication from a fully manual Safe to a purpose-built institutional looping contract. That diversity is intentional. It gives the clustering model something to actually differentiate.

---

### W-1: sUSDe on Morpho Blue

| Field | Value |
|-------|-------|
| Address | `0x9bcb2ee24bd11046c0dcdfebd608eeb360a64495` |
| Token | sUSDe (Ethena) |
| Protocol | Morpho Blue |
| Total received | $14.4M |
| Current balance | around 0 (near fully exited) |
| Distinct funders | 5 |
| Strategy | looper |
| Operator type | DeFi Saver managed smart wallet |
| Deployer | `0x080cceA8...689d88Fb0`, sole caller throughout |
| Deployed | 95 days ago |
| Last active | 17 days ago |
| Borrow asset | USDtb (Ethena's own stablecoin) |
| Total transactions | 53 |
| RQ3 role | Training set |

This one uses DeFi Saver. Every transaction goes through DeFi Saver's Cast method, and DeFi Saver takes a small fee of around 35 to 40 sUSDe on each rebalancing call. The loop uses sUSDe as collateral and USDtb as the borrow asset, which makes it a fully native Ethena ecosystem trade. The operator triggers each rebalancing manually through the DeFi Saver interface rather than automating it. 53 transactions over 95 days gives us a decent panel to work with.

Archetype: DeFi Saver assisted manual looper.

---

### W-2: sUSDe on Aave v3

| Field | Value |
|-------|-------|
| Address | `0x9a6c741c95a138e6de1f3464a0ab6166926abfaa` |
| Token | sUSDe (Ethena) |
| Protocol | Aave v3 |
| Total received | $49M |
| Current balance | around 0 (position exited) |
| Distinct funders | 3 |
| Strategy | looper |
| Operator type | Gnosis Safe with partial automation |
| Deployer | `0x8fC2b6C5...CC3F735Da` |
| Deployed | 269 days ago |
| Last active | Active |
| Total transactions | 141 |
| RQ3 role | Training set, strongest candidate |

The busiest wallet in the sample with 141 transactions over 269 days. It runs on a Gnosis Safe but uses Gelato and Relend Network to submit the actual transactions. The activity pattern is episodic: quiet for weeks, then a burst of rebalancing transactions. That is exactly the kind of behavior the RQ3 classifier is trying to predict, which is why this is our most valuable training data source.

Archetype: privately operated Safe with partial automation.

---

### W-3: sUSDS on SparkLend

| Field | Value |
|-------|-------|
| Address | `0x422f7a7a75d0da268cf4bf15c52fdc41c50e1e88` |
| Token | sUSDS (Sky) |
| Protocol | SparkLend |
| Total received | $9.7M |
| Current balance | 0 (fully exited) |
| Distinct funders | 3 |
| Strategy | looper |
| Operator type | Fully manual Gnosis Safe |
| Deployer | `0xF0577f03...67Ab9244d`, sole caller with no automation |
| Deployed | 1 year 318 days ago |
| Last active | 363 days ago |
| Total transactions | 58 |
| RQ3 role | Out-of-sample validation |

The oldest wallet in the sample by a wide margin, deployed nearly two years ago. Every one of its 58 transactions was sent directly by the deployer with no automation layer at all. It is the purest example of a human operator making individual manual decisions. It has been fully exited and inactive for over a year. That is worth noting as a limitation: DeFi rates and market conditions in 2024 were meaningfully different from today, so the model trained on 2025 to 2026 data may not generalise perfectly to this wallet's behavior.

Archetype: fully manual private Safe looper. Also the only SparkLend representative in the sample.

---

### W-4: sUSDe on Aave v3

| Field | Value |
|-------|-------|
| Address | `0xea03e659a2e59c3715c6517afe58541be162161a` |
| Token | sUSDe (Ethena) |
| Protocol | Aave v3 |
| Total received | $15.7M |
| Current balance | 0 (fully exited 70 days ago) |
| Distinct funders | 5 |
| Strategy | looper |
| Operator type | Fully manual Gnosis Safe |
| Deployer | `0x778A93C3...065ed13c8`, sole caller throughout |
| Deployed | 266 days ago |
| Last active | 70 days ago |
| Borrow asset | USDe and USDC |
| Total transactions | 257 |
| RQ3 role | Training set, second strongest candidate |

With 257 transactions across 266 days this has the densest panel in the sample. Like W-3 it is a fully manual Safe with no automation, but this operator rebalanced almost every single day. That gives us a roughly 97% positive rebalancing rate, compared to W-1 and W-2 at around 50 to 55%. That creates a class imbalance problem when we pool the training set, so we downsample W-4 before pooling (see the ML section below). The ERC-20 transfers are clean: burn aEthsUSDe, repay USDe debt, operator sends fresh USDe back in from their external wallet.

Archetype: purely manual private Safe looper, same contract type as W-3 but much higher rebalancing frequency.

---

### W-5: sUSDe on Morpho Blue

| Field | Value |
|-------|-------|
| Address | `0x0d4f7b204626e8233c5b42b1269a78e236e9a06b` |
| Token | sUSDe (Ethena) |
| Protocol | Morpho Blue |
| Total received | $74M |
| Current balance | 0 (fully exited 17 days ago) |
| Distinct funders | 2 |
| Strategy | looper |
| Operator type | Purpose-built private looping contract |
| Contract type | Custom verified contract |
| Deployer | `0x06f92C97...4E8bE3Be7`, sole caller, same operator as W-6 |
| Deployed | 58 days ago |
| Last active | 17 days ago |
| Borrow asset | PYUSD (PayPal USD) |
| Position size | Up to around $18M sUSDe per loop leg |
| Total transactions | 24 |
| RQ3 role | Out-of-sample validation |

One of two contracts operated by the same entity (see W-6). The operator wrote their own custom verified looping contract with explicit methods for each phase of the strategy: Assemble, Update Assembling, Deposit, Borrow, Withdraw Supply, Repay All. The borrow asset is PYUSD, which is unique in our sample, and the operator runs a companion PYUSD liquidity vault to supply the borrow capital. Individual positions run to $15 to 18M per leg, making this the most capital-intensive operator in the sample on a per-transaction basis. Only 24 transactions limits its usefulness for RQ3 training, so we use it for out-of-sample validation instead.

Archetype: purpose-built high-conviction private looper at institutional scale.

---

### W-6: syrupUSDC on Morpho Blue

| Field | Value |
|-------|-------|
| Address | `0x24385a793f725328d7f6224430e48b4236326717` |
| Token | syrupUSDC (Maple Finance) |
| Protocol | Morpho Blue |
| Total received | $126M |
| Current balance | 0 (fully exited 19 days ago) |
| Distinct funders | 3 |
| Strategy | looper |
| Operator type | Purpose-built private looping contract, same operator as W-5 |
| Contract type | Custom verified contract |
| Deployer | `0x06f92C97...4E8bE3Be7`, same deployer and sole caller as W-5 |
| Deployed | 63 days ago, five days before W-5 |
| Last active | 19 days ago |
| Borrow asset | PYUSD, same as W-5 |
| Position size | Up to around $28M syrupUSDC per unwind leg |
| Total transactions | 46 |
| RQ3 role | Out-of-sample validation |

Same operator as W-5, deployed five days earlier, using syrupUSDC as collateral instead of sUSDe. The two contracts together represent a deliberate parallel strategy: one leg in each collateral token, both borrowing PYUSD from the same companion liquidity vault. The loop mechanics are explicit in the transaction names. Each Assemble Background call steps through one loop leg, routing syrupUSDC through the Syrup USDC Router, then swapping to PYUSD via 1inch, then repaying to Morpho. The fact that one operator runs two coordinated contracts across different tokens is itself a finding worth highlighting in the thesis.

Archetype: same as W-5, purpose-built high-conviction private looper running a parallel multi-collateral strategy.

---

## Coverage at a glance

| Whale | Token | Protocol | Volume | Txns | Active | Operator style | RQ3 role |
|-------|-------|----------|--------|------|--------|----------------|----------|
| W-1 | sUSDe | Morpho Blue | $14.4M | 53 | Yes | DeFi Saver assisted | training |
| W-2 | sUSDe | Aave v3 | $49M | 141 | Yes | Gnosis Safe + Gelato | training |
| W-3 | sUSDS | SparkLend | $9.7M | 58 | No | Fully manual Safe | validation |
| W-4 | sUSDe | Aave v3 | $15.7M | 257 | No | Fully manual Safe | training |
| W-5 | sUSDe | Morpho Blue | $74M | 24 | No | Custom looping contract | validation |
| W-6 | syrupUSDC | Morpho Blue | $126M | 46 | No | Custom looping contract (same as W-5) | validation |

---

## How we use these in the ML pipeline

### RQ1: Finding the archetypes using HDBSCAN

All six wallets contribute here. For clustering we compute static per-wallet feature vectors covering things like average LTV, max loop depth, rebalancing frequency, borrow asset type, and whether the operator uses automation. Even W-5 with only 24 transactions gives us enough to build a meaningful vector. The goal is to see whether the clustering naturally groups them by operator sophistication, by protocol, or by some other dimension we have not anticipated.

### RQ2: Comparing risk management styles

Again all six contribute. We use the full wallet-token-day panel to compare LTV trajectories, collateral buffer sizes, how operators respond to carry spread changes, and how close they typically run to the liquidation threshold. W-3, W-5, and W-6 have shorter panels but that is fine for descriptive analysis. We just note the shorter observation window.

### RQ3: Predicting when rebalancing happens using XGBoost and SHAP

This is where the sample splits. We train on W-1, W-2, and W-4, the three wallets with the most transactions, and validate on W-3, W-5, and W-6 as held-out archetypes. If the model correctly predicts rebalancing events on wallets it has never seen, that tells us the on-chain features genuinely generalise across operator types. If it fails, that is also informative because it means the rebalancing logic is specific to each archetype.

One issue we need to handle: W-4 rebalances on about 97% of days while W-1 and W-2 are around 50 to 55%. If we pool them as-is, the model will be dominated by W-4's pattern. Our fix is to downsample W-4 days before pooling so all three training wallets contribute roughly equally, then apply per-sample weights so the remaining W-4 days do not overpower the others. We evaluate on F1-score rather than accuracy to make sure the model is not just predicting rebalancing every day.

One more caveat worth stating clearly: W-3's data is from 2024, which was a different rate environment from the 2025 to 2026 period the training wallets cover. Lower model performance on W-3 during validation might reflect that market shift rather than anything about the archetype itself.

---

## What we rejected and why

We screened a lot of addresses before landing on these six. Here are the main ones we rejected and the reason for each.

| Address | Why we rejected it |
|---------|-------------------|
| `0x4095f064b8d3c3548a3bebfd0bbfd04750e30077` | Morpho ETH Bundler V2, aggregates thousands of users, not a single operator |
| `0xa7995f71aa11525db02fc2473c37dee5dbf55107` | 299 distinct funders, clearly an aggregator of some kind |
| `0x9ffe77146cc1da3edb87af163c6c32bab474b464` | CIAN Protocol vault, multi-user, we cannot isolate one operator's decisions |
| `0xb3e6fc32cd058a1dd5ac8b0246e1701737764399` | Second CIAN vault, identical to the one above |
| `0x604117f0c94561231060f56cd2ddd16245d434c5` | ERC-20 yield vault that issues shares to external depositors, same aggregation problem |
| `0xa0cb4e1222d813d6e4de79f2a7a0b7759209588f` | Custom unverified contract running sUSDe, syrupUSDC, stUSN, and ynRWAx all at once, cannot isolate a clean daily LTV |
| `0xefc8edaa7cfd0cf272a0f55de37d62f0adfb7e93` | Origami Finance vault, multi-user protocol |
| `0xb48ac9c5585e5f3c88c63cf9bcbaedc921f76df2` | Origami Finance vault, multi-user protocol |
| `0xbfb7718329e5e223a5a09fa55ded0d44c07e4ab0` | PT-sUSDe Pendle looper, different strategy type, described in the discussion section below |
| `0x1b82b4f47e9b2cf82a37a4072d4141e23ab33a54` | Same, PT looping at institutional scale, described below |
| `0x53fcdd68ff10f916ca6fb6fe3ee5c483410efb60` | Switches between sUSDe and PT-sUSDe on Aave, contaminated panel |
| `0x45b687f03bb902cf6a8ffc14cd4f0351f5a9ce35` | EOA wallet flooded with phishing dust, 535 transactions of which most are spam |
| `0xbefdfef6930afe3b6c7be985c6baf778ea6ec215` | Personal treasury running sUSDe on Aave, Pendle sENA, and Morpho USDC at the same time |
| `0xfafc2c5f6a0d05718f3e50d0765a79fc69cdde13` | DeFi Saver Safe running sUSDS with USDT, USR, and USDtb across three markets at once |
| Anything below $1M total received | Not enough activity to build a meaningful panel |

Note on W-5 and W-6: these two share the same deployer and the same PYUSD liquidity vault. They are operated by a single entity as a coordinated parallel strategy. We keep both because they use different collateral tokens and different Morpho markets, so they give us two independent data points within the same archetype. The cross-position coordination is itself an interesting finding.

---

## A note on PT looping (for the thesis discussion section)

During the whale search we kept finding addresses that loop with PT-sUSDe (Pendle Principal Tokens) rather than sUSDe itself. We excluded them from the core analysis but they are worth describing in the thesis because they represent a closely related but economically distinct strategy.

### How PT looping works

Pendle splits a yield-bearing token into two pieces. The Principal Token (PT) matures to the full value of the underlying at a fixed date. The Yield Token (YT) captures all the floating yield in the meantime. Because the PT has been stripped of its yield, it trades at a discount to sUSDe. That discount implies a fixed annual return for whoever holds it to maturity.

PT loopers use PT-sUSDe as Morpho collateral:

```
1. Start with sUSDe
2. Split via Pendle Router to get PT-sUSDe and YT-sUSDe
3. Supply PT-sUSDe to Morpho as collateral
4. Borrow a stablecoin against it
5. Convert the borrowed stablecoin back to sUSDe
6. Repeat from step 2
```

The carry spread here is the PT implied fixed rate minus the Morpho borrow rate. It is locked in at entry rather than floating day to day. That is a fundamentally different risk profile from the strategies in our core sample.

### Why we kept them out of the main analysis

| Dimension | Our core sample | PT loopers |
|-----------|----------------|------------|
| Collateral | Floating-rate YBT | Fixed-rate zero-coupon PT |
| Carry spread | Changes daily | Locked in at entry |
| Price trajectory | Varies with yield | Predetermined accretion to par |
| Liquidation risk | YBT depeg or rate spike | PT price deviation from fair value |
| Panel structure | Continuous | Breaks at maturity, position must be rolled |
| Carry spread data | DeFiLlama APY | Pendle AMM implied rate, separate API needed |

The maturity breaks are the hardest engineering problem. Every time a PT expires the panel needs special handling that does not apply to floating-rate positions. That plus the Pendle price feed requirement makes this a meaningful scope expansion, so we scoped it as future work.

### The two PT loopers we identified

**PT-1: `0x1b82b4f47e9b2cf82a37a4072d4141e23ab33a54`**

Deployed 90 days ago, last active 86 days ago, only 6 transactions but each one moves $28 to 34M of sUSDe through Pendle in a single atomic call. The deployer is also the counterparty receiving the PT and YT tokens, suggesting they are building a matched fixed-rate book where the YT stream is held or sold separately. Six transactions is not enough for panel analysis but the scale and sophistication make it a compelling qualitative archetype: an institutional operator locking in fixed-rate leverage at $30M per leg.

**PT-2: `0xbfb7718329e5e223a5a09fa55ded0d44c07e4ab0`**

Older contract deployed one year 194 days ago, last active 558 days ago, 34 transactions across a two-day burst. Self-funded by minting sUSDe directly from Ethena. Borrows DAI and converts via Sky's PSM. The September 2025 PT maturity it used has since expired so the position is closed. This is the iterative version of the same strategy: building loop depth manually over multiple transactions rather than atomically.

### How to frame this in the thesis

PT looping sits at the boundary of what this study covers. The borrow-and-redeploy mechanics are identical to what we study but the economic logic is fixed-income arbitrage rather than yield farming. A good way to put it in the thesis:

"PT loopers use the same on-chain mechanics as the YBT loopers in this study but occupy a different position in the risk-return space. They trade floating carry exposure for a predetermined fixed return locked in at entry. This distinction places PT looping closer to fixed-income arbitrage than to the yield farming strategies analysed here, and represents a natural direction for future work."