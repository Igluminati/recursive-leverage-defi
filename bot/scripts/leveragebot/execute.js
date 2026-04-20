import hre from "hardhat";
import fs from "fs";
import path from "path";

const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const OWN_CAPITAL = 10_000_000n; // 10 USDC

function getDeployedAddress(network) {
    const latestPath = path.resolve(`deployments/LeverageBot_${network}_latest.json`);
    if (!fs.existsSync(latestPath)) {
        throw new Error(`No deployment found for ${network} — run deploy.js first`);
    }
    const record = JSON.parse(fs.readFileSync(latestPath, "utf8"));
    console.log(`Using deployment from: ${record.timestamp}`);
    console.log(`Contract address: ${record.address}`);
    return record.address;
}

const line = () => console.log("─".repeat(50));

async function main() {
    const {ethers} = hre;
    const [owner] = await ethers.getSigners();
    const BOT_ADDRESS = getDeployedAddress(hre.network.name);

    const bot = await ethers.getContractAt("LeverageBot", BOT_ADDRESS);
    const usdc = await ethers.getContractAt([
        "function balanceOf(address) view returns (uint256)",
        "function approve(address, uint256) returns (bool)",
    ], USDC);

    line();
    console.log("LeverageBot — Execute");
    line();
    console.log("Owner: ", owner.address);
    console.log("Bot: ", BOT_ADDRESS);

    // check owner USDC balance
    const usdcBalance = await usdc.balanceOf(owner.address);
    console.log("USDC balance:", ethers.formatUnits(usdcBalance, 6), "USDC");

    if (usdcBalance < OWN_CAPITAL) {
        throw new Error(`Not enough USDC — need 10, have ${ethers.formatUnits(usdcBalance, 6)}`);
    }

    line();

    // approve
    console.log("Step 1: Approving 10 USDC...");
    const approveTx = await usdc.approve(BOT_ADDRESS, OWN_CAPITAL);
    await approveTx.wait();
    console.log("✅ Approved");

    // execute
    console.log("Step 2: Executing leverage loop...");
    const executeTx = await bot.execute();
    const receipt = await executeTx.wait();

    line();
    console.log("✅ Leverage loop executed!");
    console.log("Tx hash: ", receipt.hash);
    console.log("Gas used: ", receipt.gasUsed.toString());
    console.log(`Basescan: https://basescan.org/tx/${receipt.hash}`);
    line();
}

main().catch((err) => {
    console.error("Execute failed:", err);
    process.exit(1);
});

//npx hardhat run scripts/leveragebot/execute.js --network base