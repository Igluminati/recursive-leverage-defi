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
    etherscan: {
        apiKey: process.env.BASESCAN_API_KEY ?? "",
    },
};