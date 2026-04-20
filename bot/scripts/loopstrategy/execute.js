import hre from "hardhat";
import {execSync} from "child_process";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const YO_USD = "0x0000000f2eB9f69274678c76222B35eEc7588a65";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

const BORROW_RATIO = 0.88;
const LOOPS = 3;
const OWN_CAPITAL = 3_000_000n; // 3 USDC (6 decimals)
const BORROW_BUFFER = 10_000n; // $0.01 — keeps borrow below Morpho oracle overflow boundary

const marketParams = {
    loanToken: USDC,
    collateralToken: YO_USD,
    oracle: "0x77f59C5C09e7ABEF6991B456170930324FE36222",
    irm: "0x46415998764C29aB2a25CbeA6254146D50D22687",
    lltv: 915000000000000000n
};

const DEPOSIT_IFACE = new hre.ethers.Interface([
    "event Deposit(address indexed sender, address indexed owner, uint256 assets, uint256 shares)"
]);

function sharesFromReceipt(receipt) {
    for (const log of receipt.logs) {
        try {
            const e = DEPOSIT_IFACE.parseLog(log);
            if (e?.name === "Deposit") return e.args.shares;
        } catch {
        }
    }
    return null;
}

function borrowAmount(amount) {
    return (amount * BigInt(Math.floor(BORROW_RATIO * 100)) / 100n) - BORROW_BUFFER;
}

function runUnwind() {
    console.log("\n⚠️  Running unwind.js to clean up partial position...");
    try {
        execSync("npx hardhat run scripts/loopstrategy/unwind.js --network base", {stdio: "inherit"});
    } catch {
        console.error("❌ unwind.js failed — check position manually with monitor.js");
    }
}

async function main() {
    const {ethers} = hre;
    const [signer] = await ethers.getSigners();

    const usdc = await ethers.getContractAt("IERC20", USDC, signer);
    const morpho = await ethers.getContractAt("IMorpho", MORPHO, signer);
    const yoUsd = new ethers.Contract(YO_USD, [
        "function balanceOf(address) view returns (uint256)",
        "function approve(address, uint256) returns (bool)",
        "function deposit(uint256 assets, address receiver) returns (uint256 shares)",
    ], signer);

    const walletBalance = await usdc.balanceOf(signer.address);
    const hr = "─".repeat(50);

    console.log(hr);
    console.log("Wallet USDC balance:  $" + ethers.formatUnits(walletBalance, 6));
    console.log("Capital to deploy:    $" + ethers.formatUnits(OWN_CAPITAL, 6));
    console.log("Loops:", LOOPS, "  Borrow ratio:", (BORROW_RATIO * 100).toFixed(0) + "%");
    console.log(hr);

    if (walletBalance < OWN_CAPITAL)
        throw new Error(`Insufficient USDC: have $${ethers.formatUnits(walletBalance, 6)}, need $${ethers.formatUnits(OWN_CAPITAL, 6)}`);


    const [, existingBorrows, existingCollateral] = await morpho.position(MARKET_ID, signer.address);
    if (existingBorrows > 0n || existingCollateral > 1n)
        throw new Error("Existing position detected — run unwind.js first.");
    let usdcToDeposit = OWN_CAPITAL;

    try {
        for (let i = 1; i <= LOOPS; i++) {
            console.log(`\nLoop ${i}:`);
            console.log(`  Depositing $${ethers.formatUnits(usdcToDeposit, 6)} USDC into yoUSD...`);

            await (await usdc.approve(YO_USD, usdcToDeposit)).wait();
            const receipt = await (await yoUsd.deposit(usdcToDeposit, signer.address)).wait();

            let shares = sharesFromReceipt(receipt);
            if (!shares || shares === 0n) {
                await new Promise(r => setTimeout(r, 2000));
                shares = await yoUsd.balanceOf(signer.address);
            }
            if (!shares || shares === 0n)
                throw new Error("Received 0 yoUSD shares — vault may be paused.");

            console.log(`  Received: ${shares.toString()} yoUSD shares`);

            await (await yoUsd.approve(MORPHO, shares)).wait();
            await (await morpho.supplyCollateral(marketParams, shares, signer.address, "0x")).wait();
            console.log(`  Supplying yoUSD as collateral on Morpho...`);

            await new Promise(r => setTimeout(r, 1000));

            const borrow = borrowAmount(usdcToDeposit);
            console.log(`  Borrowing $${ethers.formatUnits(borrow, 6)} USDC from Morpho...`);
            await (await morpho.borrow(marketParams, borrow, 0n, signer.address, signer.address)).wait();

            console.log(`✅ Loop ${i} complete`);
            usdcToDeposit = borrow;
        }
    } catch (err) {
        console.error(`\n❌ Loop failed: ${err.message}`);
        runUnwind();
        throw new Error("Execution failed — position has been unwound.");
    }

    const [, borrowShares, collateral] = await morpho.position(MARKET_ID, signer.address);

    let expectedCollateral = OWN_CAPITAL;
    let expectedDebt = 0n;
    let amount = OWN_CAPITAL;
    for (let i = 0; i < LOOPS; i++) {
        amount = borrowAmount(amount);
        expectedDebt += amount;
        if (i < LOOPS - 1) expectedCollateral += amount;
    }

    console.log(`\n${hr}\nFinal position:`);
    console.log("  Collateral (yoUSD shares):", collateral.toString());
    console.log("  Borrow shares:            ", borrowShares.toString());
    console.log("\nExpected USDC amounts:");
    console.log("  Total deposited: ~$" + ethers.formatUnits(expectedCollateral, 6));
    console.log("  Total borrowed:  ~$" + ethers.formatUnits(expectedDebt, 6));
    console.log("  Net exposure:    ~$" + ethers.formatUnits(OWN_CAPITAL, 6) + " own capital");
    console.log(hr);
}

main().catch(console.error);

// npx hardhat run scripts/loopstrategy/execute.js --network base