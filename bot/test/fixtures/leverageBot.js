import hardhat from "hardhat";

const { ethers } = hardhat;

/**
 * Shared fixtures for the LeverageBot test suite. Deploys a fresh bot, wires
 * shared contract handles, funds the owner with USDC, impersonates arbitrary
 * on-chain accounts, and exposes a few pre-leveraged states so individual
 * tests stay short and readable.
 */

export const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
export const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
export const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

export const OWN_CAPITAL = 10n * 1_000_000n;

// Writes a USDC balance directly into the Base USDC proxy's balances mapping (slot 9).
export async function setUsdcBalance(address, amount) {
    const slot = ethers.solidityPackedKeccak256(
        ["uint256", "uint256"],
        [address, 9]
    );
    await hardhat.network.provider.send("hardhat_setStorageAt", [
        USDC,
        slot,
        ethers.toBeHex(amount, 32),
    ]);
}

// Deploys a fresh LeverageBot and returns shared contract handles + actors.
export async function deployLeverageBotFixture() {
    const [deployer, alice, bob, stranger] = await ethers.getSigners();

    const LeverageBot = await ethers.getContractFactory("LeverageBot");
    const bot = await LeverageBot.deploy();
    await bot.waitForDeployment();

    const usdc = new ethers.Contract(USDC, [
        "function balanceOf(address) view returns (uint256)",
        "function approve(address, uint256) returns (bool)",
    ], deployer);

    const morpho = new ethers.Contract(MORPHO, [
        "function position(bytes32, address) view returns (uint256 supplyShares, uint128 borrowShares, uint128 collateral)",
    ], deployer);

    return { bot, deployer, alice, bob, stranger, usdc, morpho };
}

// Deploys and funds the deployer with OWN_CAPITAL, ready to approve and execute.
export async function deployAndFundOwner() {
    const fx = await deployLeverageBotFixture();
    await setUsdcBalance(fx.deployer.address, OWN_CAPITAL);
    return fx;
}

// Deploys, funds, approves, and calls execute() to leave the bot fully leveraged.
export async function deployAndLeverage() {
    const fx = await deployAndFundOwner();
    await fx.usdc.approve(await fx.bot.getAddress(), OWN_CAPITAL);
    await fx.bot.execute();
    return fx;
}

// Returns a Signer that sends transactions as `address` on the Hardhat fork.
export async function impersonate(address) {
    await hardhat.network.provider.request({
        method: "hardhat_impersonateAccount",
        params: [address],
    });
    await hardhat.network.provider.send("hardhat_setBalance", [
        address,
        "0x56BC75E2D63100000",
    ]);
    return await ethers.getSigner(address);
}
