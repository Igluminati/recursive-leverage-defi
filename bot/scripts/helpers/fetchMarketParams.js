/*
yoUSD/USDC: https://app.morpho.org/base/market/0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137/yousd-usdc
 */

import hre from "hardhat";

async function main() {
    const {ethers} = hre;

    const MORPHO = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb";
    const MARKET_ID = "0x1a3e69d0109bb1be42b80e11034bb6ee98fc466721f26845dc83b2aa8d979137";

    const morpho = await ethers.getContractAt(
        ["function idToMarketParams(bytes32) view returns (address, address, address, address, uint256)"],
        MORPHO
    );

    const [loanToken, collateralToken, oracle, irm, lltv] = await morpho.idToMarketParams(MARKET_ID);

    console.log("loanToken:", loanToken);
    console.log("collateralToken:", collateralToken);
    console.log("oracle:", oracle);
    console.log("irm:", irm);
    console.log("lltv:", lltv.toString());
}

main();

//npx hardhat run scripts/helpers/fetchMarketParams.js --network base