import hardhat from "hardhat";
import assert from "assert";
import {setUsdcBalance} from "./fixtures.js";

const {ethers} = hardhat;

const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

const OWN_CAPITAL = 10n * 1_000_000n; // 10 USDC

describe("LeverageBot", function () {
    let bot, owner, usdc, morpho;

    before(async function () {
        this.timeout(60_000);

        [owner] = await ethers.getSigners();

        // deploy fresh contract
        const LeverageBot = await ethers.getContractFactory("LeverageBot");
        bot = await LeverageBot.deploy();

        // token contract handles
        usdc = new ethers.Contract(USDC, [
            "function balanceOf(address) view returns (uint256)",
            "function approve(address, uint256) returns (bool)",
        ], owner);

        // morpho contract handle to read position after execute
        morpho = new ethers.Contract(MORPHO, [
            "function position(bytes32, address) view returns (uint256 supplyShares, uint128 borrowShares, uint128 collateral)"
        ], owner);

        // fund owner with 10 USDC
        await setUsdcBalance(owner.address, OWN_CAPITAL);
    });


    it("sets the correct owner", async function () {
        // ACTION
        const contractOwner = await bot.owner();

        // ASSERT
        assert.equal(contractOwner, owner.address);
    });

    it("starts with zero USDC and yoUSD balances", async function () {
        // ACTION
        const usdcBal = await bot.usdcBalance();
        const yoUsdBal = await bot.yoUsdBalance();

        // ASSERT
        assert.equal(usdcBal.toString(), "0");
        assert.equal(yoUsdBal.toString(), "0");
    });

    it("reverts if non-owner calls execute()", async function () {
        // ARRANGE
        const [, nonOwner] = await ethers.getSigners();

        // ACTION + ASSERT
        await assert.rejects(
            bot.connect(nonOwner).execute(),
            /LeverageBot: not owner/
        );
    });

    it("reverts if non-Morpho calls onMorphoFlashLoan()", async function () {
        // ARRANGE
        const fakeData = ethers.AbiCoder.defaultAbiCoder().encode(
            ["uint256", "uint256"],
            [OWN_CAPITAL, 90n * 1_000_000n]
        );

        // ACTION + ASSERT
        await assert.rejects(
            bot.connect(owner).onMorphoFlashLoan(90n * 1_000_000n, fakeData),
            /LeverageBot: caller not Morpho/
        );
    });


    it("completes the full leverage loop without reverting", async function () {
        this.timeout(60_000);

        // ARRANGE
        await usdc.approve(await bot.getAddress(), OWN_CAPITAL);

        // ACTION
        const tx = await bot.execute();
        const receipt = await tx.wait();

        // ASSERT
        assert.equal(receipt.status, 1, "transaction should succeed");
        console.log("info gas used:", receipt.gasUsed.toString());
    });

    it("emits LeverageExecuted event with correct values", async function () {
        this.timeout(60_000);

        // ARRANGE deploy fresh bot and fund it
        const LeverageBot = await ethers.getContractFactory("LeverageBot");
        const freshBot = await LeverageBot.deploy();
        await setUsdcBalance(owner.address, OWN_CAPITAL);
        await usdc.approve(await freshBot.getAddress(), OWN_CAPITAL);

        // ACTION
        const tx = await freshBot.execute();
        const receipt = await tx.wait();

        // ASSERT find LeverageExecuted in logs
        const iface = freshBot.interface;
        const botAddress = (await freshBot.getAddress()).toLowerCase();

        const log = receipt.logs.find(l => {
            if (l.address.toLowerCase() !== botAddress) {
                return false;
            }
            try {
                const parsed = iface.parseLog(l);
                return parsed !== null && parsed.name === "LeverageExecuted";
            } catch {
                return false;
            }
        });

        assert.ok(log, "LeverageExecuted event should be emitted");

        const parsed = iface.parseLog(log);
        assert.equal(parsed.args.ownCapital.toString(), OWN_CAPITAL.toString());
        assert.equal(parsed.args.usdcBorrowed.toString(), (90n * 1_000_000n).toString());
    });

    it("leaves zero USDC in the contract after execute", async function () {
        // ASSERT from the execute() test above
        const usdcBal = await bot.usdcBalance();
        assert.equal(usdcBal.toString(), "0", "no USDC should remain in contract");
    });

    it("leaves zero yoUSD in the contract after execute", async function () {
        // ASSERT all yoUSD should be in Morpho as collateral
        const yoUsdBal = await bot.yoUsdBalance();
        assert.equal(yoUsdBal.toString(), "0", "no yoUSD should remain in contract");
    });

    it("has yoUSD collateral posted in Morpho after execute", async function () {
        // ACTION
        const [, , collateral] = await morpho.position(MARKET_ID, await bot.getAddress());

        // ASSERT
        assert.ok(collateral > 0n, "bot should have collateral in Morpho");
        console.log("yoUSD collateral in Morpho:", collateral.toString());
    });

    it("has USDC debt in Morpho after execute", async function () {
        // ACTION
        const [, borrowShares] = await morpho.position(MARKET_ID, await bot.getAddress());

        // ASSERT
        assert.ok(borrowShares > 0n, "bot should have borrow position in Morpho");
        console.log("USDC borrow shares in Morpho:", borrowShares.toString());
    });


    it("owner can rescue stuck USDC from the contract", async function () {
        // ARRANGE send USDC directly to contract simulating stuck funds
        const stuckAmount = 5n * 1_000_000n;
        await setUsdcBalance(await bot.getAddress(), stuckAmount);

        const balanceBefore = await usdc.balanceOf(owner.address);

        // ACTION
        await bot.rescueToken(USDC, stuckAmount);

        // ASSERT
        const balanceAfter = await usdc.balanceOf(owner.address);
        assert.equal(
            (balanceAfter - balanceBefore).toString(),
            stuckAmount.toString()
        );
    });
});