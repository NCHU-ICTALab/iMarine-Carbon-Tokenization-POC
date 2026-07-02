const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

function abiOf(name) {
  const p = path.join(__dirname, "..", "artifacts", "contracts", `${name}.sol`, `${name}.json`);
  return JSON.parse(fs.readFileSync(p, "utf8")).abi;
}

async function main() {
  const { ethers, network } = hre;
  const [issuer, shipping, buyer] = await ethers.getSigners();

  const coin = await (await ethers.getContractFactory("MockStablecoin")).deploy();
  await coin.waitForDeployment();
  const su = await (await ethers.getContractFactory("SurplusUnit")).deploy(issuer.address);
  await su.waitForDeployment();
  const market = await (await ethers.getContractFactory("Market"))
    .deploy(await su.getAddress(), await coin.getAddress());
  await market.waitForDeployment();

  // 撥 200 萬 mUSD 給買方，讓 demo 有錢可買
  await (await coin.mint(buyer.address, 2_000_000n * 10n ** 6n)).wait();

  // ★ 產出鏈層↔後端的唯一介面檔
  const out = {
    network: network.name,
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    addresses: {
      SurplusUnit: await su.getAddress(),
      Market: await market.getAddress(),
      MockStablecoin: await coin.getAddress(),
    },
    roles: { // 位址對應角色，UI/後端用來把地址翻成人看得懂的名字
      issuer: issuer.address,     // 航港局核發者
      shipping: shipping.address, // 航商 A
      buyer: buyer.address,       // 產業買方
    },
    abis: {
      SurplusUnit: abiOf("SurplusUnit"),
      Market: abiOf("Market"),
      MockStablecoin: abiOf("MockStablecoin"),
    },
  };

  const dir = path.join(__dirname, "..", "shared");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `contracts.${network.name}.json`);
  fs.writeFileSync(file, JSON.stringify(out, null, 2));

  console.log("Deployed & exported →", file);
  console.log(out.addresses);
}

main().catch((e) => { console.error(e); process.exit(1); });
