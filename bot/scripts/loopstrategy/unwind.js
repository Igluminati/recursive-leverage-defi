import hre from "hardhat";

const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const YO_USD = "0x0000000f2eB9f69274678c76222B35eEc7588a65";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";
const UINT256_MAX = 2n ** 256n - 1n;

const marketParams = {
    loanToken: USDC,
    collateralToken: YO_USD,
    oracle: "0x77f59C5C09e7ABEF6991B456170930324FE36222",
    irm: "0x46415998764C29aB2a25CbeA6254146D50D22687",
    lltv: 915000000000000000n
};

const WITHDRAW_IFACE = new hre.ethers.Interface([
    "event WithdrawCollateral(bytes32 indexed id, address caller, address indexed onBehalf, address indexed receiver, uint256 assets)"
]);

function parseWithdrawShares(receipt, fallback) {
    const event = receipt.logs
        .map(log => {
            try {
                return WITHDRAW_IFACE.parseLog(log);
            } catch {
                return null;
            }
        })
        .find(e => e?.name === "WithdrawCollateral");
    return event ? event.args.assets : fallback;
}

async function safeWithdraw(morpho, collateral, signer) {
    for (const delta of [1n, 2n, 5n, 10n, 100n, 1000n]) {
        if (collateral <= delta) continue;
        try {
            const amount = collateral - delta;
            const receipt = await (await morpho.withdrawCollateral(marketParams, amount, signer.address, signer.address)).wait();
            const withdrawn = parseWithdrawShares(receipt, amount);
            console.log("✅ Collateral withdrawn:", withdrawn.toString(), "yoUSD shares");
            return withdrawn;
        } catch {
        }
    }
    throw new Error("Could not withdraw collateral after multiple attempts — re-run unwind.js.");
}

async function main() {
    const {ethers} = hre;
    const [signer] = await ethers.getSigners();

    const usdc = await ethers.getContractAt("IERC20", USDC, signer);
    const morpho = await ethers.getContractAt("IMorpho", MORPHO, signer);
    const yoUsd = new ethers.Contract(YO_USD, [
        "function balanceOf(address) view returns (uint256)",
        "function approve(address, uint256) returns (bool)",
        "function redeem(uint256 shares, address receiver, address owner) returns (uint256 assets)",
        "function requestRedeem(uint256 shares, address receiver, address owner) returns (uint256 requestId)",
        "function previewRedeem(uint256 shares) view returns (uint256 assets)",
    ], signer);

    const [, borrowSharesInit, collateralInit] = await morpho.position(MARKET_ID, signer.address);
    const hr = "─".repeat(50);

    console.log(`${hr}\nCurrent position:`);
    console.log("  Collateral (yoUSD shares):", collateralInit.toString());
    console.log("  Borrow shares:            ", borrowSharesInit.toString());
    console.log("  Wallet USDC:              $" + ethers.formatUnits(await usdc.balanceOf(signer.address), 6));
    console.log(hr);

    if (borrowSharesInit === 0n && collateralInit === 0n) {
        console.log("No open position found. Nothing to unwind.");
        return;
    }

    // repay
    const [, borrowShares] = await morpho.position(MARKET_ID, signer.address);
    if (borrowShares > 0n) {
        console.log("\nStep 1: Repaying all USDC debt...");
        if ((await usdc.balanceOf(signer.address)) === 0n)
            throw new Error("Wallet has no USDC to repay debt. Buy enough USDC and re-run.");
        try {
            await (await usdc.approve(MORPHO, UINT256_MAX)).wait();
            await (await morpho.repay(marketParams, 0n, borrowShares, signer.address, "0x")).wait();
            console.log("✅ Debt fully repaid");

            await new Promise(r => setTimeout(r, 6000));
        } catch (err) {
            console.error("❌ Step 1 failed:", err.message);
            throw err;
        }
    }

    // withdraw collateral
    const [, , collateral] = await morpho.position(MARKET_ID, signer.address);
    let yoUsdWithdrawn = 0n;
    if (collateral <= 1n) {
        console.log("\nStep 2: Skipped — only dust remaining.");
    } else {
        console.log("\nStep 2: Withdrawing yoUSD collateral from Morpho...");
        try {
            yoUsdWithdrawn = await safeWithdraw(morpho, collateral, signer);
        } catch (err) {
            console.error("❌ Step 2 failed:", err.message);
            throw err;
        }
    }

    //  redeem yoUSD to USDC
    const toRedeem = yoUsdWithdrawn > 0n ? yoUsdWithdrawn : await yoUsd.balanceOf(signer.address);
    if (toRedeem > 0n) {
        console.log("\nStep 3: Redeeming yoUSD...");
        console.log("  Shares:   ", toRedeem.toString());
        console.log("  Expected: ~$" + ethers.formatUnits(await yoUsd.previewRedeem(toRedeem), 6));
        try {
            await (await yoUsd.redeem(toRedeem, signer.address, signer.address)).wait();
            console.log("✅ yoUSD redeemed instantly");
        } catch {
            try {
                await (await yoUsd.requestRedeem(toRedeem, signer.address, signer.address)).wait();
                console.log("✅ Redemption requested — USDC arrives within 24h automatically.");
            } catch (err) {
                console.error("❌ Step 3 failed:", err.message);
                throw err;
            }
        }
    }

    await new Promise(r => setTimeout(r, 2000));
    console.log(`\n${hr}\nUnwind complete!`);
    console.log("  Wallet USDC: $" + ethers.formatUnits(await usdc.balanceOf(signer.address), 6));
    console.log(hr);
}

main().catch(console.error);

// npx hardhat run scripts/loopstrategy/unwind.js --network base