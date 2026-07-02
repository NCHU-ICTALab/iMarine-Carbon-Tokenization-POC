from web3 import Web3
from web3.exceptions import ContractLogicError
from . import config


class ChainTxError(Exception):
    """鏈上互動失敗（revert 等）；message 保留 reason 原樣，供 API 層轉譯 400。"""


class ChainClient:
    def __init__(self):
        self.w3 = config.w3
        self.chain_id = self.w3.eth.chain_id
        self.roles = config.ROLES
        self.keys = config.KEYS
        self.su = self.w3.eth.contract(address=config.ADDRESSES["SurplusUnit"], abi=config.ABIS["SurplusUnit"])
        self.market = self.w3.eth.contract(address=config.ADDRESSES["Market"], abi=config.ABIS["Market"])
        self.coin = self.w3.eth.contract(address=config.ADDRESSES["MockStablecoin"], abi=config.ABIS["MockStablecoin"])

    # ── 內部：用某角色簽並送出一筆交易，回傳收據；失敗轉拋 ChainTxError ──
    def _send(self, func, role: str):
        addr = self.roles[role]
        tx = func.build_transaction({
            "from": addr,
            "nonce": self.w3.eth.get_transaction_count(addr),
            "chainId": self.chain_id,
            "gas": 1_500_000,
            "maxFeePerGas": self.w3.to_wei(3, "gwei"),
            "maxPriorityFeePerGas": self.w3.to_wei(1, "gwei"),
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.keys[role])
        # eth-account 0.11 是 rawTransaction、0.13+ 改 raw_transaction；兩版相容
        raw = getattr(signed, "rawTransaction", None) or signed.raw_transaction
        try:
            h = self.w3.eth.send_raw_transaction(raw)
            receipt = self.w3.eth.wait_for_transaction_receipt(h)
        except (ContractLogicError, ValueError) as e:
            raise ChainTxError(str(e)) from e     # Hardhat 的 revert 由這裡拋出，reason 原樣保留
        if receipt.status != 1:
            raise ChainTxError(f"交易失敗（status=0）：{receipt.transactionHash.hex()}")
        return receipt

    # ── 角色解析（把地址翻成角色名，UI 顯示用）──
    def role_of(self, address: str) -> str:
        for name, addr in self.roles.items():
            if addr.lower() == address.lower():
                return name
        return address

    # ── 純查詢（免簽、免 gas）；token 不存在/已除役 → ChainTxError ──
    def owner_of(self, token_id):
        try:
            return self.su.functions.ownerOf(token_id).call()
        except ContractLogicError as e:
            raise ChainTxError(f"SU #{token_id} 不存在或已除役：{e}") from e

    # ── 讀鏈上防竄改指紋與鏈下明細指標（供 /verify 回驗）──
    def data_hash(self, token_id):
        return "0x" + self.su.functions.dataHash(int(token_id)).call().hex().removeprefix("0x")

    def data_uri(self, token_id):
        return self.su.functions.dataURI(int(token_id)).call()

    # ── 發行（由 issuer 簽）──
    def mint(self, to_role, ship_id, amount, uri, data_hash):
        to = self.roles[to_role]
        func = self.su.functions.mint(to, int(ship_id), int(amount), uri, Web3.to_bytes(hexstr=data_hash))
        return self._send(func, "issuer")

    # ── 上架（授權 + list，由持有者簽）──
    def list_su(self, token_id, price_musd):
        role = self.role_of(self.owner_of(token_id))
        price = int(price_musd) * 10 ** 6
        self._send(self.su.functions.approve(config.ADDRESSES["Market"], token_id), role)
        return self._send(self.market.functions.list(token_id, price), role)

    # ── 購買（買方授權付款幣 + buy）──
    def buy_su(self, token_id, buyer_role="buyer"):
        price = self.market.functions.listings(token_id).call()[1]
        self._send(self.coin.functions.approve(config.ADDRESSES["Market"], price), buyer_role)
        return self._send(self.market.functions.buy(token_id), buyer_role)

    # ── 除役（擁有者簽）──
    def retire(self, token_id, purpose_code, by_role=None):
        role = by_role or self.role_of(self.owner_of(token_id))
        return self._send(self.su.functions.retire(token_id, int(purpose_code)), role)
