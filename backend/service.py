import json
import os
import re
from web3 import Web3
from web3.logs import DISCARD
from .chain_client import ChainClient, ChainTxError
from . import ledger

client = ChainClient()

# 鏈下明細檔存放處（資料層 build_requests 的 OFFCHAIN_DIR）；uri 為 local://offchain/<檔名>
OFFCHAIN_DIR = os.path.join("data", "out", "offchain")
_URI_PREFIX = "local://offchain/"
_ZERO_HASH = "0x" + "00" * 32


def issue_from_requests(path: str, limit: int | None = None) -> dict:
    """讀資料層產出的核發請求，逐筆發行並更新帳本。

    limit：只發前 N 筆（測試/展示用）；單筆失敗即中止並指出是第幾筆、哪艘船（不做部分成功恢復）。
    """
    with open(path, encoding="utf-8") as f:
        reqs = json.load(f)
    if limit is not None:
        reqs = reqs[:limit]
    tx_hashes, total_tonnes = [], 0
    for i, r in enumerate(reqs):
        try:
            rcpt = client.mint(r["to_role"], r["ship_id"].replace("IMO", ""),
                               r["amount_tonnes"], r["uri"], r["data_hash"])
        except ChainTxError as e:
            raise ChainTxError(
                f"第 {i + 1}/{len(reqs)} 筆發行失敗（{r['ship_id']} {r['reporting_period']}）：{e}"
            ) from e
        ledger.apply_receipt(client.su, client.market, rcpt)
        tx_hashes.append(rcpt.transactionHash.hex())
        total_tonnes += r["amount_tonnes"]
    return {"count": len(tx_hashes), "total_tonnes": total_tonnes, "tx_hashes": tx_hashes}


def list_su(token_id, price):
    r = client.list_su(token_id, price)
    ledger.apply_receipt(client.su, client.market, r)
    return r.transactionHash.hex()


def buy_su(token_id):
    r = client.buy_su(token_id)
    ledger.apply_receipt(client.su, client.market, r)
    return r.transactionHash.hex()


def retire_su(token_id, purpose_code):
    r = client.retire(token_id, purpose_code)
    ledger.apply_receipt(client.su, client.market, r)
    return r.transactionHash.hex()


def verify_su(token_id) -> dict:
    """防竄改回驗：讀鏈上 dataHash 與 dataURI，對 uri 指向的鏈下明細重算 keccak 比對。

    回 {token_id, match, onchain_hash, recomputed_hash, uri, detail?}。
    重算方式與資料層 build_requests 一致（keccak(檔案內容)），故只能用 uri 指向的鏈下檔回算。
    """
    tid = int(token_id)
    if tid < 0:
        return {"token_id": tid, "onchain_hash": None, "uri": None, "match": False,
                "recomputed_hash": None, "detail": f"token_id 不合法（{tid}）"}

    onchain_hash = client.data_hash(tid)
    uri = client.data_uri(tid)
    base = {"token_id": tid, "onchain_hash": onchain_hash, "uri": uri}

    if onchain_hash.lower() == _ZERO_HASH or not uri:
        return {**base, "match": False, "recomputed_hash": None,
                "detail": f"SU #{tid} 無鏈上 dataHash（token 不存在或未發行）"}
    if not uri.startswith(_URI_PREFIX):
        return {**base, "match": False, "recomputed_hash": None,
                "detail": f"uri 非 {_URI_PREFIX} 格式，無法在本地回驗"}

    path = os.path.join(OFFCHAIN_DIR, uri[len(_URI_PREFIX):])
    if not os.path.isfile(path):
        return {**base, "match": False, "recomputed_hash": None,
                "detail": f"找不到鏈下明細檔 {path}（需先跑 make data）"}

    with open(path, encoding="utf-8") as f:
        recomputed = "0x" + Web3.keccak(text=f.read()).hex().removeprefix("0x")
    return {**base, "match": recomputed.lower() == onchain_hash.lower(), "recomputed_hash": recomputed}


def issue_single(ship_id: str, reporting_period: str, attained_gfi: float,
                 energy_mj: int, fuel: str) -> dict:
    """單筆自訂發行：原始驗證數據 → 資料層 build_single（算噸數/產鏈下檔/dataHash）→ 鑄造。

    缺額、重複、格式錯誤 raise ValueError（api 層轉 400）；
    鑄造失敗補償刪掉剛寫的鏈下檔，避免孤兒檔讓重試被重複防呆誤擋。
    """
    if not re.fullmatch(r"IMO\d+", str(ship_id)):
        raise ValueError("ship_id 格式異常（應為 IMO+純數字）")
    if not re.fullmatch(r"\d{4}-\d{2}", str(reporting_period)):
        raise ValueError("reporting_period 格式異常（應為 YYYY-MM）")

    fname = f"{ship_id}_{reporting_period}.json"
    fpath = os.path.join(OFFCHAIN_DIR, fname)
    if os.path.exists(fpath):
        raise ValueError(f"{ship_id} {reporting_period} 已發行過（明細檔已存在）")

    # 資料層純函式＝計算/驗證/寫鏈下檔的單一真相（介面鐵則：後端不管資料怎麼算出來）
    from data.build_requests import build_single
    req = build_single({
        "ship_id": ship_id, "reporting_period": reporting_period,
        "attained_gfi": attained_gfi, "energy_mj": energy_mj, "fuel": fuel,
    })

    try:
        rcpt = client.mint(req["to_role"], req["ship_id"].replace("IMO", ""),
                           req["amount_tonnes"], req["uri"], req["data_hash"])
    except ChainTxError:
        try:
            os.remove(fpath)   # 補償：best-effort，刪不掉就留給手動處理（PoC 接受）
        except OSError:
            pass
        raise
    ledger.apply_receipt(client.su, client.market, rcpt)
    issued = client.su.events.Issued().process_receipt(rcpt, errors=DISCARD)
    token_id = issued[0]["args"]["tokenId"] if issued else None
    return {"tx": rcpt.transactionHash.hex(), "token_id": token_id,
            "amount_tonnes": req["amount_tonnes"]}
