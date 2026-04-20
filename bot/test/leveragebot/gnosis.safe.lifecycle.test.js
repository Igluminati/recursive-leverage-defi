import {expect} from "chai";
import {
    MARKET_ID,
    OWN_CAPITAL,
    deployLeverageBotFixture,
    impersonate,
    setUsdcBalance,
} from "./fixtures.js";

const SAFE_ADDRESS = "0xf9962B0fa1910c90788E35f83Df4F15F9f857fCb";

describe("LeverageBot, Safe-controlled lifecycle", function () {
    this.timeout(180_000);

    it("runs deploy -> transferOwnership(Safe) -> execute -> unwind end-to-end with the Safe as sole controller", async function () {
        // Arrange
        const {bot, deployer, stranger, usdc, morpho} = await deployLeverageBotFixture();
        const botAddress = await bot.getAddress();

        await bot.connect(deployer).transferOwnership(SAFE_ADDRESS);
        expect(await bot.owner()).to.equal(SAFE_ADDRESS);

        // Assert (1/4)
        await expect(bot.connect(deployer).execute())
            .to.be.revertedWith("LeverageBot: not owner");
        await expect(bot.connect(deployer).unwind())
            .to.be.revertedWith("LeverageBot: not owner");

        // Assert (2/4)
        await expect(bot.connect(stranger).execute())
            .to.be.revertedWith("LeverageBot: not owner");

        // Act
        const safe = await impersonate(SAFE_ADDRESS);
        await setUsdcBalance(SAFE_ADDRESS, OWN_CAPITAL);

        const safeUsdc = usdc.connect(safe);
        await safeUsdc.approve(botAddress, OWN_CAPITAL);

        await bot.connect(safe).execute();

        // Assert (3/4)
        const [, borrowShares, collateral] = await morpho.position(MARKET_ID, botAddress);
        expect(borrowShares).to.be.gt(0n);
        expect(collateral).to.be.gt(0n);

        const safeBalanceBeforeUnwind = await usdc.balanceOf(SAFE_ADDRESS);
        await bot.connect(safe).unwind();

        // Assert (4/4)
        const [, borrowSharesAfter, collateralAfter] = await morpho.position(MARKET_ID, botAddress);
        expect(borrowSharesAfter).to.equal(0n);
        expect(collateralAfter).to.equal(0n);

        const safeBalanceAfterUnwind = await usdc.balanceOf(SAFE_ADDRESS);
        const netPayout = safeBalanceAfterUnwind - safeBalanceBeforeUnwind;
        const minExpected = (OWN_CAPITAL * 995n) / 1000n;
        expect(netPayout).to.be.gte(minExpected);

        expect(await bot.usdcBalance()).to.equal(0n);
        expect(await bot.yoUsdBalance()).to.equal(0n);
    });
});
