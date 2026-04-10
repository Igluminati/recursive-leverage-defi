import hre from "hardhat";
import fs from "fs";
import path from "path";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const IRM = "0x46415998764C29aB2a25CbeA6254146D50D22687";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

// thresholds
const LLTV = 91.5;
const DANGER_LTV = 89; // %  act immediately
const WARNING_LTV = 85; // %  watch closely
const MIN_SPREAD = 0.5; // %  minimum healthy spread
const NATIVE_APY = 8.64; // %  yoUSD native yield gotta update it manually if it changes

const pct = (n) => `${n.toFixed(2)}%`;
const usd = (n) => `$${n.toFixed(4)}`;
const line = () => console.log("─".repeat(50));

function getDeployedAddress(network) {
    const latestPath = path.resolve(`deployments/LeverageBot_${network}_latest.json`);
    if (!fs.existsSync(latestPath)) {
        throw new Error(`No deployment found for ${network} — run deploy.js first`);
    }
    const record = JSON.parse(fs.readFileSync(latestPath, "utf8"));
    return record.address;
}

async function main() {
    const {ethers} = hre;
    const BOT_ADDRESS = getDeployedAddress(hre.network.name);

    const morpho = await ethers.getContractAt([
        "function position(bytes32, address) view returns (uint256 supplyShares, uint128 borrowShares, uint128 collateral)",
        "function market(bytes32) view returns (uint128 totalSupplyAssets, uint128 totalSupplyShares, uint128 totalBorrowAssets, uint128 totalBorrowShares, uint128 lastUpdate, uint128 fee)",
        "function idToMarketParams(bytes32) view returns (address loanToken, address collateralToken, address oracle, address irm, uint256 lltv)"
    ], MORPHO);

    const irm = await ethers.getContractAt([
        "function borrowRateView((address loanToken, address collateralToken, address oracle, address irm, uint256 lltv) marketParams, (uint128 totalSupplyAssets, uint128 totalSupplyShares, uint128 totalBorrowAssets, uint128 totalBorrowShares, uint128 lastUpdate, uint128 fee) market) view returns (uint256)"
    ], IRM);

    // read position
    const [, borrowShares, collateral] = await morpho.position(MARKET_ID, BOT_ADDRESS);
    const market = await morpho.market(MARKET_ID);
    const params = await morpho.idToMarketParams(MARKET_ID);

    const totalSupply = market.totalSupplyAssets;
    const totalBorrow = market.totalBorrowAssets;
    const liquidity = totalSupply - totalBorrow;
    const utilization = Number(totalBorrow * 10000n / totalSupply) / 100;

    // calculate LTV
    // borrowShares / collateral gives approximate LTV
    // collateral is yoUSD shares (~$1.07), borrow is USDC shares
    const ltv = collateral > 0n
        ? Number(borrowShares * 100n / collateral)
        : 0;

    // calculate borrow APY
    const marketParams = {
        loanToken: params.loanToken,
        collateralToken: params.collateralToken,
        oracle: params.oracle,
        irm: params.irm,
        lltv: params.lltv
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
    const netSpread = NATIVE_APY - borrowAPY;

    // estimated yearly profit
    const grossYield = 100 * (NATIVE_APY / 100);
    const borrowCost = 90 * (borrowAPY / 100);
    const netProfit = grossYield - borrowCost;

    // output
    line();
    console.log("LeverageBot Position Monitor");
    console.log(new Date().toISOString());
    line();
    console.log(`Bot: ${BOT_ADDRESS}`);
    line();
    console.log("POSITION");
    console.log(`Collateral: ${collateral.toString()} yoUSD shares`);
    console.log(`Borrow shares: ${borrowShares.toString()}`);
    console.log(`LTV: ${pct(ltv)}`);
    console.log(`LLTV limit: ${pct(LLTV)}`);
    console.log(`Buffer: ${pct(LLTV - ltv)}`);
    line();
    console.log("MARKET");
    console.log(`Supply: $${ethers.formatUnits(totalSupply, 6)} USDC`);
    console.log(`Borrow: $${ethers.formatUnits(totalBorrow, 6)} USDC`);
    console.log(`Liquidity: $${ethers.formatUnits(liquidity, 6)} USDC`);
    console.log(`Utilization: ${pct(utilization)}`);
    line();
    console.log("RATES");
    console.log(`yoUSD APY: ${pct(NATIVE_APY)}  (paid in USDC)`);
    console.log(`Borrow APY: ${pct(borrowAPY)}`);
    console.log(`Net spread: ${pct(netSpread)}`);
    line();
    console.log("ESTIMATED YEARLY (10 USDC capital)");
    console.log(`Gross yield: ${usd(grossYield)} USDC`);
    console.log(`Borrow cost: ${usd(borrowCost)} USDC`);
    console.log(`Net profit: ${usd(netProfit)} USDC`);
    console.log(`Net APY: ${pct(netProfit / 10 * 100)}`);
    line();

    // health checks
    console.log("HEALTH");

    if (collateral === 0n) {
        console.log("ℹ️  No position open yet");
    } else if (ltv >= DANGER_LTV) {
        console.log("🚨 LTV DANGER  — above 89% — act immediately");
    } else if (ltv >= WARNING_LTV) {
        console.log("⚠️  LTV WARNING — above 85% — monitor closely");
    } else {
        console.log("✅ LTV healthy");
    }

    if (netSpread <= 0) {
        console.log("🚨 SPREAD NEGATIVE — losing money — consider unwinding");
    } else if (netSpread < MIN_SPREAD) {
        console.log("⚠️  SPREAD THIN — below 0.5%");
    } else {
        console.log("✅ Spread healthy");
    }

    line();
}

main().catch((err) => {
    console.error("Monitor failed:", err);
    process.exit(1);
});

//npx hardhat run scripts/flashloan/monitor.js --network base