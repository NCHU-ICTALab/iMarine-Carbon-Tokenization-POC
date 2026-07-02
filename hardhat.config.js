require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "cancun" },
  },
  networks: {
    // 本地測試鏈（預設）
    localhost: { url: "http://127.0.0.1:8545" },

    // 可遷移性示範：未來要上測試網，只要填 .env、解除下面註解，
    // 合約與後端程式碼都不用改。
    // sepolia: {
    //   url: process.env.SEPOLIA_RPC_URL || "",
    //   accounts: process.env.DEPLOYER_KEY ? [process.env.DEPLOYER_KEY] : [],
    // },
  },
};
