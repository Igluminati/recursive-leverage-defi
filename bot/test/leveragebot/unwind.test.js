import {expect} from "chai";
import {
    MARKET_ID,
    OWN_CAPITAL,
    deployAndFundOwner,
    deployAndLeverage,
} from "./fixtures.js";

describe("LeverageBot, unwind", function () {
    this.timeout(120_000);

    describe("authorisation", function () {
        it("reverts when called by a non-owner", async function () {
            // Arrange
            const {bot, stranger} = await deployAndLeverage();

            // Act + Assert
            await expect(bot.connect(stranger).unwind())
                .to.be.revertedWith("LeverageBot: not owner");
        });
    });

    describe("preconditions", function () {
        it("reverts when the bot has no open position", async function () {
            // Arrange
            const {bot, deployer} = await deployAndFundOwner();

            // Act + Assert
            await expect(bot.connect(deployer).unwind())
                .to.be.revertedWith("LeverageBot: no position to unwind");
        });
    });

    describe("happy path", function () {
        it("closes the Morpho debt position (borrowShares become zero)", async function () {
            // Arrange
            const {bot, deployer, morpho} = await deployAndLeverage();
            const botAddress = await bot.getAddress();
            const [, borrowSharesBefore] = await morpho.position(MARKET_ID, botAddress);
            expect(borrowSharesBefore).to.be.gt(0n);

            // Act
            await bot.connect(deployer).unwind();

            // Assert
            const [, borrowSharesAfter] = await morpho.position(MARKET_ID, botAddress);
            expect(borrowSharesAfter).to.equal(0n);
        });

        it("withdraws all yoUSD collateral from Morpho (collateral becomes zero)", async function () {
            // Arrange
            const {bot, deployer, morpho} = await deployAndLeverage();
            const botAddress = await bot.getAddress();
            const [, , collateralBefore] = await morpho.position(MARKET_ID, botAddress);
            expect(collateralBefore).to.be.gt(0n);

            // Act
            await bot.connect(deployer).unwind();

            // Assert
            const [, , collateralAfter] = await morpho.position(MARKET_ID, botAddress);
            expect(collateralAfter).to.equal(0n);
        });

        it("returns USDC to the owner (at least OWN_CAPITAL minus small slippage)", async function () {
            // Arrange
            const {bot, deployer, usdc} = await deployAndLeverage();
            const balanceBefore = await usdc.balanceOf(deployer.address);

            // Act
            await bot.connect(deployer).unwind();

            // Assert
            const balanceAfter = await usdc.balanceOf(deployer.address);
            const delta = balanceAfter - balanceBefore;
            const minExpected = (OWN_CAPITAL * 995n) / 1000n;
            expect(delta).to.be.gte(minExpected);
        });

        it("leaves zero USDC and zero yoUSD in the contract after unwind", async function () {
            // Arrange
            const {bot, deployer} = await deployAndLeverage();

            // Act
            await bot.connect(deployer).unwind();

            // Assert
            expect(await bot.usdcBalance()).to.equal(0n);
            expect(await bot.yoUsdBalance()).to.equal(0n);
        });

        it("emits LeverageUnwound with non-zero usdcRepaid, usdcReceived, and netToOwner", async function () {
            // Arrange
            const {bot, deployer} = await deployAndLeverage();

            // Act
            const tx = await bot.connect(deployer).unwind();
            const receipt = await tx.wait();

            // Assert
            const iface = bot.interface;
            const botAddress = (await bot.getAddress()).toLowerCase();
            const log = receipt.logs.find(l => {
                if (l.address.toLowerCase() !== botAddress) return false;
                try {
                    const parsed = iface.parseLog(l);
                    return parsed !== null && parsed.name === "LeverageUnwound";
                } catch {
                    return false;
                }
            });
            expect(log, "LeverageUnwound event should be emitted").to.not.be.undefined;

            const parsed = iface.parseLog(log);
            expect(parsed.args.usdcRepaid).to.be.gt(0n);
            expect(parsed.args.usdcReceived).to.be.gt(0n);
            expect(parsed.args.netToOwner).to.be.gt(0n);
        });
    });

    describe("round-trip invariant", function () {
        it("returns the owner to roughly their starting USDC balance after execute + unwind", async function () {
            // Arrange
            const {bot, deployer, usdc} = await deployAndFundOwner();
            const startingBalance = await usdc.balanceOf(deployer.address);
            await usdc.approve(await bot.getAddress(), OWN_CAPITAL);
            await bot.execute();

            // Act
            await bot.unwind();

            // Assert
            const endingBalance = await usdc.balanceOf(deployer.address);
            const lossBps = ((startingBalance - endingBalance) * 10_000n) / startingBalance;
            expect(lossBps).to.be.lte(50n);
        });
    });
});
