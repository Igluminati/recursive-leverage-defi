import hre from "hardhat";
import fs from "fs";
import path from "path";

async function main() {
    const {ethers} = hre;

    console.log("─".repeat(50));
    console.log("Deploying LeverageBot to Base mainnet...");
    console.log("─".repeat(50));

    // get deployer
    const [deployer] = await ethers.getSigners();
    const balance = await ethers.provider.getBalance(deployer.address);

    console.log("Deployer:   ", deployer.address);
    console.log("ETH balance:", ethers.formatEther(balance), "ETH");

    if (balance === 0n) {
        throw new Error("Deployer has no ETH — fund it before deploying");
    }

    // deploy
    const LeverageBot = await ethers.getContractFactory("LeverageBot");
    const bot = await LeverageBot.deploy();
    await bot.waitForDeployment();

    const botAddress = await bot.getAddress();
    const deployBlock = await ethers.provider.getBlockNumber();
    const network = hre.network.name;
    const timestamp = new Date().toISOString();

    console.log("─".repeat(50));
    console.log("✅ LeverageBot deployed!");
    console.log("Contract address:", botAddress);
    console.log("Block:", deployBlock);
    console.log("─".repeat(50));

    // save deployment record
    const deploymentsDir = path.resolve("deployments");
    if (!fs.existsSync(deploymentsDir)) {
        fs.mkdirSync(deploymentsDir, {recursive: true});
    }

    const record = {
        contract: "LeverageBot",
        address: botAddress,
        deployer: deployer.address,
        network,
        chainId: (await ethers.provider.getNetwork()).chainId.toString(),
        blockNumber: deployBlock,
        timestamp,
        abi: JSON.parse(bot.interface.formatJson()),
    };

    // save timestamped file one file per deployment
    const filename = `LeverageBot_${network}_${timestamp.replace(/[:.]/g, "-")}.json`;
    const filepath = path.join(deploymentsDir, filename);
    fs.writeFileSync(filepath, JSON.stringify(record, null, 2));

    // save latest.json, always points to most recent deployment
    const latestPath = path.join(deploymentsDir, `LeverageBot_${network}_latest.json`);
    fs.writeFileSync(latestPath, JSON.stringify(record, null, 2));

    console.log("Deployment saved to:");
    console.log(" ", filepath);
    console.log(" ", latestPath);
    console.log("─".repeat(50));
    console.log("Next steps:");
    console.log("1. Verify on Basescan:");
    console.log(`   npx hardhat verify --network base ${botAddress}`);
    console.log("2. Check rates before executing:");
    console.log("   npx hardhat run scripts/helpers/checkRates.js --network base");
    console.log("3. Execute the leverage loop:");
    console.log("   npx hardhat run scripts/execute.js --network base");
    console.log("─".repeat(50));
}

main().catch((err) => {
    console.error("Deployment failed:", err);
    process.exit(1);
});


//npx hardhat run scripts/flashloan/deploy.js --network base