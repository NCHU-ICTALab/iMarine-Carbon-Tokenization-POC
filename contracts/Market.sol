// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice 一手市場：賣家「授權」而不把 SU 交給市場，成交時一次轉給買家（全程只轉一次）
contract Market is ReentrancyGuard {
    IERC721 public immutable su;
    IERC20  public immutable pay;

    struct Listing { address seller; uint256 price; }
    mapping(uint256 => Listing) public listings;   // tokenId → 掛單

    event Listed(uint256 indexed tokenId, address indexed seller, uint256 price);
    event Unlisted(uint256 indexed tokenId);
    event Sold(uint256 indexed tokenId, address indexed seller, address indexed buyer, uint256 price);

    constructor(address _su, address _pay) {
        su = IERC721(_su);
        pay = IERC20(_pay);
    }

    function list(uint256 tokenId, uint256 price) external {
        require(price > 0, "Market: price must be > 0");
        require(su.ownerOf(tokenId) == msg.sender, "Market: not owner");
        require(
            su.getApproved(tokenId) == address(this) ||
            su.isApprovedForAll(msg.sender, address(this)),
            "Market: approve SU first"
        );
        listings[tokenId] = Listing(msg.sender, price);
        emit Listed(tokenId, msg.sender, price);
    }

    function cancelListing(uint256 tokenId) external {
        require(listings[tokenId].seller == msg.sender, "Market: not seller");
        delete listings[tokenId];
        emit Unlisted(tokenId);
    }

    function buy(uint256 tokenId) external nonReentrant {
        Listing memory L = listings[tokenId];
        require(L.price > 0, "Market: not for sale");
        delete listings[tokenId];                                  // 先改狀態再互動
        require(pay.transferFrom(msg.sender, L.seller, L.price), "Market: payment failed");
        su.safeTransferFrom(L.seller, msg.sender, tokenId);        // 這是唯一的一次轉讓
        emit Sold(tokenId, L.seller, msg.sender, L.price);
    }
}
