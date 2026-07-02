"""後端整合測試：需要本地鏈跑著 + 已 make deploy；鏈不在就整檔 skip。
測試用獨立 DB（tmp），不污染 backend/ledger.db；會在鏈上鑄測試 SU，
跑正式 demo 前重啟鏈即可回到乾淨狀態。"""
import json
import os

import pytest
from web3 import Web3

RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
NETWORK = os.getenv("NETWORK", "localhost")
_SHARED = os.path.join(os.path.dirname(__file__), "..", "..", "shared", f"contracts.{NETWORK}.json")


def _chain_ready() -> bool:
    if not os.path.exists(_SHARED):
        return False
    try:
        return Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 2})).is_connected()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _chain_ready(), reason="需要本地鏈 + make deploy（HANDOFF §7 步驟 1）")


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    """隔離測試 DB + 發行 2 筆測試 SU（3 筆請求、limit=2 驗證上限參數）。"""
    from backend import config
    config.DB_PATH = str(tmp_path_factory.mktemp("ledger") / "test_ledger.db")

    from backend import ledger, service
    ledger.init_db()

    reqs = []
    for i in (1, 2, 3):
        reqs.append({
            "ship_id": f"IMO999000{i}",
            "reporting_period": "2028-01",
            "amount_tonnes": 100 + i,
            "uri": f"local://test/{i}.json",
            "data_hash": Web3.keccak(text=f"integration-test-{i}").hex(),
            "calculation_basis": {"attained_gfi": 50.0, "target_gfi": 89.0, "energy_mj": 1, "fuel": "LNG"},
            "to_role": "shipping",
        })
    p = tmp_path_factory.mktemp("reqs") / "requests.json"
    p.write_text(json.dumps(reqs), encoding="utf-8")

    res = service.issue_from_requests(str(p), limit=2)
    assert res["count"] == 2                      # limit 生效：3 筆請求只發 2 筆
    assert res["total_tonnes"] == 101 + 102
    rows = ledger.all_su(service.client)
    assert len(rows) == 2                         # 測試 DB 是新的，只有這次發的
    return {"ledger": ledger, "service": service,
            "t1": rows[0]["token_id"], "t2": rows[1]["token_id"]}


def test_lifecycle_held_listed_sold_retired(env):
    """四段生命週期：發行 held → 上架 listed → 購買 sold(held/buyer) → 除役 retired。"""
    ledger, service, t1 = env["ledger"], env["service"], env["t1"]

    def row(tid):
        return next(s for s in ledger.all_su(service.client) if s["token_id"] == tid)

    assert row(t1)["status"] == "held"
    assert row(t1)["owner_role"] == "shipping"

    service.list_su(t1, 300)
    assert row(t1)["status"] == "listed"

    service.buy_su(t1)
    assert row(t1)["status"] == "held"
    assert row(t1)["owner_role"] == "buyer"

    service.retire_su(t1, 3)                      # 3 = SCOPE3_OFFSET
    assert row(t1)["status"] == "retired"
    assert row(t1)["purpose_name"] == "SCOPE3_OFFSET"


def test_transfer_once_revert_surfaces_reason(env):
    """第二次轉讓要 revert，且 reason 原樣傳到 ChainTxError（moderate 錯誤處理驗證）。"""
    from backend.chain_client import ChainTxError
    service, t2 = env["service"], env["t2"]

    service.list_su(t2, 300)
    service.buy_su(t2)                            # 唯一一次合法轉讓
    service.list_su(t2, 300)                      # 再上架可以（approve+list 不是轉讓）
    with pytest.raises(ChainTxError, match="transfer once only"):
        service.buy_su(t2)                        # 第二次轉讓：撞 SU: transfer once only
