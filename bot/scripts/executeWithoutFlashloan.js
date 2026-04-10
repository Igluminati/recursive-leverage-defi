import hre from "hardhat";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const YO_USD = "0x0000000f2eB9f69274678c76222B35eEc7588a65";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

const BORROW_RATIO = 0.88;
const LOOPS = 2;
const OWN_CAPITAL = 10_000_000n; // 10 USDC (6 decimals)

const marketParams = {
    loanToken: USDC,
    collateralToken: YO_USD,
    oracle: "0x77f59C5C09e7ABEF6991B456170930324FE36222",
    irm: "0x46415998764C29aB2a25CbeA6254146D50D22687",
    lltv: 915000000000000000n
};

async function main() {
    const {ethers} = hre;
    const [signer] = await ethers.getSigners();

    const usdc = await ethers.getContractAt("IERC20", USDC, signer);
    const yoUsd = await ethers.getContractAt("IERC4626", YO_USD, signer);
    const morpho = await ethers.getContractAt("IMorpho", MORPHO, signer);

    const walletBalance = await usdc.balanceOf(signer.address);
    console.log("─".repeat(50));
    console.log("Wallet USDC balance:  $" + ethers.formatUnits(walletBalance, 6));
    console.log("Capital to deploy:    $" + ethers.formatUnits(OWN_CAPITAL, 6));
    console.log("Loops:", LOOPS);
    console.log("Borrow ratio:", (BORROW_RATIO * 100).toFixed(0) + "%");
    console.log("─".repeat(50));

    if (walletBalance < OWN_CAPITAL) {
        throw new Error(
            `Insufficient USDC: wallet has $${ethers.formatUnits(walletBalance, 6)}, ` +
            `need $${ethers.formatUnits(OWN_CAPITAL, 6)}`
        );
    }

    let usdcToDeposit = OWN_CAPITAL; // start from 10 USDC

    for (let i = 1; i <= LOOPS; i++) {
        console.log(`\nLoop ${i}:`);
        console.log(`  Depositing $${ethers.formatUnits(usdcToDeposit, 6)} USDC into yoUSD...`);

        // deposit USDC into yoUSD vault
        await usdc.approve(YO_USD, usdcToDeposit);
        const depositTx = await yoUsd.deposit(usdcToDeposit, signer.address);
        await depositTx.wait();

        const yoUsdBalance = await yoUsd.balanceOf(signer.address);
        console.log(`  Received: ${yoUsdBalance.toString()} yoUSD shares`);

        // supply yoUSD as collateral on Morpho
        console.log(`  Supplying yoUSD as collateral on Morpho...`);
        await yoUsd.approve(MORPHO, yoUsdBalance);
        const supplyTx = await morpho.supplyCollateral(
            marketParams,
            yoUsdBalance,
            signer.address,
            "0x"
        );
        await supplyTx.wait();

        // borrow USDC from Morpho
        const borrowAmount = usdcToDeposit * BigInt(Math.floor(BORROW_RATIO * 100)) / 100n;
        console.log(`  Borrowing $${ethers.formatUnits(borrowAmount, 6)} USDC from Morpho...`);

        const borrowTx = await morpho.borrow(
            marketParams,
            borrowAmount,
            0n,
            signer.address,
            signer.address
        );
        await borrowTx.wait();

        console.log(`✅ Loop ${i} complete`);

        // next loop feeds off the borrowed USDC
        usdcToDeposit = borrowAmount;
    }

    // final position summary
    const [, borrowShares, collateral] = await morpho.position(MARKET_ID, signer.address);

    // calculate expected totals for display
    let expectedCollateral = OWN_CAPITAL;
    let expectedDebt = 0n;
    let loopAmount = OWN_CAPITAL;
    for (let i = 0; i < LOOPS; i++) {
        loopAmount = loopAmount * BigInt(Math.floor(BORROW_RATIO * 100)) / 100n;
        expectedDebt += loopAmount;
        if (i < LOOPS - 1) expectedCollateral += loopAmount;
    }

    console.log("\n" + "─".repeat(50));
    console.log("Final position:");
    console.log("  Collateral (yoUSD shares):", collateral.toString());
    console.log("  Borrow shares:            ", borrowShares.toString());
    console.log("\nExpected USDC amounts:");
    console.log("  Total deposited: ~$" + ethers.formatUnits(expectedCollateral, 6));
    console.log("  Total borrowed:  ~$" + ethers.formatUnits(expectedDebt, 6));
    console.log("  Net exposure:    ~$" + ethers.formatUnits(OWN_CAPITAL, 6) + " own capital");
    console.log("─".repeat(50));
}

main().catch(console.error);

// npx hardhat run scripts/executeWithoutFlashloan.js --network base