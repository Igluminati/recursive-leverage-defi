import hre from "hardhat";
import fs from "fs";
import path from "path";

/**
 * Deploys LeverageBot to Base mainnet, transfers ownership to the Gnosis Safe,
 * verifies on Basescan, and writes a deployment artefact. Set DRY_RUN=1 to run
 * the whole flow against the Hardhat fork without real ETH.
 */

const SAFE_ADDRESS = "0xf9962B0fa1910c90788E35f83Df4F15F9f857fCb";

// Entry point, invoked below.
async function main() {
    const {ethers} = hre;
    const network = hre.network.name;
    const dryRun = process.env.DRY_RUN === "1";

    if (network !== "base" && !dryRun) {
        throw new Error(`Refusing to run on network "${network}"; pass DRY_RUN=1 to simulate against the fork, or --network base for production.`);
    }

    console.log("─".repeat(60));
    console.log(dryRun
        ? "DRY RUN: deploying LeverageBot against the Hardhat fork"
        : "Deploying LeverageBot to Base with Gnosis Safe ownership");
    console.log("─".repeat(60));

    const [deployer] = await ethers.getSigners();
    const balance = await ethers.provider.getBalance(deployer.address);

    console.log("Deployer:    ", deployer.address);
    console.log("Target Safe: ", SAFE_ADDRESS);
    console.log("ETH balance: ", ethers.formatEther(balance), "ETH");

    if (balance === 0n) {
        throw new Error("Deployer has no ETH, fund it before deploying");
    }

    const safeCode = await ethers.provider.getCode(SAFE_ADDRESS);
    if (safeCode === "0x") {
        throw new Error(`No contract at Safe address ${SAFE_ADDRESS}, aborting to avoid orphaning the bot.`);
    }

    console.log("\n[1/3] Deploying LeverageBot...");
    const LeverageBot = await ethers.getContractFactory("LeverageBot");
    const bot = await LeverageBot.deploy();
    await bot.waitForDeployment();

    const botAddress = await bot.getAddress();
    const deployTx = bot.deploymentTransaction();
    const deployReceipt = await deployTx.wait(2);
    const deployBlock = deployReceipt.blockNumber;

    console.log("      address:", botAddress);
    console.log("      txHash: ", deployTx.hash);
    console.log("      block:  ", deployBlock);

    console.log("\n[2/3] Transferring ownership to the Safe...");
    let transferTx;
    const maxAttempts = 3;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            transferTx = await bot.transferOwnership(SAFE_ADDRESS);
            await transferTx.wait(1);
            break;
        } catch (err) {
            console.warn(`      attempt ${attempt}/${maxAttempts} failed:`, err.message || err);
            if (attempt === maxAttempts) {
                throw new Error(
                    `transferOwnership failed after ${maxAttempts} attempts. ` +
                    `Bot deployed at ${botAddress} but still owned by the EOA. ` +
                    `Re-run transferOwnership(${SAFE_ADDRESS}) from the EOA manually, ` +
                    `then redeploy for a clean artefact.`
                );
            }
            await new Promise((r) => setTimeout(r, 5_000 * attempt));
        }
    }
    console.log("      txHash:", transferTx.hash);

    const newOwner = await bot.owner();
    if (newOwner.toLowerCase() !== SAFE_ADDRESS.toLowerCase()) {
        throw new Error(`Ownership transfer failed: owner is ${newOwner}, expected ${SAFE_ADDRESS}`);
    }
    console.log("      owner confirmed:", newOwner);

    console.log("\n[3/3] Verifying on Basescan...");
    if (dryRun) {
        console.log("      skipped (dry run)");
    } else {
        try {
            await hre.run("verify:verify", {
                address: botAddress,
                constructorArguments: [],
            });
            console.log("      verified");
        } catch (err) {
            const msg = err.message || String(err);
            if (msg.toLowerCase().includes("already verified")) {
                console.log("      already verified");
            } else {
                console.warn("      verification failed (continue manually):", msg);
            }
        }
    }

    const deploymentsDir = path.resolve("deployments");
    if (!fs.existsSync(deploymentsDir)) {
        fs.mkdirSync(deploymentsDir, {recursive: true});
    }

    const timestamp = new Date().toISOString();
    const record = {
        contract: "LeverageBot",
        address: botAddress,
        owner: SAFE_ADDRESS,
        deployer: deployer.address,
        network,
        chainId: (await ethers.provider.getNetwork()).chainId.toString(),
        deployBlock,
        deployTxHash: deployTx.hash,
        transferOwnershipTxHash: transferTx.hash,
        timestamp,
        abi: JSON.parse(bot.interface.formatJson()),
    };

    const safeTag = timestamp.replace(/[:.]/g, "-");
    const filepath = path.join(deploymentsDir, `LeverageBot_${network}_${safeTag}.json`);
    const latestPath = path.join(deploymentsDir, `LeverageBot_${network}_latest.json`);
    fs.writeFileSync(filepath, JSON.stringify(record, null, 2));
    fs.writeFileSync(latestPath, JSON.stringify(record, null, 2));

    const executeCalldata = bot.interface.encodeFunctionData("execute", []);
    const unwindCalldata = bot.interface.encodeFunctionData("unwind", []);

    const approveCalldata = new ethers.Interface([
        "function approve(address,uint256)",
    ]).encodeFunctionData("approve", [botAddress, 10_000_000n]);
    const usdc = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";

    console.log("\n" + "─".repeat(60));
    console.log("DEPLOYMENT COMPLETE");
    console.log("─".repeat(60));
    console.log("LeverageBot:", botAddress);
    console.log("Owner:      ", SAFE_ADDRESS, "(Gnosis Safe)");
    console.log("Artefact:   ", filepath);
    console.log("\nDrive the bot via https://app.safe.global/home?safe=base:" + SAFE_ADDRESS);
    console.log("Fund the Safe with 10 USDC, then submit these transactions:");
    console.log(`  1. approve    to=${usdc}  data=${approveCalldata}`);
    console.log(`  2. execute()  to=${botAddress}  data=${executeCalldata}`);
    console.log(`  3. unwind()   to=${botAddress}  data=${unwindCalldata}`);
    console.log("─".repeat(60));
}

main().catch((err) => {
    console.error("Deployment failed:", err);
    process.exit(1);
});
