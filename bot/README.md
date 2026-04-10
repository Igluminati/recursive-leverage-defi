# recursive-leverage-defi/bot

A proof-of-concept leverage bot on Base mainnet using Morpho and yoUSD.
Built as part of a master's thesis studying recursive leverage strategies among large holders of yield-bearing stablecoins.

*University of Zurich — 2026*

---

## Quick commands

```bash
# deploy
npx hardhat run scripts/flashloan/deploy.js --network base

# check rates
npx hardhat run scripts/helpers/checkRates.js --network base

# execute with flashloan (requires deployed LeverageBot)
npx hardhat run scripts/flashloan/execute.js --network base

# execute without flashloan
npx hardhat run scripts/executeWithoutFlashloan.js --network base

# unwind without flashloan (requires enough USDC in wallet to repay debt)
npx hardhat run scripts/unwindWithoutFlashloan.js --network base

# monitor position
npx hardhat run scripts/flashloan/monitor.js --network base

# run tests
npm run test
```

---

## What this does

You put in **10 USDC** of your own money.
The bot builds a leveraged position in yoUSD on Morpho, earning yield on more capital than you own.

Two strategies are implemented:

### Strategy 1 — With flashloan (LeverageBot.sol)

Uses a Morpho flashloan to build the position **atomically in one transaction**.

```
1. Owner approves 10 USDC and calls execute()
2. Contract pulls 10 USDC, then requests 90 USDC flashloan from Morpho
3. Morpho calls back onMorphoFlashLoan() — contract holds 100 USDC total
4. Deposit 100 USDC into yoUSD vault, receive ~93 yoUSD
5. Supply yoUSD as collateral on Morpho
6. Borrow 90 USDC against that collateral
7. Repay the 90 USDC flashloan — tx completes ✅
```

Result: ~100 USDC of yoUSD collateral with 90 USDC debt, funded with only 10 USDC (~10x leverage)

### Strategy 2 — Without flashloan (executeWithoutFlashloan.js)

Uses your own USDC and loops **step by step across multiple transactions**.

```
Loop 1: deposit USDC → supply yoUSD → borrow 88% back
Loop 2: deposit borrowed USDC → supply more yoUSD → borrow 88% back
...repeat
```

No contract needed  just a script.

### Unwind — Without flashloan (unwindWithoutFlashloan.js)

Closes the position in three steps across multiple transactions.

```
Step 1: Repay all USDC debt on Morpho (requires USDC in wallet)
Step 2: Withdraw all yoUSD collateral from Morpho
Step 3: Redeem yoUSD back to USDC
```

Requires enough USDC in your wallet to cover the outstanding borrow before running(at least 20 USDC).

---

## Why yoUSD?

[yoUSD](https://app.yo.xyz) is a yield-bearing stablecoin vault by YO Protocol.
Deposit USDC, receive yoUSD, and it automatically earns yield across 2600+ DeFi pools.

- **No whitelist** — fully permissionless
- **ERC-4626 standard** — simple deposit/redeem
- **~8.64% native APY** paid in USDC
- **Confirmed Morpho market** on Base


## Project structure

```
bot/
├── contracts/
│   ├── LeverageBot.sol                    flashloan contract (strategy 1)
│   └── ILeverageBot.sol                   interfaces
├── scripts/
│   ├── flashloan/
│   │   ├── deploy.js                      deploy LeverageBot to Base
│   │   ├── execute.js                     run strategy 1 (with flashloan)
│   │   └── monitor.js                     check position health
│   ├── executeWithoutFlashloan.js         run strategy 2 (no flashloan)
│   ├── unwindWithoutFlashloan.js          close position and redeem to USDC
│   └── helpers/
│       ├── checkRates.js                  check live APY and spread
│       └── fetchMarketParams.js           fetch Morpho market params
├── test/
│   └── LeverageBot.test.js                integration tests on Base fork
├── deployments/                           saved deployment records
└── hardhat.config.js
```

---

## Contracts on Base

| Name | Address |
|---|---|
| LeverageBot | deployed via `deploy.js` |
| Morpho Blue | `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb` |
| yoUSD vault | `0x0000000f2eB9f69274678c76222B35eEc7588a65` |
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| yoUSD/USDC market | `0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137` |
| LLTV | 91.5% |

---

## Setup

```bash
# install dependencies
npm install

# copy env and fill in your values
cp .env.example .env
```

`.env` file:

```
BASE_RPC_URL=https://mainnet.base.org
BASE_PRIVATE_KEY=0xyourprivatekey
```

---

## Tests

Tests run against a real Base fork — no stubs, all real Morpho and yoUSD interactions.

```bash
npm run test
```


---

## Monitor output explained

```
LTV:      90.00%   your current loan-to-value ratio
LLTV:     91.5%    liquidation threshold
Buffer:   1.5%     how much yoUSD can drop before liquidation
Spread:   1.71%    yoUSD yield minus borrow cost — must stay positive
```

Run the monitor regularly. If spread goes negative or LTV approaches 91.5% — act immediately.

---

## Risks

**Liquidation** — if yoUSD price drops and LTV exceeds 91.5%, Morpho liquidates your position. Both sides are stablecoins pegged to $1 so this is unlikely but not impossible.

**Spread risk** — if Morpho borrow rate rises above yoUSD yield, you are losing money. Check rates before executing.

**yoUSD APY is variable** — rebalances automatically across 2600+ pools. The 8.64% is historical and can change.

**Smart contract risk** — this contract interacts with Morpho, yoUSD, and USDC. A bug in any of them could affect your position.