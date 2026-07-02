import os
import json
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

NETWORK = os.getenv("NETWORK", "localhost")
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")

# 讀鏈層匯出的唯一介面檔（鏈層→後端介面，由 scripts/deploy.js 產生）
_shared_path = os.path.join(os.path.dirname(__file__), "..", "shared", f"contracts.{NETWORK}.json")
if not os.path.exists(_shared_path):
    raise FileNotFoundError(
        f"找不到鏈層介面檔 {_shared_path}："
        f"請先啟動本地鏈（make chain）並執行 make deploy；"
        f"並確認 .env 的 NETWORK（目前={NETWORK}）與檔名一致"
    )
with open(_shared_path, encoding="utf-8") as f:
    CONTRACTS = json.load(f)

ADDRESSES = CONTRACTS["addresses"]
ABIS = CONTRACTS["abis"]
ROLES = CONTRACTS["roles"]          # {issuer, shipping, buyer} → address

# 角色私鑰（從 .env；Hardhat 公開測試金鑰，僅限本地，永遠不可用於正式網）
KEYS = {
    "issuer": os.getenv("ISSUER_KEY"),
    "shipping": os.getenv("SHIPPING_KEY"),
    "buyer": os.getenv("BUYER_KEY"),
}

w3 = Web3(Web3.HTTPProvider(RPC_URL))

DB_PATH = os.path.join(os.path.dirname(__file__), "ledger.db")
