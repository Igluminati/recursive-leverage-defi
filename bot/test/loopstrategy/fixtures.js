import hardhat from "hardhat";

export const {ethers} = hardhat;

export const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
export const YO_USD = "0x0000000f2eB9f69274678c76222B35eEc7588a65";
export const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
export const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

export const OWN_CAPITAL = 3_000_000n;  // 3 USDC (6 decimals)
export const BORROW_RATIO = 88n;
export const LOOPS = 3;
export const REPAY_FUND = 20_000_000n; // 20 USDC

export const marketParams = [
    USDC,
    YO_USD,
    "0x77f59C5C09e7ABEF6991B456170930324FE36222",
    "0x46415998764C29aB2a25CbeA6254146D50D22687",
    915000000000000000n,
];

export const MORPHO_ABI = [
    "function supplyCollateral(tuple(address loanToken, address collateralToken, address oracle, address irm, uint256 lltv) marketParams, uint256 assets, address onBehalf, bytes data) external",
    "function borrow(tuple(address loanToken, address collateralToken, address oracle, address irm, uint256 lltv) marketParams, uint256 assets, uint256 shares, address onBehalf, address receiver) external returns (uint256, uint256)",
    "function repay(tuple(address loanToken, address collateralToken, address oracle, address irm, uint256 lltv) marketParams, uint256 assets, uint256 shares, address onBehalf, bytes data) external returns (uint256, uint256)",
    "function withdrawCollateral(tuple(address loanToken, address collateralToken, address oracle, address irm, uint256 lltv) marketParams, uint256 assets, address onBehalf, address receiver) external",
    "function position(bytes32 marketId, address user) view returns (uint256 supplyShares, uint128 borrowShares, uint128 collateral)",
];


export async function setUsdcBalance(address, amount) {
    await hardhat.network.provider.send("hardhat_mine", ["0x1"]);
    const slot = ethers.solidityPackedKeccak256(["uint256", "uint256"], [address, 9]);
    await hardhat.network.provider.send("hardhat_setStorageAt", [USDC, slot, ethers.toBeHex(amount, 32)]);
}

export function borrowOf(amount) {
    return amount * BORROW_RATIO / 100n;
}

export let owner, usdc, yoUsd, morpho;

export async function setup() {
    [owner] = await ethers.getSigners();

    usdc = new ethers.Contract(USDC, [
        "function balanceOf(address) view returns (uint256)",
        "function approve(address, uint256) returns (bool)",
    ], owner);

    yoUsd = new ethers.Contract(YO_USD, [
        "function balanceOf(address) view returns (uint256)",
        "function approve(address, uint256) returns (bool)",
        "function deposit(uint256 assets, address receiver) returns (uint256 shares)",
        "function redeem(uint256 shares, address receiver, address owner) returns (uint256 assets)",
        "function previewRedeem(uint256 shares) view returns (uint256 assets)",
    ], owner);

    morpho = new ethers.Contract(MORPHO, MORPHO_ABI, owner);
}


export async function runLoop() {
    let usdcToDeposit = OWN_CAPITAL;
    for (let i = 1; i <= LOOPS; i++) {
        await usdc.connect(owner).approve(YO_USD, usdcToDeposit);
        await yoUsd.connect(owner).deposit(usdcToDeposit, owner.address);

        const yoUsdBalance = await yoUsd.balanceOf(owner.address);
        await yoUsd.connect(owner).approve(MORPHO, yoUsdBalance);
        await morpho.connect(owner).supplyCollateral(marketParams, yoUsdBalance, owner.address, "0x");

        const borrowAmount = borrowOf(usdcToDeposit);
        await morpho.connect(owner).borrow(marketParams, borrowAmount, 0n, owner.address, owner.address);

        usdcToDeposit = borrowAmount;
    }
}

export async function runUnwind() {
    const {borrowShares, collateral} = await morpho.position(MARKET_ID, owner.address);

    if (borrowShares > 0n) {
        const usdcBalance = await usdc.balanceOf(owner.address);
        await usdc.connect(owner).approve(MORPHO, usdcBalance);
        await morpho.connect(owner).repay(marketParams, 0n, borrowShares, owner.address, "0x");
    }

    if (collateral > 0n) {
        await morpho.connect(owner).withdrawCollateral(marketParams, collateral, owner.address, owner.address);
    }

    const yoUsdBalance = await yoUsd.balanceOf(owner.address);
    if (yoUsdBalance > 0n) {
        await yoUsd.connect(owner).redeem(yoUsdBalance, owner.address, owner.address);
    }
}

// step 1 only — repay debt, stop (simulates crash after step 1)
export async function runUnwindStep1Only() {
    const {borrowShares} = await morpho.position(MARKET_ID, owner.address);
    if (borrowShares > 0n) {
        const usdcBalance = await usdc.balanceOf(owner.address);
        await usdc.connect(owner).approve(MORPHO, usdcBalance);
        await morpho.connect(owner).repay(marketParams, 0n, borrowShares, owner.address, "0x");
    }
}

// steps 1+2 only — repay + withdraw, stop (simulates crash after step 2)
export async function runUnwindStep2Only() {
    const {borrowShares, collateral} = await morpho.position(MARKET_ID, owner.address);
    if (borrowShares > 0n) {
        const usdcBalance = await usdc.balanceOf(owner.address);
        await usdc.connect(owner).approve(MORPHO, usdcBalance);
        await morpho.connect(owner).repay(marketParams, 0n, borrowShares, owner.address, "0x");
    }
    if (collateral > 0n) {
        await morpho.connect(owner).withdrawCollateral(marketParams, collateral, owner.address, owner.address);
    }
}

// runs the loop with a failure injected at the given loop number
export async function runLoopWithFailureAt(failAtLoop) {
    let usdcToDeposit = OWN_CAPITAL;

    try {
        for (let i = 1; i <= LOOPS; i++) {
            if (i === failAtLoop) {
                await setUsdcBalance(owner.address, 0n);
            }

            await usdc.connect(owner).approve(YO_USD, usdcToDeposit);
            await yoUsd.connect(owner).deposit(usdcToDeposit, owner.address);

            const yoUsdBalance = await yoUsd.balanceOf(owner.address);
            await yoUsd.connect(owner).approve(MORPHO, yoUsdBalance);
            await morpho.connect(owner).supplyCollateral(marketParams, yoUsdBalance, owner.address, "0x");

            const borrowAmount = borrowOf(usdcToDeposit);
            await morpho.connect(owner).borrow(marketParams, borrowAmount, 0n, owner.address, owner.address);

            usdcToDeposit = borrowAmount;
        }
    } catch {
        await setUsdcBalance(owner.address, REPAY_FUND);
        await runUnwind();
    }
}