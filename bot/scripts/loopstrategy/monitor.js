import hre from "hardhat";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const YO_USD = "0x0000000f2eB9f69274678c76222B35eEc7588a65";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

const LLTV = 91.5;
const WARN_BUFFER = 1.0;
const DANGER_BUFFER = 0.5;

function bufferStatus(buffer) {
    if (buffer < DANGER_BUFFER) return "🚨 DANGER — unwind immediately";
    if (buffer < WARN_BUFFER) return "⚠️  depeg risk — monitor closely";
    return "✅";
}

async function main() {
    const {ethers} = hre;
    const [signer] = await ethers.getSigners();

    const morpho = await ethers.getContractAt("IMorpho", MORPHO, signer);
    const usdc = await ethers.getContractAt("IERC20", USDC, signer);
    const yoUsd = new ethers.Contract(YO_USD, [
        "function previewRedeem(uint256 shares) view returns (uint256 assets)",
    ], signer);

    const [, borrowShares, collateralShares] = await morpho.position(MARKET_ID, signer.address);

    if (borrowShares === 0n && collateralShares === 0n) {
        console.log("No open position found for", signer.address);
        return;
    }

    const [totalSupplyAssets, , totalBorrowAssets, totalBorrowShares] = await morpho.market(MARKET_ID);

    const borrowAssets = totalBorrowShares > 0n ? (borrowShares * totalBorrowAssets) / totalBorrowShares : 0n;
    const collateralUsdc = await yoUsd.previewRedeem(collateralShares);
    const walletUsdc = await usdc.balanceOf(signer.address);

    const util = totalSupplyAssets > 0n ? Number(totalBorrowAssets * 10000n / totalSupplyAssets) / 100 : 0;
    const ltv = collateralUsdc > 0n ? Number(borrowAssets * 10000n / collateralUsdc) / 100 : 0;
    const buffer = LLTV - ltv;

    const hr = "─".repeat(50);
    console.log(`\n${hr}\nPosition monitor — ${signer.address}\n${hr}`);
    console.log("\nPosition:");
    console.log("  Collateral (yoUSD shares): ", collateralShares.toString());
    console.log("  Collateral (USDC value):   $" + ethers.formatUnits(collateralUsdc, 6));
    console.log("  Debt (USDC):               $" + ethers.formatUnits(borrowAssets, 6));
    console.log("  Wallet USDC:               $" + ethers.formatUnits(walletUsdc, 6));
    console.log("\nHealth:");
    console.log("  LTV:     " + ltv.toFixed(2) + "%");
    console.log("  LLTV:    " + LLTV.toFixed(1) + "%");
    console.log("  Buffer:  " + buffer.toFixed(2) + "%  " + bufferStatus(buffer));
    console.log("  Note:    both sides USD-pegged — buffer is stable by design");
    console.log("\nMarket:");
    console.log("  Utilisation:  " + util.toFixed(2) + "%");
    console.log("  yoUSD APY:    ~8.6%  (live: https://app.yo.xyz)");
    console.log(hr);
}

main().catch(console.error);

// npx hardhat run scripts/loopstrategy/monitor.js --network base