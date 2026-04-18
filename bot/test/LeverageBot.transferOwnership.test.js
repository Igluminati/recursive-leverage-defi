import hardhat from "hardhat";
import { expect } from "chai";
import { deployLeverageBotFixture } from "./fixtures/leverageBot.js";

const { ethers } = hardhat;

describe("LeverageBot, ownership", function () {

    describe("initial state", function () {
        it("sets the deployer as the initial owner", async function () {
            // Arrange
            const { bot, deployer } = await deployLeverageBotFixture();

            // Act
            const owner = await bot.owner();

            // Assert
            expect(owner).to.equal(deployer.address);
        });
    });

    describe("transferOwnership()", function () {
        it("reverts when called by a non-owner", async function () {
            // Arrange
            const { bot, alice, bob } = await deployLeverageBotFixture();

            // Act + Assert
            await expect(bot.connect(alice).transferOwnership(bob.address))
                .to.be.revertedWith("LeverageBot: not owner");
        });

        it("reverts when newOwner is the zero address", async function () {
            // Arrange
            const { bot, deployer } = await deployLeverageBotFixture();

            // Act + Assert
            await expect(bot.connect(deployer).transferOwnership(ethers.ZeroAddress))
                .to.be.revertedWith("LeverageBot: zero owner");
        });

        it("updates the owner to the new address", async function () {
            // Arrange
            const { bot, deployer, alice } = await deployLeverageBotFixture();

            // Act
            await bot.connect(deployer).transferOwnership(alice.address);

            // Assert
            expect(await bot.owner()).to.equal(alice.address);
        });

        it("emits OwnershipTransferred with the old and new owner", async function () {
            // Arrange
            const { bot, deployer, alice } = await deployLeverageBotFixture();

            // Act + Assert
            await expect(bot.connect(deployer).transferOwnership(alice.address))
                .to.emit(bot, "OwnershipTransferred")
                .withArgs(deployer.address, alice.address);
        });

        it("revokes privileges from the previous owner after transfer", async function () {
            // Arrange
            const { bot, deployer, alice, bob } = await deployLeverageBotFixture();
            await bot.connect(deployer).transferOwnership(alice.address);

            // Act + Assert
            await expect(bot.connect(deployer).transferOwnership(bob.address))
                .to.be.revertedWith("LeverageBot: not owner");
        });

        it("grants privileges to the new owner after transfer", async function () {
            // Arrange
            const { bot, deployer, alice, bob } = await deployLeverageBotFixture();
            await bot.connect(deployer).transferOwnership(alice.address);

            // Act
            await bot.connect(alice).transferOwnership(bob.address);

            // Assert
            expect(await bot.owner()).to.equal(bob.address);
        });
    });
});
