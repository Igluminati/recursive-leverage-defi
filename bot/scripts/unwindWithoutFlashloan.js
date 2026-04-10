import hre from "hardhat";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const YO_USD = "0x0000000f2eB9f69274678c76222B35eEc7588a65";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

const marketParams = {
    loanToken: USDC,
    collateralToken: YO_USD,
    oracle: "0x77f59C5C09e7ABEF6991B456170930324FE36222",
    irm: "0x46415998764C29aB2a25CbeA6254146D50D22687",
    lltv: 915000000000000000n
};

async function main() {
    const { ethers } = hre;
    const [signer] = await ethers.getSigners();

    const usdc = await ethers.getContractAt("IERC20", USDC, signer);
    const yoUsd = await ethers.getContractAt("IERC4626", YO_USD, signer);
    const morpho = await ethers.getContractAt("IMorpho", MORPHO, signer);

    // read current position
    const [, borrowShares, collateral] = await morpho.position(MARKET_ID, signer.address);
    const usdcBalance = await usdc.balanceOf(signer.address);

    console.log("─".repeat(50));
    console.log("Current position:");
    console.log("  Collateral (yoUSD shares):", collateral.toString());
    console.log("  Borrow shares:            ", borrowShares.toString());
    console.log("  Wallet USDC:              $" + ethers.formatUnits(usdcBalance, 6));
    console.log("─".repeat(50));

    if (borrowShares === 0n && collateral === 0n) {
        console.log("No open position found. Nothing to unwind.");
        return;
    }

    // repay all USDC debt
    if (borrowShares > 0n) {
        console.log("\nStep 1: Repaying all USDC debt...");

        // check we have enough USDC to repay
        if (usdcBalance === 0n) {
            throw new Error(
                "Wallet has no USDC to repay debt. " +
                "You need to buy enough USDC to cover your borrow before unwinding."
            );
        }

        // approve Morpho to pull USDC for repayment
        await usdc.approve(MORPHO, usdcBalance);

        // repay using shares = borrowShares to close position exactly
        // using assets=0 + shares=borrowShares is the safest way to repay exactly
        const repayTx = await morpho.repay(
            marketParams,
            0n,           // assets (0 = use shares instead)
            borrowShares, // shares — repays exactly your debt, no dust left
            signer.address,
            "0x"
        );
        await repayTx.wait();
        console.log("✅ Debt fully repaid");
    }

    // step 2: withdraw all yoUSD collateral
    if (collateral > 0n) {
        console.log("\nStep 2: Withdrawing yoUSD collateral from Morpho...");

        const withdrawTx = await morpho.withdrawCollateral(
            marketParams,
            collateral,    // withdraw all shares
            signer.address,
            signer.address
        );
        await withdrawTx.wait();
        console.log("✅ Collateral withdrawn:", collateral.toString(), "yoUSD shares");
    }

    // redeem yoUSD to USDC
    const yoUsdBalance = await yoUsd.balanceOf(signer.address);

    if (yoUsdBalance > 0n) {
        console.log("\nStep 3: Redeeming yoUSD back to USDC...");
        console.log("  yoUSD shares to redeem:", yoUsdBalance.toString());

        // preview how much USDC we'll get back
        const expectedUsdc = await yoUsd.previewRedeem(yoUsdBalance);
        console.log("  Expected USDC back: ~$" + ethers.formatUnits(expectedUsdc, 6));

        const redeemTx = await yoUsd.redeem(
            yoUsdBalance,
            signer.address,
            signer.address
        );
        await redeemTx.wait();
        console.log("✅ yoUSD redeemed");
    }

    const finalUsdc = await usdc.balanceOf(signer.address);
    console.log("\n" + "─".repeat(50));
    console.log("Unwind complete!");
    console.log("  Final wallet USDC: $" + ethers.formatUnits(finalUsdc, 6));
    console.log("─".repeat(50));
}

main().catch(console.error);

// npx hardhat run scripts/unwindWithoutFlashloan.js --network base