const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("SurplusUnit + Market", function () {
  let su, coin, market, issuer, shipping, buyer;
  const HASH = ethers.keccak256(ethers.toUtf8Bytes("demo-offchain-data"));

  beforeEach(async () => {
    [issuer, shipping, buyer] = await ethers.getSigners();

    coin = await (await ethers.getContractFactory("MockStablecoin")).deploy();
    su = await (await ethers.getContractFactory("SurplusUnit")).deploy(issuer.address);
    market = await (await ethers.getContractFactory("Market"))
      .deploy(await su.getAddress(), await coin.getAddress());

    // 撥 100 萬 mUSD 給買方
    await coin.mint(buyer.address, 1_000_000n * 10n ** 6n);
  });

  it("只有 MINTER 能發行，數量必須 > 0", async () => {
    await expect(
      su.connect(shipping).mint(shipping.address, 9811000, 500, "uri", HASH)
    ).to.be.reverted; // 非 MINTER
    await expect(
      su.connect(issuer).mint(shipping.address, 9811000, 0, "uri", HASH)
    ).to.be.revertedWith("SU: amount must be > 0");

    await su.connect(issuer).mint(shipping.address, 9811000, 500, "uri", HASH);
    expect(await su.ownerOf(0)).to.equal(shipping.address);
    expect(await su.amount(0)).to.equal(500);
  });

  it("僅可轉讓一次：第二次轉讓要失敗", async () => {
    await su.connect(issuer).mint(shipping.address, 9811000, 500, "uri", HASH);
    await su.connect(shipping).transferFrom(shipping.address, buyer.address, 0);
    await expect(
      su.connect(buyer).transferFrom(buyer.address, shipping.address, 0)
    ).to.be.revertedWith("SU: transfer once only");
  });

  it("到期後不能轉讓", async () => {
    await su.connect(issuer).mint(shipping.address, 9811000, 500, "uri", HASH);
    await time.increase(731 * 24 * 60 * 60); // 快轉超過兩年
    await expect(
      su.connect(shipping).transferFrom(shipping.address, buyer.address, 0)
    ).to.be.revertedWith("SU: expired");
  });

  it("撤銷：只有擁有者能燒、燒完就不存在、要留 Retired 稽核事件", async () => {
    await su.connect(issuer).mint(shipping.address, 9811000, 500, "uri", HASH);
    await expect(su.connect(buyer).retire(0, 3)).to.be.revertedWith("SU: not owner");
    // 除役必須留下 Retired(purpose) 稽核事件——這正是移除公開 burn() 要保護的東西
    await expect(su.connect(shipping).retire(0, 3)) // 3 = SCOPE3_OFFSET
      .to.emit(su, "Retired").withArgs(0, shipping.address, 3);
    await expect(su.ownerOf(0)).to.be.reverted; // 已不存在
  });

  it("市場：授權→上架→購買，一次交錢交券；買後不能再轉賣", async () => {
    await su.connect(issuer).mint(shipping.address, 9811000, 500, "uri", HASH);
    const price = 300n * 10n ** 6n; // 300 mUSD

    await su.connect(shipping).approve(await market.getAddress(), 0);
    await market.connect(shipping).list(0, price);

    await coin.connect(buyer).approve(await market.getAddress(), price);
    await market.connect(buyer).buy(0);

    expect(await su.ownerOf(0)).to.equal(buyer.address);
    expect(await coin.balanceOf(shipping.address)).to.equal(price);
    // 已轉一次，買家不能再賣
    expect(await su.transferCount(0)).to.equal(1);
    await su.connect(buyer).approve(await market.getAddress(), 0);
    await market.connect(buyer).list(0, price);
    // 讓賣家(shipping)這次有錢又有授權，確保 revert 是撞到 transfer-once，而非付款失敗
    await coin.connect(shipping).approve(await market.getAddress(), price);
    await expect(market.connect(shipping).buy(0)).to.be.revertedWith("SU: transfer once only");
  });
});
