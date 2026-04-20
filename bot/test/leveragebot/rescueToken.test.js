import { expect } from "chai";
import {
    USDC,
    OWN_CAPITAL,
    deployLeverageBotFixture,
    setUsdcBalance,
} from "./fixtures.js";

describe("LeverageBot, rescueToken", function () {
    this.timeout(120_000);

    it("reverts when called by a non-owner", async function () {
        // Arrange
        const { bot, stranger } = await deployLeverageBotFixture();

        // Act + Assert
        await expect(
            bot.connect(stranger).rescueToken(USDC, 1n)
        ).to.be.revertedWith("LeverageBot: not owner");
    });

    it("sweeps a stuck ERC20 balance back to the owner", async function () {
        // Arrange
        const { bot, deployer, usdc } = await deployLeverageBotFixture();
        const botAddress = await bot.getAddress();
        await setUsdcBalance(botAddress, OWN_CAPITAL);
        const ownerBalanceBefore = await usdc.balanceOf(deployer.address);

        // Act
        await bot.connect(deployer).rescueToken(USDC, OWN_CAPITAL);

        // Assert
        expect(await usdc.balanceOf(botAddress)).to.equal(0n);
        expect(await usdc.balanceOf(deployer.address)).to.equal(ownerBalanceBefore + OWN_CAPITAL);
    });
});
