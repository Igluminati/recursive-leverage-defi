import hardhat from "hardhat";
import { expect } from "chai";
import {
    MORPHO,
    deployLeverageBotFixture,
    impersonate,
} from "./fixtures.js";

const { ethers } = hardhat;

describe("LeverageBot, onMorphoFlashLoan dispatcher", function () {
    this.timeout(120_000);

    it("reverts when called by an address that is not Morpho", async function () {
        // Arrange
        const { bot, stranger } = await deployLeverageBotFixture();

        // Act + Assert
        await expect(
            bot.connect(stranger).onMorphoFlashLoan(0, "0x")
        ).to.be.revertedWith("LeverageBot: caller not Morpho");
    });

    it("reverts when Morpho delivers an unknown action tag", async function () {
        // Arrange
        const { bot } = await deployLeverageBotFixture();
        const morphoSigner = await impersonate(MORPHO);
        const badData = ethers.AbiCoder.defaultAbiCoder().encode(
            ["uint8", "uint256", "uint256"],
            [99, 0, 0]
        );

        // Act + Assert
        await expect(
            bot.connect(morphoSigner).onMorphoFlashLoan(0, badData)
        ).to.be.revertedWith("LeverageBot: unknown action");
    });
});
