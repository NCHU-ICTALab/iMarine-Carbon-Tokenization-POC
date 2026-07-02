import json
from .chain_client import ChainClient, ChainTxError
from . import ledger

client = ChainClient()


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
