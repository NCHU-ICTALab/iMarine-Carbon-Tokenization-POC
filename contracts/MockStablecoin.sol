// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @notice PoC 專用假穩定幣，6 位小數（比照 USDC）。mint 全開，僅限本地測試。
contract MockStablecoin is ERC20 {
    constructor() ERC20("Mock USD", "mUSD") {}

    function decimals() public pure override returns (uint8) { return 6; }

    function mint(address to, uint256 amt) external { _mint(to, amt); } // 測試水龍頭
}
