// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

/// @title 剩餘配額單位 SU（對照 IMO NZF Surplus Units 的國內模擬憑證）
/// @notice 四動作：發行 mint / 儲存(放著不動) / 轉讓一次 / 撤銷 burn
/// @dev 刻意不繼承 ERC721Burnable：其 public burn() 會繞過 Retired(purpose) 稽核事件；除役一律走 retire()，內部用基底 _burn
contract SurplusUnit is ERC721, AccessControl {
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    uint256 private _nextId;

    // 每個 SU 的屬性（唯一序號 tokenId → 值）
    mapping(uint256 => uint256) public shipId;        // 哪艘船發的（IMO Number）
    mapping(uint256 => uint256) public amount;        // 超額減碳噸數（tonnes CO2e）
    mapping(uint256 => uint256) public expiry;        // 到期時間（unix 秒）
    mapping(uint256 => uint256) public transferCount; // 已被轉讓次數
    mapping(uint256 => string)  public dataURI;       // 指向鏈下完整明細
    mapping(uint256 => bytes32) public dataHash;      // 鏈下明細的 keccak 指紋（防竄改）

    // 效期可由管理員調整（維護性：規則不寫死在常數）
    uint256 public validityPeriod = 730 days;

    // 撤銷用途（擴展性：未來加用途只在此列舉尾端追加，不動其他程式）
    enum Purpose { NZF_REWARD, EU_ETS_OFFSET, PORT_FEE_REBATE, SCOPE3_OFFSET }

    // 事件（後端據此同步本地帳本；欄位 indexed 方便日後用 indexer 過濾）
    event Issued(
        uint256 indexed tokenId, address indexed to, uint256 indexed shipId,
        uint256 amount, uint256 expiry, bytes32 dataHash
    );
    event Retired(uint256 indexed tokenId, address indexed by, Purpose purpose);

    constructor(address admin) ERC721("Surplus Unit", "SU") {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(MINTER_ROLE, admin);
    }

    // ── 動作一：發行 ──
    function mint(
        address to, uint256 _shipId, uint256 _amount, string calldata uri, bytes32 hash
    ) external onlyRole(MINTER_ROLE) returns (uint256 tokenId) {
        require(_amount > 0, "SU: amount must be > 0");       // 鏈上鐵則
        tokenId = _nextId++;
        _safeMint(to, tokenId);
        shipId[tokenId] = _shipId;
        amount[tokenId] = _amount;
        expiry[tokenId] = block.timestamp + validityPeriod;
        dataURI[tokenId] = uri;
        dataHash[tokenId] = hash;
        emit Issued(tokenId, to, _shipId, _amount, expiry[tokenId], hash);
    }

    // ── 動作四：撤銷（先記用途事件，再永久銷毀）──
    function retire(uint256 tokenId, Purpose purpose) external {
        require(ownerOf(tokenId) == msg.sender, "SU: not owner");
        emit Retired(tokenId, msg.sender, purpose);
        _burn(tokenId);
    }

    // 管理員可調效期（維護性）
    function setValidityPeriod(uint256 secs) external onlyRole(DEFAULT_ADMIN_ROLE) {
        validityPeriod = secs;
    }

    // ── 兩限制：僅轉讓一次 + 到期，只對「真正的轉讓」生效 ──
    // OZ v5：所有轉移（含發行、銷毀）都經過 _update；覆寫它即可集中管控。
    function _update(address to, uint256 tokenId, address auth)
        internal override returns (address)
    {
        address from = super._update(to, tokenId, auth);
        // from==0 是發行；to==0 是銷毀；兩者都非零才是真正的轉讓
        if (from != address(0) && to != address(0)) {
            require(transferCount[tokenId] == 0, "SU: transfer once only");
            require(block.timestamp <= expiry[tokenId], "SU: expired");
            transferCount[tokenId] += 1;
        }
        return from;
    }

    // 兩個父合約都有 supportsInterface，需明確合併
    function supportsInterface(bytes4 id)
        public view override(ERC721, AccessControl) returns (bool)
    {
        return super.supportsInterface(id);
    }
}
