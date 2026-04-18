import "@nomicfoundation/hardhat-toolbox";
import dotenv from "dotenv";
dotenv.config();

export default {
    solidity: "0.8.28",
    networks: {
        base: {
            url: process.env.BASE_RPC_URL ?? "",
            accounts: process.env.BASE_PRIVATE_KEY ? [process.env.BASE_PRIVATE_KEY] : [],
            chainId: 8453,
        },
        hardhat: {
            forking: {
                url: process.env.BASE_RPC_URL ?? "",
                blockNumber: 44_800_000,
            },
            chainId: 8453,
        },
    },
    mocha: {
        timeout: 60000,
    },
    // Etherscan v2 API (unified across chains). Needs only a single api key;
    // Hardhat picks the right chain automatically from network config.
    etherscan: {
        apiKey: process.env.BASESCAN_API_KEY ?? "",
    },
};