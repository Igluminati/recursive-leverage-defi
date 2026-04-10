import hre from "hardhat";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";
const IRM = "0x46415998764C29aB2a25CbeA6254146D50D22687";

const OWN_CAPITAL = 10;
const FLASHLOAN = 90;
const COLLATERAL = OWN_CAPITAL + FLASHLOAN;
const NATIVE_APY = 8.64;

const pct = (n) => `${n.toFixed(2)}%`;
const usd = (n) => `$${n.toFixed(4)} USDC/year`;
const line = () => console.log("─".repeat(50));

async function main() {
    const {ethers} = hre;

    // read market state
    const morpho = await ethers.getContractAt([
        "function market(bytes32) view returns (uint128 totalSupplyAssets, uint128 totalSupplyShares, uint128 totalBorrowAssets, uint128 totalBorrowShares, uint128 lastUpdate, uint128 fee)"
    ], MORPHO);

    const market = await morpho.market(MARKET_ID);
    const supplyAssets = market.totalSupplyAssets;
    const borrowAssets = market.totalBorrowAssets;
    const liquidity = supplyAssets - borrowAssets;
    const utilization = Number(borrowAssets * 10000n / supplyAssets) / 100;

    // read live borrow rate from IRM
    const irm = await ethers.getContractAt([
        "function borrowRateView((address loanToken, address collateralToken, address oracle, address irm, uint256 lltv) marketParams, (uint128 totalSupplyAssets, uint128 totalSupplyShares, uint128 totalBorrowAssets, uint128 totalBorrowShares, uint128 lastUpdate, uint128 fee) market) view returns (uint256)"
    ], IRM);

    const marketParams = {
        loanToken: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        collateralToken: "0x0000000f2eB9f69274678c76222B35eEc7588a65",
        oracle: "0x77f59C5C09e7ABEF6991B456170930324FE36222",
        irm: IRM,
        lltv: 915000000000000000n
    };

    const marketState = {
        totalSupplyAssets: market.totalSupplyAssets,
        totalSupplyShares: market.totalSupplyShares,
        totalBorrowAssets: market.totalBorrowAssets,
        totalBorrowShares: market.totalBorrowShares,
        lastUpdate: market.lastUpdate,
        fee: market.fee
    };

    const ratePerSecond = Number(
        await irm.borrowRateView(marketParams, marketState)
    ) / 1e18;

    const borrowAPY = ((1 + ratePerSecond) ** (365 * 24 * 3600) - 1) * 100;

    // supply APY = borrow APY × utilization × (1 - protocol fee)
    const fee = Number(market.fee) / 1e18;
    const supplyAPY = borrowAPY * (utilization / 100) * (1 - fee);

    // calculate profit
    const grossYield = COLLATERAL * (NATIVE_APY / 100);
    const borrowCost = FLASHLOAN * (borrowAPY / 100);
    const netProfit = grossYield - borrowCost;
    const netAPY = (netProfit / OWN_CAPITAL) * 100;
    const baseline = OWN_CAPITAL * (NATIVE_APY / 100);

    // output
    line();
    console.log("yoUSD/USDC — Morpho Base");
    line();
    console.log(`Supply:       $${ethers.formatUnits(supplyAssets, 6)} USDC`);
    console.log(`Borrow:       $${ethers.formatUnits(borrowAssets, 6)} USDC`);
    console.log(`Liquidity:    $${ethers.formatUnits(liquidity, 6)} USDC`);
    console.log(`Utilization:  ${pct(utilization)}`);
    line();
    console.log(`yoUSD APY:    ${pct(NATIVE_APY)}  (paid in USDC — what we earn on collateral)`);
    console.log(`Borrow APY:   ${pct(borrowAPY)}  (what we pay on 90 USDC debt)`);
    console.log(`Supply APY:   ${pct(supplyAPY)}  (what USDC lenders earn — informational only)`);
    console.log(`Net Spread:   ${pct(NATIVE_APY - borrowAPY)}`);
    line();
    console.log(`Position: $${OWN_CAPITAL} own + $${FLASHLOAN} flashloan = $${COLLATERAL} collateral`);
    line();
    console.log(`Gross yield:  ${usd(grossYield)}`);
    console.log(`Borrow cost:  ${usd(borrowCost)}`);
    console.log(`Net profit:   ${usd(netProfit)}`);
    console.log(`Net APY:      ${pct(netAPY)}`);
    line();
    console.log(`Baseline (no leverage): ${usd(baseline)} — ${pct(NATIVE_APY)}`);
    line();

    // safety checks
    if (netProfit <= 0) {
        console.log("🚨 SPREAD NEGATIVE — do NOT execute");
    } else if (netAPY < 5) {
        console.log("⚠️  LOW SPREAD — consider waiting");
    } else {
        console.log("✅ Spread healthy — safe to execute");
    }

    if (Number(ethers.formatUnits(liquidity, 6)) < FLASHLOAN) {
        console.log("🚨 NOT ENOUGH LIQUIDITY for flashloan");
    } else {
        console.log(`✅ Liquidity ok — $${FLASHLOAN} flashloan covered`);
    }
}

main();

//npx hardhat run scripts/helpers/checkRates.js --network base
